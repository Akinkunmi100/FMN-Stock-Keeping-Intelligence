"""Show the historical check for the stockout-warning rule."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ui.charts import build_backtest_heatmap


def render_backtest_view(meta: dict[str, Any]) -> None:
    """Render the historical check for the warning rule."""
    bt = meta.get("backtest", {})
    if not bt:
        st.warning("Backtest results unavailable.")
        return

    date_min = meta.get("date_min", "")
    date_max = meta.get("date_max", "")
    history_days = "an unknown span of"
    try:
        history_days = str((date_max - date_min).days + 1)
    except TypeError:
        pass

    st.markdown(
        "<div class='queue-head'>"
        "<h2>Model check</h2>"
        f"<div class='section-note'>{bt['total_evaluations']:,} historical checkpoints tested</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"The app re-ran the warning rule across the {history_days}-day history ({date_min} to {date_max}). "
        "At each point it used only information that would have been available the day before, then checked "
        "whether the SKU reached zero stock within its supplier lead time."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. METRIC CARDS
    # ─────────────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Stockouts caught early</div>"
            f"<div class='metric-value' style='color: #27AE60;'>{bt['recall']:.1%}</div>"
            f"<div class='metric-sub'>stockouts caught in advance</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Alerts followed by stockout</div>"
            f"<div class='metric-value'>{bt['precision']:.1%}</div>"
            f"<div class='metric-sub'>of all warnings raised</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Warning balance</div>"
            f"<div class='metric-value'>{bt['f1']:.1%}</div>"
            f"<div class='metric-sub'>one view of both measures</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Historical checks</div>"
            f"<div class='metric-value'>{bt['total_evaluations']:,}</div>"
            f"<div class='metric-sub'>across evaluated SKUs</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CONFUSION MATRIX VISUALIZATION
    # ─────────────────────────────────────────────────────────────────────────
    c_heat, c_tbl = st.columns([1.5, 1])

    with c_heat:
        st.plotly_chart(
            build_backtest_heatmap(bt["tp"], bt["fp"], bt["fn"], bt["tn"]),
            width="stretch",
        )

    with c_tbl:
        st.markdown("### What these results mean")
        total_eval = bt['total_evaluations'] if bt['total_evaluations'] > 0 else 1
        summary_df = pd.DataFrame({
            "Result": [
                "Stockouts caught",
                "Warnings without stockout",
                "Stockouts missed",
                "Healthy days left unflagged",
                "Overall accuracy",
                "Review rate for healthy days",
            ],
            "Value": [
                f"{bt['tp']:,} ({bt['tp']/total_eval:.1%})",
                f"{bt['fp']:,} ({bt['fp']/total_eval:.1%})",
                f"{bt['fn']:,} ({bt['fn']/total_eval:.1%})",
                f"{bt['tn']:,} ({bt['tn']/total_eval:.1%})",
                f"{bt['accuracy']:.1%}",
                f"{bt['false_alarm_rate']:.1%}",
            ],
            "What it means": [
                "The warning came before stock reached zero",
                "A review was requested, but stock did not reach zero",
                "Stock reached zero without an earlier warning",
                "The app correctly left healthy stock alone",
                "Share of historical checks classified correctly",
                "Share of healthy days that still received a warning",
            ],
        })
        st.dataframe(summary_df, width="stretch", hide_index=True)

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 3. OPERATIONAL INTERPRETATION
    # ─────────────────────────────────────────────────────────────────────────
    dow_multipliers = meta.get("dow_multipliers", {})
    dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    seasonality_note = ""
    if dow_multipliers:
        peak_day_idx = max(dow_multipliers, key=lambda d: dow_multipliers[d])
        peak_pct = (dow_multipliers[peak_day_idx] - 1.0) * 100
        if abs(peak_pct) >= 1.0:
            seasonality_note = (
                f"Demand is not flat across the week — {dow_names[peak_day_idx]} runs "
                f"{peak_pct:+.1f}% relative to the daily average in this dataset, computed from "
                f"the day-of-week multipliers actually used in the forward lead-time projection, "
                f"not a fixed assumption."
            )

    interpretation_paragraph = (
        f"• <b>Early warnings ({bt['recall']:.1%}) versus confirmed warnings ({bt['precision']:.1%}):</b> the current rule catches more potential "
        f"stockouts by accepting more review alerts. That balance is a starting policy, not a measured cost optimum, because "
        f"the dataset does not include the financial cost of a stockout or an unnecessary order."
    )
    if seasonality_note:
        interpretation_paragraph += f"<br><br>• {seasonality_note}"

    st.markdown(
        f"<div class='evidence'>"
        f"<div class='evidence-title'>How to read these results</div>"
        f"<p>{interpretation_paragraph}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )
