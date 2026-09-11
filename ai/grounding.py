"""Build evidence for assistant responses and check the numbers they cite.

The module also routes common inventory questions to the smallest relevant set
of scored rows before asking the assistant to answer.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from ai.llm_client import LLMResult, execute_groq_chat


# ─────────────────────────────────────────────────────────────────────────────
# 1. EVIDENCE DICTIONARY BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_sku_facts(row: pd.Series) -> dict[str, Any]:
    """
    Construct a verified, strictly factual dictionary summarizing the SKU's state.
    """
    return {
        "sku": str(row.get("sku_id", "")),
        "category": str(row.get("category", "")),
        "abc_class": str(row.get("abc_class", "B")),
        "risk_bucket": str(row.get("bucket", "")),
        "severity": str(row.get("severity", "Low")),
        "risk_score": round(float(row.get("risk_score", 0.0)), 1),
        "flag_type": str(row.get("flag_type", "")),
        "history_days": int(row.get("history_days", 0)),
        "observations": int(row.get("observations", 0)),
        "closing_stock_units": round(float(row.get("stock", 0.0)), 1),
        "daily_demand_units": round(float(row.get("daily_demand", 0.0)), 1),
        "forward_lead_time_demand": round(float(row.get("forward_lead_demand", 0.0)), 1),
        "recommended_order_quantity": round(float(row.get("roq", 0.0)), 0),
        "days_of_coverage": round(float(row.get("days_coverage", 0.0)), 1),
        "lead_time_days": round(float(row.get("lead_time", 0.0)), 1),
        "lead_time_std_days": round(float(row.get("lead_time_std", 0.0)), 2),
        "reorder_point_units": round(float(row.get("reorder_point", 0.0)), 1),
        "safety_stock_units": round(float(row.get("safety_stock", 0.0)), 1),
        "demand_change_percent": round(float(row.get("trend_pct", 0.0) * 100), 1),
        "receipts_last_7_days": round(float(row.get("receipts_7d", 0.0)), 1),
        "coefficient_of_variation": round(float(row.get("cv", 0.0)), 3),
        "data_method": str(row.get("method", "")),
        # Replenishment timing details
        "order_by_date": str(row.get("order_by_date", "")),
        "stockout_date": str(row.get("stockout_date", "")),
        "timing_urgency_badge": str(row.get("timing_urgency_badge", "")),
        "timing_urgency_msg": str(row.get("timing_urgency_msg", "")),
        # Overstock diagnostics
        "excess_units": round(float(row.get("excess_units", 0.0)), 0),
        "days_over_target": round(float(row.get("days_over_target", 0.0)), 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. NUMERICAL TOKEN VALIDATION (ANTI-HALLUCINATION)
# ─────────────────────────────────────────────────────────────────────────────

_DASH_VARIANTS = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
})


def _normalize_dashes(text: str) -> str:
    """
    Map Unicode dash/hyphen variants (hyphen, non-breaking hyphen, en/em dash)
    to a plain ASCII "-". Groq's Llama output typesets dates and compound
    words with these (e.g. "2026‑06‑26", "order‑by") rather than
    ASCII "-", which would otherwise make an ISO date fail to match its
    plain-ASCII counterpart in the evidence dict.
    """
    return text.translate(_DASH_VARIANTS)


_THOUSANDS_GROUPING = ",  "  # comma, narrow no-break space, no-break space


def extract_number_tokens(text: str) -> list[float]:
    """
    Extract all standalone numerical values from a text string.

    Groq's Llama output formats large numbers with U+202F (narrow no-break
    space) as a thousands separator, e.g. "2 190.4" for 2190.4 — not a
    plain ASCII space, so this doesn't risk merging two unrelated numbers
    that happen to sit next to each other in prose (which uses a normal
    space). Without treating it as a grouping character, "2 190.4"
    would be misread as two separate numbers, 2 and 190.4, neither of which
    matches the real value.
    """
    matches = re.findall(rf"(?<![A-Za-z])\d[\d{_THOUSANDS_GROUPING}]*(?:\.\d+)?", text)
    cleaned = [re.sub(f"[{_THOUSANDS_GROUPING}]", "", x) for x in matches]
    return [float(x) for x in cleaned]


def _collect_numeric_candidates(obj: Any) -> list[float]:
    """
    Recursively collect numeric values from a nested evidence dict/list —
    both structured numeric leaves (risk_score=74.6) and numbers embedded in
    string fields (timing_urgency_msg="...(8 days window)"). The latter
    matters because a live response is free to paraphrase a string field
    ("providing an 8-day safety window") rather than quote it verbatim, and
    that number is still genuinely grounded even though it isn't its own
    top-level fact.
    """
    found: list[float] = []
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        found.append(float(obj))
    elif isinstance(obj, str):
        found.extend(extract_number_tokens(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.extend(_collect_numeric_candidates(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found.extend(_collect_numeric_candidates(v))
    return found


def _collect_digit_bearing_strings(obj: Any) -> set[str]:
    """
    Recursively collect string leaf values from evidence that contain a digit
    — SKU codes ("SKU-1010"), ISO dates, badges ("ORDER IN 3D"), the "method"
    label ("full-history baseline (141 obs...)"), etc. These are identifiers
    or labels being echoed back, not numeric claims about the SKU, so they
    must not be tokenized as citable figures. Only an exact verbatim
    substring match against the model's own text is stripped, so a
    paraphrased mention of e.g. timing_urgency_msg is left untouched and can
    still be checked against the real numeric facts.
    """
    found: set[str] = set()
    if isinstance(obj, str):
        if any(ch.isdigit() for ch in obj):
            found.add(obj)
        found.update(re.findall(r"\d{4}-\d{2}-\d{2}", obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.update(_collect_digit_bearing_strings(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found.update(_collect_digit_bearing_strings(v))
    return found


def validate_grounded_numbers(text: str, facts: Any) -> bool:
    """
    Verify that every number cited in the LLM response is traceable to the
    factual evidence actually passed into the prompt. Permits reasonable
    rounding (within 1% or 0.5 units).

    `facts` may be a flat dict (single-SKU evidence, e.g. explain_sku) or a
    nested dict/list (multi-SKU payloads, e.g. the category/Class-A/portfolio
    Q&A routes) — numeric leaves are collected recursively either way.

    `facts` should include the system prompt's own instructions text
    alongside the evidence payload (e.g. `[instructions, facts]`) — the
    instructions we write ourselves are trusted, not model output, and can
    legitimately contain a number (e.g. "top 70% volume" in the Class-A
    route's prompt) that the model is entitled to echo back without that
    being an invented figure.

    The check makes four practical adjustments to a simple digit scan:
    - Digit-bearing identifier/label strings already present verbatim in the
      evidence (the SKU code "SKU-1010", ISO dates, timing badges like
      "ORDER IN 3D") are stripped out of the text before number-tokenizing,
      so e.g. citing "SKU-1010" doesn't get read as the bare number 1010
      and flagged as an unverifiable figure.
    - Unicode dash variants (Groq's output typesets dates/compounds with a
      non-breaking hyphen, e.g. "2026‑06‑26") are normalized to ASCII "-"
      first, so those strings actually match their evidence counterparts.
    - Comparisons use absolute value on both sides: a negative trend like
      demand_change_percent=-37.0 is written in prose as "-37%" or "37%
      decline," and extract_number_tokens never captures a leading minus
      sign, so the unsigned token must be compared against |candidate|.
    """
    text = _normalize_dashes(text)
    for id_str in _collect_digit_bearing_strings(facts):
        text = text.replace(_normalize_dashes(id_str), "")

    allowed_candidates: list[float] = []
    for val in _collect_numeric_candidates(facts):
        mag = abs(val)
        allowed_candidates.extend([mag, round(mag, 0), round(mag, 1)])

    for number in extract_number_tokens(text):
        if not any(abs(number - cand) <= max(0.5, cand * 0.01) for cand in allowed_candidates):
            return False
    return True


_UNGROUNDED_WARNING = (
    "Live model response cited a figure that couldn't be verified against the "
    "retrieved data — showing the local grounded summary instead."
)


def _reject_if_ungrounded(result: LLMResult, evidence: Any) -> LLMResult:
    """
    Gate a live LLM result through validate_grounded_numbers. A live response
    that fails the check is replaced with an explicit non-live rejection (not
    just silently ignored), so every call site's fallback path carries the
    same clear warning explaining why the user is seeing the local
    deterministic answer instead of a live one.
    """
    if result.live and result.text and not validate_grounded_numbers(result.text, evidence):
        return LLMResult(text="", live=False, warning=_UNGROUNDED_WARNING)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. SINGLE-SKU EXPLANATION GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def explain_sku(row: pd.Series) -> LLMResult:
    """
    Generate a grounded diagnostic explanation for a single SKU.

    If Groq is enabled and returns a grounded response, uses that (the
    specific model that answered is recorded on the returned LLMResult, not
    assumed — config.py can point at any Groq model, with fallbacks tried in
    order if the primary is unavailable). Otherwise, builds a deterministic
    evidence-based explanation.
    """
    facts = build_sku_facts(row)
    instructions = (
        "You are an expert supply-chain analyst presenting to operations leadership. "
        "Explain the SKU's risk bucket, stockout timeline, and recommended action in 2 concise paragraphs. "
        "Strictly cite only the provided figures: closing stock, days of coverage, lead time, "
        "reorder point, recommended order quantity (ROQ), order-by date, and demand trend. "
        "Never invent external figures. Do not use markdown bullet points."
    )
    user_content = json.dumps({"evidence": facts}, ensure_ascii=False)

    result = execute_groq_chat([
        {"role": "system", "content": instructions},
        {"role": "user", "content": user_content},
    ])
    result = _reject_if_ungrounded(result, [instructions, facts])

    if result.live and result.text:
        return result

    # Deterministic local fallback
    roq_val = float(row.get("roq", 0.0))
    roq_text = f" Recommend ordering {roq_val:,.0f} units to restore the target inventory buffer." if roq_val > 0 else ""
    order_by = str(row.get("order_by_date", "immediately"))
    timing_msg = str(row.get("timing_urgency_msg", ""))

    local_text = (
        f"{row['sku_id']} (Category: {row['category']}, Class {row['abc_class']}) is classified in the {row['bucket'].lower()} queue "
        f"with a composite risk score of {row['risk_score']:.0f}/100 ({row['severity']} severity). On-hand inventory stands at {row['stock']:,.0f} units, "
        f"providing {row['days_coverage']:.1f} days of coverage against a {row['lead_time']:.0f}-day replenishment cycle. "
        f"The seasonal reorder point is {row['reorder_point']:,.0f} units (incorporating {row['safety_stock']:,.0f} units of safety buffer). "
        f"Recent demand has moved {row['trend_pct']:+.1%} (CV={row['cv']:.2f}). "
        f"Replenishment status: {timing_msg}.{roq_text} "
        f"Recommended action: {('release purchase requisition immediately for ' + f'{roq_val:,.0f} units by ' + order_by + '.' if row['urgency'] >= 2 else 'maintain routine operational monitoring.')}"
    )

    return LLMResult(text=local_text, live=False, warning=result.warning)


# ─────────────────────────────────────────────────────────────────────────────
# 4. AGENTIC CONVERSATIONAL Q&A
# ─────────────────────────────────────────────────────────────────────────────

def answer_agentic_question(
    question: str,
    scores: pd.DataFrame,
    chat_history: list[dict[str, str]] | None = None,
) -> LLMResult:
    """
    Intelligently route and answer natural language supply chain questions.
    
    Routes supported:
    1. Single SKU drill-down (e.g. "Why is SKU-1004 flagged?", "How much to order for SKU-1002?")
    2. Category-level status (e.g. "Which Beverage SKUs are at risk?", "Dairy summary")
    3. Class A Pareto high-priority items (e.g. "Show high-priority Class A items")
    4. General portfolio queue inquiries (e.g. "Which SKUs need attention this week?")
    """
    q_lower = question.lower()

    # ── ROUTE 1: Single SKU inquiry ──
    mentioned = re.findall(r"SKU[- ]?\d{4}", question.upper())
    if mentioned:
        target = mentioned[0].replace(" ", "-")
        selected = scores[scores["sku_id"] == target]
        if not selected.empty:
            row = selected.iloc[0]
            facts = build_sku_facts(row)
            instructions = (
                "Answer the user's specific inquiry about this SKU using only the provided factual evidence. "
                "Include current stock, days of coverage, lead time, reorder point, "
                "recommended order quantity (ROQ), order-by date, and plain-language action."
            )
            prompt = [{"role": "system", "content": instructions}, {"role": "user", "content": json.dumps({"sku_evidence": facts})}]
            result = _reject_if_ungrounded(execute_groq_chat(prompt), [instructions, facts])
            if result.live and result.text:
                return result

            # Local fallback
            roq_units = f"Recommended order: {row['roq']:,.0f} units" if row['roq'] > 0 else "Stock is currently adequate"
            return LLMResult(
                text=(
                    f"**{row['sku_id']}** ({row['category']}, Class {row['abc_class']}): Classified as **{row['bucket'].upper()}** "
                    f"(Risk {row['risk_score']:.0f}/100, {row['severity']} severity).\n\n"
                    f"• **Current Stock**: {row['stock']:,.0f} units ({row['days_coverage']:.1f} days coverage vs. {row['lead_time']:.0f}-day lead time)\n"
                    f"• **Reorder Point**: {row['reorder_point']:,.0f} units (Safety Stock: {row['safety_stock']:,.0f} units)\n"
                    f"• **Replenishment Timing**: {row['timing_urgency_msg']}\n"
                    f"• **Action Required**: {roq_units} by {row['order_by_date']}."
                ),
                live=False,
                warning=result.warning,
            )

    # ── ROUTE 2: Category filter inquiry ──
    unique_categories = scores["category"].unique()
    matched_cats = [
        c for c in unique_categories
        if c.lower() in q_lower or c.lower().rstrip("s") in q_lower or (q_lower in c.lower())
    ]
    if matched_cats:
        cat_df = scores[scores["category"].isin(matched_cats)]
        flagged_in_cat = cat_df[cat_df["urgency"] > 0]
        payload = {
            "type": "category_filter",
            "categories": matched_cats,
            "total_skus": len(cat_df),
            "flagged_skus": [build_sku_facts(r) for _, r in flagged_in_cat.iterrows()],
        }
        instructions = "Summarize the inventory health, stockout risks, and procurement needs for the requested category using only the evidence."
        result = execute_groq_chat([{"role": "system", "content": instructions}, {"role": "user", "content": json.dumps(payload)}])
        result = _reject_if_ungrounded(result, [instructions, payload])
        if result.live and result.text:
            return result

        # Local fallback
        flagged_summary = ", ".join(f"{r['sku_id']} (ROQ: {r['roq']:,.0f})" for _, r in flagged_in_cat.iterrows()) or "None"
        return LLMResult(
            text=(
                f"**Category Analysis: {matched_cats[0]}**\n\n"
                f"• Total tracked SKUs: **{len(cat_df)}**\n"
                f"• SKUs requiring action: **{len(flagged_in_cat)}**\n"
                f"• Immediate reorder items: {flagged_summary}."
            ),
            live=False,
            warning=result.warning,
        )

    # ── ROUTE 3: Class A Pareto inquiry ──
    if "class a" in q_lower or "pareto" in q_lower or "top priority" in q_lower or "critical sku" in q_lower:
        class_a = scores[scores["abc_class"] == "A"]
        flagged_a = class_a[class_a["urgency"] > 0]
        payload = {
            "type": "class_a_summary",
            "total_class_a": len(class_a),
            "flagged_class_a": [build_sku_facts(r) for _, r in flagged_a.iterrows()],
        }
        instructions = "Detail which high-priority Class A SKUs (top 70% volume) are at risk and need immediate procurement action."
        result = execute_groq_chat([{"role": "system", "content": instructions}, {"role": "user", "content": json.dumps(payload)}])
        result = _reject_if_ungrounded(result, [instructions, payload])
        if result.live and result.text:
            return result

        # Local fallback
        a_list = "\n".join(f"• **{r['sku_id']}** ({r['category']}): {r['bucket']} | Stock: {r['stock']:,.0f} u | Order-by: {r['order_by_date']} | ROQ: {r['roq']:,.0f} u" for _, r in flagged_a.iterrows())
        return LLMResult(
            text=(
                f"**Class A Pareto Summary (Top 70% Volume Drivers)**\n\n"
                f"There are **{len(class_a)}** Class A items in the catalog. **{len(flagged_a)}** currently require intervention:\n\n"
                f"{a_list}"
            ),
            live=False,
            warning=result.warning,
        )

    # ── ROUTE 4: General portfolio / attention queue inquiry ──
    flagged = scores[scores["urgency"] > 0].head(10)
    payload = {
        "portfolio_summary": {
            "total_skus": len(scores),
            "flagged_total": int((scores["urgency"] > 0).sum()),
            "critical_count": int((scores["severity"] == "Critical").sum()),
            "order_soon_count": int((scores["bucket"] == "Order soon").sum()),
            "overstock_count": int((scores["bucket"] == "Overstock risk").sum()),
            "total_reorder_units": int(scores["roq"].sum()),
        },
        "priority_skus": [build_sku_facts(r) for _, r in flagged.iterrows()],
    }
    instructions = (
        "Answer the supply chain inquiry concisely. Detail the high-risk SKUs that need action, "
        "citing specific stock levels, days of coverage, exact order-by dates, and recommended order quantities."
    )
    result = execute_groq_chat([{"role": "system", "content": instructions}, {"role": "user", "content": json.dumps(payload)}])
    result = _reject_if_ungrounded(result, [instructions, payload])
    if result.live and result.text:
        return result

    # Local fallback
    summary_items = "\n".join(
        f"• **{r['sku_id']}** (Class {r['abc_class']}, {r['severity']}): {r['timing_urgency_msg']} — ROQ: {r['roq']:,.0f} units"
        for _, r in scores[scores["urgency"] > 0].head(5).iterrows()
    )
    return LLMResult(
        text=(
            f"**Supply Chain Portfolio Status**\n\n"
            f"• Flagged SKUs: **{int((scores['urgency'] > 0).sum())} of {len(scores)}**\n"
            f"• Critical Severity: **{int((scores['severity'] == 'Critical').sum())}**\n"
            f"• Total Reorder Demand: **{int(scores['roq'].sum()):,} units**\n\n"
            f"**Top Immediate Procurement Priorities:**\n{summary_items}"
        ),
        live=False,
        warning=result.warning,
    )
