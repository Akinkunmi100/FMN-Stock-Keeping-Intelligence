"""
test_app_verification.py — Core Pipeline & Grounding Verification
===================================================================
Standalone verification script (not pytest — no test framework is a
project dependency). Run directly: `python test_app_verification.py`.

Covers the checklist in docs/BUILD_BRIEF.md "Before You Ship, Verify" and
the non-negotiables in CLAUDE.md that are actually testable offline:
- Every SKU (including the 3 new ones) loads and scores without error.
- The units_sold missing-value rule (bounded interpolation, not silent
  zeroing) actually behaves as documented.
- Category-casing normalization collapses the raw CSV's variants correctly.
- A flag fires for at least one established SKU and the new SKUs produce
  their own distinct cold-start scoring path.
- The backtest runs end-to-end and produces a sane metrics dict.
- The anti-hallucination grounding check accepts genuinely grounded text
  and rejects a fabricated number — this is deterministic and offline
  (no Groq call), unlike the live LLM grounding itself which needs a
  network call and an API key to exercise for real.
"""

from __future__ import annotations

import sys

import pandas as pd

from config import DATA_PATH
from core.backtest import run_historical_backtest
from core.data_pipeline import load_and_prepare_dataset
from core.inventory_engine import score_sku_inventory
from ai.grounding import validate_grounded_numbers


PASS = "PASS"
FAIL = "FAIL"
_failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        _failures.append(label)


def main() -> int:
    print("=" * 70)
    print("SIGNAL — CORE VERIFICATION SUITE")
    print("=" * 70)

    # ── 1. Data pipeline sanity ──
    sanitized, abc_map, dow_multipliers, cat_cv, cat_kurt = load_and_prepare_dataset(DATA_PATH)
    raw = pd.read_csv(DATA_PATH, parse_dates=["date"])

    check("CSV loads", len(raw) > 0)
    check(
        "Category normalization collapses raw casing variants",
        sanitized["category_key"].nunique() < raw["category"].nunique(),
        f"got {sanitized['category_key'].nunique()} normalized from {raw['category'].nunique()} raw",
    )

    raw_missing = int((sanitized["units_sold_raw"].isna()).sum())
    imputed = int((sanitized["units_sold_raw"].isna() & sanitized["units_sold"].notna()).sum())
    check(
        "units_sold gap rule: genuinely-missing rows are detected (not silently zeroed)",
        raw_missing > 0,
        f"raw_missing={raw_missing} — if this is 0, the groupby-sum aggregation bug has regressed",
    )
    check(
        "units_sold gap rule: short gaps get bounded-interpolated, not left as fabricated zeros",
        imputed > 0 and imputed <= raw_missing,
        f"imputed={imputed} of {raw_missing} missing",
    )
    check(
        "closing_stock gaps are forward-filled (no NaN reaches scoring)",
        int(sanitized["closing_stock"].isna().sum()) == 0,
    )

    # ── 2. Every SKU scores without error, established and new alike ──
    records: list[dict] = []
    errors: list[str] = []
    for sku, group in sanitized.groupby("sku_id", sort=True):
        try:
            rec = score_sku_inventory(
                sku_id=str(sku),
                sku_group=group,
                abc_class=abc_map.get(str(sku), "B"),
                dow_multipliers=dow_multipliers,
                cat_cv=cat_cv,
                cat_kurt=cat_kurt,
            )
            records.append(rec)
        except Exception as exc:  # noqa: BLE001 — want to report every failing SKU, not stop at the first
            errors.append(f"{sku}: {exc}")

    scores = pd.DataFrame(records)
    check("Every SKU scores without raising", not errors, "; ".join(errors))
    check("All 28 expected SKUs are present", len(scores) == 28, f"got {len(scores)}")

    new_skus = scores[scores["is_new"]]
    established_skus = scores[~scores["is_new"]]
    check("New SKUs (cold-start) are present and distinctly labeled", not new_skus.empty)
    check(
        "New SKUs use the cold-start method label, not the established one",
        bool(new_skus["method"].str.startswith("launch baseline").all()) if not new_skus.empty else False,
    )
    check(
        "At least one established SKU produces an active flag",
        bool((established_skus["urgency"] > 0).any()),
    )
    check(
        "At least one new SKU produces an active flag (or would, given its sparse history)",
        bool((new_skus["urgency"] > 0).any()) if not new_skus.empty else False,
    )

    # ── 3. Backtest runs end-to-end and reports sane metrics ──
    bt = run_historical_backtest(sanitized, abc_map)
    check("Backtest produces all expected metric keys", set(bt) >= {"precision", "recall", "f1", "accuracy", "total_evaluations"})
    check("Backtest evaluated a non-trivial number of checkpoints", bt["total_evaluations"] > 1000, f"got {bt['total_evaluations']}")
    check("Backtest recall is a valid probability", 0.0 <= bt["recall"] <= 1.0)

    # ── 4. Anti-hallucination grounding check (offline, deterministic) ──
    facts = {"stock": 112.0, "order_by_date": "2026-06-26", "roq": 1839.0}
    grounded_text = "Stock is 112 units, order by 2026-06-26, ROQ 1,839 units."
    fabricated_text = "Stock is 9999 units, order by 2026-06-26."
    check("Grounding check accepts genuinely grounded text", validate_grounded_numbers(grounded_text, facts))
    check("Grounding check rejects a fabricated number", not validate_grounded_numbers(fabricated_text, facts))

    print("=" * 70)
    if _failures:
        print(f"RESULT: {len(_failures)} check(s) FAILED: {_failures}")
        return 1
    print(f"RESULT: all checks passed ({len(scores)} SKUs, {bt['total_evaluations']} backtest checkpoints)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
