"""
ui/sku_detail.py — SKU Deep-Dive, Interactive Charts & What-If Simulator
========================================================================
Provides granular visibility into any individual SKU:
- Time-series inventory trajectory vs. ROP and Safety Stock
- Demand velocity vs. replenishment delivery spikes
- Speedometer composite risk gauge
- Interactive stress-test simulator (demand surges & vendor delivery delays)
- Free-tier Groq LLM diagnostic explanation (strictly grounded)
- Full parameter evidence audit table
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from ai.grounding import build_sku_facts, explain_sku
from ai.llm_client import LLMResult
from config import ABC_THRESHOLDS, COLORS
from ui.charts import (
    build_demand_and_receipts_chart,
    build_risk_gauge,
    build_stock_trajectory_chart,
)


def render_sku_detail(raw: pd.DataFrame, scores: pd.DataFrame) -> None:
    """Render the comprehensive SKU deep-dive tab."""
    selected_sku = st.selectbox(
        "Select a SKU for Deep-Dive Analysis",
        scores["sku_id"].tolist(),
        index=0,
    )
    row = scores[scores["sku_id"] == selected_sku].iloc[0]
    sku_history = raw[raw["sku_id"] == selected_sku].sort_values("date")

    # ─────────────────────────────────────────────────────────────────────────
    # 1. HEADER & BADGES
    # ─────────────────────────────────────────────────────────────────────────
    status_badge_class = f"status-{row['severity'].lower()}"
    abc_badge_class = f"status-{row['abc_class'].lower()}"
    timing_class = f"timing-{row['timing_color']}"

    st.markdown(
        f"<div class='queue-head'>"
        f"<h2>{row['sku_id']} · {row['category']}</h2>"
        f"<div>"
        f"<span class='status {abc_badge_class}'>CLASS {row['abc_class']}</span> "
        f"<span class='status {status_badge_class}'>{row['bucket'].upper()} · {row['severity'].upper()}</span> "
        f"<span class='timing-badge {timing_class}'>{row['timing_urgency_badge']}</span>"
        f"</div>"
        f"</div>"
        f"<div class='section-note'>Methodology: {row['method']} · {row['history_days']} days recorded ({row['observations']} uncensored demand observations)</div>",
        unsafe_allow_html=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. KEY METRICS ROW
    # ─────────────────────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Closing Stock", f"{row['stock']:,.0f}", "units on hand")
    m2.metric("Days Coverage", f"{row['days_coverage']:.1f} d", f"lead time: {row['lead_time']:.0f} d")
    m3.metric("Reorder Point", f"{row['reorder_point']:,.0f}", f"safety stock: {row['safety_stock']:,.0f}")
    m4.metric("Order Deadline", str(row["order_by_date"]), row["timing_urgency_badge"])
    m5.metric("Recommended Order", f"{row['roq']:,.0f} u", "target replenishment" if row["roq"] > 0 else "adequate")
    m6.metric("Risk Score", f"{row['risk_score']:.0f}/100", f"{row['severity']} priority")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. ACTION CALLOUT PANEL
    # ─────────────────────────────────────────────────────────────────────────
    border_color = (
        COLORS["critical"] if row["severity"] == "Critical" else
        COLORS["high"] if row["severity"] == "High" else
        COLORS["overstock"] if row["bucket"] == "Overstock risk" else
        COLORS["low"]
    )

    if row["urgency"] >= 2 and row["bucket"] != "Overstock risk":
        action_html = f"""
        <div class='action-card' style='border-left-color: {border_color};'>
            <div class='action-card-title' style='color: {border_color};'>
                RECOMMENDED PROCUREMENT ACTION: {row['timing_urgency_badge']}
            </div>
            <p>
                • <b>Action:</b> Release Purchase Order for <b>{row['roq']:,.0f} units</b> by <b>{row['order_by_date']}</b>.<br>
                • <b>Lead Time:</b> Supplier delivery takes {row['lead_time']:.0f} days (variance: ±{row['lead_time_std']:.1f}d).<br>
                • <b>Stockout Horizon:</b> Projected to deplete completely by <b>{row['stockout_date']}</b> ({row['days_coverage']:.1f} days remaining).<br>
                • <b>Impact:</b> Class {row['abc_class']} item — failure to place order will cause factory stockouts.
            </p>
        </div>
        """
    elif row["bucket"] == "Overstock risk":
        action_html = f"""
        <div class='overstock-card'>
            <div class='overstock-card-title'>RECOMMENDED OVERSTOCK ACTION: EXCESS INVENTORY DETECTED</div>
            <p>
                • <b>Surplus Units:</b> {row['excess_units']:,.0f} units over target Order-Up-To level.<br>
                • <b>Coverage:</b> {row['days_coverage']:.1f} days of supply (+{row['days_over_target']:.1f} days over {row['coverage_limit']:.0f}-day target).<br>
                • <b>Recommended Action:</b> Freeze subsequent purchase orders and review regional inter-warehouse transfer options.
            </p>
        </div>
        """
    else:
        action_html = f"""
        <div class='action-card' style='border-left-color: {COLORS["low"]};'>
            <div class='action-card-title' style='color: {COLORS["low"]};'>INVENTORY POSITION HEALTHY</div>
            <p>
                Current stock ({row['stock']:,.0f} units) provides {row['days_coverage']:.1f} days of coverage, safely above the {row['lead_time']:.0f}-day replenishment cycle. No purchase order required at this time.
            </p>
        </div>
        """
    st.markdown(action_html, unsafe_allow_html=True)

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 4. INTERACTIVE PLOTLY CHARTS
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### Visual Time-Series Analytics")
    col_c1, col_c2, col_c3 = st.columns([1.6, 1.6, 1])

    with col_c1:
        st.plotly_chart(
            build_stock_trajectory_chart(sku_history, row["reorder_point"], row["safety_stock"]),
            use_container_width=True,
        )
    with col_c2:
        st.plotly_chart(
            build_demand_and_receipts_chart(sku_history),
            use_container_width=True,
        )
    with col_c3:
        st.plotly_chart(
            build_risk_gauge(row["risk_score"], row["severity"]),
            use_container_width=True,
        )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 5. WHAT-IF SENSITIVITY SIMULATOR
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### What-If Sensitivity Simulator")
    st.caption("Simulate unexpected consumer demand surges and supplier delivery delays in real time.")

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        sim_demand_surge = st.slider("Simulated Demand Surge (%)", min_value=-50, max_value=100, value=0, step=5)
    with sim_col2:
        sim_lead_delay = st.slider("Simulated Supplier Delivery Delay (Days)", min_value=0, max_value=14, value=0, step=1)

    # Simulator calculations
    sim_demand = row["daily_demand"] * (1.0 + sim_demand_surge / 100.0)
    sim_lead = row["lead_time"] + sim_lead_delay
    sim_ss = row["safety_stock"] * np.sqrt(sim_lead / max(row["lead_time"], 1.0)) * (1.0 + sim_demand_surge / 200.0)
    sim_rop = (sim_demand * sim_lead) + sim_ss
    sim_coverage = row["stock"] / sim_demand if sim_demand > 0 else np.inf
    sim_cycle = max(7.0 * sim_demand, sim_demand * np.sqrt(2 * max(sim_lead, 1.0)))
    sim_roq = max(0.0, round((sim_demand * sim_lead + sim_ss + sim_cycle) - row["stock"], 0))

    sim_df = pd.DataFrame({
        "Parameter": ["Daily Demand", "Lead Time", "Safety Stock", "Reorder Point", "Days Coverage", "Recommended Order (ROQ)"],
        "Baseline": [
            f"{row['daily_demand']:,.1f} u/d",
            f"{row['lead_time']:.0f} days",
            f"{row['safety_stock']:,.0f} units",
            f"{row['reorder_point']:,.0f} units",
            f"{row['days_coverage']:.1f} days",
            f"{row['roq']:,.0f} units",
        ],
        "Simulated": [
            f"{sim_demand:,.1f} u/d",
            f"{sim_lead:.0f} days",
            f"{sim_ss:,.0f} units",
            f"{sim_rop:,.0f} units",
            f"{sim_coverage:.1f} days",
            f"{sim_roq:,.0f} units",
        ],
        "Delta / Impact": [
            f"{sim_demand - row['daily_demand']:+,.1f} u/d",
            f"{sim_lead_delay:+d} days",
            f"{sim_ss - row['safety_stock']:+,.0f} units",
            f"{sim_rop - row['reorder_point']:+,.0f} units",
            f"{sim_coverage - row['days_coverage']:+.1f} days",
            f"{sim_roq - row['roq']:+,.0f} units",
        ],
    })
    st.dataframe(sim_df, width="stretch", hide_index=True)

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 6. AI GROUNDED EXPLANATION (FREE GROQ / LOCAL ENGINE)
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### Operational Diagnosis")
    st.caption("Strictly grounded in empirical calculation evidence — a live model call when available, otherwise a deterministic local explanation.")

    if st.button("Generate / Refresh Diagnosis", type="primary") or "explanation" not in st.session_state or st.session_state.get("explanation_sku") != selected_sku:
        with st.spinner("Compiling facts and generating diagnostic report…"):
            st.session_state.explanation = explain_sku(row)
            st.session_state.explanation_sku = selected_sku

    if "explanation" in st.session_state:
        llm_res: LLMResult = st.session_state.explanation
        if llm_res.warning:
            st.info(llm_res.warning)

        source_label = f"Live Model Explanation ({llm_res.model})" if llm_res.live and llm_res.model else "Local Grounded Deterministic Explanation"
        st.markdown(
            f"<div class='evidence'>"
            f"<div class='evidence-title'>{source_label}</div>"
            f"<p>{llm_res.text}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 7. DETAILED EVIDENCE AUDIT TABLE
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### Complete Parameter Evidence Table")
    facts = build_sku_facts(row)
    abc_tier_label = {
        "A": f"Top {ABC_THRESHOLDS['A']:.0%} Volume",
        "B": "Moderate Volume",
        "C": "Tail Item",
    }.get(facts["abc_class"], "")
    evidence_table = pd.DataFrame({
        "Parameter": [
            "Current Closing Stock",
            "Daily Sales Velocity (Blended)",
            "Forward Lead-Time Demand (Seasonally Modulated)",
            "Day-of-Week Multiplier Factor",
            "Days of Coverage",
            "Supplier Lead Time",
            "Lead Time Std Dev (Stochastic Variability)",
            "Seasonal Reorder Point (ROP)",
            "Stochastic Safety Stock",
            "Target Order-Up-To Level (S)",
            "Recommended Order Quantity (ROQ)",
            "Projected Stockout Date",
            "Order-By Replenishment Deadline",
            "Order Urgency Status",
            "Excess Units (Overstock Diagnostic)",
            "Days Over Coverage Target",
            "ABC Pareto Classification",
            "Coefficient of Variation (CV)",
            "Demand Acceleration Trend",
            "Composite Risk Score",
        ],
        "Value": [
            f"{facts['closing_stock_units']:,.1f} units",
            f"{facts['daily_demand_units']:,.1f} units/day",
            f"{facts['forward_lead_time_demand']:,.1f} units over {facts['lead_time_days']:.0f}d",
            f"{row['dow_multiplier']:.2f}x cyclical modulation",
            f"{facts['days_of_coverage']:.1f} days",
            f"{facts['lead_time_days']:.0f} days",
            f"{facts['lead_time_std_days']:.2f} days",
            f"{facts['reorder_point_units']:,.1f} units",
            f"{facts['safety_stock_units']:,.1f} units",
            f"{row['order_up_to']:,.0f} units",
            f"{facts['recommended_order_quantity']:,.0f} units",
            str(row["stockout_date"]),
            str(row["order_by_date"]),
            f"{row['timing_urgency_badge']} ({row['timing_urgency_msg']})",
            f"{row['excess_units']:,.0f} units",
            f"{row['days_over_target']:.1f} days",
            f"Class {facts['abc_class']} ({abc_tier_label})",
            f"{facts['coefficient_of_variation']:.3f}",
            f"{facts['demand_change_percent']:+.1f}%",
            f"{facts['risk_score']:.0f} / 100 ({row['severity']} priority)",
        ],
    })
    st.dataframe(evidence_table, width="stretch", hide_index=True)
