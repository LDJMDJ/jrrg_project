from __future__ import annotations

import streamlit as st

from frontend.theme import get_theme_colors, PLOTLY_TEMPLATE
import plotly.io as pio


def inject_styles(is_dark_mode: bool = False) -> None:
    colors = get_theme_colors(is_dark_mode)

    # Update Plotly template with dynamic theme colors
    PLOTLY_TEMPLATE.layout.font.color = colors["text_secondary"]
    PLOTLY_TEMPLATE.layout.title.font.color = colors["text_primary"]
    PLOTLY_TEMPLATE.layout.xaxis.title.font.color = colors["text_muted"]
    PLOTLY_TEMPLATE.layout.yaxis.title.font.color = colors["text_muted"]
    PLOTLY_TEMPLATE.layout.legend.bgcolor = colors["bg_card"] # Use card background for legend
    # Plotly hoverlabel bgcolor can remain dark for contrast

    pio.templates["defi_theme"] = PLOTLY_TEMPLATE
    pio.templates.default = "defi_theme"

    CSS = f"""
<style>
:root {{
  --primary: #10b981;
  --primary-hover: #0ea371;
  --primary-light: rgba(16,185,129,0.15);
  --primary-glow: rgba(16,185,129,0.35);
  --danger: #ef4444;
  --danger-hover: #dc2626;
  --blue: #2563eb;
  --blue-light: #3b82f6;
  --amber: #f59e0b;

  --text-primary: {colors["text_primary"]};
  --text-secondary: {colors["text_secondary"]};
  --text-muted: {colors["text_muted"]};

  --bg-body: {colors["bg_body"]};
  --bg-nav: {colors["bg_nav"]};
  --bg-card: {colors["bg_card"]};
  --bg-input: {colors["bg_input"]};
  --bg-input-hover: {colors["bg_input_hover"]};
  --bg-input-active: {colors["bg_input_active"]};

  --border-light: {colors["border_light"]};
  --border-medium: {colors["border_medium"]};
  --border-dark: {colors["border_dark"]};
  --border-nav: {colors["border_nav"]};

  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
  --shadow-glow: 0 8px 20px var(--primary-glow);
  --radius-sm: 8px;
  --radius-md: 10px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --transition-fast: 0.15s ease;
  --transition-base: 0.2s ease;
}}

html {{
    color-scheme: {'dark' if is_dark_mode else 'light'};
}}

body {{
    background-color: var(--bg-body);
    color: var(--text-primary);
    font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
}}

.st-emotion-cache-vk32no,
.st-emotion-cache-k3k9o8 {{
    background-color: var(--bg-body);
}}

.st-key-nav_history button,
.st-key-nav_strategy button,
.st-key-nav_backtest button,
.st-key-nav_history_backtest button {{
    width: 100% !important;
    border-radius: var(--radius-md) !important;
    background: var(--bg-nav) !important;
    color: var(--text-primary) !important;
    border: 1px solid transparent !important;
    min-height: 46px !important;
    font-weight: 600 !important;
    transition: all var(--transition-base) !important;
}}
.st-key-nav_history button:hover,
.st-key-nav_strategy button:hover,
.st-key-nav_backtest button:hover,
.st-key-nav_history_backtest button:hover {{
    background: #dce6f1 !important;
    color: var(--text-primary) !important;
    border-color: var(--primary) !important;
    transform: translateX(2px);
}}

[data-testid="stSidebar"] [data-testid="stToggle"] label {{
    color: var(--text-primary) !important;
}}

section[data-testid="stSidebar"] h2 {{
    color: var(--text-primary) !important;
}}
.st-key-active_nav button {{
    background: var(--primary) !important;
    color: white !important;
    box-shadow: var(--shadow-glow) !important;
    border-color: var(--primary) !important;
}}
.st-key-active_nav button:hover {{
    background: var(--primary-hover) !important;
    transform: translateX(2px);
}}

.st-key-add_strategy_fab button {{
    width: 56px !important;
    height: 56px !important;
    border-radius: 50% !important;
    border: none !important;
    background: var(--primary) !important;
    color: white !important;
    font-size: 28px !important;
    line-height: 1 !important;
    padding: 0 !important;
    box-shadow: var(--shadow-glow);
    transition: all var(--transition-base) !important;
}}
.st-key-add_strategy_fab button:hover {{
    background: var(--primary-hover) !important;
    box-shadow: 0 10px 28px rgba(16,185,129,0.45) !important;
    transform: scale(1.08);
}}
.st-key-add_strategy_fab button:active {{
    transform: scale(0.95);
}}

[class*="st-key-strategy_edit_"] button {{
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all var(--transition-fast) !important;
}}
[class*="st-key-strategy_edit_"] button:hover {{
    background: var(--primary-hover) !important;
    box-shadow: 0 4px 12px rgba(16,185,129,0.3) !important;
}}

[class*="st-key-strategy_delete_"] button {{
    background: var(--danger) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all var(--transition-fast) !important;
}}
[class*="st-key-strategy_delete_"] button:hover {{
    background: var(--danger-hover) !important;
    box-shadow: 0 4px 12px rgba(239,68,68,0.3) !important;
}}

[class*="st-key-view_history_"] button {{
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all var(--transition-base) !important;
}}
[class*="st-key-view_history_"] button:hover {{
    background: var(--primary-hover) !important;
    box-shadow: 0 4px 12px rgba(16,185,129,0.3) !important;
}}

[class*="st-key-delete_history_"] button {{
    background: var(--danger) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all var(--transition-base) !important;
}}
[class*="st-key-delete_history_"] button:hover {{
    background: var(--danger-hover) !important;
    box-shadow: 0 4px 12px rgba(239,68,68,0.3) !important;
}}

.stNumberInput button {{
    background: var(--bg-input) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-medium) !important;
    border-radius: 6px !important;
    transition: all var(--transition-fast) !important;
}}
.stNumberInput button:hover {{
    background: var(--bg-input-hover) !important;
    color: var(--text-primary) !important;
    border-color: #cbd5e1 !important;
}}
.stNumberInput button:active {{
    background: var(--bg-input-active) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-dark) !important;
}}
.stNumberInput button:focus,
.stNumberInput button:focus-visible {{
    background: var(--bg-input) !important;
    color: var(--text-secondary) !important;
    border-color: var(--border-medium) !important;
    outline: none !important;
    box-shadow: none !important;
}}

.metric-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-lg);
    padding: 16px 18px;
    min-height: 92px;
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--transition-base), transform var(--transition-base);
}}
.metric-card:hover {{
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}}
.metric-card-label {{
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.metric-card-value {{
    color: var(--text-primary);
    font-size: 22px;
    font-weight: 700;
    line-height: 1.25;
    white-space: normal;
    word-break: break-word;
}}

.strategy-card {{
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-xl) !important;
    padding: 20px 24px !important;
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--transition-base), border-color var(--transition-base);
}}
.strategy-card:hover {{
    box-shadow: var(--shadow-md);
    border-color: var(--border-medium) !important;
}}

.config-panel {{
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-xl) !important;
    padding: 20px 24px !important;
    box-shadow: var(--shadow-sm);
    background: var(--bg-card);
}}

[data-testid="stHeader"] {{
    background: rgba(0,0,0,0);
}}

section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {colors["bg_sidebar_gradient_start"]} 0%, {colors["bg_sidebar_gradient_end"]} 100%);
}}

.stApp [data-testid="stExpander"] {{
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--transition-base);
}}
.stApp [data-testid="stExpander"]:hover {{
    box-shadow: var(--shadow-md);
}}

div[data-testid="stTooltipHoverTarget"] {{
    display: inline-flex;
}}

div[data-testid="stNotification"] {{
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-md) !important;
}}

.st-key-save_strategy_btn button {{
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all var(--transition-fast) !important;
}}
.st-key-save_strategy_btn button:hover {{
    background: var(--primary-hover) !important;
    box-shadow: 0 4px 12px rgba(16,185,129,0.3) !important;
}}

.st-key-cancel_strategy_btn button {{
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
}}

button[kind="primary"] {{
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all var(--transition-fast) !important;
    box-shadow: var(--shadow-sm);
}}
button[kind="primary"]:hover {{
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}}
button[kind="primary"]:active {{
    transform: translateY(0);
}}

.st-key-backtest_benchmark_select [data-baseweb="select"],
.st-key-backtest_chart_mode [data-baseweb="select"] {{
    border-radius: var(--radius-sm) !important;
}}
</style>
"""
    st.markdown(CSS, unsafe_allow_html=True)
