"""
core/demand_model.py — Mathematical Demand Estimation & Seasonality Modeling
============================================================================
Provides statistical functions for:
1. Censored demand correction (filtering zero-stock days to prevent underforecasting)
2. Robust baseline velocity estimation (blending median and EWMA)
3. Cyclical day-of-week seasonality forward projection over lead-time horizons
4. Short-term trend acceleration detection
5. Demand volatility and coefficient of variation (CV) calculations
"""

from __future__ import annotations

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# 1. CENSORED DEMAND CORRECTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_uncensored_demand(sku_history: pd.DataFrame) -> pd.Series:
    """
    Filter historical demand to remove stockout-induced demand censoring.
    
    Why this is critical:
    When on-hand stock hits zero (closing_stock <= 0), observed sales drop to zero
    not because customer demand disappeared, but because there was nothing to sell.
    Treating these days as zero demand creates a severe negative bias.
    
    If at least 14 days of positive-stock history exist, we anchor velocity on
    positive-stock days. Otherwise, we use all recorded sales to ensure stability.
    """
    positive_stock_mask = sku_history["closing_stock"] > 0
    positive_stock_days = sku_history[positive_stock_mask]

    if len(positive_stock_days) >= 14:
        return positive_stock_days["units_sold"].dropna()
    return sku_history["units_sold"].dropna()


# ─────────────────────────────────────────────────────────────────────────────
# 2. BLENDED VELOCITY ESTIMATION (MEDIAN + EWMA)
# ─────────────────────────────────────────────────────────────────────────────

def estimate_baseline_velocity(
    demand_series: pd.Series,
    lead_time: float,
) -> tuple[float, float, float]:
    """
    Calculate an unconstrained baseline daily sales velocity by blending:
    - 60% Full-history median (robust against temporary one-off purchase spikes)
    - 40% Exponentially Weighted Moving Average (EWMA, agile to persistent trend shifts)
    
    Returns:
        (blended_daily_demand, full_median, ewma_latest)
    """
    n = len(demand_series)
    if n >= 2:
        full_median = float(demand_series.median())
        ewma_span = max(7, int(round(lead_time)))
        ewma_series = demand_series.ewm(span=ewma_span, min_periods=1).mean()
        ewma_latest = float(ewma_series.iloc[-1])
        blended = 0.60 * full_median + 0.40 * ewma_latest
        daily_demand = max(0.1, blended)
    elif n == 1:
        full_median = float(demand_series.iloc[0])
        ewma_latest = full_median
        daily_demand = max(0.1, full_median)
    else:
        full_median = 0.0
        ewma_latest = 0.0
        daily_demand = 0.1

    return daily_demand, full_median, ewma_latest


# ─────────────────────────────────────────────────────────────────────────────
# 3. DEMAND VOLATILITY & COEFFICIENT OF VARIATION (CV)
# ─────────────────────────────────────────────────────────────────────────────

def compute_demand_volatility(
    demand_series: pd.Series,
    daily_demand: float,
) -> tuple[float, float]:
    """
    Calculate sample standard deviation of demand (ddof=1) and
    the coefficient of variation (CV = sigma / mu).
    """
    if len(demand_series) > 1:
        volatility = float(demand_series.std(ddof=1))
    else:
        volatility = daily_demand * 0.25  # Sensible 25% default prior

    cv = volatility / daily_demand if daily_demand > 0 else 0.30
    return volatility, cv


# ─────────────────────────────────────────────────────────────────────────────
# 4. FORWARD SEASONAL PROJECTION OVER LEAD TIME
# ─────────────────────────────────────────────────────────────────────────────

def project_forward_lead_demand(
    daily_demand: float,
    lead_time: float,
    last_dow: int,
    dow_multipliers: dict[int, float],
) -> tuple[float, float]:
    """
    Project total expected demand over the upcoming lead-time duration by summing
    day-of-week multipliers for each calendar day of the lead-time window.
    
    Example:
    If lead time is 7 days starting from Wednesday, the forecast will directly
    incorporate the high Wednesday demand spike and weekend dips.
    
    Returns:
        (forward_lead_demand, avg_forward_dow_factor)
    """
    lt_days = max(1, int(round(lead_time)))
    
    # Sum multipliers for the next lt_days calendar days
    dow_sum = sum(dow_multipliers.get((last_dow + k + 1) % 7, 1.0) for k in range(lt_days))
    avg_factor = dow_sum / lt_days
    forward_lead_demand = daily_demand * dow_sum

    return forward_lead_demand, avg_factor


# ─────────────────────────────────────────────────────────────────────────────
# 5. DEMAND ACCELERATION & TREND DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def compute_demand_trend(
    demand_series: pd.Series,
    lead_time: float,
    daily_demand: float,
) -> tuple[float, float, float]:
    """
    Detect recent demand trend shifts by comparing the most recent window
    against the immediately preceding baseline window.
    
    Window size scales dynamically with supplier lead time: max(7, round(lead_time)).
    
    Returns:
        (trend_pct, recent_mean, prior_mean)
    """
    trend_window = max(7, int(round(lead_time)))
    n = len(demand_series)

    recent = demand_series.tail(min(trend_window, n))
    prior_source = demand_series.iloc[max(0, n - 2 * trend_window) : max(0, n - trend_window)]
    prior = prior_source if len(prior_source) > 0 else demand_series.head(min(trend_window, n))

    recent_mean = float(recent.mean()) if len(recent) > 0 else daily_demand
    prior_mean = float(prior.mean()) if len(prior) > 0 else daily_demand
    trend_pct = (recent_mean - prior_mean) / max(prior_mean, 0.1)

    return trend_pct, recent_mean, prior_mean
