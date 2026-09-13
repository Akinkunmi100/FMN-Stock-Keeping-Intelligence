"""The main review screen: filters, risk summaries, and recommended actions."""

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
from ui.hero import render_kpi_cards


ALL_CATEGORIES = "All categories"
ALL_SKUS = "All SKUs"
FLAGGED_ONLY = "Needs attention"
CRITICAL_ONLY = "Critical"
ORDER_SOON = "Order soon"
OVERSTOCK = "Overstock risk"
STATUS_FILTERS = [ALL_SKUS, FLAGGED_ONLY, CRITICAL_ONLY, ORDER_SOON, OVERSTOCK]


def _apply_filters(scores: pd.DataFrame, meta: dict[str, Any]) -> pd.DataFrame:
    """Show the queue filters and return the rows that match them."""
    category_column, class_column, status_column = st.columns([2, 2, 2])
    with category_column:
        selected_category = st.selectbox("Category", [ALL_CATEGORIES] + meta["categories"])
    with class_column:
        selected_abc = st.multiselect("Priority class", ["A", "B", "C"], default=["A", "B", "C"])
    with status_column:
        selected_status = st.selectbox(
            "Show",
            STATUS_FILTERS,
        )

    filtered = scores.copy()
    if selected_category != ALL_CATEGORIES:
        filtered = filtered[filtered["category"] == selected_category]
    if selected_abc:
        filtered = filtered[filtered["abc_class"].isin(selected_abc)]
    if selected_status == FLAGGED_ONLY:
        filtered = filtered[filtered["urgency"] > 0]
    elif selected_status == CRITICAL_ONLY:
        filtered = filtered[filtered["severity"] == "Critical"]
    elif selected_status == ORDER_SOON:
        filtered = filtered[filtered["bucket"] == "Order soon"]
    elif selected_status == OVERSTOCK:
        filtered = filtered[filtered["bucket"] == "Overstock risk"]

    return filtered


