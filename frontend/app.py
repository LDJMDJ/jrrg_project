from __future__ import annotations

import streamlit as st
import time
from PIL import Image

from shared import get_logo_image_path
from styles import inject_styles

if "is_dark_mode" not in st.session_state:
    st.session_state.is_dark_mode = False

st.set_page_config(page_title="DeFi策略回测系统", layout="wide", initial_sidebar_state="expanded")


@st.cache_data
def get_logo_image(is_dark_mode: bool):
    logo_path = get_logo_image_path(use_sidebar_variant=True, is_dark_mode=is_dark_mode)
    if logo_path.exists():
        logo_image = Image.open(logo_path)
        width, height = logo_image.size
        # Resize the image by 80%
        logo_image = logo_image.resize((int(width * 1.8), int(height * 1.8)))
        return logo_image
    return None

logo_image = get_logo_image(st.session_state.is_dark_mode)
if logo_image:
    st.logo(logo_image)

# --- Welcome Page Logic ---
if "page" not in st.session_state:
    st.session_state.page = "welcome"

if st.session_state.page == "welcome":
    from frontend.pages import welcome
    welcome.run()
    time.sleep(2)
    st.session_state.page = "main_app"
    st.rerun()
else:
    # Main App Navigation
    with st.sidebar:

        is_dark_mode = st.toggle("深色模式", value=st.session_state.is_dark_mode)
        if is_dark_mode != st.session_state.is_dark_mode:
            st.session_state.is_dark_mode = is_dark_mode
            st.rerun()

    history_page = st.Page("pages/history_data.py", title="历史数据", icon="📊")
    strategy_page = st.Page("pages/strategy_manage.py", title="策略管理", icon="⚙️")
    backtest_page = st.Page("pages/backtest.py", title="策略回测", icon="🚀")
    history_backtest_page = st.Page("pages/backtest_history.py", title="回测历史", icon="📋")

    pg = st.navigation(
        {
            "导航": [history_page, strategy_page, backtest_page, history_backtest_page],
        }
    )

    inject_styles(st.session_state.is_dark_mode)
    pg.run()
