"""共享模块：提供跨页面复用的工具函数、绘图、数据适配器等。"""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import datetime
from decimal import Decimal, getcontext
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

# 设置 Decimal 全局精度，确保高精度金额运算
getcontext().prec = 28

# 项目根目录与路径配置
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from simulator.backtest_engine import BacktestEngineCore
from src.data_io_adapter import DataIOAdapter
from data.init_db import DB_PATH, initialize_database

DATA_DIR = APP_ROOT / "data"
SIGNAL_IMAGE_PATH = DATA_DIR / "signal.jpg"
SIGNAL_SIDEBAR_IMAGE_PATH = DATA_DIR / "signal_sidebar.png"
SIGNAL_SIDEBAR_DARK_IMAGE_PATH = DATA_DIR / "signal_sidebar(dark).png"

# 可选的基准策略映射（前端下拉框）
BENCHMARK_OPTIONS = {
    "不对比": None,
    "网格交易": "grid_trading",
    "60日均线择时": "ma60_timing",
    "持币不动": "buy_and_hold",
}


def _convert_equity_to_float(df: pd.DataFrame) -> pd.DataFrame:
    """
    将 DataFrame 中的 equity 列从 Decimal 转换为 float（用于绘图）。
    由于 plotly 接受 float，而 Decimal 无法直接参与 pandas 算术运算，
    此辅助函数在绘图前统一转换。
    """
    if df.empty:
        return df
    df = df.copy()
    if "equity" in df.columns and df["equity"].dtype == object:
        # 检查第一个有效值是否为 Decimal 类型（通过类名判断）
        first_valid = df["equity"].dropna().iloc[0] if not df["equity"].dropna().empty else None
        if first_valid is not None and hasattr(first_valid, '__class__') and first_valid.__class__.__name__ == 'Decimal':
            df["equity"] = df["equity"].apply(float)
    return df


def ensure_db(adapter: DataIOAdapter) -> None:
    """确保数据库存在且可读，若不存在则初始化。"""
    if not Path(DB_PATH).exists():
        initialize_database()
    try:
        _ = adapter.list_exchanges()
    except Exception:
        initialize_database()


@st.cache_resource
def get_adapter() -> DataIOAdapter:
    """获取全局唯一的 DataIOAdapter 实例（缓存）。"""
    adapter = DataIOAdapter(DB_PATH)
    ensure_db(adapter)
    return adapter


@st.cache_resource
def get_engine() -> BacktestEngineCore:
    """获取全局唯一的 BacktestEngineCore 实例（缓存）。"""
    return BacktestEngineCore()


def get_logo_image_path(use_sidebar_variant: bool = False, is_dark_mode: bool = False) -> Path:
    """根据明暗主题和位置返回合适的 logo 图片路径。"""
    if use_sidebar_variant:
        if is_dark_mode:
            if SIGNAL_SIDEBAR_DARK_IMAGE_PATH.exists():
                return SIGNAL_SIDEBAR_DARK_IMAGE_PATH
        elif SIGNAL_SIDEBAR_IMAGE_PATH.exists():
            return SIGNAL_SIDEBAR_IMAGE_PATH
    # 回退到默认图片
    if SIGNAL_SIDEBAR_IMAGE_PATH.exists():
        return SIGNAL_SIDEBAR_IMAGE_PATH
    return SIGNAL_IMAGE_PATH


@st.cache_data(show_spinner=False)
def load_signal_image_data_uri(
    max_width: int | None = None, use_sidebar_variant: bool = False
) -> str | None:
    """
    加载 logo 图片并返回 data URI（Base64），用于嵌入 HTML。
    可缩放图片宽度。
    """
    image_path = get_logo_image_path(use_sidebar_variant=use_sidebar_variant)
    if not image_path.exists():
        return None

    image = Image.open(image_path).convert("RGB")
    if max_width and image.width > max_width:
        new_height = int(image.height * (max_width / image.width))
        image = image.resize((max_width, new_height), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", optimize=True, quality=90)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def parse_params(params_text: str) -> dict:
    """解析策略参数 JSON 字符串为字典。"""
    try:
        return json.loads(params_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"参数JSON格式错误: {exc}") from exc


def parse_selected_exchanges(raw_value: object) -> list[str]:
    """解析数据库存储的交易所列表（可能为 JSON 字符串或直接列表）。"""
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value]
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            return []
    return []


