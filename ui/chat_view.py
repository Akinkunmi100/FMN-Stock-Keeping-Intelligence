"""The analyst question view, used both as a page and inside other views."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ai.grounding import answer_agentic_question


# ─────────────────────────────────────────────────────────────────────────────
# REUSABLE INLINE ANALYST (embeddable in any view via st.expander)
# ─────────────────────────────────────────────────────────────────────────────

def render_inline_analyst(
    scores: pd.DataFrame,
    context_key: str,
    default_query: str = "",
    placeholder: str = "Ask about stock, deadlines, or a specific SKU...",
) -> None:
    """
    Render a compact question box inside an expander.

    Each call site passes a unique `context_key` (e.g. "attention_queue",
    "sku_detail_SKU-1010") so its chat history lives in its own session
    state slot and doesn't collide with other instances.
    """
    state_key = f"inline_chat_{context_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = []

    with st.expander("Ask about this data", expanded=False):
        st.caption("The answer is based on the current scored data, not a general stock recommendation.")

        # Display existing messages
        for msg in st.session_state[state_key]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        query = st.chat_input(placeholder, key=f"inline_input_{context_key}")

        if query:
            st.session_state[state_key].append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("Checking the matching inventory data..."):
                    response = answer_agentic_question(query, scores, st.session_state[state_key])
                    st.markdown(response.text)
                    if response.warning:
                        st.caption(response.warning)
                    st.session_state[state_key].append({"role": "assistant", "content": response.text})


# ─────────────────────────────────────────────────────────────────────────────
# FULL-PAGE DEDICATED CHAT VIEW
# ─────────────────────────────────────────────────────────────────────────────

def render_chat_view(scores: pd.DataFrame) -> None:
    """Render the full-page question-and-answer view."""
    st.markdown("### Ask about the inventory data")
    st.caption("Ask about a SKU, a category, or the attention queue. The app looks up the relevant rows before it answers.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": (
                    "Try asking which SKUs need attention, why a SKU is flagged, or how much stock the app suggests ordering."
                ),
            }
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. QUICK SUGGESTION CHIPS
    # ─────────────────────────────────────────────────────────────────────────
    # SKU references are drawn from the live scores DataFrame rather than
    # hardcoded, so a chip never asks about a SKU that isn't actually in its
    # claimed state in the current data (e.g. "why is X flagged" for a SKU
    # that's actually on track this run).
    flagged_skus = scores[scores["urgency"] > 0]
    example_flagged = flagged_skus.iloc[0]["sku_id"] if not flagged_skus.empty else scores.iloc[0]["sku_id"]
    on_track_skus = scores[scores["bucket"] == "On track"]
    example_order_qty = on_track_skus.iloc[0]["sku_id"] if not on_track_skus.empty else scores.iloc[-1]["sku_id"]

    st.markdown("<div class='eyebrow'>Quick Questions</div>", unsafe_allow_html=True)
    c_chip1, c_chip2, c_chip3, c_chip4 = st.columns(4)
    with c_chip1:
        if st.button("Which SKUs need attention?", width="stretch"):
            st.session_state.user_query = "Which SKUs need attention this week?"
    with c_chip2:
        if st.button(f"Why is {example_flagged} flagged?", width="stretch"):
            st.session_state.user_query = f"Why is {example_flagged} flagged?"
    with c_chip3:
        if st.button("Show highest-volume items at risk", width="stretch"):
            st.session_state.user_query = "Show top priority items at risk"
    with c_chip4:
        if st.button(f"Suggested order for {example_order_qty}", width="stretch"):
            st.session_state.user_query = f"How much to order for {example_order_qty}?"

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CHAT HISTORY DISPLAY
    # ─────────────────────────────────────────────────────────────────────────
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ─────────────────────────────────────────────────────────────────────────
    # 3. CHAT INPUT HANDLING
    # ─────────────────────────────────────────────────────────────────────────
    query = st.chat_input("Ask about stock, deadlines, or a specific SKU...")
    if "user_query" in st.session_state and st.session_state.user_query:
        query = st.session_state.user_query
        st.session_state.user_query = None

    if query:
        st.session_state.chat_messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("Checking the matching inventory data..."):
                response = answer_agentic_question(query, scores, st.session_state.chat_messages)
                st.markdown(response.text)
                if response.warning:
                    st.caption(response.warning)
                st.session_state.chat_messages.append({"role": "assistant", "content": response.text})
