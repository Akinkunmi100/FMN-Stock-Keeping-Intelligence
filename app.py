"""
app.py — Signal / Supply Chain Control Room (Main Entry Point)
==============================================================
Slim, modular application wiring together the core data pipeline,
mathematical inventory engine, AI diagnostic assistant, and interactive UI views.

Architecture:
- config.py: Central operational thresholds, service level z-scores, and color palette
- core/: Data sanitization, stochastic safety stock, backtest simulation, and alerts
- ai/: Free-tier Groq LLM client (Llama-3.3-70B), evidence grounding, and conversational Q&A
- ui/: Streamlit components, Plotly interactive visualizations, and CSS design system
- monitor.py: Standalone scheduled CLI alert dispatcher
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Central Configuration
from config import DATA_PATH

# Core Analytics Engines
from core.backtest import run_historical_backtest
from core.data_pipeline import load_and_prepare_dataset
from core.inventory_engine import score_sku_inventory

# AI Diagnostic Engine
from ai.grounding import answer_agentic_question, explain_sku
from ai.llm_client import LLMResult

# UI Visual Components
from ui.attention_queue import render_attention_queue
from ui.backtest_view import render_backtest_view
from ui.chat_view import render_chat_view
from ui.hero import render_hero_banner, render_kpi_cards
from ui.sku_detail import render_sku_detail
from ui.styles import get_application_css


# ─────────────────────────────────────────────────────────────────────────────
# 1. CACHED MASTER DATA PIPELINE & SCORING
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_and_score(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    Load raw CSV, run data sanitization, compute ABC classifications and seasonality,
    score all SKUs with stochastic safety stock, and run historical backtesting.
    
    Returns:
        (raw_clean_df, scored_skus_df, metadata_dict)
    """
    sanitized, abc_map, dow_multipliers, cat_cv, cat_kurt = load_and_prepare_dataset(path)

    records: list[dict[str, Any]] = []
    for sku, group in sanitized.groupby("sku_id", sort=True):
        sku_abc = abc_map.get(str(sku), "B")
        sku_score = score_sku_inventory(
            sku_id=str(sku),
            sku_group=group,
            abc_class=sku_abc,
            dow_multipliers=dow_multipliers,
            cat_cv=cat_cv,
            cat_kurt=cat_kurt,
        )
        records.append(sku_score)

    scores = pd.DataFrame(records).sort_values(
        ["urgency", "risk_score", "days_coverage"],
        ascending=[False, False, True]
    ).reset_index(drop=True)

    # Historical walk-forward backtest
    backtest_metrics = run_historical_backtest(sanitized, abc_map)

    metadata: dict[str, Any] = {
        "date_min": sanitized["date"].min().date(),
        "date_max": sanitized["date"].max().date(),
        "rows": len(sanitized),
        "raw_missing": int(sanitized["units_sold_raw"].isna().sum()),
        "imputed": int((sanitized["units_sold_raw"].isna() & sanitized["units_sold"].notna()).sum()),
        "excluded": int((sanitized["units_sold_raw"].isna() & sanitized["units_sold"].isna()).sum()),
        "categories": sorted(scores["category"].unique().tolist()),
        "abc_distribution": pd.Series(abc_map).value_counts().to_dict(),
        "backtest": backtest_metrics,
        "dow_multipliers": dow_multipliers,
    }

    return sanitized, scores, metadata


# Expose explain function for backward compatibility
def explain(row: pd.Series) -> LLMResult:
    """Generate a diagnostic explanation for an individual SKU."""
    return explain_sku(row)


