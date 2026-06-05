from __future__ import annotations

import streamlit as st

from frontend.shared import load_signal_image_data_uri


def run() -> None:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    left, center, right = st.columns([1, 2.2, 1])
    with center:
        logo_uri = load_signal_image_data_uri(760, use_sidebar_variant=False)
        if logo_uri:
            st.markdown(
                f"""
                <div style="display:flex; justify-content:center; align-items:center; width:100%;">
                    <img src="{logo_uri}" style="width: min(100%, 520px); height: auto; display: block;" />
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown(
            """
            <h1 style='text-align:center; margin-top: 18px; margin-bottom: 0; font-size: 3.2rem; line-height: 1.25; color: #2b2d3a;'>
                欢迎使用策略回测系统!
            </h1>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    run()
