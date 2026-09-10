"""
ui/attention_queue.py — Triage Attention Queue, Timing Deadlines & Overstock Playbook
===================================================================================
The primary operational workspace for inventory planners and procurement managers.
Presents interactive charts, multi-criteria filtering, exact order-by deadlines,
recommended order quantities (ROQ), overstock remediation playbooks, and CSV export.

Filters at the top propagate to KPI cards, all charts, the data table,
replenishment timing cards, and overstock playbooks.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config import COLORS
from ui.charts import (
    build_abc_pareto_bar,
    build_coverage_countdown_bar,
    build_portfolio_risk_donut,
)
from ui.chat_view import render_inline_analyst


def _apply_filters(scores: pd.DataFrame, meta: dict[str, Any]) -> pd.DataFrame:
    """Render filter controls and return the filtered DataFrame."""
    f1, f2, f3 = st.columns([2, 2, 2])
    with f1:
        selected_category = st.selectbox("Filter Category", ["All Categories"] + meta["categories"])
    with f2:
        selected_abc = st.multiselect("Filter ABC Tier", ["A", "B", "C"], default=["A", "B", "C"])
    with f3:
        selected_status = st.selectbox(
            "Filter Status / Severity",
            [
                "All Items",
                "Flagged Items Only (Urgency > 0)",
                "Critical Severity Only (Risk ≥ 75)",
                "Order Soon (Imminent Stockout)",
                "Overstock Risk",
            ],
        )

    filtered = scores.copy()
    if selected_category != "All Categories":
        filtered = filtered[filtered["category"] == selected_category]
    if selected_abc:
        filtered = filtered[filtered["abc_class"].isin(selected_abc)]
    if selected_status == "Flagged Items Only (Urgency > 0)":
        filtered = filtered[filtered["urgency"] > 0]
    elif selected_status == "Critical Severity Only (Risk ≥ 75)":
        filtered = filtered[filtered["severity"] == "Critical"]
    elif selected_status == "Order Soon (Imminent Stockout)":
        filtered = filtered[filtered["bucket"] == "Order soon"]
    elif selected_status == "Overstock Risk":
        filtered = filtered[filtered["bucket"] == "Overstock risk"]

    return filtered


def render_attention_queue(scores: pd.DataFrame, meta: dict[str, Any]) -> None:
    """Render the full attention queue view with global filter propagation."""

    # ─────────────────────────────────────────────────────────────────────────
    # 1. FILTERS AT THE TOP — affect everything below
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown(
        "<div class='queue-head'>"
        "<h2>Ranked Attention Queue</h2>"
        "<div class='section-note'>Prioritized by: Urgency Tier → Composite Risk Score → Stockout Deadline</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    filtered = _apply_filters(scores, meta)

    flagged = filtered[filtered["urgency"] > 0]
    overstock = filtered[filtered["bucket"] == "Overstock risk"]

    # ─────────────────────────────────────────────────────────────────────────
    # 2. KPI CARDS (reflect active filters)
    # ─────────────────────────────────────────────────────────────────────────
    from ui.hero import render_kpi_cards
    render_kpi_cards(filtered)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. SKUS AT RISK AT A GLANCE (DETAILS OF WHAT HAPPENED WITHOUT CLICKING)
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### 🚨 SKUs at Risk at a Glance")
    st.caption(
        "Immediate operational triage: All flagged items in the active filter selection "
        "with root-cause details of what happened, risk drivers, and recommended procurement actions."
    )

    if not flagged.empty:
        for _, r in flagged.iterrows():
            border_color = (
                COLORS["critical"] if r["severity"] == "Critical" else
                COLORS["high"] if r["severity"] == "High" else
                COLORS["overstock"] if r["bucket"] == "Overstock risk" else
                COLORS["medium"]
            )
            st.markdown(
                f"<div class='action-card' style='border-left-color: {border_color}; margin-bottom: 0.85rem;'>"
                f"<div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.35rem;'>"
                f"  <span class='action-card-title' style='color: {border_color}; margin: 0; font-size: 1.05rem;'>"
                f"    <b>{r['sku_id']}</b> · {r['category']} (Risk {r['risk_score']:.0f}/100)"
                f"  </span>"
                f"  <div>"
                f"    <span class='status status-{r['abc_class'].lower()}'>CLASS {r['abc_class']}</span> "
                f"    <span class='status status-{r['severity'].lower()}'>{r['severity'].upper()}</span> "
                f"    <span class='timing-badge timing-{r['timing_color']}'>{r['timing_urgency_badge']}</span>"
                f"  </div>"
                f"</div>"
                f"<div style='font-size: 0.92rem; line-height: 1.45; margin: 0.4rem 0;'>"
                f"  <b>What Happened:</b> {r['what_happened']}"
                f"</div>"
                f"<div style='font-size: 0.82rem; color: rgba(245,246,243,0.75); display: flex; gap: 1.4rem; flex-wrap: wrap; margin-top: 0.3rem;'>"
                f"  <span>📦 <b>Stock:</b> {r['stock']:,.0f} u ({r['days_coverage']:.1f}d coverage)</span>"
                f"  <span>⏱️ <b>Lead Time:</b> {r['lead_time']:.0f}d (±{r['lead_time_std']:.1f}d)</span>"
                f"  <span>🎯 <b>Reorder Point:</b> {r['reorder_point']:,.0f} u</span>"
                f"  <span>📅 <b>Order Deadline:</b> {r['order_by_date']}</span>"
                f"  <span>🛒 <b>Reorder Quantity:</b> <b>{r['roq']:,.0f} units</b></span>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ No SKUs currently at risk under the active filter selection.")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 4. PORTFOLIO CHARTS (reflect active filters) — 2+1 layout to avoid overlap
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### Portfolio Health & Stockout Horizons")

    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.plotly_chart(build_portfolio_risk_donut(filtered), use_container_width=True)
    with c_chart2:
        st.plotly_chart(build_abc_pareto_bar(filtered), use_container_width=True)

    # Countdown bar — full width below
    if not flagged.empty:
        st.plotly_chart(build_coverage_countdown_bar(flagged), use_container_width=True)
    else:
        st.info("No flagged SKUs in the current filter selection.")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 5. INTERACTIVE DATA TABLE (same filters already applied)
    # ─────────────────────────────────────────────────────────────────────────
    display = filtered.copy()
    display["SKU"] = display["sku_id"]
    display["Category"] = display["category"]
    display["ABC"] = display["abc_class"]
    display["Signal"] = display["bucket"]
    display["Severity"] = display["severity"]
    display["Risk"] = display["risk_score"].map(lambda x: f"{x:.0f}")
    display["Stock"] = display["stock"].map(lambda x: f"{x:,.0f}")
    display["Demand/Day"] = display["daily_demand"].map(lambda x: f"{x:,.1f}")
    display["Coverage"] = display["days_coverage"].map(lambda x: f"{x:.1f} d")
    display["Lead Time"] = display["lead_time"].map(lambda x: f"{x:.0f} d")
    display["Order By Date"] = display["order_by_date"].astype(str)
    display["Order Timing"] = display["timing_urgency_badge"]
    display["ROQ (Units)"] = display["roq"].map(lambda x: f"{x:,.0f}" if x > 0 else "—")
    display["What Happened"] = display["what_happened"]
    display["Trend"] = display["trend_pct"].map(lambda x: f"{x:+.0%}")
    display["CV"] = display["cv"].map(lambda x: f"{x:.2f}")

    columns_to_show = [
        "SKU", "Category", "ABC", "Signal", "Severity", "Risk", "Stock",
        "Demand/Day", "Coverage", "Lead Time", "Order By Date", "Order Timing",
        "ROQ (Units)", "What Happened", "Trend", "CV"
    ]
    st.dataframe(display[columns_to_show], width="stretch", hide_index=True, height=450)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. ONE-CLICK CSV EXPORT
    # ─────────────────────────────────────────────────────────────────────────
    csv_df = filtered[[
        "sku_id", "category", "abc_class", "bucket", "severity", "risk_score",
        "stock", "daily_demand", "days_coverage", "lead_time", "stockout_date",
        "order_by_date", "timing_urgency_badge", "timing_urgency_msg",
        "reorder_point", "safety_stock", "roq", "excess_units", "days_over_target",
        "what_happened"
    ]].rename(columns={
        "sku_id": "SKU_ID", "category": "Category", "abc_class": "ABC_Class",
        "bucket": "Signal", "severity": "Severity", "risk_score": "Risk_Score",
        "stock": "Current_Stock", "daily_demand": "Daily_Demand",
        "days_coverage": "Days_Coverage", "lead_time": "Lead_Time_Days",
        "stockout_date": "Projected_Stockout_Date", "order_by_date": "Order_By_Date",
        "timing_urgency_badge": "Order_Urgency", "timing_urgency_msg": "Replenishment_Timing_Detail",
        "reorder_point": "Reorder_Point", "safety_stock": "Safety_Stock",
        "roq": "Recommended_Order_Qty", "excess_units": "Excess_Units",
        "days_over_target": "Days_Over_Target", "what_happened": "Root_Cause_Explanation"
    })
    csv_bytes = csv_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Procurement Requisition Plan (CSV with Order-By Dates)",
        data=csv_bytes,
        file_name=f"fmn_procurement_requisitions_{meta.get('date_max', 'latest')}.csv",
        mime="text/csv",
    )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 7. REPLENISHMENT TIMING PANEL — ALL flagged SKUs, wrapped rows of 3
    # ─────────────────────────────────────────────────────────────────────────
    urgent_order_items = filtered[filtered["urgency"] >= 2]
    if not urgent_order_items.empty:
        st.markdown("### Replenishment Timing & Order Deadlines")
        st.caption(
            f"All {len(urgent_order_items)} SKUs requiring immediate procurement action "
            f"(filtered view). When exactly must purchase orders be released before stockouts occur?"
        )

        CARDS_PER_ROW = 3
        items_list = list(urgent_order_items.iterrows())
        for row_start in range(0, len(items_list), CARDS_PER_ROW):
            row_batch = items_list[row_start:row_start + CARDS_PER_ROW]
            cols = st.columns(CARDS_PER_ROW)
            for idx, (_, r) in enumerate(row_batch):
                with cols[idx]:
                    border_color = COLORS["critical"] if r["timing_color"] == "critical" else COLORS["high"]
                    st.markdown(
                        f"<div class='action-card' style='border-left-color: {border_color};'>"
                        f"<div class='action-card-title'><b>{r['sku_id']}</b> ({r['category']})</div>"
                        f"<span class='status status-{r['abc_class'].lower()}'>CLASS {r['abc_class']}</span> "
                        f"<span class='timing-badge timing-{r['timing_color']}'>{r['timing_urgency_badge']}</span>"
                        f"<p style='margin-top: 0.6rem;'>"
                        f"• <b>Order-By Date:</b> {r['order_by_date']}<br>"
                        f"• <b>Stockout Date:</b> {r['stockout_date']} ({r['days_coverage']:.1f}d supply)<br>"
                        f"• <b>Supplier Lead Time:</b> {r['lead_time']:.0f} days<br>"
                        f"• <b>Order Quantity (ROQ):</b> <b>{r['roq']:,.0f} units</b>"
                        f"</p>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 7. OVERSTOCK REMEDIATION PANEL (filtered)
    # ─────────────────────────────────────────────────────────────────────────
    if not overstock.empty:
        st.markdown("### Overstock Diagnostics & Remediation Playbook")
        st.caption("Detailed metrics and operational actions for capital tied up in surplus inventory.")

        for _, r in overstock.iterrows():
            st.markdown(
                f"<div class='overstock-card'>"
                f"<div class='overstock-card-title'>{r['sku_id']} — {r['category']} (Class {r['abc_class']})</div>"
                f"<div style='display:flex; gap:20px; margin: 0.6rem 0;'>"
                f"<div><b>Current Stock:</b> {r['stock']:,.0f} units</div>"
                f"<div><b>Days of Coverage:</b> {r['days_coverage']:.1f} days (Max Target: {r['coverage_limit']:.0f}d)</div>"
                f"<div><b>Excess Inventory:</b> <span style='color:#C0392B; font-weight:bold;'>+{r['excess_units']:,.0f} units</span></div>"
                f"<div><b>Days Over Maximum:</b> +{r['days_over_target']:.1f} days</div>"
                f"</div>"
                f"<p><b>Recommended Operational Action Playbook:</b></p>"
                f"<ul>"
                f"<li><b>Freeze Purchases:</b> Freeze subsequent purchase orders until stock depletes to target Order-Up-To level ({r['order_up_to']:,.0f} units).</li>"
                f"<li><b>Inter-Warehouse Balancing:</b> If operating across regional hubs, reallocate excess stock to distribution centers experiencing stockouts.</li>"
                f"<li><b>Commercial Acceleration:</b> Coordinate with sales and commercial teams for targeted volume bundling or short-term promotions.</li>"
                f"<li><b>Structural Demand Audit:</b> Review historical sales patterns to determine whether baseline customer demand has permanently shifted downward.</li>"
                f"<li><b>Perishable Shelf-Life Review:</b> Verify batch manufacturing dates to guard against product expiration and inventory write-downs.</li>"
                f"</ul>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 8. INLINE ASK THE ANALYST
    # ─────────────────────────────────────────────────────────────────────────
    render_inline_analyst(
        scores=scores,  # full scores for Q&A context
        context_key="attention_queue",
        placeholder="Ask about the attention queue, flagged SKUs, or procurement needs…",
    )