# ─────────────────────────────────────────────────────────────────────────────
# 2. STREAMLIT APPLICATION ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_app() -> None:
    """Launch the interactive Streamlit dashboard."""
    st.set_page_config(
        page_title="Signal / Supply Chain Control Room",
        page_icon="◌",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Inject custom design stylesheet
    st.markdown(get_application_css(), unsafe_allow_html=True)

    # Load data and run analytical pipeline
    raw, scores, meta = load_and_score(str(DATA_PATH))

    # Sidebar Navigation & Knowledge Panels
    with st.sidebar:
        st.markdown("<div class='eyebrow'>SIGNAL / 01</div>", unsafe_allow_html=True)
        st.markdown("### Early Warning Control")
        st.caption("Production replenishment triage, ABC analysis, stochastic lead time & rolling backtesting.")
        st.divider()

        workspace_view = st.radio(
            "Workspace View",
            [
                "Attention queue",
                "SKU detail",
                "Model validation & backtest",
                "Ask the analyst",
            ],
            label_visibility="collapsed",
        )
        st.divider()

        st.markdown("<div class='eyebrow'>Dataset Overview</div>", unsafe_allow_html=True)
        st.caption(f"{meta['date_min']} → {meta['date_max']}")
        st.caption(f"{len(scores)} SKUs tracked · {meta['rows']:,} records")
        st.caption(
            f"ABC Distribution: {meta['abc_distribution'].get('A', 0)} Class A · "
            f"{meta['abc_distribution'].get('B', 0)} Class B · {meta['abc_distribution'].get('C', 0)} Class C"
        )
        st.caption("Engine: Stochastic Lead Time ($\\sigma_L$) + DOW Seasonality + Leptokurtic Safety Buffer.")

        st.divider()

        # Expandable: Free AI Model Information
        with st.expander("🤖 Free AI Model Info"):
            st.markdown(
                "**Powered by Groq Free Tier**\n\n"
                "• Model: `llama-3.3-70b-versatile`\n"
                "• **100% Free**: No credit card required, 1,000 requests/day allowance.\n"
                "• Get free key at: [console.groq.com](https://console.groq.com)\n"
                "• *Note*: The app works completely without any key using deterministic evidence-based fallback."
            )

        # Expandable: App Sharing & Deployment Guide
        with st.expander("🚀 How to Share This App"):
            st.markdown(
                "**Deployment Options:**\n\n"
                "1. **Streamlit Community Cloud (Free)**:\n"
                "   - Push repo to GitHub\n"
                "   - Connect at [share.streamlit.io](https://share.streamlit.io)\n"
                "   - 1-Click public or password-protected URL\n\n"
                "2. **Render.com (Free Tier)**:\n"
                "   - Connect repo, set build command: `pip install -r requirements.txt`\n"
                "   - Start command: `streamlit run app.py --server.port $PORT`\n\n"
                "3. **Docker Container**:\n"
                "   - Built-in `Dockerfile` ready for internal server hosting"
            )

        # Expandable: Significant Unaddressed Prediction Drivers
        with st.expander("⚠️ Critical Missing Signals"):
            st.markdown(
                "**7 Drivers for ERP Integration:**\n\n"
                "1. **Open POs**: In-transit stock is currently invisible.\n"
                "2. **Promotional Calendar**: Planned commercial sales spikes.\n"
                "3. **Supplier Reliability**: Vendor-specific on-time delivery rates.\n"
                "4. **Weather & Festivities**: Holiday FMCG demand multipliers.\n"
                "5. **Cross-SKU Cannibalization**: Product substitution effects.\n"
                "6. **Minimum Order Quantities (MOQ)**: Supplier batch constraints.\n"
                "7. **Shelf Life / Expiration**: Spoilage risk on perishable inventory."
            )

    # Top Hero Banner & Primary Workspace Router
    render_hero_banner(meta, scores)

    if workspace_view == "Attention queue":
        render_kpi_cards(scores)
        render_attention_queue(scores, meta)

    elif workspace_view == "SKU detail":
        render_sku_detail(raw, scores)

    elif workspace_view == "Model validation & backtest":
        render_backtest_view(meta)

    elif workspace_view == "Ask the analyst":
        render_chat_view(scores)

    # Footer
    st.markdown(
        f"<div class='footer-note'>"
        f"Signal Early Warning System · Data: {meta['date_min']} to {meta['date_max']} · "
        f"{meta['rows']:,} rows · Stochastic Lead-Time Variance & DOW Seasonality Enabled · "
        f"Groq Llama-3.3-70B / Local Grounded Engine."
        f"</div>",
        unsafe_allow_html=True,
    )


# Automatically execute UI when running in Streamlit runtime
if st.runtime.exists():
    run_app()