def render_attention_queue(scores: pd.DataFrame, meta: dict[str, Any]) -> None:
    """Render the review queue. The filters apply to every section below them."""

    # ─────────────────────────────────────────────────────────────────────────
    # 1. FILTERS AT THE TOP — affect everything below
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown(
        "<div class='queue-head'>"
        "<h2>Attention queue</h2>"
        "<div class='section-note'>Sorted by urgency, risk score, and time left before stockout</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    filtered = _apply_filters(scores, meta)

    flagged = filtered[filtered["urgency"] > 0]
    overstock = filtered[filtered["bucket"] == "Overstock risk"]

    # ─────────────────────────────────────────────────────────────────────────
    # 2. KPI CARDS (reflect active filters)
    # ─────────────────────────────────────────────────────────────────────────
    render_kpi_cards(filtered)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. SKUS AT RISK AT A GLANCE (DETAILS OF WHAT HAPPENED WITHOUT CLICKING)
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### SKUs needing attention")
    st.caption(
        "Start here for the products that need a review. Each row shows the reason, the deadline, and the suggested order quantity."
    )

    if not flagged.empty:
        for _, row in flagged.iterrows():
            border_color = (
                COLORS["critical"] if row["severity"] == "Critical" else
                COLORS["high"] if row["severity"] == "High" else
                COLORS["overstock"] if row["bucket"] == "Overstock risk" else
                COLORS["medium"]
            )
            stock_display = (
                "<span style='color: #D32F2F; font-weight: 700;'>0 units (Stocked out)</span>"
                if row["stock"] <= 0
                else f"{row['stock']:,.0f} units ({round(row['days_coverage'] * 24)} hours)"
                if row["days_coverage"] < 1.0
                else f"{row['stock']:,.0f} units ({row['days_coverage']:.1f} days)"
            )
            st.markdown(
                f"<div class='action-card' style='border-left-color: {border_color}; margin-bottom: 0.85rem;'>"
                f"<div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.35rem;'>"
                f"  <span class='action-card-title' style='color: {border_color}; margin: 0; font-size: 1.05rem;'>"
                f"    <b>{row['sku_id']}</b> - {row['category']} (risk {row['risk_score']:.0f}/100)"
                f"  </span>"
                f"  <div>"
                f"    <span class='status status-{row['abc_class'].lower()}'>CLASS {row['abc_class']}</span> "
                f"    <span class='status status-{row['severity'].lower()}'>{row['severity'].upper()}</span> "
                f"    <span class='timing-badge timing-{row['timing_color']}'>{row['timing_urgency_badge']}</span>"
                f"  </div>"
                f"</div>"
                f"<div style='font-size: 0.92rem; line-height: 1.45; margin: 0.4rem 0;'>"
                f"  <b>Why this needs attention:</b> {row['what_happened']}"
                f"</div>"
                f"<div style='font-size: 0.82rem; color: #5B6560; display: flex; gap: 1.4rem; flex-wrap: wrap; margin-top: 0.3rem;'>"
                f"  <span><b>Stock:</b> {stock_display}</span>"
                f"  <span><b>Lead time:</b> {row['lead_time']:.0f} days (variation {row['lead_time_std']:.1f} days)</span>"
                f"  <span><b>Reorder point:</b> {row['reorder_point']:,.0f} units</span>"
                f"  <span><b>Order by:</b> {row['order_by_date']}</span>"
                f"  <span><b>Suggested order:</b> <b>{row['roq']:,.0f} units</b></span>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("No SKUs need attention with these filters.")

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 4. PORTFOLIO CHARTS (reflect active filters) — 2+1 layout to avoid overlap
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### Portfolio overview")

    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.plotly_chart(build_portfolio_risk_donut(filtered), width="stretch")
    with c_chart2:
        st.plotly_chart(build_abc_pareto_bar(filtered), width="stretch")

    # Countdown bar — full width below
    if not flagged.empty:
        st.plotly_chart(build_coverage_countdown_bar(flagged), width="stretch")
    else:
        st.info("There are no flagged SKUs in this filtered view, so there is no countdown to show.")

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
    display["Coverage"] = display["days_coverage"].map(
        lambda x: "0 d (Stocked out)" if x <= 0 else f"{round(x * 24)} hrs" if x < 1.0 else f"{x:.1f} d"
    )
    display["Lead Time"] = display["lead_time"].map(lambda x: f"{x:.0f} d")
    display["Order By Date"] = display["order_by_date"].astype(str)
    display["Order Timing"] = display["timing_urgency_badge"]
    display["Suggested Order"] = display["roq"].map(lambda x: f"{x:,.0f}" if x > 0 else "—")
    display["What Happened"] = display["what_happened"]
    display["Trend"] = display["trend_pct"].map(lambda x: f"{x:+.0%}")
    display["CV"] = display["cv"].map(lambda x: f"{x:.2f}")

    columns_to_show = [
        "SKU", "Category", "ABC", "Signal", "Severity", "Risk", "Stock",
        "Demand/Day", "Coverage", "Lead Time", "Order By Date", "Order Timing",
        "Suggested Order", "What Happened", "Trend", "CV"
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
        label="Download this review list (CSV)",
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
        st.markdown("### Replenishment deadlines")
        st.caption(
            f"These {len(urgent_order_items)} SKUs have the least time left before the current stock is expected to run out."
        )

        CARDS_PER_ROW = 3
        items_list = list(urgent_order_items.iterrows())
        for row_start in range(0, len(items_list), CARDS_PER_ROW):
            row_batch = items_list[row_start:row_start + CARDS_PER_ROW]
            cols = st.columns(CARDS_PER_ROW)
            for idx, (_, row) in enumerate(row_batch):
                with cols[idx]:
                    border_color = COLORS["critical"] if row["timing_color"] == "critical" else COLORS["high"]
                    stockout_info = (
                        "<span style='color: #D32F2F; font-weight: 700;'>Already stocked out</span> (0 days of supply)"
                        if row["stock"] <= 0
                        else f"{row['stockout_date']} ({round(row['days_coverage'] * 24)} hours of supply)"
                        if row["days_coverage"] < 1.0
                        else f"{row['stockout_date']} ({row['days_coverage']:.1f} days of supply)"
                    )
                    st.markdown(
                        f"<div class='action-card' style='border-left-color: {border_color};'>"
                        f"<div class='action-card-title'><b>{row['sku_id']}</b> ({row['category']})</div>"
                        f"<span class='status status-{row['abc_class'].lower()}'>CLASS {row['abc_class']}</span> "
                        f"<span class='timing-badge timing-{row['timing_color']}'>{row['timing_urgency_badge']}</span>"
                        f"<p style='margin-top: 0.6rem;'>"
                        f"<b>Order by:</b> {row['order_by_date']}<br>"
                        f"<b>Expected stockout:</b> {stockout_info}<br>"
                        f"<b>Supplier lead time:</b> {row['lead_time']:.0f} days<br>"
                        f"<b>Suggested order:</b> <b>{row['roq']:,.0f} units</b>"
                        f"</p>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 7. OVERSTOCK REMEDIATION PANEL (filtered)
    # ─────────────────────────────────────────────────────────────────────────
    if not overstock.empty:
        st.markdown("### Overstock actions")
        st.caption("Use these suggestions to review stock that is sitting above the target level.")

        for _, row in overstock.iterrows():
            cov_label = f"{round(row['days_coverage'] * 24)} hours" if 0 < row["days_coverage"] < 1.0 else f"{row['days_coverage']:.1f} days"
            st.markdown(
                f"<div class='overstock-card'>"
                f"<div class='overstock-card-title'>{row['sku_id']} - {row['category']} (Class {row['abc_class']})</div>"
                f"<div style='display:flex; gap:20px; margin: 0.6rem 0;'>"
                f"<div><b>Current stock:</b> {row['stock']:,.0f} units</div>"
                f"<div><b>Days of coverage:</b> {cov_label} (target: {row['coverage_limit']:.0f} days)</div>"
                f"<div><b>Excess inventory:</b> <span style='color:#C0392B; font-weight:bold;'>+{row['excess_units']:,.0f} units</span></div>"
                f"<div><b>Above target by:</b> +{row['days_over_target']:.1f} days</div>"
                f"</div>"
                f"<p><b>What to review next:</b></p>"
                f"<ul>"
                f"<li><b>Pause purchases:</b> Pause new purchase orders until stock reaches the target level ({row['order_up_to']:,.0f} units).</li>"
                f"<li><b>Rebalance stock:</b> Move surplus to another location if a different site has low coverage.</li>"
                f"<li><b>Review demand:</b> Check with the commercial team whether a promotion or bundle could use the surplus.</li>"
                f"<li><b>Check the trend:</b> Confirm whether demand has fallen or the current baseline needs updating.</li>"
                f"<li><b>Check shelf life:</b> Confirm batch dates before stock becomes difficult to sell.</li>"
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
