from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.shared import get_adapter, parse_params, render_empty_state


def _strategy_params_form(strategy_type: str, existing: dict | None = None) -> dict:
    existing = existing or {}
    if strategy_type == "auto_compound":
        max_sell_pct = st.number_input(
            "止盈阈值(%)",
            min_value=0.0,
            value=float(existing.get("max_sell_amount", 0.010)) * 100,
            step=0.1,
            format="%.3f",
            help="当收益率超过此阈值时触发卖出。",
        )
        min_sell_pct = st.number_input(
            "止损阈值(%)",
            max_value=0.0,
            value=float(existing.get("min_sell_amount", -0.010)) * 100,
            step=0.1,
            format="%.3f",
            help="当收益率低于此阈值时触发止损。请输入负数。",
        )
        return {
            "compound_frequency": st.selectbox(
                "复投频率",
                options=["daily", "weekly", "monthly"],
                index=0,
                help="收益复投的时间间隔。",
            ),
            "compound_ratio": st.number_input(
                "复投比例",
                min_value=0.0,
                max_value=1.0,
                value=float(existing.get("compound_ratio", 0.7)),
                step=0.01,
                format="%.2f",
                help="每次复投时用于再投资的比例，取值范围 0~1。",
            ),
            "max_sell_amount": max_sell_pct / 100,
            "min_sell_amount": min_sell_pct / 100,
        }
    spread_pct = st.number_input(
        "套利价差阈值(%)",
        min_value=0.0,
        value=float(existing.get("spread_threshold", 0.0)) * 100,
        step=0.1,
        format="%.3f",
        help="跨交易所价差超过此阈值时触发套利。",
    )
    return {
        "spread_threshold": spread_pct / 100,
        "trade_amount": st.number_input(
            "单次交易金额",
            min_value=0.0,
            value=float(existing.get("trade_amount", 0.0)),
            step=100.0,
            help="每次套利交易使用的资金量。",
        ),
    }


def _render_strategy_cards(adapter, strategies: pd.DataFrame) -> None:
    st.subheader("我的策略")
    for row in strategies.itertuples():
        strategy_type_label = "自动复投" if row.strategy_type == "auto_compound" else "多协议套利"
        with st.container(border=True):
            st.markdown(f"### {row.strategy_name}")
            st.caption(f"类型：{strategy_type_label}")
            if row.description:
                st.write(row.description)
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("修改", use_container_width=True, key=f"strategy_edit_{int(row.strategy_id)}"):
                    st.session_state.show_create_strategy_panel = True
                    st.session_state.strategy_editor_mode = "edit"
                    st.session_state.strategy_editor_target_id = int(row.strategy_id)
                    st.rerun()
            with c2:
                if int(row.built_in) == 1:
                    st.button("删除", disabled=True, use_container_width=True, key=f"strategy_delete_{int(row.strategy_id)}")
                else:
                    if st.button("删除", use_container_width=True, key=f"strategy_delete_{int(row.strategy_id)}"):
                        adapter.delete_strategy(int(row.strategy_id))
                        st.toast(f"策略「{row.strategy_name}」已删除！", icon="🗑️")
                        st.rerun()


