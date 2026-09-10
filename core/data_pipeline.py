"""
core/data_pipeline.py — Data Ingestion, Sanitization & Feature Engineering
==========================================================================
Handles loading raw supply chain CSV datasets, deduplicating records,
sanitizing lead times, applying bounded linear interpolation for missing demand,
computing ABC Pareto classifications, and estimating day-of-week seasonality.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import (
    ABC_THRESHOLDS,
    MIN_HISTORY_DAYS_ESTABLISHED,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. TEXT & CATEGORY NORMALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def normalize_category_key(value: Any) -> str:
    """
    Standardize category labels into consistent lowercase tokens.
    Removes extraneous spaces and trailing characters (e.g. 'Dairy ' -> 'dairy').
    """
    cleaned = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return cleaned if cleaned else "uncategorized"


# ─────────────────────────────────────────────────────────────────────────────
# 2. DEDUPLICATION & SANITIZATION
# ─────────────────────────────────────────────────────────────────────────────

def clean_and_deduplicate(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate multiple records recorded for the same (sku_id, date) pair.
    
    Aggregation Rules:
    - units_sold: Sum of reported transactions.
    - units_received: Sum of incoming shipments.
    - closing_stock: Most recent closing inventory (last observation).
    - lead_time_days: First reported supplier lead time.
    - category: Preserves the primary category name.
    """
    df = raw_df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    # Enforce numeric types and handle non-numeric artifacts gracefully
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce")
    df["units_received"] = pd.to_numeric(df["units_received"], errors="coerce").fillna(0.0)
    df["closing_stock"] = pd.to_numeric(df["closing_stock"], errors="coerce")
    df["lead_time_days"] = pd.to_numeric(df["lead_time_days"], errors="coerce")

    # Aggregate duplicates
    agg_rules = {
        "units_sold": "sum",
        "units_received": "sum",
        "closing_stock": "last",
        "lead_time_days": "first",
        "category": "first",
    }
    deduped = df.groupby(["sku_id", "date"], as_index=False).agg(agg_rules)
    deduped = deduped.sort_values(["sku_id", "date"]).reset_index(drop=True)
    return deduped


# ─────────────────────────────────────────────────────────────────────────────
# 3. GAP IMPUTATION & INTERPOLATION
# ─────────────────────────────────────────────────────────────────────────────

def interpolate_demand_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply short-bounded linear interpolation to fill short observation gaps (<= 2 days).
    
    Important Safeguard:
    - We NEVER interpolate outside known dates (no extrapolation at boundaries).
    - Long gaps (> 2 consecutive missing days) remain NaN to avoid creating fake demand.
    - Preserves raw values in 'units_sold_raw' for auditing data lineage.
    """
    df = df.copy()
    df["category_key"] = df["category"].map(normalize_category_key)
    df["category_clean"] = df["category_key"].map(lambda x: x.title())
    df["units_sold_raw"] = df["units_sold"].copy()

    # Interpolate bounded gaps inside the series per SKU
    df["units_sold"] = (
        df.groupby("sku_id", group_keys=False)["units_sold_raw"]
        .apply(lambda s: s.interpolate(limit=2, limit_direction="both", limit_area="inside"))
        .reset_index(level=0, drop=True)
    )
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. LEAD TIME SANITIZATION
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_lead_times(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize supplier lead time values:
    - Lead times must fall within realistic physical bounds (1 to 60 days).
    - Missing or outlier values are imputed using the SKU's median lead time.
    - If a SKU has no valid lead time history, fallback to the global dataset median.
    """
    df = df.copy()
    valid_mask = df["lead_time_days"].between(1, 60)
    global_lead_median = float(df.loc[valid_mask, "lead_time_days"].median()) if valid_mask.any() else 7.0

    df["lead_time_valid"] = valid_mask
    df["lead_time_used"] = df["lead_time_days"].where(valid_mask)
    df["lead_time_used"] = df.groupby("sku_id")["lead_time_used"].transform(lambda s: s.fillna(s.median()))
    df["lead_time_used"] = df["lead_time_used"].fillna(global_lead_median)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 5. ABC PARETO CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_abc_pareto(df: pd.DataFrame) -> dict[str, str]:
    """
    Perform 80/20 Pareto classification based on total unit sales volume:
    - Class A: Top 70% cumulative volume (high-priority revenue drivers).
    - Class B: Next 20% cumulative volume (moderate volume).
    - Class C: Bottom 10% cumulative volume (slow-moving or niche items).
    """
    total_volume_per_sku = df.groupby("sku_id")["units_sold"].sum().sort_values(ascending=False)
    total_market_volume = total_volume_per_sku.sum()

    if total_market_volume <= 0:
        return {str(sku): "B" for sku in total_volume_per_sku.index}

    cum_share = total_volume_per_sku.cumsum() / total_market_volume
    abc_map: dict[str, str] = {}

    for sku_id, share in cum_share.items():
        if share <= ABC_THRESHOLDS["A"] or len(abc_map) == 0:
            abc_map[str(sku_id)] = "A"
        elif share <= ABC_THRESHOLDS["B"]:
            abc_map[str(sku_id)] = "B"
        else:
            abc_map[str(sku_id)] = "C"

    return abc_map