def render_metric_cards(items: list[tuple[str, str]]) -> None:
    """
    在 Streamlit 中以卡片样式渲染一组指标（标签-值对）。
    items: [(label1, value1), (label2, value2), ...]
    """
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-card-label">{label}</div>
                    <div class="metric-card-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def build_benchmark_curve(
    raw_df: pd.DataFrame, initial_capital: float, benchmark_code: str | None
) -> pd.DataFrame | None:
    """
    根据基准策略代码（grid_trading / buy_and_hold / ma60_timing）
    生成基准权益曲线。
    - raw_df: 包含 date, price 的原始数据（可能多交易所）
    - initial_capital: 初始资金（float，仅用于基准计算）
    - 返回 DataFrame 包含 date 和 equity 列
    """
    if not benchmark_code or raw_df.empty or initial_capital <= 0:
        return None

    daily = (
        raw_df.groupby("date", as_index=False)
        .agg(price=("price", "mean"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    if daily.empty:
        return None

    prices = daily["price"].astype(float)
    if benchmark_code == "grid_trading":
        # 网格交易：初始半仓，每涨5%卖20%仓位，每跌5%买20%现金
        first_price = float(prices.iloc[0])
        if first_price <= 0:
            return None
        cash = initial_capital * 0.5
        asset_units = (initial_capital * 0.5) / first_price
        anchor_price = first_price
        grid_step = 0.05
        trade_ratio = 0.20
        equity_values: list[float] = []
        for price in prices:
            current_price = float(price)
            if current_price <= 0:
                equity_values.append(cash + asset_units * max(anchor_price, 0.0))
                continue
            # 价格上涨网格卖出
            while current_price >= anchor_price * (1.0 + grid_step):
                sell_units = asset_units * trade_ratio
                if sell_units <= 0:
                    break
                asset_units -= sell_units
                cash += sell_units * current_price
                anchor_price *= 1.0 + grid_step
            # 价格下跌网格买入
            while current_price <= anchor_price * (1.0 - grid_step):
                buy_cash = cash * trade_ratio
                if buy_cash <= 0:
                    break
                asset_units += buy_cash / current_price
                cash -= buy_cash
                anchor_price *= 1.0 - grid_step
            equity_values.append(cash + asset_units * current_price)
        equity = pd.Series(equity_values)
    elif benchmark_code == "buy_and_hold":
        # 持币不动：始终全仓
        first_price = float(prices.iloc[0])
        if first_price <= 0:
            return None
        equity = (initial_capital / first_price) * prices
    elif benchmark_code == "ma60_timing":
        # 60日均线择时：价格上穿均线买入，下穿卖出
        ma60 = prices.rolling(window=60, min_periods=1).mean()
        signal = (prices >= ma60).astype(float).shift(1).fillna(0.0)
        returns = prices.pct_change().fillna(0.0)
        equity = initial_capital * (1.0 + returns * signal).cumprod()
    else:
        return None

    return pd.DataFrame({"date": daily["date"], "equity": equity})


def render_equity_chart(
    equity_curve: pd.DataFrame,
    title: str,
    benchmark_curve: pd.DataFrame | None = None,
    benchmark_label: str | None = None,
) -> go.Figure:
    """
    渲染权益曲线图表（回测策略 vs 可选基准）。
    注意：内部会将 equity 列从 Decimal 转为 float，以便 plotly 处理。
    """
    from frontend.theme import BLUE, AMBER

    equity_curve = _convert_equity_to_float(equity_curve)
    if benchmark_curve is not None:
        benchmark_curve = _convert_equity_to_float(benchmark_curve)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity_curve["date"],
            y=equity_curve["equity"],
            mode="lines",
            line=dict(color=BLUE, width=2.2),
            name="回测策略",
            hovertemplate="回测策略权益: %{y:.4f}<extra></extra>",
        )
    )
    if benchmark_curve is not None and not benchmark_curve.empty and benchmark_label:
        fig.add_trace(
            go.Scatter(
                x=benchmark_curve["date"],
                y=benchmark_curve["equity"],
                mode="lines",
                line=dict(color=AMBER, width=2.2, dash="dash"),
                name=benchmark_label,
                hovertemplate=f"{benchmark_label}权益: " + "%{y:.4f}<extra></extra>",
            )
        )
    fig.update_layout(title=title, hovermode="x unified")
    fig.update_xaxes(hoverformat="%Y-%m-%d")
    return fig


def render_return_chart(
    equity_curve: pd.DataFrame,
    title: str,
    benchmark_curve: pd.DataFrame | None = None,
    benchmark_label: str | None = None,
) -> go.Figure:
    """
    渲染收益率曲线图表（相对初始权益的百分比变化）。
    同样会转换 Decimal 为 float。
    """
    from frontend.theme import BLUE, AMBER

    equity_curve = _convert_equity_to_float(equity_curve)
    if benchmark_curve is not None:
        benchmark_curve = _convert_equity_to_float(benchmark_curve)

    fig = go.Figure()
    base_equity = float(equity_curve["equity"].iloc[0]) if not equity_curve.empty else 1.0
    returns = (equity_curve["equity"] / base_equity - 1.0)
    fig.add_trace(
        go.Scatter(
            x=equity_curve["date"],
            y=returns,
            mode="lines",
            line=dict(color=BLUE, width=2.2),
            name="回测策略",
            hovertemplate="回测策略收益率: %{y:.2%}<extra></extra>",
        )
    )
    if benchmark_curve is not None and not benchmark_curve.empty and benchmark_label:
        benchmark_base = float(benchmark_curve["equity"].iloc[0]) if not benchmark_curve.empty else 1.0
        benchmark_returns = (
            benchmark_curve["equity"] / benchmark_base - 1.0
            if benchmark_base
            else pd.Series(0.0, index=benchmark_curve.index)
        )
        fig.add_trace(
            go.Scatter(
                x=benchmark_curve["date"],
                y=benchmark_returns,
                mode="lines",
                line=dict(color=AMBER, width=2.2, dash="dash"),
                name=benchmark_label,
                hovertemplate=f"{benchmark_label}收益率: " + "%{y:.2%}<extra></extra>",
            )
        )
    fig.update_layout(title=title, hovermode="x unified")
    fig.update_xaxes(hoverformat="%Y-%m-%d")
    fig.update_yaxes(tickformat=".0%")
    return fig


def get_max_drawdown_summary(equity_curve: pd.DataFrame) -> dict[str, object] | None:
    """
    计算权益曲线的最大回撤相关信息：
    - 回撤曲线
    - 峰值点、谷值点、修复点索引
    - 最大回撤幅度、修复时长
    内部会将 equity 列转为 float。
    """
    if equity_curve.empty:
        return None
    curve = equity_curve.copy()
    # 确保 equity 为 float（若为 Decimal 则转换）
    if curve["equity"].dtype == object:
        curve["equity"] = curve["equity"].apply(float)
    curve["rolling_max"] = curve["equity"].cummax()
    curve["drawdown"] = curve["equity"] / curve["rolling_max"] - 1.0
    trough_idx = int(curve["drawdown"].idxmin())
    peak_idx = int(curve.loc[:trough_idx, "equity"].idxmax())
    max_drawdown = float(curve.loc[trough_idx, "drawdown"])
    # 若无明显回撤（接近0）
    if abs(max_drawdown) < 1e-12:
        return {
            "curve": curve,
            "peak_idx": peak_idx,
            "trough_idx": trough_idx,
            "recovery_idx": None,
            "recovery_status": "无",
            "max_drawdown": 0.0,
            "has_drawdown": False,
        }
    peak_equity = float(curve.loc[peak_idx, "equity"])
    recovery_candidates = curve.index[(curve.index > trough_idx) & (curve["equity"] >= peak_equity)]
    recovery_idx = int(recovery_candidates[0]) if len(recovery_candidates) > 0 else None
    recovery_status = "修复中"
    if recovery_idx is not None:
        recovery_days = (
            pd.to_datetime(curve.loc[recovery_idx, "date"]) - pd.to_datetime(curve.loc[peak_idx, "date"])
        ).days
        recovery_status = f"{recovery_days}天"
    return {
        "curve": curve,
        "peak_idx": peak_idx,
        "trough_idx": trough_idx,
        "recovery_idx": recovery_idx,
        "recovery_status": recovery_status,
        "max_drawdown": max_drawdown,
        "has_drawdown": True,
    }


def render_max_drawdown_chart(equity_curve: pd.DataFrame, title: str) -> tuple[go.Figure, str]:
    """
    绘制最大回撤分析图，高亮最大回撤段和修复段。
    返回 (figure, recovery_status)。
    """
    from frontend.theme import BLUE, DANGER, PRIMARY

    equity_curve = _convert_equity_to_float(equity_curve)
    summary = get_max_drawdown_summary(equity_curve)
    fig = go.Figure()
    if summary is None:
        fig.update_layout(title=title)
        return fig, "修复中"

    curve = summary["curve"]
    peak_idx = int(summary["peak_idx"])
    trough_idx = int(summary["trough_idx"])
    recovery_idx = summary["recovery_idx"]
    recovery_status = str(summary["recovery_status"])
    has_drawdown = bool(summary.get("has_drawdown", True))

    # 全程回撤线（半透明）
    fig.add_trace(
        go.Scatter(
            x=curve["date"],
            y=curve["drawdown"],
            mode="lines",
            line=dict(color="rgba(148,163,184,0.45)", width=2),
            name="回撤全程",
            hovertemplate="回撤: %{y:.2%}<extra></extra>",
        )
    )
    if has_drawdown:
        # 最大回撤段（红色加粗）
        fig.add_trace(
            go.Scatter(
                x=curve.loc[peak_idx:trough_idx, "date"],
                y=curve.loc[peak_idx:trough_idx, "drawdown"],
                mode="lines",
                line=dict(color=DANGER, width=3),
                name="最大回撤段",
                hovertemplate="最大回撤段: %{y:.2%}<extra></extra>",
            )
        )
        # 修复段（绿色）
        repair_end = recovery_idx if recovery_idx is not None else len(curve) - 1
        if repair_end >= trough_idx:
            fig.add_trace(
                go.Scatter(
                    x=curve.loc[trough_idx:repair_end, "date"],
                    y=curve.loc[trough_idx:repair_end, "drawdown"],
                    mode="lines",
                    line=dict(color=PRIMARY, width=3),
                    name="修复段",
                    hovertemplate="修复段: %{y:.2%}<extra></extra>",
                )
            )
        # 峰值点标记
        fig.add_trace(
            go.Scatter(
                x=[curve.loc[peak_idx, "date"]],
                y=[curve.loc[peak_idx, "drawdown"]],
                mode="markers+text",
                marker=dict(color=BLUE, size=10, symbol="circle"),
                text=["峰值点"],
                textposition="top center",
                name="峰值点",
                hovertemplate="峰值点: %{y:.2%}<extra></extra>",
            )
        )
        # 谷值点标记
        fig.add_trace(
            go.Scatter(
                x=[curve.loc[trough_idx, "date"]],
                y=[curve.loc[trough_idx, "drawdown"]],
                mode="markers+text",
                marker=dict(color=DANGER, size=10, symbol="circle"),
                text=["谷值点"],
                textposition="bottom center",
                name="谷值点",
                hovertemplate="谷值点: %{y:.2%}<extra></extra>",
            )
        )
        # 修复点标记（若有）
        if recovery_idx is not None:
            fig.add_trace(
                go.Scatter(
                    x=[curve.loc[recovery_idx, "date"]],
                    y=[curve.loc[recovery_idx, "drawdown"]],
                    mode="markers+text",
                    marker=dict(color=PRIMARY, size=10, symbol="circle"),
                    text=["修复点"],
                    textposition="top center",
                    name="修复点",
                    hovertemplate="修复点: %{y:.2%}<extra></extra>",
                )
            )
    fig.update_layout(
        title=f"{title} | 最大回撤: {summary['max_drawdown']:.2%} | 修复时长: {recovery_status}",
        hovermode="x unified",
    )
    fig.update_xaxes(hoverformat="%Y-%m-%d")
    fig.update_yaxes(tickformat=".0%", title="回撤")
    return fig, recovery_status


def render_trade_gas_chart(trade_points: pd.DataFrame, title: str) -> go.Figure | None:
    """
    绘制交易 Gas 费用柱状图（需要包含 gas_fee_eth 列，单位为 ETH）。
    """
    from frontend.theme import BLUE_TRANSLUCENT

    if trade_points.empty:
        return None
    points = trade_points.copy()
    if "gas_fee_eth" not in points.columns:
        points["gas_fee_eth"] = 0.0
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=points["date"],
            y=points["gas_fee_eth"],
            marker=dict(color=BLUE_TRANSLUCENT),
            name="Gas费",
            hovertemplate="Gas费: %{y:.6f}<extra></extra>",
        )
    )
    fig.update_layout(title=title, hovermode="x unified")
    fig.update_xaxes(hoverformat="%Y-%m-%d")
    fig.update_yaxes(title="Gas费 (ETH)")
    return fig


def render_empty_state(
    message: str,
    icon: str = "ℹ️",
    button_label: str | None = None,
    button_key: str | None = None,
    on_button_click: callable | None = None,
) -> None:
    """
    渲染一个居中的空状态提示框，可选一个按钮回调。
    """
    st.markdown(f"""
    <div style="text-align: center; padding: 40px 20px; background-color: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-light); margin-top: 20px;">
        <div style="font-size: 60px; margin-bottom: 20px;">{icon}</div>
        <p style="font-size: 18px; color: var(--text-muted);">{message}</p>
    </div>
    """, unsafe_allow_html=True)
    if button_label and on_button_click:
        st.markdown("<div style=\"text-align: center; margin-top: 20px;\">", unsafe_allow_html=True)
        if st.button(button_label, key=button_key or "empty_state_button", type="primary"):
            on_button_click()
        st.markdown("</div>", unsafe_allow_html=True)
