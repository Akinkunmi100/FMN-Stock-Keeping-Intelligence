"""Render the portfolio summary shown above each workspace."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config import ABC_THRESHOLDS, COLORS


def render_hero_banner(meta: dict[str, Any], scores: pd.DataFrame) -> None:
    """Show the portfolio status and the main counts a reviewer needs first."""
    flagged = scores[scores["urgency"] > 0]
    critical = scores[scores["severity"] == "Critical"]
    class_a_flagged = scores[(scores["abc_class"] == "A") & (scores["urgency"] > 0)]
    date_str = str(meta.get("date_max", ""))

    st.markdown(
        f"<div class='hero'>"
        f"<div class='eyebrow' style='color: rgba(245,246,243,0.55);'>INVENTORY REVIEW · AS OF {date_str}</div>"
        f"<h1>Inventory risk overview</h1>"
        f"<div class='hero-note'>A ranked review list based on recent demand, current stock, supplier lead time, "
        f"and the amount of stock needed to restore a safe buffer.</div>"
        f"<div class='hero-stamp'>"
        f"{len(flagged)} OF {len(scores)} SKUS NEED REVIEW &nbsp;·&nbsp; "
        f"{len(critical)} CRITICAL &nbsp;·&nbsp; "
        f"{len(class_a_flagged)} HIGH-VOLUME ITEMS AT RISK"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_kpi_cards(scores: pd.DataFrame) -> None:
    """Show the key counts for the current queue or filter selection."""
    flagged = scores[scores["urgency"] > 0]
    critical = scores[scores["severity"] == "Critical"]
    order_soon = scores[scores["bucket"] == "Order soon"]
    class_a_flagged = scores[(scores["abc_class"] == "A") & (scores["urgency"] > 0)]
    total_roq = scores["roq"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Needs review</div>"
            f"<div class='metric-value'>{len(flagged)}</div>"
            f"<div class='metric-sub'>of {len(scores)} tracked SKUs</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='metric' style='border-top-color: {COLORS['critical']};'>"
            f"<div class='metric-label'>Critical</div>"
            f"<div class='metric-value' style='color: {COLORS['critical']};'>{len(critical)}</div>"
            f"<div class='metric-sub'>risk score 75 or higher</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='metric' style='border-top-color: {COLORS['high']};'>"
            f"<div class='metric-label'>Order soon</div>"
            f"<div class='metric-value' style='color: {COLORS['high']};'>{len(order_soon)}</div>"
            f"<div class='metric-sub'>stock may not last to delivery</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"<div class='metric' style='border-top-color: {COLORS['abc_a']};'>"
            f"<div class='metric-label'>High-volume items at risk</div>"
            f"<div class='metric-value' style='color: {COLORS['abc_a']};'>{len(class_a_flagged)}</div>"
            f"<div class='metric-sub'>top {ABC_THRESHOLDS['A']:.0%} of unit volume</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Suggested order units</div>"
            f"<div class='metric-value'>{total_roq:,.0f}</div>"
            f"<div class='metric-sub'>for SKUs needing replenishment</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
