from __future__ import annotations

from datetime import datetime

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from frontend.shared import get_adapter, render_empty_state


def run() -> None:
    adapter = get_adapter()

    st.header("历史数据展示")
    exchanges = adapter.list_exchanges()
    date_bounds = adapter.get_historical_date_bounds()
    if date_bounds is None:
        render_empty_state(
            "暂无可用历史数据。请确保已运行数据初始化脚本，或检查数据源。",
            icon="😔",
        )
        return

    min_date = datetime.strptime(date_bounds[0], "%Y-%m-%d").date()
    max_date = datetime.strptime(date_bounds[1], "%Y-%m-%d").date()
    c1, c2, c3 = st.columns([1.5, 1.5, 2])
    with c1:
        start_date = st.date_input(
            "开始日期",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="history_start_date",
        )
    with c2:
        end_date = st.date_input(
            "结束日期",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="history_end_date",
        )
    with c3:
        selected_ex = st.multiselect("交易所", options=exchanges, default=exchanges[:2])

    if start_date > end_date:
        st.error("开始时间不能晚于结束时间。")
        return

    if st.button("筛选数据", use_container_width=True):
        df = adapter.load_historical_data(str(start_date), str(end_date), selected_ex)
        if df.empty:
            st.warning("所选条件暂无历史数据。")
            return
        daily = (
            df.groupby("date", as_index=False)
            .agg(
                price_mean=("price", "mean"),
                price_min=("price", "min"),
                price_max=("price", "max"),
                gas_price=("gas_price", "mean"),
            )
            .sort_values("date")
        )
        col_a, col_b = st.columns(2)
        with col_a:
            fig_price = go.Figure()
            fig_price.add_trace(
                go.Scatter(
                    x=daily["date"],
                    y=daily["price_min"],
                    mode="lines",
                    line=dict(width=1.2, color="rgba(16,185,129,0.45)", dash="dot"),
                    hoverinfo="skip",
                    name="最低价",
                    showlegend=False,
                )
            )
            fig_price.add_trace(
                go.Scatter(
                    x=daily["date"],
                    y=daily["price_max"],
                    mode="lines",
                    fill="tonexty",
                    fillcolor="rgba(16,185,129,0.38)",
                    line=dict(width=1.2, color="rgba(16,185,129,0.45)", dash="dot"),
                    name="最高/最低价区间",
                    customdata=daily["price_min"],
                    hovertemplate="最高价: %{y:.2f} USD<br>最低价: %{customdata:.2f} USD<extra></extra>",
                )
            )
            fig_price.add_trace(
                go.Scatter(
                    x=daily["date"],
                    y=daily["price_mean"],
                    mode="lines",
                    line=dict(color="#10b981", width=1.4),
                    name="均值线",
                    hovertemplate="均值价: %{y:.2f} USD<extra></extra>",
                )
            )
            fig_price.update_layout(title="ETH价格走势", hovermode="x unified")
            fig_price.update_xaxes(hoverformat="%Y-%m-%d")
            st.plotly_chart(fig_price, use_container_width=True)
        with col_b:
            fig_gas = px.line(daily, x="date", y="gas_price", title="Gas费用走势")
            fig_gas.update_traces(
                hovertemplate="Gas均价: %{y:.2f} Gwei<extra></extra>",
                line=dict(width=2, color="#3b82f6"),
            )
            fig_gas.update_layout(hovermode="x unified")
            fig_gas.update_xaxes(hoverformat="%Y-%m-%d")
            st.plotly_chart(fig_gas, use_container_width=True)


if __name__ == "__main__":
    run()
