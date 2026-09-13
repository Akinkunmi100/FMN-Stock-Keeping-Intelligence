"""The detailed view for one SKU, including trends, scenarios, and evidence."""

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
from ui.chat_view import render_inline_analyst


def render_sku_detail(raw: pd.DataFrame, scores: pd.DataFrame) -> None:
    """Render the detailed view for the selected SKU."""

    # Narrow the list before asking the user to choose a SKU.
    filt_col1, filt_col2, filt_col3 = st.columns([1.2, 1.2, 2])
    with filt_col1:
        flagged_count = int((scores["urgency"] > 0).sum())
        show_flagged_only = st.checkbox(f"Show only SKUs needing attention ({flagged_count})", value=False)
    with filt_col2:
        all_categories = sorted(scores["category"].unique().tolist())
        sku_category_filter = st.selectbox(
            "Category",
            ["All categories"] + all_categories,
            key="sku_detail_cat_filter",
        )

    # Build the filtered SKU list for the dropdown
    available = scores.copy()
    if show_flagged_only:
        available = available[available["urgency"] > 0]
    if sku_category_filter != "All categories":
        available = available[available["category"] == sku_category_filter]

    sku_options = available["sku_id"].tolist()
    if not sku_options:
        st.warning("No SKUs match the current filters. Adjust the filters above.")
        return

    with filt_col3:
        selected_sku = st.selectbox(
            f"SKU ({len(sku_options)} available)",
            sku_options,
            index=0,
        )

    row = scores[scores["sku_id"] == selected_sku].iloc[0]
    sku_history = raw[raw["sku_id"] == selected_sku].sort_values("date")

    # Status and timing are shown before the supporting charts.
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
        f"<div class='section-note'>Method: {row['method']} · {row['history_days']} days recorded ({row['observations']} usable demand observations)</div>",
        unsafe_allow_html=True,
    )

    stock_delta = "STOCKED OUT" if row["stock"] <= 0 else "units"
    coverage_delta = (
        "STOCKED OUT" if row["stock"] <= 0
        else "IMMINENT (<24h)" if row["days_coverage"] < 1.0
        else f"lead time: {row['lead_time']:.0f} days"
    )
    coverage_display_val = (
        "0.0" if row["stock"] <= 0
        else f"{round(row['days_coverage'] * 24)} hrs" if row["days_coverage"] < 1.0
        else f"{row['days_coverage']:.1f}"
    )
    m1.metric("Stock on hand", f"{row['stock']:,.0f}", stock_delta, delta_color="inverse" if row["stock"] <= 0 else "off")
    m2.metric(
        "Stock coverage",
        coverage_display_val,
        coverage_delta,
        delta_color="inverse" if (row["stock"] <= 0 or row["days_coverage"] < 1.0) else "off",
    )
    m3.metric("Reorder point", f"{row['reorder_point']:,.0f}", f"buffer: {row['safety_stock']:,.0f}")
    m4.metric("Order by", str(row["order_by_date"]), row["timing_urgency_badge"])
    m5.metric("Suggested order", f"{row['roq']:,.0f}", "units" if row["roq"] > 0 else "no order needed")
    m6.metric("Risk score", f"{row['risk_score']:.0f}/100", f"{row['severity']} level")

    border_color = (
        COLORS["critical"] if row["severity"] == "Critical" else
        COLORS["high"] if row["severity"] == "High" else
        COLORS["overstock"] if row["bucket"] == "Overstock risk" else
        COLORS["low"]
    )

    cov_text = (
        f"{round(row['days_coverage'] * 24)} hours"
        if 0 < row["days_coverage"] < 1.0
        else f"{row['days_coverage']:.1f} days"
    )

    if row["urgency"] >= 2 and row["bucket"] != "Overstock risk":
        order_action_clause = (
            f"Review an emergency expedited order for <b>{row['roq']:,.0f} units</b> immediately (reorder deadline was <b>{row['order_by_date']}</b>)."
            if row.get("days_until_deadline", 0) < 0
            else f"Review an order for <b>{row['roq']:,.0f} units</b> by <b>{row['order_by_date']}</b>."
        )
        stockout_line = (
            f"<span style='color: #D32F2F; font-weight: 700;'>Already stocked out</span> (fully depleted as of {row['stockout_date']})."
            if row["stock"] <= 0
            else f"<b>{row['stockout_date']}</b> (imminent — ~{round(row['days_coverage'] * 24)} hours of supply remaining)."
            if row["days_coverage"] < 1.0
            else f"<b>{row['stockout_date']}</b> if demand and supply stay on the current path."
        )
        action_html = f"""
        <div class='action-card' style='border-left-color: {border_color};'>
            <div class='action-card-title' style='color: {border_color};'>
                NEXT ACTION: {row['timing_urgency_badge']}
            </div>
            <p>
                • <b>Why this needs attention:</b> {row['what_happened']}<br>
                • <b>Suggested action:</b> {order_action_clause}<br>
                • <b>Lead time:</b> Supplier delivery takes {row['lead_time']:.0f} days (variation: {row['lead_time_std']:.1f} days).<br>
                • <b>Expected stockout:</b> {stockout_line}<br>
                • <b>Priority:</b> Class {row['abc_class']} by unit volume.
            </p>
        </div>
        """
    elif row["bucket"] == "Overstock risk":
        action_html = f"""
        <div class='overstock-card'>
            <div class='overstock-card-title'>NEXT ACTION: REVIEW EXCESS STOCK</div>
            <p>
                • <b>Above target:</b> {row['excess_units']:,.0f} units.<br>
                • <b>Coverage:</b> {cov_text} of supply ({row['days_over_target']:.1f} days above target).<br>
                • <b>Suggested action:</b> Pause new purchases and review whether stock should be moved or promoted.
            </p>
        </div>
        """
    else:
        action_html = f"""
        <div class='action-card' style='border-left-color: {COLORS["low"]};'>
            <div class='action-card-title' style='color: {COLORS["low"]};'>NO ACTION NEEDED RIGHT NOW</div>
            <p>
                Current stock ({row['stock']:,.0f} units) provides {cov_text} of coverage, above the {row['lead_time']:.0f}-day supplier lead time.
            </p>
        </div>
        """
    st.markdown(action_html, unsafe_allow_html=True)

    st.divider()

    st.markdown("### Stock and demand over time")
    col_c1, col_c2, col_c3 = st.columns([1.6, 1.6, 1])

    with col_c1:
        st.plotly_chart(
            build_stock_trajectory_chart(sku_history, row["reorder_point"], row["safety_stock"]),
            width="stretch",
        )
    with col_c2:
        st.plotly_chart(
            build_demand_and_receipts_chart(sku_history),
            width="stretch",
        )
    with col_c3:
        st.plotly_chart(
            build_risk_gauge(row["risk_score"], row["severity"]),
            width="stretch",
        )

    st.divider()

    st.markdown("### Try a scenario")
    st.caption("See how the suggested order changes if demand rises or delivery takes longer.")

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        sim_demand_surge = st.slider("Change in demand (%)", min_value=-50, max_value=100, value=0, step=5)
    with sim_col2:
        sim_lead_delay = st.slider("Extra supplier days", min_value=0, max_value=14, value=0, step=1)

    # Simulator calculations
    sim_demand = row["daily_demand"] * (1.0 + sim_demand_surge / 100.0)
    sim_lead = row["lead_time"] + sim_lead_delay
    sim_ss = row["safety_stock"] * np.sqrt(sim_lead / max(row["lead_time"], 1.0)) * (1.0 + sim_demand_surge / 200.0)
    sim_rop = (sim_demand * sim_lead) + sim_ss
    sim_coverage = row["stock"] / sim_demand if sim_demand > 0 else np.inf
    sim_cycle = max(7.0 * sim_demand, sim_demand * np.sqrt(2 * max(sim_lead, 1.0)))
    sim_roq = max(0.0, round((sim_demand * sim_lead + sim_ss + sim_cycle) - row["stock"], 0))

    baseline_cov_str = (
        f"{round(row['days_coverage'] * 24)} hrs ({row['days_coverage']:.1f}d)"
        if 0 < row["days_coverage"] < 1.0
        else f"{row['days_coverage']:.1f} days"
    )
    sim_cov_str = (
        f"{round(sim_coverage * 24)} hrs ({sim_coverage:.1f}d)"
        if 0 < sim_coverage < 1.0
        else f"{sim_coverage:.1f} days"
    )
    sim_df = pd.DataFrame({
        "Parameter": ["Daily demand", "Supplier lead time", "Safety buffer", "Reorder point", "Days of stock", "Suggested order"],
        "Baseline": [
            f"{row['daily_demand']:,.1f} u/d",
            f"{row['lead_time']:.0f} days",
            f"{row['safety_stock']:,.0f} units",
            f"{row['reorder_point']:,.0f} units",
            baseline_cov_str,
            f"{row['roq']:,.0f} units",
        ],
        "Simulated": [
            f"{sim_demand:,.1f} u/d",
            f"{sim_lead:.0f} days",
            f"{sim_ss:,.0f} units",
            f"{sim_rop:,.0f} units",
            sim_cov_str,
            f"{sim_roq:,.0f} units",
        ],
        "Change": [
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

    st.markdown("### Why this SKU is flagged")
    st.caption("The explanation uses this SKU's calculated values. Groq is used when configured; otherwise the app shows a local summary.")

    if st.button("Explain this SKU", type="primary") or "explanation" not in st.session_state or st.session_state.get("explanation_sku") != selected_sku:
        with st.spinner("Checking the SKU data..."):
            st.session_state.explanation = explain_sku(row)
            st.session_state.explanation_sku = selected_sku

    if "explanation" in st.session_state:
        llm_res: LLMResult = st.session_state.explanation
        if llm_res.warning:
            st.info(llm_res.warning)

        source_label = f"Live assistant answer ({llm_res.model})" if llm_res.live and llm_res.model else "Local evidence summary"
        st.markdown(
            f"<div class='evidence'>"
            f"<div class='evidence-title'>{source_label}</div>"
            f"<p>{llm_res.text}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### Numbers behind the decision")
    facts = build_sku_facts(row)
    abc_tier_label = {
        "A": f"Top {ABC_THRESHOLDS['A']:.0%} Volume",
        "B": "Moderate Volume",
        "C": "Tail Item",
    }.get(facts["abc_class"], "")
    evidence_table = pd.DataFrame({
        "Parameter": [
            "Current stock",
            "Daily demand estimate",
            "Demand during supplier lead time",
            "Day-of-week demand adjustment",
            "Days of stock",
            "Supplier lead time",
            "Lead-time variation",
            "Reorder point",
            "Safety buffer",
            "Target stock level",
            "Suggested order quantity",
            "Expected stockout date",
            "Order-by date",
            "Order status",
            "Excess stock",
            "Days above target",
            "Volume priority",
            "Demand variability",
            "Recent demand change",
            "Risk score",
        ],
        "Value": [
            f"{facts['closing_stock_units']:,.1f} units",
            f"{facts['daily_demand_units']:,.1f} units/day",
            f"{facts['forward_lead_time_demand']:,.1f} units over {facts['lead_time_days']:.0f}d",
            f"{row['dow_multiplier']:.2f}x cyclical modulation",
            f"{round(facts['days_of_coverage'] * 24)} hours ({facts['days_of_coverage']:.1f} days)" if 0 < facts["days_of_coverage"] < 1.0 else f"{facts['days_of_coverage']:.1f} days",
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

    st.divider()

    render_inline_analyst(
        scores=scores,
        context_key=f"sku_detail_{selected_sku}",
        placeholder=f"Ask about {selected_sku}, its risk, or the suggested order...",
    )
