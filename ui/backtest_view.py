"""
ui/backtest_view.py — Historical Backtesting, Validation & Empirical Performance
================================================================================
Renders the model validation tab:
- Walk-forward historical backtest metrics
- Interactive Plotly confusion matrix heatmap
- Operational analysis of recall vs. precision trade-offs in manufacturing supply chains
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ui.charts import build_backtest_heatmap


def render_backtest_view(meta: dict[str, Any]) -> None:
    """Render the model validation & backtest workspace tab."""
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
        "<h2>Model Validation & Historical Backtest</h2>"
        f"<div class='section-note'>Empirical validation across {bt['total_evaluations']:,} historical checkpoints</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"A rolling-origin walk-forward backtest was executed over the {history_days}-day history ({date_min} to {date_max}). "
        "At each date t, the model scored SKUs using strictly information available at t-1 (preventing data leakage) "
        "and evaluated whether an 'Order Soon' alert was triggered ahead of an actual physical stockout occurring within the supplier lead-time horizon."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. METRIC CARDS
    # ─────────────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Historical Recall</div>"
            f"<div class='metric-value' style='color: #27AE60;'>{bt['recall']:.1%}</div>"
            f"<div class='metric-sub'>stockouts caught in advance</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Precision</div>"
            f"<div class='metric-value'>{bt['precision']:.1%}</div>"
            f"<div class='metric-sub'>actionable risk alerts</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>F1-Score</div>"
            f"<div class='metric-value'>{bt['f1']:.1%}</div>"
            f"<div class='metric-sub'>harmonic balance</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"<div class='metric'>"
            f"<div class='metric-label'>Total Checkpoints</div>"
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
            use_container_width=True,
        )

    with c_tbl:
        st.markdown("### Empirical Performance Breakdown")
        total_eval = bt['total_evaluations'] if bt['total_evaluations'] > 0 else 1
        summary_df = pd.DataFrame({
            "Classification Category": [
                "True Positives (TP)",
                "False Alarms (FP)",
                "Missed Crises (FN)",
                "True Negatives (TN)",
                "Accuracy",
                "False Alarm Rate",
            ],
            "Value": [
                f"{bt['tp']:,} ({bt['tp']/total_eval:.1%})",
                f"{bt['fp']:,} ({bt['fp']/total_eval:.1%})",
                f"{bt['fn']:,} ({bt['fn']/total_eval:.1%})",
                f"{bt['tn']:,} ({bt['tn']/total_eval:.1%})",
                f"{bt['accuracy']:.1%}",
                f"{bt['false_alarm_rate']:.1%}",
            ],
            "Operational Meaning": [
                "Crisis successfully caught before stockout",
                "Safety review triggered; stock did not reach 0",
                "Stockout occurred without advance warning",
                "Healthy stock correctly left unflagged",
                "Overall correct classification rate",
                "Rate of review among healthy inventory days",
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
        f"• <b>Recall ({bt['recall']:.1%}) vs. precision ({bt['precision']:.1%}):</b> the model is deliberately tuned toward "
        f"catching real stockouts over minimizing false alarms — a missed stockout halts production, while a false alarm "
        f"only costs a few minutes of review. That tradeoff is a stated design decision (see docs/DECISIONS.md), not a "
        f"claim about a specific cost ratio this dataset can't measure."
    )
    if seasonality_note:
        interpretation_paragraph += f"<br><br>• {seasonality_note}"

    st.markdown(
        f"<div class='evidence'>"
        f"<div class='evidence-title'>Reading These Results</div>"
        f"<p>{interpretation_paragraph}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )
