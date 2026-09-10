"""
ui/hero.py — Executive Hero Banner & KPI Summary Metrics
========================================================
Renders the top-level command banner and high-visibility KPI cards.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def render_hero_banner(meta: dict[str, Any], scores: pd.DataFrame) -> None:
    """Render the top visual banner summarizing system status."""
    flagged = scores[scores["urgency"] > 0]
    critical = scores[scores["severity"] == "Critical"]
    class_a_flagged = scores[(scores["abc_class"] == "A") & (scores["urgency"] > 0)]
    date_str = str(meta.get("date_max", ""))

    st.markdown(
        f"<div class='hero'>"
        f"<div class='eyebrow'>SUPPLY CHAIN CONTROL ROOM · {date_str}</div>"
        f"<h1>Know what needs<br>action next.</h1>"
        f"<div class='hero-note'>Ranked early warning signals combining seasonality-adjusted demand velocity, stochastic lead-time variance, exact order-by deadlines, and Recommended Order Quantities (ROQ).</div>"
        f"<div class='hero-stamp'>{len(flagged)} OF {len(scores)} SKUS FLAGGED · {len(critical)} CRITICAL · {len(class_a_flagged)} CLASS-A AT RISK</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_kpi_cards(scores: pd.DataFrame) -> None:
    """Render top 5 high-level operational KPI cards."""
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
            f"<div class='metric'>"
            f"<div class='metric-label'>Critical Severity</div>"
            f"<div class='metric-value' style='color: #E74C3C;'>{len(critical)}</div>"
            f"<div class='metric-sub'>risk score ≥ 75</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Order Soon</div>"
            f"<div class='metric-value'>{len(order_soon)}</div>"
            f"<div class='metric-sub'>coverage ≤ lead time</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Class A at Risk</div>"
            f"<div class='metric-value' style='color: #1E8449;'>{len(class_a_flagged)}</div>"
            f"<div class='metric-sub'>top 70% volume drivers</div>"
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
