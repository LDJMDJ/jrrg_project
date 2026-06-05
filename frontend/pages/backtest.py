from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal

import pandas as pd
import streamlit as st

from src.models import BacktestConfig
from frontend.shared import (
    BENCHMARK_OPTIONS,
    build_benchmark_curve,
    get_adapter,
    get_engine,
    parse_params,
    render_equity_chart,
    render_max_drawdown_chart,
    render_metric_cards,
    render_return_chart,
    render_trade_gas_chart,
    render_empty_state,  # Added this import
)


def run() -> None:
    adapter = get_adapter()
    engine = get_engine()

    st.header("策略回测")
    strategies = adapter.list_strategies()
    exchanges = adapter.list_exchanges()
    date_bounds = adapter.get_historical_date_bounds()
    if date_bounds is None:
        render_empty_state(
            "暂无可用历史数据，无法执行回测。请确保已运行数据初始化脚本，或检查数据源。",
            icon="🚫",
        )
        return
    min_date = datetime.strptime(date_bounds[0], "%Y-%m-%d").date()
    max_date = datetime.strptime(date_bounds[1], "%Y-%m-%d").date()
    option_map = {
        f"{int(row.strategy_id)} - {row.strategy_name}": int(row.strategy_id)
        for row in strategies.itertuples()
    }

    if "last_backtest" not in st.session_state:
        st.session_state.last_backtest = None
    if "last_backtest_input_signature" not in st.session_state:
        st.session_state.last_backtest_input_signature = None

    run_clicked = False
    left_col, right_col = st.columns([1.0, 2.1])
    with left_col:
        with st.container(border=True):
            st.subheader("回测配置")
            selected_label = st.selectbox("回测策略", options=list(option_map.keys()))
            start_date = st.date_input(
                "开始日期",
                value=min_date,
                min_value=min_date,
                max_value=max_date,
                key="backtest_start_date",
            )
            end_date = st.date_input(
                "结束日期",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key="backtest_end_date",
            )
            initial_capital_float = st.number_input(
                "初始资金", min_value=100.0, value=10000.0, step=100.0
            )
            initial_capital = Decimal(str(initial_capital_float))
            selected_ex = st.multiselect("交易所", options=exchanges, default=exchanges[:2])
            run_clicked = st.button("执行回测", use_container_width=True, type="primary")

        if start_date > end_date:
            st.error("开始时间不能晚于结束时间。")
            run_clicked = False

    current_signature = (
        selected_label,
        str(start_date),
        str(end_date),
        str(initial_capital),
        tuple(sorted(selected_ex)),
    )
    if (
        st.session_state.last_backtest_input_signature is not None
        and current_signature != st.session_state.last_backtest_input_signature
    ):
        st.session_state.last_backtest = None
        st.session_state.last_backtest_input_signature = current_signature

    with right_col:
        if not run_clicked and st.session_state.last_backtest is None:
            render_empty_state(
                "请在左侧配置回测参数，然后点击「执行回测」按钮开始仿真。",
                icon="📈",
            )

        if run_clicked:
            strategy_id = option_map[selected_label]
            row = strategies[strategies["strategy_id"] == strategy_id].iloc[0]
            params = parse_params(row["params"])
            if row["strategy_type"] == "multi_arbitrage" and len(selected_ex) < 2:
                st.error("多协议套利策略必须至少选择2个交易所。")
                return

            with st.status("正在执行回测...", expanded=True) as status:
                st.write("加载历史数据...")
                time.sleep(0.15)
                df = adapter.load_historical_data(str(start_date), str(end_date), selected_ex)
                if df.empty:
                    status.update(label="回测失败：无可用数据", state="error")
                    return

                st.write("构建回测配置...")
                time.sleep(0.1)
                config = BacktestConfig(
                    start_time=str(start_date),
                    end_time=str(end_date),
                    initial_capital=initial_capital,
                    strategy_id=int(strategy_id),
                    strategy_name=str(row["strategy_name"]),
                    strategy_type=str(row["strategy_type"]),
                    params=params,
                    selected_exchanges=selected_ex,
                )

                st.write("执行策略仿真...")
                time.sleep(0.2)
                result = engine.run_backtest(df, config)

                st.write("保存回测结果...")
                time.sleep(0.1)
                adapter.save_backtest_result(result, config)

                st.session_state.last_backtest = {"config": config, "result": result}
                st.session_state.last_backtest_input_signature = current_signature
                status.update(label="回测完成！", state="complete")

            st.toast("回测执行完成！", icon="🚀")

        if st.session_state.last_backtest is not None:
            config = st.session_state.last_backtest["config"]
            result = st.session_state.last_backtest["result"]

            total_gas_eth = Decimal(result.total_gas_cost) / Decimal(1_000_000_000_000_000_000)

            render_metric_cards(
                [
                    ("累计收益率", f"{result.cumulative_return:.2%}"),
                    ("年化收益率", f"{result.annualized_return:.2%}"),
                    ("最大回撤", f"{result.max_drawdown:.4%}"),
                    ("总Gas成本", f"{total_gas_eth:.6f} ETH"),
                    ("净收益", f"{result.net_profit:.2f} USD"),
                ]
            )

            ctrl_left, ctrl_right = st.columns([1.2, 1.2])
            with ctrl_left:
                chart_mode = st.selectbox(
                    "展示模式",
                    options=["权益", "收益率", "最大回撤"],
                    key="backtest_chart_mode",
                )
            selected_benchmark_label = "不对比"
            if chart_mode in {"权益", "收益率"}:
                with ctrl_right:
                    selected_benchmark_label = st.selectbox(
                        "对比指标",
                        options=list(BENCHMARK_OPTIONS.keys()),
                        key="backtest_benchmark_select",
                    )
            benchmark_curve = None
            benchmark_code = BENCHMARK_OPTIONS.get(selected_benchmark_label)
            if chart_mode in {"权益", "收益率"} and benchmark_code:
                benchmark_df = adapter.load_historical_data(
                    config.start_time, config.end_time, config.selected_exchanges
                )
                benchmark_curve = build_benchmark_curve(
                    benchmark_df, float(config.initial_capital), benchmark_code
                )

            if chart_mode == "权益":
                main_fig = render_equity_chart(
                    result.equity_curve,
                    "权益曲线",
                    benchmark_curve=benchmark_curve,
                    benchmark_label=selected_benchmark_label if benchmark_code else None,
                )
            elif chart_mode == "收益率":
                main_fig = render_return_chart(
                    result.equity_curve,
                    "收益率曲线",
                    benchmark_curve=benchmark_curve,
                    benchmark_label=selected_benchmark_label if benchmark_code else None,
                )
            else:
                main_fig, _ = render_max_drawdown_chart(result.equity_curve, "最大回撤分析")
            st.plotly_chart(main_fig, use_container_width=True)

            if not result.trade_points.empty:
                points_display = result.trade_points.copy()
                points_display["gas_fee_eth"] = points_display["gas_fee"] / Decimal(1_000_000_000_000_000_000)
                gas_fig = render_trade_gas_chart(points_display, "Gas消耗情况")
                if gas_fig is not None:
                    st.plotly_chart(gas_fig, use_container_width=True)

            report_df = pd.DataFrame(
                [
                    {
                        "strategy_name": config.strategy_name,
                        "start_date": config.start_time,
                        "end_date": config.end_time,
                        "initial_capital": float(config.initial_capital),
                        "cumulative_return": float(result.cumulative_return),
                        "annualized_return": float(result.annualized_return),
                        "max_drawdown": float(result.max_drawdown),
                        "trade_count": result.trade_count,
                        "win_rate": result.win_rate,
                        "total_gas_cost_wei": result.total_gas_cost,
                        "total_gas_cost_eth": float(total_gas_eth),
                        "net_profit": float(result.net_profit),
                    }
                ]
            )
            st.download_button(
                "导出回测报告CSV",
                data=report_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"backtest_report_{config.start_time}_{config.end_time}.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    run()