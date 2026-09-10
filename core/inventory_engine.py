"""
core/inventory_engine.py — Safety Stock, ROP, Order Timing & Overstock Analytics
================================================================================
Calculates:
1. Stochastic safety stock combining demand variance and lead-time variance
2. ABC-adjusted Reorder Points (ROP) and Order-Up-To Levels (S)
3. Recommended Order Quantities (ROQ) for procurement
4. Exact replenishment deadlines and order-by dates (answers "when to order")
5. Actionable overstock diagnostics, excess unit calculations, and remediation playbooks
6. Continuous 0–100 multi-factor composite risk scores
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
    tail_multiplier = 1.0 + 0.08 * min(max(0.0, cat_kurtosis - 1.5), 3.0)
    effective_z = base_z * tail_multiplier

    if is_new:
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
    if daily_demand <= 0:
        days_to_stockout = 999
    else:
        days_to_stockout = int(np.floor(stock / daily_demand))

    stockout_date = current_date + timedelta(days=min(days_to_stockout, 365))
    lt_days = max(1, int(round(lead_time)))
    order_by_date = stockout_date - timedelta(days=lt_days)
    
    days_until_deadline = (order_by_date - current_date).days

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
    excess_units = max(0.0, round(stock - order_up_to, 0))
    days_over_target = max(0.0, round(days_coverage - coverage_limit, 1))

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
    coverage_ratio = min(days_coverage / max(lead_time, 1.0), 3.0) / 3.0
    trend_factor = min(abs(trend_pct), 0.50) / 0.50
    volatility_factor = min(cv, 1.0)
    rop_ratio = min(stock / max(reorder_point, 1.0), 2.0) / 2.0
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
# 5. MASTER SKU SCORING ENGINE
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
    history_days = int((group["date"].max() - group["date"].min()).days + 1)
    is_new = history_days < 56
    lead_time = float(group["lead_time_used"].median())
    stock = float(group.iloc[-1]["closing_stock"])
    receipts_7d = float(group.tail(7)["units_received"].sum())
    cat_clean = group.iloc[-1]["category_clean"]
    cat_key = str(group.iloc[-1]["category_key"])
    last_date = group.iloc[-1]["date"].date()
    last_dow = int(group.iloc[-1]["date"].dayofweek)

    # Lead time variability
    lt_series = group["lead_time_days"].dropna()
    lead_time_std = float(lt_series.std(ddof=1)) if lt_series.nunique() > 1 else 0.0

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
    cat_kurtosis = cat_kurt.get(cat_key, 1.0)
    inherited_cv = cat_cv.get(cat_key, 0.30)
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
    days_coverage = min(stock / daily_demand, 999.0) if daily_demand > 0 else 999.0
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

    method = (
        f"launch baseline ({observations} obs, ABC-{abc_class}, cat CV {inherited_cv:.2f}, LT std {lead_time_std:.1f}d)"
        if is_new else
        f"full-history baseline ({observations} obs, ABC-{abc_class}, z={eff_z:.2f})"
    )

    missing_raw = int(group["units_sold_raw"].isna().sum())
    imputed = int((group["units_sold_raw"].isna() & group["units_sold"].notna()).sum())

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
    }
