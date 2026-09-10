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
MIN_HISTORY_DAYS_ESTABLISHED = 56  # Minimum recorded days to qualify as established SKU
NEW_SKU_COVERAGE_LIMIT = 21.0      # Maximum target days of supply for ramp-up SKUs
ESTABLISHED_COVERAGE_LIMIT = 28.0  # Maximum target days of supply for established SKUs

# Demand trend lookback window
MIN_TREND_WINDOW_DAYS = 7
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

# Categorical severity cutoffs for the 0–100 composite risk score
SEVERITY_THRESHOLDS = {
    "Critical": 75.0,  # Immediate stockout risk or broken safety stock
    "High": 50.0,      # Urgent replenishment planning needed
    "Medium": 30.0,    # Approaching reorder boundary, monitor closely
    "Low": 0.0,        # Healthy stock posture
}

# ─────────────────────────────────────────────────────────────────────────────
# 5. UI BRANDING, TYPOGRAPHY & COLOR SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
# Visual language mapping statuses and severities to cohesive colors
COLORS = {
    # Severity & Risk Colors
    "critical": "#E74C3C",  # Vibrant Red
    "critical_bg": "#FDEDEC",
    "high": "#E67E22",      # Energetic Amber/Orange
    "high_bg": "#FEF5E7",
    "medium": "#F1C40F",    # Cautionary Yellow
    "medium_bg": "#FEF9E7",
    "low": "#27AE60",       # Calming Forest Green
    "low_bg": "#EAFAF1",
    "overstock": "#2980B9", # Corporate Cyan/Blue
    "overstock_bg": "#EBF5FB",

    # ABC Tier Colors
    "abc_a": "#1E8449",     # Emerald Green
    "abc_b": "#D4AC0D",     # Mustard Yellow
    "abc_c": "#7F8C8D",     # Slate Grey

    # Core Theme Palette
    "ink": "#17211F",       # Deep Charcoal
    "paper": "#F6F7F3",     # Off-white warm background
    "card_bg": "#FFFFFF",   # Crisp White for cards
    "line": "#DFE5DE",      # Soft border grey
    "muted": "#69736F",     # Muted text grey
    "accent_lime": "#C7EE5C",
    "accent_coral": "#F2A188",
    "accent_blue": "#9ED2DC",
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
