"""Streamlit entry point for the Signal supply-chain review tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Configuration and data pipeline
from config import DATA_PATH, DEFAULT_GROQ_MODEL

from core.backtest import run_historical_backtest
from core.data_pipeline import load_and_prepare_dataset
from core.inventory_engine import score_sku_inventory

from ai.grounding import explain_sku
from ai.llm_client import LLMResult

from ui.attention_queue import render_attention_queue
from ui.backtest_view import render_backtest_view
from ui.chat_view import render_chat_view
from ui.hero import render_hero_banner
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
        page_title="Signal - Supply chain early warning",
        page_icon="◌",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Apply the shared visual style.
    st.markdown(get_application_css(), unsafe_allow_html=True)

    # Load and score the current dataset.
    raw, scores, meta = load_and_score(str(DATA_PATH))

    # Keep navigation and definitions together in the sidebar.
    with st.sidebar:
        st.markdown("<div class='eyebrow'>SIGNAL / 01</div>", unsafe_allow_html=True)
        st.markdown("### Inventory early warning")
        st.caption("Review stock risk, see why a SKU is flagged, and decide what to check next.")
        st.divider()

        workspace_view = st.radio(
            "Go to",
            [
                "Attention queue",
                "SKU detail",
                "Model validation & backtest",
                "Ask the analyst",
            ],
            label_visibility="collapsed",
        )
        st.divider()

        st.markdown("<div class='eyebrow'>Data in use</div>", unsafe_allow_html=True)
        st.caption(f"{meta['date_min']} → {meta['date_max']}")
        st.caption(f"{len(scores)} SKUs · {meta['rows']:,} daily records")
        st.caption(
            f"Priority classes: {meta['abc_distribution'].get('A', 0)} A · "
            f"{meta['abc_distribution'].get('B', 0)} B · {meta['abc_distribution'].get('C', 0)} C"
        )
        st.caption("Risk uses stock coverage, demand changes, lead time, and a safety buffer.")

        st.divider()

        with st.expander("Assistant details"):
            st.markdown(
                f"The assistant uses Groq model `{DEFAULT_GROQ_MODEL}` when a key is configured. "
                "It receives the numbers retrieved for the question and does not decide the risk status. "
                "Without a key, the app uses a local evidence summary instead."
            )

        with st.expander("For developers"):
            st.markdown(
                "Run `streamlit run app.py` locally. For deployment steps and environment variables, "
                "see the README."
            )

        with st.expander("What the model does not include"):
            st.markdown(
                "Open purchase orders, supplier reliability, promotions, holidays, "
                "substitution between products, minimum order quantities, and shelf life."
            )

    # Show the portfolio summary, then render the selected workspace.
    render_hero_banner(meta, scores)

    if workspace_view == "Attention queue":
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
        f"Signal · Data from {meta['date_min']} to {meta['date_max']} · "
        f"{meta['rows']:,} daily records · Groq assistant with local fallback."
        f"</div>",
        unsafe_allow_html=True,
    )


# Automatically execute UI when running in Streamlit runtime
if st.runtime.exists():
    run_app()
