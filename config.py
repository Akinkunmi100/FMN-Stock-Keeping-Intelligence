"""
config.py — Central Configuration & Operational Constants
=========================================================
Defines all business rules, mathematical constants, service-level targets,
color palettes, and system configurations for the Supply Chain Early Warning System.

This central configuration ensures all modules reference a single source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# 1. DIRECTORY & FILE PATHS
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "project1_supply_chain_demand.csv"

# ─────────────────────────────────────────────────────────────────────────────
# 2. ABC PARETO CLASSIFICATION THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
# Cumulative volume thresholds for Pareto triage
ABC_THRESHOLDS = {
    "A": 0.70,  # Top 70% of cumulative unit sales volume (Mission-Critical)
    "B": 0.90,  # Next 20% of sales volume (Moderate Priority)
    "C": 1.00,  # Bottom 10% of sales volume (Low Priority / Tail)
}

# Target cycle service levels and standard normal z-scores by ABC tier
SERVICE_LEVEL_Z = {
    "A": 2.05,  # 98.0% Cycle Service Level (minimizes costly factory downtime)
    "B": 1.65,  # 95.0% Cycle Service Level
    "C": 1.28,  # 90.0% Cycle Service Level
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. INVENTORY POLICY & THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
# 56 days = 8 full weekly cycles. Below that, a per-SKU CV/variance estimate
# is dominated by whichever 1-2 unusual days happened to land in the window;
# 8 cycles is the point where day-of-week noise starts averaging out enough
# to trust the estimate for safety-stock sizing. See docs/DECISIONS.md.
MIN_HISTORY_DAYS_ESTABLISHED = 56  # Minimum recorded days to qualify as established SKU

# Observed supplier lead times in this dataset range 3-14 days (median 7).
# ESTABLISHED_COVERAGE_LIMIT = 2x the longest observed lead time (14d): a
# full extra replenishment cycle of buffer is allowed to sit as working
# capital before it's flagged as overstock, on the (established-SKU) belief
# that current demand velocity is trustworthy.
# NEW_SKU_COVERAGE_LIMIT is tighter (1.5x the max lead time, not 2x) because
# a new SKU's velocity estimate rests on ~2 weeks of data and isn't equally
# trustworthy — an unnecessary overstock review a few days early costs far
# less than discovering 2 full cycles of capital tied up in an item whose
# early demand read turns out to be wrong.
NEW_SKU_COVERAGE_LIMIT = 21.0      # Maximum target days of supply for ramp-up SKUs
ESTABLISHED_COVERAGE_LIMIT = 28.0  # Maximum target days of supply for established SKUs

# Demand trend lookback window
MIN_TREND_WINDOW_DAYS = 7
# Per-SKU CV in this dataset typically runs ~0.25-0.37 (daily-level noise).
# For a windowed mean of >=7 days, that implies a standard error on the
# windowed mean of roughly CV/sqrt(7) ~= 10-14%. A 15% shift is just past
# one standard error of that noise floor — enough to be a real signal
# rather than day-to-day jitter, while still loose on purpose: this only
# drives "Monitor closely" (urgency=1, no order forced), so a false
# positive here just means an operator glances at a SKU one extra time.
DEMAND_SURGE_THRESHOLD_PCT = 0.15  # 15% demand acceleration triggers proactive monitor flag

# ─────────────────────────────────────────────────────────────────────────────
# 4. RISK SCORING & SEVERITY MAPPING
# ─────────────────────────────────────────────────────────────────────────────
# Weights for the 0–100 multi-factor composite risk index
RISK_WEIGHTS = {
    "coverage_depletion": 35.0,  # Stock depletion relative to lead time
    "demand_acceleration": 25.0, # Rapid upward movement in sales rate
    "demand_volatility": 20.0,   # Coefficient of variation (CV) uncertainty
    "reorder_proximity": 20.0,   # Proximity of on-hand inventory to ROP
}

# Multipliers adjusting overall risk score based on ABC importance
ABC_RISK_MULTIPLIERS = {
    "A": 1.15,  # Amplified urgency for top-selling volume drivers
    "B": 1.00,  # Baseline
    "C": 0.85,  # Dampened urgency for slow-moving tail SKUs
}

# Categorical severity cutoffs for the 0-100 composite risk score.
# 50/30 roughly quarter the scale, reserving the top half for anything
# already inside its reorder window (coverage_depletion is the single
# heaviest weight at 35%, so it dominates once a SKU crosses that line).
# KNOWN CALIBRATION GAP: on this dataset, a SKU that is already OVERDUE
# with same-day stockout (e.g. SKU-1010: 0.6 days coverage, order-by date
# already passed) still only scores ~74 and lands in "High," not
# "Critical" — the 75 cutoff is calibrated tighter than the worst cases
# actually seen. Left as-is rather than silently lowered, since changing
# it changes which SKUs are labeled Critical throughout the app and export;
# flagged here and in docs/DECISIONS.md rather than fixed unilaterally.
SEVERITY_THRESHOLDS = {
    "Critical": 75.0,  # Immediate stockout risk or broken safety stock
    "High": 50.0,      # Urgent replenishment planning needed
    "Medium": 30.0,    # Approaching reorder boundary, monitor closely
    "Low": 0.0,        # Healthy stock posture
}

# ─────────────────────────────────────────────────────────────────────────────
# 5. UI BRANDING, TYPOGRAPHY & COLOR SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
# Functional color system — every color here encodes a specific operational
# meaning (severity, ABC tier) and is used exactly where that meaning applies.
# No decorative/accent colors that exist purely for visual flourish.
COLORS = {
    # Severity & Risk Colors
    "critical": "#B3261E",
    "critical_bg": "#FBEAE9",
    "high": "#B0530A",
    "high_bg": "#FCF1E4",
    "medium": "#8A6D00",
    "medium_bg": "#FBF6DE",
    "low": "#1E6B42",
    "low_bg": "#E7F3EC",
    "overstock": "#2E5C8A",
    "overstock_bg": "#E9F0F7",

    # ABC Tier Colors
    "abc_a": "#1E6B42",
    "abc_b": "#8A6D00",
    "abc_c": "#5B6560",

    # Core Theme Palette
    "ink": "#1C2420",       # Deep charcoal — primary text and headers
    "paper": "#F5F6F3",     # Off-white page background
    "card_bg": "#FFFFFF",
    "line": "#DEE3DD",      # Border grey
    "muted": "#5B6560",     # Secondary text grey
    "chart_series": "#4A7A87",  # Neutral slate-teal for non-severity chart series (demand line, etc.)
}

# ─────────────────────────────────────────────────────────────────────────────
# 6. AI & GROQ CLIENT CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
]
GROQ_TEMPERATURE = 0.1  # Low temperature for deterministic, factual outputs
GROQ_MAX_TOKENS = 650

# ─────────────────────────────────────────────────────────────────────────────
# 7. NOTIFICATION & MONITORING DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────
ALERT_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "smtp_user": os.getenv("SMTP_USER", ""),
    "smtp_password": os.getenv("SMTP_PASSWORD", ""),
    "email_recipients": [e.strip() for e in os.getenv("ALERT_RECIPIENTS", "").split(",") if e.strip()],
    "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
    "teams_webhook_url": os.getenv("TEAMS_WEBHOOK_URL", ""),
    "generic_webhook_url": os.getenv("GENERIC_WEBHOOK_URL", ""),
}