def run() -> None:
    adapter = get_adapter()

    st.header("策略管理")
    strategies = adapter.list_strategies()
    if strategies.empty:
        def _add_strategy_action():
            st.session_state.show_create_strategy_panel = True
            st.session_state.strategy_editor_mode = "create"
            st.session_state.strategy_editor_target_id = None
            st.rerun()

        render_empty_state(
            "暂无策略。点击下方按钮新建您的第一个策略吧！",
            icon="✨",
            button_label="新建策略",
            button_key="empty_state_add_strategy_btn",
            on_button_click=_add_strategy_action,
        )
        if "show_create_strategy_panel" not in st.session_state:
            st.session_state.show_create_strategy_panel = False
        if "strategy_editor_mode" not in st.session_state:
            st.session_state.strategy_editor_mode = "create"
        if "strategy_editor_target_id" not in st.session_state:
            st.session_state.strategy_editor_target_id = None
        # Remove the floating FAB button when empty state is shown
        # fab_space, fab_col = st.columns([20, 1])
        # with fab_col:
        #     if st.button("＋", key="add_strategy_fab"):
        #         st.session_state.show_create_strategy_panel = True
        #         st.session_state.strategy_editor_mode = "create"
        #         st.session_state.strategy_editor_target_id = None
        #         st.rerun()
        return

    if "show_create_strategy_panel" not in st.session_state:
        st.session_state.show_create_strategy_panel = False
    if "strategy_editor_mode" not in st.session_state:
        st.session_state.strategy_editor_mode = "create"
    if "strategy_editor_target_id" not in st.session_state:
        st.session_state.strategy_editor_target_id = None

    if st.session_state.show_create_strategy_panel:
        left_col, right_col = st.columns([1.0, 1.25])
        with left_col:
            _render_strategy_cards(adapter, strategies)
        with right_col:
            is_edit = st.session_state.strategy_editor_mode == "edit"
            st.subheader("修改策略" if is_edit else "新建策略")
            type_map = {"自动复投": "auto_compound", "多协议套利": "multi_arbitrage"}
            edit_row = None
            if is_edit and st.session_state.strategy_editor_target_id is not None:
                target = strategies[strategies["strategy_id"] == st.session_state.strategy_editor_target_id]
                if not target.empty:
                    edit_row = target.iloc[0]
            default_name = edit_row["strategy_name"] if edit_row is not None else ""
            default_desc = edit_row["description"] if edit_row is not None else ""
            default_type = edit_row["strategy_type"] if edit_row is not None else None

            new_name = st.text_input(
                "策略名称",
                value=default_name,
                disabled=bool(edit_row is not None and int(edit_row["built_in"]) == 1),
                placeholder="请输入策略名称",
            )
            new_desc = st.text_input("策略描述", value=default_desc or "", placeholder="可选，简要描述此策略")

            type_options = list(type_map.keys())
            reverse_type_map = {v: k for k, v in type_map.items()}
            type_index = None
            if default_type:
                type_index = type_options.index(reverse_type_map[default_type])
            type_label = st.selectbox(
                "策略类型",
                options=type_options,
                index=type_index,
                placeholder="请选择策略类型",
                disabled=bool(edit_row is not None and int(edit_row["built_in"]) == 1),
            )

            new_type = type_map[type_label] if type_label else None
            params: dict = {}
            if new_type:
                existing_params = parse_params(edit_row["params"]) if edit_row is not None else None
                params = _strategy_params_form(new_type, existing=existing_params)

            has_errors = False
            if not new_name.strip():
                st.error("策略名称不能为空。")
                has_errors = True
            if not new_type:
                st.error("请先选择策略类型。")
                has_errors = True
            if is_edit and edit_row is not None:
                if (
                    new_name.strip() != edit_row["strategy_name"]
                    and new_name.strip() in strategies["strategy_name"].values
                ):
                    st.error("策略名称已存在，请使用其他名称。")
                    has_errors = True
            elif not is_edit and new_name.strip() in strategies["strategy_name"].values:
                st.error("策略名称已存在，请使用其他名称。")
                has_errors = True

            c1, c2 = st.columns([1, 1])
            with c1:
                submit = st.button("保存策略", use_container_width=True, key="save_strategy_btn", disabled=has_errors)
            with c2:
                cancel = st.button("取消", use_container_width=True, key="cancel_strategy_btn")

            if cancel:
                st.session_state.show_create_strategy_panel = False
                st.session_state.strategy_editor_mode = "create"
                st.session_state.strategy_editor_target_id = None
                st.rerun()
            if submit:
                if has_errors:
                    return
                if is_edit and edit_row is not None:
                    conn_id = int(edit_row["strategy_id"])
                    adapter.update_strategy(
                        strategy_id=conn_id,
                        strategy_name=new_name.strip(),
                        strategy_type=new_type,
                        description=new_desc.strip(),
                        params=params,
                    )
                    st.session_state.show_create_strategy_panel = False
                    st.session_state.strategy_editor_mode = "create"
                    st.session_state.strategy_editor_target_id = None
                    st.toast(f"策略「{new_name.strip()}」已更新！", icon="✅")
                    st.rerun()
                else:
                    adapter.create_strategy(new_name.strip(), new_type, new_desc.strip(), params)
                    st.session_state.show_create_strategy_panel = False
                    st.session_state.strategy_editor_mode = "create"
                    st.session_state.strategy_editor_target_id = None
                    st.toast(f"策略「{new_name.strip()}」创建成功！", icon="🎉")
                    st.rerun()
    else:
        _render_strategy_cards(adapter, strategies)

    fab_space, fab_col = st.columns([20, 1])
    with fab_col:
        if st.button("＋", key="add_strategy_fab"):
            st.session_state.show_create_strategy_panel = True
            st.session_state.strategy_editor_mode = "create"
            st.session_state.strategy_editor_target_id = None
            st.rerun()


if __name__ == "__main__":
    run()
