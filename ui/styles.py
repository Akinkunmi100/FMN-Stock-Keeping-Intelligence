"""
ui/styles.py — Global CSS Design System & Visual Language
=========================================================
Centralized styling for the Supply Chain Control Room.
Implements modern typography (Manrope + DM Mono), color-coded status badges,
glassmorphism metric cards, animated hover transitions, gradient hero banners,
and responsive operational alert callouts.

Design Philosophy:
- Clean, data-dense layouts optimized for operations leadership
- Color-coded severity system (Red → Amber → Yellow → Green → Blue)
- High contrast for warehouse floor readability
- Smooth micro-animations for interactive engagement
"""

from __future__ import annotations

from config import COLORS


def get_application_css() -> str:
    """Return the complete CSS stylesheet string injected into Streamlit."""
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

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
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.04);
        --shadow-lg: 0 10px 20px rgba(0,0,0,0.06), 0 4px 8px rgba(0,0,0,0.04);
        --radius: 8px;
        --transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
    }}

    /* ───────────────────── GLOBAL BASE ───────────────────── */
    .stApp {{
        background: linear-gradient(180deg, #F0F2EC 0%, var(--paper) 100%);
        color: var(--ink);
    }}

    .block-container {{
        padding: 2rem 3.5rem 4rem;
        max-width: 1560px;
    }}

    html, body, [class*="css"] {{
        font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        -webkit-font-smoothing: antialiased;
    }}

    /* ───────────────────── TYPOGRAPHY ───────────────────── */
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

    h3 {{
        font-size: 1.15rem !important;
        margin-bottom: 0.3rem !important;
    }}

    .mono, code {{
        font-family: 'DM Mono', 'Fira Code', monospace;
    }}

    /* ───────────────────── EYEBROW LABELS ───────────────────── */
    .eyebrow {{
        font: 500 0.72rem 'DM Mono', monospace;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #6b776f;
        margin-bottom: 0.5rem;
    }}

    /* ───────────────────── HERO BANNER ───────────────────── */
    .hero {{
        background: linear-gradient(135deg, #17211F 0%, #1E3A2F 50%, #1B4F48 100%);
        border-radius: var(--radius);
        padding: 2.2rem 2.6rem 2rem;
        margin-bottom: 1.8rem;
        box-shadow: var(--shadow-lg);
        position: relative;
        overflow: hidden;
    }}

    .hero::before {{
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(199, 238, 92, 0.08) 0%, transparent 70%);
        pointer-events: none;
    }}

    .hero h1 {{
        color: #F6F7F3 !important;
    }}

    .hero-note {{
        color: rgba(246, 247, 243, 0.70);
        font-size: 1.02rem;
        max-width: 760px;
        line-height: 1.6;
        margin-top: 0.8rem;
    }}

    .hero-stamp {{
        background: rgba(199, 238, 92, 0.15);
        color: {COLORS['accent_lime']};
        border: 1px solid rgba(199, 238, 92, 0.25);
        padding: 0.55rem 1.1rem;
        font: 600 0.74rem 'DM Mono', monospace;
        display: inline-block;
        margin-top: 1.1rem;
        letter-spacing: 0.05em;
        border-radius: 4px;
    }}

    /* ───────────────────── KPI METRIC CARDS ───────────────────── */
    .metric {{
        background: var(--card-bg);
        border-radius: var(--radius);
        padding: 1.1rem 1.2rem 1.2rem;
        border: 1px solid var(--line);
        border-top: 3px solid var(--ink);
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
    }}

    .metric:hover {{
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }}

    .metric-label {{
        color: var(--muted);
        font-size: 0.72rem;
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
        font-size: 0.74rem;
        margin-top: 0.3rem;
    }}

    /* ───────────────────── QUEUE HEADER ───────────────────── */
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

    /* ───────────────────── STATUS & ABC BADGES ───────────────────── */
    .status {{
        display: inline-block;
        padding: 0.25rem 0.65rem;
        font: 600 0.70rem 'DM Mono', monospace;
        border-radius: 4px;
        letter-spacing: 0.04em;
        transition: var(--transition);
    }}

    .status-critical {{
        background: var(--critical);
        color: #ffffff !important;
        font-weight: 700;
        box-shadow: 0 0 0 1px var(--critical);
    }}

    .status-high {{
        background: #FAD7A0;
        color: #7E5109 !important;
        box-shadow: 0 0 0 1px var(--high);
    }}

    .status-medium {{
        background: #FCF3CF;
        color: #7D6608 !important;
        box-shadow: 0 0 0 1px #D4AC0D;
    }}

    .status-low {{
        background: #D4EFDF;
        color: #145A32 !important;
        box-shadow: 0 0 0 1px var(--low);
    }}

    .status-overstock {{
        background: #D6EAF8;
        color: #1B4F72 !important;
        box-shadow: 0 0 0 1px var(--overstock);
    }}

    .status-a {{
        background: #D4EFDF;
        color: #145A32 !important;
        font-weight: 700;
        box-shadow: 0 0 0 1px #1E8449;
    }}

    .status-b {{
        background: #FCF3CF;
        color: #7D6608 !important;
        box-shadow: 0 0 0 1px #D4AC0D;
    }}

    .status-c {{
        background: #EAEDED;
        color: #515A5A !important;
        box-shadow: 0 0 0 1px #7F8C8D;
    }}

    /* ───────────────────── ORDER TIMING BADGES ───────────────────── */
    .timing-badge {{
        display: inline-block;
        padding: 0.22rem 0.55rem;
        font: 700 0.68rem 'DM Mono', monospace;
        border-radius: 4px;
        transition: var(--transition);
    }}

    .timing-overdue, .timing-critical {{
        background: #FDEDEC;
        color: #C0392B;
        border: 1px solid #E74C3C;
        animation: pulse-red 2s ease-in-out infinite;
    }}

    @keyframes pulse-red {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.75; }}
    }}

    .timing-today {{
        background: #FDEDEC;
        color: #C0392B;
        border: 1px solid #E74C3C;
        font-weight: 800;
    }}

    .timing-soon, .timing-high {{
        background: #FEF5E7;
        color: #B9770E;
        border: 1px solid #E67E22;
    }}

    .timing-medium {{
        background: #FCF3CF;
        color: #7D6608;
        border: 1px solid #D4AC0D;
    }}

    .timing-healthy, .timing-low {{
        background: #EAFAF1;
        color: #1E8449;
        border: 1px solid #27AE60;
    }}

    /* ───────────────────── ACTION CALLOUT CARDS ───────────────────── */
    .action-card {{
        background: #ffffff;
        border-left: 4.5px solid var(--ink);
        border-radius: 0 var(--radius) var(--radius) 0;
        border-top: 1px solid var(--line);
        border-right: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
        padding: 1.1rem 1.3rem;
        margin: 1rem 0 1.4rem;
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
    }}

    .action-card:hover {{
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
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

    /* ───────────────────── OVERSTOCK CARD ───────────────────── */
    .overstock-card {{
        background: linear-gradient(135deg, #EBF5FB 0%, #D6EAF8 100%);
        border-left: 4.5px solid var(--overstock);
        border-radius: 0 var(--radius) var(--radius) 0;
        border-top: 1px solid #AED6F1;
        border-right: 1px solid #AED6F1;
        border-bottom: 1px solid #AED6F1;
        padding: 1.1rem 1.3rem;
        margin: 1rem 0 1.4rem;
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
    }}

    .overstock-card:hover {{
        box-shadow: var(--shadow-md);
    }}

    .overstock-card-title {{
        color: #1B4F72;
        font-weight: 800;
        font-size: 0.96rem;
        margin-bottom: 0.5rem;
    }}

    /* ───────────────────── EVIDENCE / EXPLANATION BOX ───────────────────── */
    .evidence {{
        background: linear-gradient(135deg, #EEF2EA 0%, #E4EAE0 100%);
        border-left: 4.5px solid var(--ink);
        border-radius: 0 var(--radius) var(--radius) 0;
        padding: 1.1rem 1.3rem;
        margin: 0.8rem 0 1.2rem;
        box-shadow: var(--shadow-sm);
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

    /* ───────────────────── SIDEBAR ───────────────────── */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #E3EAE0 0%, #E9EEE6 100%);
        border-right: 1px solid var(--line);
    }}

    [data-testid="stSidebar"] .block-container {{
        padding: 2rem 1.4rem;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        border: 1px solid var(--line);
        border-radius: var(--radius);
        background: rgba(255,255,255,0.6);
        backdrop-filter: blur(4px);
        margin-bottom: 0.5rem;
    }}

    /* ───────────────────── FOOTER ───────────────────── */
    .footer-note {{
        color: var(--muted);
        font-size: 0.76rem;
        border-top: 1px solid var(--line);
        padding-top: 1.2rem;
        margin-top: 3rem;
        text-align: center;
    }}

    /* ───────────────────── BUTTONS ───────────────────── */
    .stButton button {{
        border-radius: var(--radius) !important;
        border: 1px solid var(--ink) !important;
        background: transparent !important;
        color: var(--ink) !important;
        font-weight: 700 !important;
        transition: var(--transition) !important;
        padding: 0.45rem 1rem !important;
    }}

    .stButton button:hover {{
        background: var(--ink) !important;
        color: var(--paper) !important;
        border-color: var(--ink) !important;
        transform: translateY(-1px);
        box-shadow: var(--shadow-md);
    }}

    .stDownloadButton button {{
        border-radius: var(--radius) !important;
        border: 1px solid var(--ink) !important;
        background: var(--ink) !important;
        color: var(--paper) !important;
        font-weight: 700 !important;
        transition: var(--transition) !important;
    }}

    .stDownloadButton button:hover {{
        background: #2C3E2E !important;
        color: var(--paper) !important;
        transform: translateY(-1px);
        box-shadow: var(--shadow-md);
    }}

    /* ───────────────────── DATA TABLES ───────────────────── */
    [data-testid="stDataFrame"] {{
        border-radius: var(--radius);
        overflow: hidden;
        box-shadow: var(--shadow-sm);
    }}

    /* ───────────────────── PLOTLY CHART CONTAINERS ───────────────────── */
    [data-testid="stPlotlyChart"] {{
        border-radius: var(--radius);
        background: var(--card-bg);
        border: 1px solid var(--line);
        padding: 0.4rem;
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
    }}

    [data-testid="stPlotlyChart"]:hover {{
        box-shadow: var(--shadow-md);
    }}

    /* ───────────────────── STREAMLIT METRICS ───────────────────── */
    [data-testid="stMetric"] {{
        background: var(--card-bg);
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 0.8rem 1rem;
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
    }}

    [data-testid="stMetric"]:hover {{
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }}

    /* ───────────────────── CHAT INTERFACE ───────────────────── */
    [data-testid="stChatMessage"] {{
        border-radius: var(--radius);
        border: 1px solid var(--line);
        margin-bottom: 0.5rem;
        box-shadow: var(--shadow-sm);
    }}

    /* ───────────────────── DIVIDERS ───────────────────── */
    hr {{
        border: none;
        border-top: 1px solid var(--line);
        margin: 1.5rem 0;
    }}

    /* ───────────────────── ANIMATIONS ───────────────────── */
    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(12px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .metric, .action-card, .overstock-card, .evidence {{
        animation: fadeInUp 0.4s ease-out;
    }}
    </style>
    """
