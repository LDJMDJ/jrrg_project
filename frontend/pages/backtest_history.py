from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd
import streamlit as st

from frontend.shared import (
    BENCHMARK_OPTIONS,
    build_benchmark_curve,
    get_adapter,
    parse_selected_exchanges,
    render_equity_chart,
    render_max_drawdown_chart,
    render_metric_cards,
    render_return_chart,
    render_trade_gas_chart,
    render_empty_state,
)


def _to_decimal(val) -> Decimal:
    if val is None:
        return Decimal(0)
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def run() -> None:
    adapter = get_adapter()

    st.header("回测历史")
    if "history_detail_record_id" not in st.session_state:
        st.session_state.history_detail_record_id = None

    records = adapter.list_backtest_records()
    if records.empty:
        render_empty_state(
            "暂无回测记录。运行策略回测后，这里将显示您的历史记录。",
            icon="📜",
        )
        return

    if st.session_state.history_detail_record_id is not None:
        detail = adapter.get_backtest_record_detail(int(st.session_state.history_detail_record_id))
        if detail.empty:
            st.warning("该回测记录已不存在。")
            st.session_state.history_detail_record_id = None
            st.rerun()
            return

        row = detail.iloc[0]

        cumulative_return = _to_decimal(row.get("cumulative_return", 0))
        max_drawdown = _to_decimal(row.get("max_drawdown", 0))
        total_gas_cost_wei = _to_decimal(row.get("total_gas_cost", 0))
        net_profit = _to_decimal(row.get("net_profit", 0))
        trade_count = int(row.get("trade_count", 0))

        total_gas_eth = total_gas_cost_wei / Decimal(1e18)

        top_left, top_right = st.columns([4, 1])
        with top_left:
            st.subheader("回测结果详情")
        with top_right:
            if st.button("返回列表", use_container_width=True):
                st.session_state.history_detail_record_id = None
                st.rerun()

        render_metric_cards(
            [
                ("累计收益", f"{cumulative_return:.2%}"),
                ("最大回撤", f"{max_drawdown:.2%}"),
                ("总Gas成本", f"{total_gas_eth:.6f} ETH"),
                ("净收益", f"{net_profit:.2f} USD"),
                ("交易次数", f"{trade_count}"),
            ]
        )

        curve = row["equity_curve"] if isinstance(row["equity_curve"], pd.DataFrame) else pd.DataFrame()
        points = row["trade_points"] if isinstance(row["trade_points"], pd.DataFrame) else pd.DataFrame()

        if not curve.empty:
            history_exchanges = parse_selected_exchanges(row.get("selected_exchanges"))
            chart_mode_key = f"history_chart_mode_{int(row['record_id'])}"
            detail_benchmark_key = f"history_benchmark_select_{int(row['record_id'])}"
            ctrl_left, ctrl_right = st.columns([1.2, 1.2])
            with ctrl_left:
                chart_mode = st.selectbox(
                    "展示模式",
                    options=["权益", "收益率", "最大回撤"],
                    key=chart_mode_key,
                )
            selected_benchmark_label = "不对比"
            if chart_mode in {"权益", "收益率"}:
                with ctrl_right:
                    selected_benchmark_label = st.selectbox(
                        "对比指标",
                        options=list(BENCHMARK_OPTIONS.keys()),
                        key=detail_benchmark_key,
                    )
            benchmark_curve = None
            benchmark_code = BENCHMARK_OPTIONS.get(selected_benchmark_label)
            if chart_mode in {"权益", "收益率"} and benchmark_code:
                initial_capital_float = float(_to_decimal(row.get("initial_capital", 0)))
                benchmark_df = adapter.load_historical_data(
                    str(row["start_date"]),
                    str(row["end_date"]),
                    history_exchanges or None,
                )
                benchmark_curve = build_benchmark_curve(
                    benchmark_df, initial_capital_float, benchmark_code
                )
            if chart_mode == "权益":
                main_fig = render_equity_chart(
                    curve,
                    "权益曲线",
                    benchmark_curve=benchmark_curve,
                    benchmark_label=selected_benchmark_label if benchmark_code else None,
                )
            elif chart_mode == "收益率":
                main_fig = render_return_chart(
                    curve,
                    "收益率曲线",
                    benchmark_curve=benchmark_curve,
                    benchmark_label=selected_benchmark_label if benchmark_code else None,
                )
            else:
                main_fig, _ = render_max_drawdown_chart(curve, "最大回撤分析")
            st.plotly_chart(main_fig, use_container_width=True)

        if not points.empty:
            points_display = points.copy()
            if "gas_fee" in points_display.columns:
                points_display["gas_fee_eth"] = points_display["gas_fee"] / Decimal(1e18)
                gas_fig = render_trade_gas_chart(points_display, "Gas消耗情况")
            else:
                gas_fig = None
        else:
            gas_fig = None

        if gas_fig is not None:
            st.plotly_chart(gas_fig, use_container_width=True)

        report_df = pd.DataFrame(
            [
                {
                    "record_id": int(row["record_id"]),
                    "strategy_id": int(row["strategy_id"]),
                    "start_date": row["start_date"],
                    "end_date": row["end_date"],
                    "initial_capital": float(_to_decimal(row.get("initial_capital", 0))),
                    "final_equity": float(_to_decimal(row.get("final_equity", 0))),
                    "cumulative_return": float(cumulative_return),
                    "annualized_return": float(_to_decimal(row.get("annualized_return", 0))),
                    "max_drawdown": float(max_drawdown),
                    "total_gas_cost_wei": int(total_gas_cost_wei),
                    "total_gas_cost_eth": float(total_gas_eth),
                    "net_profit": float(net_profit),
                    "trade_count": trade_count,
                    "win_rate": float(row.get("win_rate", 0)),
                }
            ]
        )
        st.download_button(
            "导出详情CSV",
            data=report_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"backtest_detail_{int(row['record_id'])}.csv",
            mime="text/csv",
        )
        return

    for row in records.itertuples():
        with st.container(border=True):
            execution_time_text = datetime.fromtimestamp(int(row.execution_time)).strftime("%Y-%m-%d %H:%M:%S")
            c1, c2, c3, c4, c5, c6 = st.columns([2.2, 0.9, 0.9, 0.9, 1, 1])
            with c1:
                st.markdown(f"### {row.strategy_name or f'策略#{int(row.strategy_id)}'}")
                st.caption(f"回测时间：{execution_time_text}")
            with c2:
                cum_ret = Decimal(str(row.cumulative_return)) if row.cumulative_return else Decimal(0)
                st.caption("累计收益")
                st.write(f"{cum_ret:.2%}")
            with c3:
                max_dd = Decimal(str(row.max_drawdown)) if row.max_drawdown else Decimal(0)
                st.caption("最大回撤")
                st.write(f"{max_dd:.2%}")
            with c4:
                total_gas_wei = Decimal(str(row.total_gas_cost)) if row.total_gas_cost else Decimal(0)
                gas_eth = total_gas_wei / Decimal(1e18)
                st.caption("总Gas")
                st.write(f"{gas_eth:.10f} ETH")
            with c5:
                if st.button("查看详情", key=f"view_history_{int(row.record_id)}", use_container_width=True):
                    st.session_state.history_detail_record_id = int(row.record_id)
                    st.rerun()
            with c6:
                if st.button("删除", key=f"delete_history_{int(row.record_id)}", use_container_width=True):
                    adapter.delete_backtest_record(int(row.record_id))
                    if st.session_state.history_detail_record_id == int(row.record_id):
                        st.session_state.history_detail_record_id = None
                    st.toast("回测记录已删除！", icon="🗑️")
                    st.rerun()


if __name__ == "__main__":
    run()
