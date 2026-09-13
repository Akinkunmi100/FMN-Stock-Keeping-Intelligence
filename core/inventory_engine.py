"""Calculate stock coverage, reorder points, timing, and risk scores.

The functions here turn cleaned daily demand and inventory history into the
numbers shown in the review queue and SKU detail view.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from config import (
    ABC_RISK_MULTIPLIERS,
    DEMAND_SURGE_THRESHOLD_PCT,
    ESTABLISHED_COVERAGE_LIMIT,
    NEW_SKU_COVERAGE_LIMIT,
    RISK_WEIGHTS,
    SERVICE_LEVEL_Z,
    SEVERITY_THRESHOLDS,
)
from core.demand_model import (
    compute_demand_trend,
    compute_demand_volatility,
    estimate_baseline_velocity,
    extract_uncensored_demand,
    project_forward_lead_demand,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. STOCHASTIC SAFETY STOCK & REORDER POINT
# ─────────────────────────────────────────────────────────────────────────────

def calculate_stochastic_safety_stock(
    daily_demand: float,
    lead_time: float,
    demand_std: float,
    lead_time_std: float,
    abc_class: str,
    cat_kurtosis: float,
    is_new: bool,
    inherited_cat_cv: float = 0.30,
) -> tuple[float, float, float]:
    """
    Calculate stochastic safety stock accounting for BOTH demand volatility
    and supplier delivery lead-time variability.
    
    Formula:
        SS = z_eff * sqrt( L * sigma_D^2 + D^2 * sigma_L^2 )
        
    Where:
        - z_eff: Base service-level z-score adjusted by excess kurtosis for heavy tails
        - L: Supplier lead time (days)
        - sigma_D: Demand standard deviation (units/day)
        - sigma_L: Lead time standard deviation (days)
        
    Returns:
        (safety_stock, effective_z, total_variance)
    """
    base_z = SERVICE_LEVEL_Z.get(abc_class, 1.65)
    
    # Leptokurtic adjustment: add buffer if historical distribution has fat tails
    if cat_kurtosis is None or np.isnan(cat_kurtosis):
        cat_kurtosis = 1.0
    tail_multiplier = 1.0 + 0.08 * min(max(0.0, cat_kurtosis - 1.5), 3.0)
    effective_z = base_z * tail_multiplier

    lead_time = max(1.0, 7.0 if (lead_time is None or np.isnan(lead_time)) else lead_time)
    lead_time_std = max(0.0, 0.0 if (lead_time_std is None or np.isnan(lead_time_std)) else lead_time_std)
    demand_std = max(0.0, 0.0 if (demand_std is None or np.isnan(demand_std)) else demand_std)
    daily_demand = max(0.1, 0.1 if (daily_demand is None or np.isnan(daily_demand)) else daily_demand)

    if is_new:
        if inherited_cat_cv is None or np.isnan(inherited_cat_cv) or inherited_cat_cv <= 0:
            inherited_cat_cv = 0.30
        effective_demand_std = max(demand_std, inherited_cat_cv * daily_demand)
        variance = lead_time * (effective_demand_std ** 2) + (daily_demand ** 2) * (lead_time_std ** 2)
        ss = max(daily_demand * 0.50, effective_z * np.sqrt(max(0.0, variance)))
    else:
        variance = lead_time * (demand_std ** 2) + (daily_demand ** 2) * (lead_time_std ** 2)
        ss = max(daily_demand * 0.25, effective_z * np.sqrt(max(0.0, variance)))

    return ss, effective_z, variance


# ─────────────────────────────────────────────────────────────────────────────
# 2. EXACT ORDER TIMING & REPLENISHMENT DEADLINES
# ─────────────────────────────────────────────────────────────────────────────

def calculate_order_timing(
    current_date: date,
    stock: float,
    daily_demand: float,
    lead_time: float,
) -> dict[str, Any]:
    """
    Calculate precise replenishment deadlines and projected stockout dates.
    
    Answers the critical operational question:
    "When exactly does a purchase order need to be placed?"
    
    Formulas:
        Days_to_Stockout = floor(Stock / Daily_Demand)
        Stockout_Date = Current_Date + Days_to_Stockout
        Order_By_Date = Stockout_Date - Lead_Time
        Days_Until_Order_Deadline = (Order_By_Date - Current_Date)
    """
    if current_date is None:
        calc_date = date.today()
    elif isinstance(current_date, date) and not hasattr(current_date, "hour"):
        calc_date = current_date
    elif hasattr(current_date, "date"):
        calc_date = current_date.date()
    else:
        calc_date = pd.to_datetime(current_date).date()

    safe_stock = 0.0 if (stock is None or np.isnan(stock)) else float(stock)
    safe_demand = 0.0 if (daily_demand is None or np.isnan(daily_demand)) else float(daily_demand)

    if safe_demand <= 0:
        days_to_stockout = 999
    else:
        days_to_stockout = max(0, int(np.floor(safe_stock / safe_demand)))

    stockout_date = calc_date + timedelta(days=min(days_to_stockout, 365))
    safe_lt = 7.0 if (lead_time is None or np.isnan(lead_time) or lead_time <= 0) else float(lead_time)
    lt_days = max(1, int(round(safe_lt)))
    order_by_date = stockout_date - timedelta(days=lt_days)
    
    days_until_deadline = (order_by_date - calc_date).days

    if days_until_deadline < 0:
        urgency_badge = "OVERDUE"
        urgency_msg = f"Overdue by {abs(days_until_deadline)} day{'s' if abs(days_until_deadline) != 1 else ''} (Order should have been placed on {order_by_date})"
        urgency_color = "critical"
    elif days_until_deadline == 0:
        urgency_badge = "ORDER TODAY"
        urgency_msg = f"Place Purchase Order today ({order_by_date}) to prevent stockout"
        urgency_color = "critical"
    elif days_until_deadline <= 3:
        urgency_badge = f"ORDER IN {days_until_deadline}D"
        urgency_msg = f"Place order within {days_until_deadline} days (by {order_by_date})"
        urgency_color = "high"
    elif days_until_deadline <= 7:
        urgency_badge = f"ORDER IN {days_until_deadline}D"
        urgency_msg = f"Plan replenishment within {days_until_deadline} days (by {order_by_date})"
        urgency_color = "medium"
    else:
        urgency_badge = "BUFFER HEALTHY"
        urgency_msg = f"Sufficient coverage until {order_by_date} ({days_until_deadline} days window)"
        urgency_color = "low"

    return {
        "days_to_stockout": days_to_stockout,
        "stockout_date": stockout_date,
        "order_by_date": order_by_date,
        "days_until_deadline": days_until_deadline,
        "timing_urgency_badge": urgency_badge,
        "timing_urgency_msg": urgency_msg,
        "timing_color": urgency_color,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. OVERSTOCK METRICS & RECOMMENDED ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_overstock_diagnostics(
    stock: float,
    daily_demand: float,
    days_coverage: float,
    coverage_limit: float,
    order_up_to: float,
) -> dict[str, Any]:
    """
    Calculate comprehensive overstock metrics and concrete remediation playbooks.
    
    Metrics:
    - Excess Units: Stock beyond target Order-Up-To level S
    - Days Over Maximum Target: Coverage beyond target maximum days
    - Holding Cost Impact: Estimated tied up working capital
    """
    safe_stock = 0.0 if (stock is None or np.isnan(stock)) else max(0.0, float(stock))
    safe_out = 0.0 if (order_up_to is None or np.isnan(order_up_to)) else max(0.0, float(order_up_to))
    safe_cov = 0.0 if (days_coverage is None or np.isnan(days_coverage)) else max(0.0, float(days_coverage))
    safe_limit = 28.0 if (coverage_limit is None or np.isnan(coverage_limit) or coverage_limit <= 0) else float(coverage_limit)

    excess_units = max(0.0, round(safe_stock - safe_out, 0))
    days_over_target = max(0.0, round(safe_cov - safe_limit, 1))

    # Recommended action playbook for operations
    actions = [
        "1. Pause/Freeze scheduled Purchase Orders until stock depletes to target level.",
        "2. Inter-facility transfers: Reallocate surplus to satellite depots with low coverage.",
        "3. Commercial bundling: Coordinate with marketing for promotional volume discounts.",
        "4. Forecast review: Assess if recent demand indicates a permanent structural decline.",
        "5. Vendor return/swap: If shelf-life/expiry is constrained, negotiate return with supplier.",
    ]

    return {
        "excess_units": excess_units,
        "days_over_target": days_over_target,
        "overstock_action_playbook": actions,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. COMPOSITE RISK INDEX (0–100)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_composite_risk(
    days_coverage: float,
    lead_time: float,
    trend_pct: float,
    cv: float,
    stock: float,
    reorder_point: float,
    abc_class: str,
) -> tuple[float, str]:
    """
    Compute a calibrated 0–100 composite risk score synthesizing:
    1. Coverage depletion relative to supplier lead time (35%)
    2. Demand acceleration trend (25%)
    3. Demand volatility coefficient of variation (20%)
    4. Proximity to reorder point threshold (20%)
    5. ABC priority multiplier (Class A +15%, Class C -15%)
    """
    safe_cov = 0.0 if (days_coverage is None or np.isnan(days_coverage)) else max(0.0, float(days_coverage))
    safe_lt = 7.0 if (lead_time is None or np.isnan(lead_time) or lead_time <= 0) else float(lead_time)
    safe_trend = 0.0 if (trend_pct is None or np.isnan(trend_pct)) else float(trend_pct)
    safe_cv = 0.30 if (cv is None or np.isnan(cv)) else max(0.0, float(cv))
    safe_stock = 0.0 if (stock is None or np.isnan(stock)) else max(0.0, float(stock))
    safe_rop = 1.0 if (reorder_point is None or np.isnan(reorder_point) or reorder_point <= 0) else float(reorder_point)

    coverage_ratio = max(0.0, min(safe_cov / safe_lt, 3.0)) / 3.0
    trend_factor = max(0.0, min(abs(safe_trend), 0.50)) / 0.50
    volatility_factor = max(0.0, min(safe_cv, 1.0))
    rop_ratio = max(0.0, min(safe_stock / safe_rop, 2.0)) / 2.0
    abc_multiplier = ABC_RISK_MULTIPLIERS.get(abc_class, 1.0)

    base_score = (
        RISK_WEIGHTS["coverage_depletion"] * (1.0 - coverage_ratio)
        + RISK_WEIGHTS["demand_acceleration"] * trend_factor
        + RISK_WEIGHTS["demand_volatility"] * volatility_factor
        + RISK_WEIGHTS["reorder_proximity"] * (1.0 - rop_ratio)
    )

    composite_score = round(max(0.0, min(100.0, base_score * abc_multiplier)), 1)

    if composite_score >= SEVERITY_THRESHOLDS["Critical"]:
        severity = "Critical"
    elif composite_score >= SEVERITY_THRESHOLDS["High"]:
        severity = "High"
    elif composite_score >= SEVERITY_THRESHOLDS["Medium"]:
        severity = "Medium"
    else:
        severity = "Low"

    return composite_score, severity


# ─────────────────────────────────────────────────────────────────────────────
# 5. DIAGNOSTIC ROOT-CAUSE SYNTHESIZER ("WHAT HAPPENED")
# ─────────────────────────────────────────────────────────────────────────────

def format_coverage_text(days: float) -> str:
    """Format days of coverage into human-readable text, converting sub-day values into hours."""
    if days <= 0:
        return "0 days"
    if days < 1.0:
        hrs = round(days * 24)
        return f"{hrs} hour{'s' if hrs != 1 else ''}"
    return f"{days:.1f} days"


def synthesize_what_happened(
    sku_id: str,
    category: str,
    abc_class: str,
    bucket: str,
    severity: str,
    stock: float,
    daily_demand: float,
    days_coverage: float,
    lead_time: float,
    lead_time_std: float,
    reorder_point: float,
    safety_stock: float,
    trend_pct: float,
    cv: float,
    roq: float,
    order_by_date: Any,
    stockout_date: Any,
    days_until_deadline: int,
    timing_urgency_badge: str,
    timing_urgency_msg: str,
    excess_units: float,
    days_over_target: float,
    coverage_limit: float,
    receipts_7d: float = 0.0,
    is_new: bool = False,
    history_days: int = 0,
) -> str:
    """
    Build the short explanation shown in the review queue and SKU detail view.

    Keep this message understandable without inventory-model terminology. The
    underlying values remain available in the evidence table for deeper review.
    """
    def readable_date(value: Any) -> str:
        """Format dates in a way that is easier to scan than YYYY-MM-DD."""
        try:
            return pd.Timestamp(value).strftime("%B %d, %Y").replace(" 0", " ")
        except (TypeError, ValueError):
            return str(value)

    def demand_change_sentence() -> str:
        """Describe a meaningful demand change without exposing CV terminology."""
        if abs(trend_pct) < 0.05:
            return ""
        direction = "up" if trend_pct > 0 else "down"
        return f" Recent demand is {direction} {abs(trend_pct):.1%} compared with the previous period."

    def cold_start_note() -> str:
        """Append a data-quality caveat for newly introduced products."""
        if not is_new:
            return ""
        return (
            f" Note: as a newly introduced product ({history_days} days recorded), "
            f"inventory targets use category-level demand baselines rather than SKU-specific history."
        )

    order_by = readable_date(order_by_date)
    projected_stockout = readable_date(stockout_date)
    cov_str = format_coverage_text(days_coverage)

    # ── ACTIVE STOCKOUT (stock = 0) ──
    if stock <= 0:
        timing_clause = (
            f"The reorder deadline was {abs(days_until_deadline)} day{'s' if abs(days_until_deadline) != 1 else ''} ago ({order_by}), meaning an order is overdue"
            if days_until_deadline < 0 else
            f"The order is due today ({order_by})"
            if days_until_deadline == 0 else
            f"The order is due in {days_until_deadline} day{'s' if days_until_deadline != 1 else ''} ({order_by})"
        )
        return (
            f"Stockout alert: 0 units on hand (currently out of stock). "
            f"Supplier delivery takes {lead_time:.0f} days, and the safe reorder point is {reorder_point:,.0f} units. "
            f"{timing_clause}. Stock has been fully depleted as of {projected_stockout}.{demand_change_sentence()} "
            f"Suggested action: place an emergency expedited order for {roq:,.0f} units immediately.{cold_start_note()}"
        )

    # ── IMMINENT STOCKOUT (less than 1 day of supply) ──
    if bucket == "Order soon" and days_coverage < 1.0:
        timing_clause = (
            f"The reorder deadline was {abs(days_until_deadline)} day{'s' if abs(days_until_deadline) != 1 else ''} ago ({order_by})"
            if days_until_deadline < 0 else
            f"The order is due today ({order_by})"
            if days_until_deadline == 0 else
            f"The order is due in {days_until_deadline} day{'s' if days_until_deadline != 1 else ''} ({order_by})"
        )
        hrs = round(days_coverage * 24)
        hrs_str = f"{hrs} hour{'s' if hrs != 1 else ''}"
        return (
            f"Stockout is imminent: only {stock:,.0f} units remain (approximately {hrs_str} of supply). "
            f"Supplier delivery takes {lead_time:.0f} days. The safe reorder point is {reorder_point:,.0f} units. "
            f"{timing_clause}. Stock is projected to deplete today.{demand_change_sentence()} "
            f"Suggested action: place an expedited order for {roq:,.0f} units immediately.{cold_start_note()}"
        )

    # ── ORDER SOON (stock > 0, coverage > 1 day but still critical) ──
    if bucket == "Order soon":
        timing_clause = (
            f"The reorder deadline was {abs(days_until_deadline)} day{'s' if abs(days_until_deadline) != 1 else ''} ago ({order_by})"
            if days_until_deadline < 0 else
            f"The order is due today ({order_by})"
            if days_until_deadline == 0 else
            f"The order is due in {days_until_deadline} day{'s' if days_until_deadline != 1 else ''} ({order_by})"
        )
        return (
            f"Stock is low: {stock:,.0f} units will last about {cov_str}, "
            f"but supplier delivery takes {lead_time:.0f} days. The safe reorder point is {reorder_point:,.0f} units, "
            f"so current stock is below the level needed to cover delivery time. {timing_clause}. "
            f"Stock is expected to run out on {projected_stockout}.{demand_change_sentence()} "
            f"Suggested action: place an order for {roq:,.0f} units now.{cold_start_note()}"
        )

    # ── PLAN REPLENISHMENT ──
    if bucket == "Plan replenishment":
        return (
            f"Stock is below the safe reorder point: {stock:,.0f} units on hand versus {reorder_point:,.0f} units needed. "
            f"It will last about {cov_str}, while supplier delivery takes {lead_time:.0f} days."
            f"{demand_change_sentence()} Order by {order_by}. "
            f"Suggested action: prepare an order for {roq:,.0f} units.{cold_start_note()}"
        )

    # ── OVERSTOCK RISK ──
    if bucket == "Overstock risk":
        return (
            f"Stock exceeds target levels: {stock:,.0f} units will last about {cov_str} "
            f"({days_over_target:.1f} days above the {coverage_limit:.0f}-day target ceiling). "
            f"Current inventory is approximately {excess_units:,.0f} units above the target order-up-to level."
            f"{demand_change_sentence()} Suggested action: pause new purchases and review whether the extra stock can be redistributed or promoted."
        )

    # ── MONITOR CLOSELY (demand acceleration) ──
    if bucket == "Monitor closely":
        return (
            f"Demand surge detected: recent sales velocity has increased by {trend_pct:+.1%} compared with the previous period. "
            f"Current stock of {stock:,.0f} units will last about {cov_str}, "
            f"approaching the {lead_time:.0f}-day supplier delivery window. "
            f"Suggested action: monitor daily sales closely and prepare a purchase order before inventory "
            f"hits the safe reorder point ({reorder_point:,.0f} units)."
        )

    # ── ON TRACK ──
    # Issue #1 fix: when coverage < lead time but receipts suppressed the trigger,
    # explain the receipt pipeline rather than contradicting the math.
    if days_coverage < lead_time and receipts_7d > 0:
        return (
            f"Recent delivery received: {receipts_7d:,.0f} units arrived in the past 7 days, "
            f"maintaining stock at {stock:,.0f} units ({cov_str} of supply). "
            f"Although coverage is within the {lead_time:.0f}-day lead time window, "
            f"new purchase orders are temporarily held while the recent shipment settles into the pipeline. "
            f"No additional order is needed at this time."
        )

    return (
        f"Stock is in a healthy position: {stock:,.0f} units will last about {cov_str}, "
        f"which is longer than the {lead_time:.0f}-day supplier delivery time. No order is needed right now."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. MASTER SKU SCORING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def score_sku_inventory(
    sku_id: str,
    sku_group: pd.DataFrame,
    abc_class: str,
    dow_multipliers: dict[int, float],
    cat_cv: dict[str, float],
    cat_kurt: dict[str, float],
) -> dict[str, Any]:
    """
    Full diagnostic evaluation of a single SKU's inventory posture.
    """
    group = sku_group.sort_values("date").reset_index(drop=True)
    date_col = pd.to_datetime(group["date"])
    history_days = int((date_col.max() - date_col.min()).days + 1)
    is_new = history_days < 56

    if "lead_time_used" in group.columns:
        raw_lt = group["lead_time_used"].median()
    elif "lead_time_days" in group.columns:
        valid_lt = group["lead_time_days"].dropna()
        raw_lt = valid_lt.median() if len(valid_lt) > 0 else 7.0
    else:
        raw_lt = 7.0
    lead_time = 7.0 if (pd.isna(raw_lt) or raw_lt <= 0) else float(raw_lt)

    raw_stock = group.iloc[-1]["closing_stock"] if "closing_stock" in group.columns else 0.0
    stock = 0.0 if pd.isna(raw_stock) else max(0.0, float(raw_stock))

    receipts_7d = float(group.tail(7)["units_received"].sum()) if "units_received" in group.columns else 0.0
    if pd.isna(receipts_7d):
        receipts_7d = 0.0

    cat_raw = group.iloc[-1]["category"] if "category" in group.columns else "General"
    cat_clean = str(group.iloc[-1]["category_clean"]) if "category_clean" in group.columns else str(cat_raw).title()
    cat_key = str(group.iloc[-1]["category_key"]) if "category_key" in group.columns else str(cat_raw).strip().lower()

    last_dt = date_col.iloc[-1]
    last_date = last_dt.date()
    last_dow = int(last_dt.dayofweek)

    # Lead time variability
    lt_col = "lead_time_days" if "lead_time_days" in group.columns else ("lead_time_used" if "lead_time_used" in group.columns else None)
    if lt_col:
        lt_series = group[lt_col].dropna()
        lead_time_std = float(lt_series.std(ddof=1)) if lt_series.nunique() > 1 else 0.0
    else:
        lead_time_std = 0.0
    if pd.isna(lead_time_std):
        lead_time_std = 0.0

    # Uncensored demand series
    demand_series = extract_uncensored_demand(group)
    observations = int(demand_series.size)

    # Velocity & volatility
    daily_demand, full_median, ewma_latest = estimate_baseline_velocity(demand_series, lead_time)
    volatility, cv = compute_demand_volatility(demand_series, daily_demand)

    # Forward seasonal projection
    forward_lead_demand, dow_multiplier = project_forward_lead_demand(
        daily_demand, lead_time, last_dow, dow_multipliers
    )

    # Trend acceleration
    trend_pct, recent_mean, prior_mean = compute_demand_trend(demand_series, lead_time, daily_demand)

    # Safety stock & ROP
    raw_kurt = cat_kurt.get(cat_key, 1.0) if cat_kurt else 1.0
    cat_kurtosis = 1.0 if (raw_kurt is None or pd.isna(raw_kurt)) else float(raw_kurt)

    raw_cv = cat_cv.get(cat_key, 0.30) if cat_cv else 0.30
    inherited_cv = 0.30 if (raw_cv is None or pd.isna(raw_cv) or raw_cv <= 0) else float(raw_cv)

    safety_stock, eff_z, _ = calculate_stochastic_safety_stock(
        daily_demand=daily_demand,
        lead_time=lead_time,
        demand_std=volatility,
        lead_time_std=lead_time_std,
        abc_class=abc_class,
        cat_kurtosis=cat_kurtosis,
        is_new=is_new,
        inherited_cat_cv=inherited_cv,
    )

    reorder_point = forward_lead_demand + safety_stock
    days_coverage = max(0.0, min(stock / daily_demand, 999.0)) if daily_demand > 0 else 999.0
    coverage_limit = NEW_SKU_COVERAGE_LIMIT if is_new else ESTABLISHED_COVERAGE_LIMIT

    # Pipeline awareness
    recent_receipt_active = receipts_7d > 0 and stock > safety_stock

    # Recommended Order Quantity (ROQ) / Order-Up-To Level (S)
    cycle_stock = max(7.0 * daily_demand, daily_demand * np.sqrt(2 * max(lead_time, 1.0)))
    order_up_to = forward_lead_demand + safety_stock + cycle_stock
    recommended_order_qty = max(0.0, round(order_up_to - stock, 0))

    # Trigger logic
    coverage_multiplier = 1.0 + (cv * 0.50)
    stockout_trigger_raw = stock <= reorder_point or days_coverage <= (lead_time * coverage_multiplier)
    stockout_trigger = stockout_trigger_raw and not recent_receipt_active
    overstock_trigger = days_coverage >= coverage_limit and stock > (reorder_point * 1.5)
    trend_trigger = trend_pct >= DEMAND_SURGE_THRESHOLD_PCT and days_coverage <= (lead_time * 2.5)

    if stockout_trigger:
        if days_coverage <= lead_time:
            bucket, urgency = "Order soon", 3
        else:
            bucket, urgency = "Plan replenishment", 2
        flag_type = "stockout risk"
    elif overstock_trigger:
        bucket, urgency, flag_type = "Overstock risk", 2, "overstock risk"
    elif trend_trigger:
        bucket, urgency, flag_type = "Monitor closely", 1, "demand acceleration"
    else:
        bucket, urgency, flag_type = "On track", 0, "no active flag"

    # Composite Risk Score
    risk_score, severity = calculate_composite_risk(
        days_coverage=days_coverage,
        lead_time=lead_time,
        trend_pct=trend_pct,
        cv=cv,
        stock=stock,
        reorder_point=reorder_point,
        abc_class=abc_class,
    )

    # Order Timing & Exact Deadlines
    timing = calculate_order_timing(
        current_date=last_date,
        stock=stock,
        daily_demand=daily_demand,
        lead_time=lead_time,
    )

    # Overstock diagnostics
    overstock_diag = evaluate_overstock_diagnostics(
        stock=stock,
        daily_demand=daily_demand,
        days_coverage=days_coverage,
        coverage_limit=coverage_limit,
        order_up_to=order_up_to,
    )

    # Empirical root cause synthesis ("What Happened")
    what_happened = synthesize_what_happened(
        sku_id=sku_id,
        category=cat_clean,
        abc_class=abc_class,
        bucket=bucket,
        severity=severity,
        stock=stock,
        daily_demand=daily_demand,
        days_coverage=days_coverage,
        lead_time=lead_time,
        lead_time_std=lead_time_std,
        reorder_point=reorder_point,
        safety_stock=safety_stock,
        trend_pct=trend_pct,
        cv=cv,
        roq=recommended_order_qty if urgency >= 2 else 0.0,
        order_by_date=timing["order_by_date"],
        stockout_date=timing["stockout_date"],
        days_until_deadline=timing["days_until_deadline"],
        timing_urgency_badge=timing["timing_urgency_badge"],
        timing_urgency_msg=timing["timing_urgency_msg"],
        excess_units=overstock_diag["excess_units"],
        days_over_target=overstock_diag["days_over_target"],
        coverage_limit=coverage_limit,
        receipts_7d=receipts_7d,
        is_new=is_new,
        history_days=history_days,
    )

    method = (
        f"launch baseline ({observations} obs, ABC-{abc_class}, cat CV {inherited_cv:.2f}, LT std {lead_time_std:.1f}d)"
        if is_new else
        f"full-history baseline ({observations} obs, ABC-{abc_class}, z={eff_z:.2f})"
    )

    if "units_sold_raw" in group.columns:
        missing_raw = int(group["units_sold_raw"].isna().sum())
        imputed = int((group["units_sold_raw"].isna() & group["units_sold"].notna()).sum())
    else:
        missing_raw = int(group["units_sold"].isna().sum()) if "units_sold" in group.columns else 0
        imputed = 0

    return {
        "sku_id": sku_id,
        "category": cat_clean,
        "category_key": cat_key,
        "abc_class": abc_class,
        "history_days": history_days,
        "observations": observations,
        "is_new": is_new,
        "method": method,
        "stock": stock,
        "daily_demand": daily_demand,
        "forward_lead_demand": forward_lead_demand,
        "dow_multiplier": dow_multiplier,
        "ewma_demand": ewma_latest,
        "full_median": full_median,
        "recent_mean": recent_mean,
        "prior_mean": prior_mean,
        "trend_pct": trend_pct,
        "volatility": volatility,
        "cv": cv,
        "lead_time": lead_time,
        "lead_time_std": lead_time_std,
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "days_coverage": days_coverage,
        "hours_coverage": round(days_coverage * 24, 1),
        "roq": recommended_order_qty if urgency >= 2 else 0.0,
        "order_up_to": order_up_to,
        "receipts_7d": receipts_7d,
        "coverage_limit": coverage_limit,
        "missing_raw": missing_raw,
        "imputed": imputed,
        "bucket": bucket,
        "urgency": urgency,
        "flag_type": flag_type,
        "risk_score": risk_score,
        "severity": severity,
        # Exact order timing fields
        "days_to_stockout": timing["days_to_stockout"],
        "stockout_date": timing["stockout_date"],
        "order_by_date": timing["order_by_date"],
        "days_until_deadline": timing["days_until_deadline"],
        "timing_urgency_badge": timing["timing_urgency_badge"],
        "timing_urgency_msg": timing["timing_urgency_msg"],
        "timing_color": timing["timing_color"],
        # Overstock diagnostics fields
        "excess_units": overstock_diag["excess_units"],
        "days_over_target": overstock_diag["days_over_target"],
        "overstock_action_playbook": overstock_diag["overstock_action_playbook"],
        # Diagnostic narrative
        "what_happened": what_happened,
    }