# ─────────────────────────────────────────────────────────────────────────────
# 6. CYCLICAL DAY-OF-WEEK SEASONALITY
# ─────────────────────────────────────────────────────────────────────────────

def compute_dow_seasonality(df: pd.DataFrame) -> dict[int, float]:
    """
    Compute day-of-week (DOW) multiplicative seasonal indices (0 = Monday, 6 = Sunday).
    
    Formula:
        Multiplier(dow) = Mean_Sales(dow) / Overall_Mean_Sales
    """
    df = df.copy()
    df["dow"] = df["date"].dt.dayofweek
    valid_sales = df["units_sold"].dropna()
    mean_overall_sales = float(valid_sales.mean()) if not valid_sales.empty else 1.0

    dow_multipliers: dict[int, float] = {}
    for dow, group in df.groupby("dow"):
        v = group["units_sold"].dropna()
        if not v.empty and mean_overall_sales > 0:
            dow_multipliers[int(dow)] = float(v.mean() / mean_overall_sales)
        else:
            dow_multipliers[int(dow)] = 1.0

    return dow_multipliers


# ─────────────────────────────────────────────────────────────────────────────
# 7. CATEGORY PRIORS (CV & KURTOSIS)
# ─────────────────────────────────────────────────────────────────────────────

def compute_category_priors(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    """
    Compute empirical category-level prior distributions from mature, established SKUs.
    
    Outputs:
    - category_cv: Median coefficient of variation (CV) used for cold-start ramp-up SKUs.
    - category_kurt: Excess kurtosis used to calculate heavy-tail safety stock buffers.
    """
    category_cv: dict[str, float] = {}
    category_kurt: dict[str, float] = {}

    for cat_key, cat_group in df.groupby("category_key"):
        cat_valid_cv: list[float] = []
        cat_all_sales: list[float] = []

        for _sku, sku_g in cat_group.groupby("sku_id"):
            sku_g = sku_g.sort_values("date")
            days_history = int((sku_g["date"].max() - sku_g["date"].min()).days + 1)
            
            # Only use mature SKUs with >= 56 days of data for baseline priors
            if days_history >= MIN_HISTORY_DAYS_ESTABLISHED:
                v = sku_g["units_sold"].dropna()
                if len(v) > 1 and v.mean() > 0:
                    cat_valid_cv.append(float(v.std(ddof=1) / v.mean()))
                    cat_all_sales.extend(v.tolist())

        category_cv[str(cat_key)] = float(np.median(cat_valid_cv)) if cat_valid_cv else 0.30
        series = pd.Series(cat_all_sales)
        category_kurt[str(cat_key)] = float(series.kurtosis()) if len(series) > 10 else 1.0

    return category_cv, category_kurt


# ─────────────────────────────────────────────────────────────────────────────
# 8. MASTER PIPELINE LOADER
# ─────────────────────────────────────────────────────────────────────────────

def load_and_prepare_dataset(csv_path: str | Path) -> tuple[
    pd.DataFrame,
    dict[str, str],
    dict[int, float],
    dict[str, float],
    dict[str, float],
]:
    """
    Full data preparation pipeline:
    1. Reads CSV and parses dates
    2. Cleans column names & aggregates duplicates
    3. Interpolates short demand gaps
    4. Sanitizes lead times
    5. Computes ABC Pareto tiers
    6. Computes cyclical seasonality
    7. Computes category statistical priors
    """
    raw = pd.read_csv(csv_path, parse_dates=["date"])
    deduped = clean_and_deduplicate(raw)
    interpolated = interpolate_demand_gaps(deduped)
    sanitized = sanitize_lead_times(interpolated)

    abc_map = compute_abc_pareto(sanitized)
    dow_multipliers = compute_dow_seasonality(sanitized)
    cat_cv, cat_kurt = compute_category_priors(sanitized)

    return sanitized, abc_map, dow_multipliers, cat_cv, cat_kurt
