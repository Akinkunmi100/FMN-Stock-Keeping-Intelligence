"""
ui/styles.py — Global CSS Design System & Visual Language
=========================================================
Centralized styling for the Supply Chain Control Room.

Design Philosophy:
- Flat, bordered surfaces — no gradients, no glassmorphism, no drop-shadow
  "floating card" treatment. A supply-chain planner should be able to scan
  this at a glance the way they'd scan a spreadsheet or an ERP screen, not
  a marketing landing page.
- Color is reserved for operational meaning (severity, ABC tier) — never
  used decoratively.
- No animation beyond a fast, functional color/border transition on
  interactive elements. Nothing pulses, fades in, or lifts on hover.
- Moderate type scale and weight. Headings are legible, not loud.
"""

from __future__ import annotations

from config import COLORS


def get_application_css() -> str:
    """Return the complete CSS stylesheet string injected into Streamlit."""
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700&display=swap');

    /* ───────────────────── CSS CUSTOM PROPERTIES ───────────────────── */
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
        --radius: 6px;
        --transition: border-color 0.15s ease, background-color 0.15s ease;
    }}

    /* ───────────────────── GLOBAL BASE ───────────────────── */
    .stApp {{
        background: var(--paper);
        color: var(--ink);
    }}

    .block-container {{
        padding: 1.8rem 3rem 3rem;
        max-width: 1520px;
    }}

    html, body, [class*="css"] {{
        font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        -webkit-font-smoothing: antialiased;
    }}

    /* ───────────────────── TYPOGRAPHY ───────────────────── */
    h1, h2, h3, h4 {{
        letter-spacing: -0.01em;
        color: var(--ink);
        font-weight: 700;
    }}

    h1 {{
        font-size: 1.9rem !important;
        line-height: 1.2 !important;
        margin: 0 !important;
    }}

    h2 {{
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        margin-top: 1.4rem !important;
        margin-bottom: 0.4rem !important;
    }}

    h3 {{
        font-size: 1.02rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.3rem !important;
    }}

    .mono, code {{
        font-family: 'DM Mono', 'Fira Code', monospace;
    }}

    /* ───────────────────── EYEBROW LABELS ───────────────────── */
    .eyebrow {{
        font: 500 0.7rem 'DM Mono', monospace;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 0.4rem;
    }}

    /* ───────────────────── HEADER BAR ───────────────────── */
    .hero {{
        background: var(--ink);
        border-radius: var(--radius);
        padding: 1.5rem 1.8rem;
        margin-bottom: 1.4rem;
        border: 1px solid var(--ink);
    }}

    .hero h1 {{
        color: var(--paper) !important;
    }}

    .hero-note {{
        color: rgba(245, 246, 243, 0.68);
        font-size: 0.92rem;
        max-width: 760px;
        line-height: 1.55;
        margin-top: 0.5rem;
    }}

    .hero-stamp {{
        background: transparent;
        color: rgba(245, 246, 243, 0.85);
        border: 1px solid rgba(245, 246, 243, 0.28);
        padding: 0.4rem 0.85rem;
        font: 600 0.72rem 'DM Mono', monospace;
        display: inline-block;
        margin-top: 0.9rem;
        letter-spacing: 0.03em;
        border-radius: 4px;
    }}

    /* ───────────────────── KPI METRIC CARDS ───────────────────── */
    .metric {{
        background: var(--card-bg);
        border-radius: var(--radius);
        padding: 0.95rem 1.1rem 1rem;
        border: 1px solid var(--line);
        border-top: 2px solid var(--ink);
    }}

    .metric-label {{
        color: var(--muted);
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 600;
    }}

    .metric-value {{
        font-size: 1.7rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        margin-top: 0.2rem;
        line-height: 1.15;
    }}

    .metric-sub {{
        color: var(--muted);
        font-size: 0.72rem;
        margin-top: 0.25rem;
    }}

    /* ───────────────────── QUEUE HEADER ───────────────────── */
    .queue-head {{
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem;
        margin: 1.6rem 0 0.6rem;
    }}

    .queue-head h2 {{
        margin: 0 !important;
    }}

    .section-note {{
        color: var(--muted);
        font-size: 0.84rem;
        line-height: 1.55;
    }}

    /* ───────────────────── STATUS & ABC BADGES ───────────────────── */
    .status {{
        display: inline-block;
        padding: 0.22rem 0.6rem;
        font: 600 0.68rem 'DM Mono', monospace;
        border-radius: 4px;
        letter-spacing: 0.02em;
        border: 1px solid transparent;
    }}

    .status-critical {{
        background: var(--critical);
        color: #ffffff !important;
        font-weight: 700;
    }}

    .status-high {{
        background: var(--high-bg);
        color: var(--high) !important;
        border-color: var(--high);
    }}

    .status-medium {{
        background: var(--medium-bg);
        color: var(--medium) !important;
        border-color: var(--medium);
    }}

    .status-low {{
        background: var(--low-bg);
        color: var(--low) !important;
        border-color: var(--low);
    }}

    .status-overstock {{
        background: var(--overstock-bg);
        color: var(--overstock) !important;
        border-color: var(--overstock);
    }}

    .status-a {{
        background: var(--low-bg);
        color: var(--low) !important;
        font-weight: 700;
        border-color: var(--low);
    }}

    .status-b {{
        background: var(--medium-bg);
        color: var(--medium) !important;
        border-color: var(--medium);
    }}

    .status-c {{
        background: #EEF0ED;
        color: #5B6560 !important;
        border-color: #C7CDC5;
    }}

    /* ───────────────────── ORDER TIMING BADGES ───────────────────── */
    .timing-badge {{
        display: inline-block;
        padding: 0.2rem 0.5rem;
        font: 700 0.66rem 'DM Mono', monospace;
        border-radius: 4px;
    }}

    .timing-overdue, .timing-critical, .timing-today {{
        background: var(--critical-bg);
        color: var(--critical);
        border: 1px solid var(--critical);
    }}

    .timing-soon, .timing-high {{
        background: var(--high-bg);
        color: var(--high);
        border: 1px solid var(--high);
    }}

    .timing-medium {{
        background: var(--medium-bg);
        color: var(--medium);
        border: 1px solid var(--medium);
    }}

    .timing-healthy, .timing-low {{
        background: var(--low-bg);
        color: var(--low);
        border: 1px solid var(--low);
    }}

    /* ───────────────────── ACTION CALLOUT CARDS ───────────────────── */
    .action-card {{
        background: var(--card-bg);
        border-left: 3px solid var(--ink);
        border-radius: 0 var(--radius) var(--radius) 0;
        border-top: 1px solid var(--line);
        border-right: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
        padding: 1rem 1.2rem;
        margin: 0.9rem 0 1.2rem;
    }}

    .action-card-title {{
        font-weight: 700;
        font-size: 0.92rem;
        margin-bottom: 0.45rem;
    }}

    .action-card p, .action-card li {{
        color: #333B36;
        font-size: 0.87rem;
        line-height: 1.55;
    }}

    .action-card ul {{
        margin: 0.4rem 0 0;
        padding-left: 1.2rem;
    }}

    /* ───────────────────── OVERSTOCK CARD ───────────────────── */
    .overstock-card {{
        background: var(--overstock-bg);
        border-left: 3px solid var(--overstock);
        border-radius: 0 var(--radius) var(--radius) 0;
        border-top: 1px solid var(--line);
        border-right: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
        padding: 1rem 1.2rem;
        margin: 0.9rem 0 1.2rem;
    }}

    .overstock-card-title {{
        color: var(--overstock);
        font-weight: 700;
        font-size: 0.92rem;
        margin-bottom: 0.45rem;
    }}

    /* ───────────────────── EVIDENCE / EXPLANATION BOX ───────────────────── */
    .evidence {{
        background: #EEF0EB;
        border-left: 3px solid var(--ink);
        border-radius: 0 var(--radius) var(--radius) 0;
        padding: 1rem 1.2rem;
        margin: 0.7rem 0 1.1rem;
    }}

    .evidence-title {{
        font-weight: 700;
        margin-bottom: 0.4rem;
        font-size: 0.9rem;
    }}

    .evidence p {{
        color: #333B36;
        font-size: 0.88rem;
        line-height: 1.6;
        margin: 0;
    }}

    /* ───────────────────── SIDEBAR ───────────────────── */
    [data-testid="stSidebar"] {{
        background: #EDF0EA;
        border-right: 1px solid var(--line);
    }}

    [data-testid="stSidebar"] .block-container {{
        padding: 1.8rem 1.3rem;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        border: 1px solid var(--line);
        border-radius: var(--radius);
        background: var(--card-bg);
        margin-bottom: 0.5rem;
    }}

    /* ───────────────────── FOOTER ───────────────────── */
    .footer-note {{
        color: var(--muted);
        font-size: 0.74rem;
        border-top: 1px solid var(--line);
        padding-top: 1.1rem;
        margin-top: 2.5rem;
    }}

    /* ───────────────────── BUTTONS ───────────────────── */
    .stButton button {{
        border-radius: var(--radius) !important;
        border: 1px solid var(--ink) !important;
        background: transparent !important;
        color: var(--ink) !important;
        font-weight: 600 !important;
        transition: var(--transition) !important;
        padding: 0.4rem 0.9rem !important;
    }}

    .stButton button:hover {{
        background: var(--ink) !important;
        color: var(--paper) !important;
        border-color: var(--ink) !important;
    }}

    .stDownloadButton button {{
        border-radius: var(--radius) !important;
        border: 1px solid var(--ink) !important;
        background: var(--ink) !important;
        color: var(--paper) !important;
        font-weight: 600 !important;
        transition: var(--transition) !important;
    }}

    .stDownloadButton button:hover {{
        background: #2C362F !important;
        border-color: #2C362F !important;
    }}

    /* ───────────────────── DATA TABLES ───────────────────── */
    [data-testid="stDataFrame"] {{
        border-radius: var(--radius);
        overflow: hidden;
        border: 1px solid var(--line);
    }}

    /* ───────────────────── PLOTLY CHART CONTAINERS ───────────────────── */
    [data-testid="stPlotlyChart"] {{
        border-radius: var(--radius);
        background: var(--card-bg);
        border: 1px solid var(--line);
        padding: 0.4rem;
    }}

    /* ───────────────────── STREAMLIT METRICS ───────────────────── */
    [data-testid="stMetric"] {{
        background: var(--card-bg);
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 0.75rem 0.95rem;
    }}

    /* ───────────────────── CHAT INTERFACE ───────────────────── */
    [data-testid="stChatMessage"] {{
        border-radius: var(--radius);
        border: 1px solid var(--line);
        margin-bottom: 0.5rem;
    }}

    /* ───────────────────── DIVIDERS ───────────────────── */
    hr {{
        border: none;
        border-top: 1px solid var(--line);
        margin: 1.4rem 0;
    }}
    </style>
    """
