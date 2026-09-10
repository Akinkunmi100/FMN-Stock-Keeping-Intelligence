"""
ui/chat_view.py — Conversational Supply Chain Q&A Interface
===========================================================
Interactive multi-turn diagnostic chat interface enabling operations leaders
to ask questions about flagged SKUs, categories, Class A items, and procurement quantities.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ai.grounding import answer_agentic_question


def render_chat_view(scores: pd.DataFrame) -> None:
    """Render the conversational diagnostic Q&A interface."""
    st.markdown("### 💬 Ask the Supply Chain Analyst")
    st.caption("Ask natural language questions about SKUs, categories, Class A drivers, or the attention queue. Powered by free Groq Llama-3.3-70B with verified local grounding.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": (
                    "Hello! I am your AI Supply Chain Diagnostic Assistant. "
                    "You can ask me about flagged SKUs, recommended purchase order quantities, "
                    "exact order-by deadlines, Class A items at risk, or specific categories like Beverages or Snacks."
                ),
            }
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. QUICK SUGGESTION CHIPS
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("<div class='eyebrow'>Quick Questions</div>", unsafe_allow_html=True)
    c_chip1, c_chip2, c_chip3, c_chip4 = st.columns(4)
    with c_chip1:
        if st.button("Which SKUs need attention this week?", use_container_width=True):
            st.session_state.user_query = "Which SKUs need attention this week?"
    with c_chip2:
        if st.button("Why is SKU-1004 flagged?", use_container_width=True):
            st.session_state.user_query = "Why is SKU-1004 flagged?"
    with c_chip3:
        if st.button("Show high-priority Class A items", use_container_width=True):
            st.session_state.user_query = "Show high-priority Class A items"
    with c_chip4:
        if st.button("How much to order for SKU-1002?", use_container_width=True):
            st.session_state.user_query = "How much to order for SKU-1002?"

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
    query = st.chat_input("Ask a question about inventory, replenishment deadlines, or specific SKUs…")
    if "user_query" in st.session_state and st.session_state.user_query:
        query = st.session_state.user_query
        st.session_state.user_query = None

    if query:
        st.session_state.chat_messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("Retrieving verified evidence and synthesizing answer…"):
                response = answer_agentic_question(query, scores, st.session_state.chat_messages)
                st.markdown(response.text)
                if response.warning:
                    st.caption(f"ℹ️ {response.warning}")
                st.session_state.chat_messages.append({"role": "assistant", "content": response.text})
