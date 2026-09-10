"""
core/backtest.py — Rolling-Origin Walk-Forward Backtesting Engine
================================================================
Empirical validation engine that evaluates the early warning model's performance
across the entire historical dataset without lookahead data leakage.

Evaluates whether an 'Order Soon' alert was triggered ahead of an actual stockout
occurring within the supplier lead-time horizon.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config import SERVICE_LEVEL_Z


def run_historical_backtest(raw: pd.DataFrame, abc_map: dict[str, str]) -> dict[str, Any]:
    """
    Execute a vectorized walk-forward simulation across historical dates and SKUs.
    
    Data Leakage Prevention:
    - At each date t, rolling demand and volatility are calculated strictly on data
      available up to t-1 (using `.shift(1)`).
      
    Target Event:
    - Actual Stockout = Minimum closing stock within the future lead-time horizon <= 0.
    
    Model Signal:
    - Predicted Alert = Closing stock <= Reorder Point OR Days Coverage <= Lead Time.
    """
    results: list[dict[str, int]] = []
    
    for sku, g in raw.groupby("sku_id"):
        g = g.sort_values("date").reset_index(drop=True)
        if len(g) < 28:
            continue
            
        lt = max(1, int(g["lead_time_days"].median()))
        sku_abc = abc_map.get(str(sku), "B")
        z_factor = SERVICE_LEVEL_Z.get(sku_abc, 1.65)
        
        # Rolling demand & volatility estimates (lagged by 1 day to prevent leakage)
        roll_med = g["units_sold"].shift(1).rolling(28, min_periods=14).median()
        roll_ewm = g["units_sold"].shift(1).ewm(span=max(7, lt), min_periods=7).mean()
        roll_demand = (0.60 * roll_med + 0.40 * roll_ewm).clip(lower=0.10)
        roll_std = g["units_sold"].shift(1).rolling(28, min_periods=14).std(ddof=1).fillna(roll_demand * 0.25)
        
        lt_std = float(g["lead_time_days"].std(ddof=1)) if g["lead_time_days"].nunique() > 1 else 0.0
        ss = z_factor * np.sqrt(lt * (roll_std ** 2) + (roll_demand ** 2) * (lt_std ** 2))
        rop = roll_demand * lt + ss
        
        flagged = (g["closing_stock"] <= rop) | (g["closing_stock"] / roll_demand <= lt)
        
        # Future minimum stock within the lead time horizon (excluding current day)
        future_min = g["closing_stock"].iloc[::-1].rolling(lt, min_periods=1).min().iloc[::-1].shift(-lt)
        future_stockout = future_min <= 0
        
        valid = roll_demand.notna() & future_min.notna()
        f = flagged[valid]
        s = future_stockout[valid]
        
        results.append({
            "tp": int((f & s).sum()),
            "fp": int((f & ~s).sum()),
            "fn": int((~f & s).sum()),
            "tn": int((~f & ~s).sum()),
        })
    
    res_df = pd.DataFrame(results)
    tp = int(res_df["tp"].sum()) if not res_df.empty else 0
    fp = int(res_df["fp"].sum()) if not res_df.empty else 0
    fn = int(res_df["fn"].sum()) if not res_df.empty else 0
    tn = int(res_df["tn"].sum()) if not res_df.empty else 0
    
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / total if total > 0 else 0.0
    false_alarm_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total_evaluations": total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "false_alarm_rate": false_alarm_rate,
    }
