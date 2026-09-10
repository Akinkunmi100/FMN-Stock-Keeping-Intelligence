"""
ui/hero.py — Status Header & KPI Summary Metrics
=================================================
Renders the top-level status bar and high-level KPI cards with color-coded
severity indicators.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config import ABC_THRESHOLDS, COLORS


def render_hero_banner(meta: dict[str, Any], scores: pd.DataFrame) -> None:
    """
    Render the top status bar summarizing portfolio state at a glance:
    total flagged SKU count vs. portfolio size, critical severity count,
    and Class-A-at-risk count.
    """
    flagged = scores[scores["urgency"] > 0]
    critical = scores[scores["severity"] == "Critical"]
    class_a_flagged = scores[(scores["abc_class"] == "A") & (scores["urgency"] > 0)]
    date_str = str(meta.get("date_max", ""))

    st.markdown(
        f"<div class='hero'>"
        f"<div class='eyebrow' style='color: rgba(245,246,243,0.55);'>SUPPLY CHAIN CONTROL ROOM · AS OF {date_str}</div>"
        f"<h1>Portfolio Early-Warning Summary</h1>"
        f"<div class='hero-note'>Ranked stockout and overstock risk combining seasonality-adjusted demand velocity, "
        f"stochastic lead-time variance, exact order-by deadlines, and recommended order quantities.</div>"
        f"<div class='hero-stamp'>"
        f"{len(flagged)} OF {len(scores)} SKUS FLAGGED &nbsp;·&nbsp; "
        f"{len(critical)} CRITICAL &nbsp;·&nbsp; "
        f"{len(class_a_flagged)} CLASS-A AT RISK"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_kpi_cards(scores: pd.DataFrame) -> None:
    """
    Render top 5 high-level operational KPI cards.

    Each card has a color-coded border-top that matches its severity context,
    providing instant visual scanning for operations teams.
    """
    flagged = scores[scores["urgency"] > 0]
    critical = scores[scores["severity"] == "Critical"]
    order_soon = scores[scores["bucket"] == "Order soon"]
    class_a_flagged = scores[(scores["abc_class"] == "A") & (scores["urgency"] > 0)]
    total_roq = scores["roq"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Flagged Now</div>"
            f"<div class='metric-value'>{len(flagged)}</div>"
            f"<div class='metric-sub'>of {len(scores)} tracked SKUs</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='metric' style='border-top-color: {COLORS['critical']};'>"
            f"<div class='metric-label'>Critical Severity</div>"
            f"<div class='metric-value' style='color: {COLORS['critical']};'>{len(critical)}</div>"
            f"<div class='metric-sub'>risk score ≥ 75</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='metric' style='border-top-color: {COLORS['high']};'>"
            f"<div class='metric-label'>Order Soon</div>"
            f"<div class='metric-value' style='color: {COLORS['high']};'>{len(order_soon)}</div>"
            f"<div class='metric-sub'>coverage ≤ lead time</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"<div class='metric' style='border-top-color: {COLORS['abc_a']};'>"
            f"<div class='metric-label'>Class A at Risk</div>"
            f"<div class='metric-value' style='color: {COLORS['abc_a']};'>{len(class_a_flagged)}</div>"
            f"<div class='metric-sub'>top {ABC_THRESHOLDS['A']:.0%} volume drivers</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Total Reorder Units</div>"
            f"<div class='metric-value'>{total_roq:,.0f}</div>"
            f"<div class='metric-sub'>immediate procurement need</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
