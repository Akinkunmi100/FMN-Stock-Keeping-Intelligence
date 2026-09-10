"""
ui/styles.py — Global CSS Design System & Visual Language
=========================================================
Centralized styling for the Supply Chain Control Room.
Implements modern typography, color-coded status badges, metric cards,
and responsive operational alert callouts.
"""

from __future__ import annotations

from config import COLORS


def get_application_css() -> str:
    """Return the complete CSS stylesheet string injected into Streamlit."""
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

    :root {{
        --ink: {COLORS['ink']};
        --paper: {COLORS['paper']};
        --card-bg: {COLORS['card_bg']};
        --line: {COLORS['line']};
        --muted: {COLORS['muted']};
        --critical: {COLORS['critical']};
        --critical-bg: {COLORS['critical_bg']};
        --high: {COLORS['high']};
        --high-bg: {COLORS['high_bg']};
        --medium: {COLORS['medium']};
        --medium-bg: {COLORS['medium_bg']};
        --low: {COLORS['low']};
        --low-bg: {COLORS['low_bg']};
        --overstock: {COLORS['overstock']};
        --overstock-bg: {COLORS['overstock_bg']};
    }}

    .stApp {{
        background: var(--paper);
        color: var(--ink);
    }}

    .block-container {{
        padding: 2.2rem 4rem 4rem;
        max-width: 1540px;
    }}

    html, body, [class*="css"] {{
        font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    h1, h2, h3, h4 {{
        letter-spacing: -0.04em;
        color: var(--ink);
        font-weight: 800;
    }}

    h1 {{
        font-size: clamp(2.2rem, 3.6vw, 3.6rem) !important;
        line-height: 1.05 !important;
        margin: 0 !important;
    }}

    h2 {{
        font-size: 1.45rem !important;
        margin-top: 1.4rem !important;
        margin-bottom: 0.4rem !important;
    }}

    .mono, code {{
        font-family: 'DM Mono', monospace;
    }}

    /* Eyebrows & Section Headers */
    .eyebrow {{
        font: 500 0.72rem 'DM Mono', monospace;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #6b776f;
        margin-bottom: 0.5rem;
    }}

    /* Hero Banner Component */
    .hero {{
        border-bottom: 1px solid var(--line);
        padding-bottom: 1.8rem;
        margin-bottom: 1.5rem;
    }}

    .hero-note {{
        color: var(--muted);
        font-size: 1.02rem;
        max-width: 760px;
        line-height: 1.6;
        margin-top: 0.8rem;
    }}

    .hero-stamp {{
        background: var(--ink);
        color: var(--paper);
        padding: 0.65rem 1.1rem;
        font: 500 0.74rem 'DM Mono', monospace;
        display: inline-block;
        margin-top: 1.1rem;
        letter-spacing: 0.05em;
    }}

    /* Metric KPI Cards */
    .metric {{
        border-top: 2.5px solid var(--ink);
        padding: 0.85rem 0 1.1rem;
        background: transparent;
    }}

    .metric-label {{
        color: var(--muted);
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }}

    .metric-value {{
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        margin-top: 0.25rem;
        line-height: 1.1;
    }}

    .metric-sub {{
        color: var(--muted);
        font-size: 0.76rem;
        margin-top: 0.3rem;
    }}

    /* Queue Header */
    .queue-head {{
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem;
        margin: 1.8rem 0 0.7rem;
    }}

    .queue-head h2 {{
        margin: 0 !important;
    }}

    .section-note {{
        color: var(--muted);
        font-size: 0.86rem;
        line-height: 1.6;
    }}

    /* Status & ABC Badges */
    .status {{
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font: 600 0.70rem 'DM Mono', monospace;
        border: 1px solid var(--ink);
        color: var(--ink);
        letter-spacing: 0.04em;
    }}

    .status-critical {{
        background: var(--critical);
        border-color: var(--critical);
        color: #ffffff !important;
        font-weight: 700;
    }}

    .status-high {{
        background: #FAD7A0;
        border-color: var(--high);
        color: #7E5109 !important;
    }}

    .status-medium {{
        background: #FCF3CF;
        border-color: #D4AC0D;
        color: #7D6608 !important;
    }}

    .status-low {{
        background: #D4EFDF;
        border-color: var(--low);
        color: #145A32 !important;
    }}

    .status-overstock {{
        background: #D6EAF8;
        border-color: var(--overstock);
        color: #1B4F72 !important;
    }}

    .status-a {{
        background: #D4EFDF;
        border-color: #1E8449;
        color: #145A32 !important;
        font-weight: 700;
    }}

    .status-b {{
        background: #FCF3CF;
        border-color: #D4AC0D;
        color: #7D6608 !important;
    }}

    .status-c {{
        background: #EAEDED;
        border-color: #7F8C8D;
        color: #515A5A !important;
    }}

    /* Order Timing Badges */
    .timing-badge {{
        display: inline-block;
        padding: 0.2rem 0.5rem;
        font: 700 0.68rem 'DM Mono', monospace;
        border-radius: 2px;
    }}
    .timing-overdue {{ background: #FDEDEC; color: #C0392B; border: 1px solid #E74C3C; }}
    .timing-today {{ background: #FDEDEC; color: #C0392B; border: 1px solid #E74C3C; font-weight: 800; }}
    .timing-soon {{ background: #FEF5E7; color: #B9770E; border: 1px solid #E67E22; }}
    .timing-healthy {{ background: #EAFAF1; color: #1E8449; border: 1px solid #27AE60; }}

    /* Action Callout Cards */
    .action-card {{
        background: #ffffff;
        border-left: 4.5px solid var(--ink);
        border-top: 1px solid var(--line);
        border-right: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
        padding: 1.1rem 1.3rem;
        margin: 1rem 0 1.4rem;
    }}

    .action-card-title {{
        font-weight: 800;
        font-size: 0.96rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}

    .action-card p, .action-card li {{
        color: #3d4642;
        font-size: 0.88rem;
        line-height: 1.6;
    }}

    .action-card ul {{
        margin: 0.4rem 0 0;
        padding-left: 1.2rem;
    }}

    /* Overstock Alert Box */
    .overstock-card {{
        background: #EBF5FB;
        border-left: 4.5px solid var(--overstock);
        border-top: 1px solid #AED6F1;
        border-right: 1px solid #AED6F1;
        border-bottom: 1px solid #AED6F1;
        padding: 1.1rem 1.3rem;
        margin: 1rem 0 1.4rem;
    }}

    .overstock-card-title {{
        color: #1B4F72;
        font-weight: 800;
        font-size: 0.96rem;
        margin-bottom: 0.5rem;
    }}

    .evidence {{
        background: #EEF2EA;
        border-left: 4.5px solid var(--ink);
        padding: 1.1rem 1.3rem;
        margin: 0.8rem 0 1.2rem;
    }}

    .evidence-title {{
        font-weight: 800;
        margin-bottom: 0.45rem;
        font-size: 0.95rem;
    }}

    .evidence p {{
        color: #37413c;
        font-size: 0.90rem;
        line-height: 1.65;
        margin: 0;
    }}

    /* Sidebar and Footer */
    [data-testid="stSidebar"] {{
        background: #E9EEE6;
        border-right: 1px solid var(--line);
    }}

    [data-testid="stSidebar"] .block-container {{
        padding: 2rem 1.4rem;
    }}

    .footer-note {{
        color: var(--muted);
        font-size: 0.78rem;
        border-top: 1px solid var(--line);
        padding-top: 1.2rem;
        margin-top: 3rem;
    }}

    /* Button Polish */
    .stButton button {{
        border-radius: 0;
        border: 1px solid var(--ink);
        background: transparent;
        color: var(--ink);
        font-weight: 700;
        transition: all 0.15s ease;
    }}

    .stButton button:hover {{
        background: var(--ink);
        color: var(--paper);
        border-color: var(--ink);
    }}

    .stDownloadButton button {{
        border-radius: 0;
        border: 1px solid var(--ink);
        background: var(--ink);
        color: var(--paper);
        font-weight: 700;
        transition: all 0.15s ease;
    }}

    .stDownloadButton button:hover {{
        background: #333333;
        color: var(--paper);
    }}
    </style>
    """
