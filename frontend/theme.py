from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

PRIMARY = "#10b981"
PRIMARY_HOVER = "#0ea371"
PRIMARY_LIGHT = "rgba(16,185,129,0.45)"
PRIMARY_GLOW = "rgba(16,185,129,0.38)"

DANGER = "#ef4444"
DANGER_HOVER = "#dc2626"

BLUE = "#2563eb"
BLUE_LIGHT = "#3b82f6"
BLUE_TRANSLUCENT = "rgba(59,130,246,0.80)"

AMBER = "#f59e0b"

# Light Theme Colors
LIGHT_THEME_COLORS = {
    "text_primary": "#111827",
    "text_secondary": "#425466",
    "text_muted": "#6b7280",
    "bg_nav": "#eef3f9",
    "bg_card": "#ffffff",
    "bg_input": "#f8fafc",
    "bg_input_hover": "#eef3f9",
    "bg_input_active": "#dbe4ee",
    "border_light": "#e5e7eb",
    "border_medium": "#dbe4ee",
    "border_dark": "#94a3b8",
    "border_nav": "rgba(16,185,129,0.28)",
    "bg_sidebar_gradient_start": "#f8fafc",
    "bg_sidebar_gradient_end": "#eef3f9",
    "bg_body": "#f0f2f6",
}

# Dark Theme Colors
DARK_THEME_COLORS = {
    "text_primary": "#f8fafc",
    "text_secondary": "#cbd5e1",
    "text_muted": "#94a3b8",
    "bg_nav": "#1e293b",
    "bg_card": "#1f2937",
    "bg_input": "#334155",
    "bg_input_hover": "#475569",
    "bg_input_active": "#64748b",
    "border_light": "#334155",
    "border_medium": "#475569",
    "border_dark": "#64748b",
    "border_nav": "rgba(16,185,129,0.48)",
    "bg_sidebar_gradient_start": "#0f172a",
    "bg_sidebar_gradient_end": "#1e293b",
    "bg_body": "#1f2937",
}

def get_theme_colors(is_dark_mode: bool) -> dict[str, str]:
    return DARK_THEME_COLORS if is_dark_mode else LIGHT_THEME_COLORS

PLOTLY_TEMPLATE = go.layout.Template()

PLOTLY_TEMPLATE.layout = go.Layout(
    font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", color=LIGHT_THEME_COLORS["text_secondary"]),
    title=dict(font=dict(size=18, color=LIGHT_THEME_COLORS["text_primary"], family="Inter, -apple-system, BlinkMacSystemFont, sans-serif")),
    xaxis=dict(
        gridcolor="rgba(148,163,184,0.15)",
        zerolinecolor="rgba(148,163,184,0.25)",
        title_font=dict(color=LIGHT_THEME_COLORS["text_muted"]),
    ),
    yaxis=dict(
        gridcolor="rgba(148,163,184,0.15)",
        zerolinecolor="rgba(148,163,184,0.25)",
        title_font=dict(color=LIGHT_THEME_COLORS["text_muted"]),
    ),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=48, r=24, t=56, b=48),
    hovermode="x unified",
    hoverlabel=dict(
        bgcolor="rgba(17,24,39,0.92)", # This might need to be dynamic or a neutral dark color
        font_size=13,
        font_family="Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        font_color="#ffffff",
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor="rgba(255,255,255,0.85)", # This might need to be dynamic
        bordercolor="rgba(148,163,184,0.25)",
        borderwidth=1,
    ),
)

PLOTLY_TEMPLATE.layout.xaxis.update(dict(hoverformat="%Y-%m-%d"))

pio.templates["defi_theme"] = PLOTLY_TEMPLATE
pio.templates.default = "defi_theme"
