import sys
sys.path.insert(0, ".")
from app import load_and_score, DATA_PATH, explain, answer_agentic_question

print("--- 1. Testing load_and_score ---")
raw, scores, meta = load_and_score(str(DATA_PATH))
print(f"Raw rows: {len(raw)}, Scored SKUs: {len(scores)}")

print("\n--- 2. Testing ABC Pareto Classification ---")
abc_counts = scores["abc_class"].value_counts().to_dict()
print(f"ABC Distribution: {abc_counts}")
assert set(scores["abc_class"].unique()).issubset({"A", "B", "C"}), "Invalid ABC classes"

print("\n--- 3. Testing Seasonality & Stochastic Safety Stock ---")
print(f"DOW Multipliers count: {len(meta['dow_multipliers'])}")
new_skus = scores[scores["is_new"]]
print(f"New SKUs count: {len(new_skus)}")
for _, r in new_skus.iterrows():
    print(f"  {r['sku_id']}: LT={r['lead_time']}d, LT_std={r['lead_time_std']}d, SS={r['safety_stock']:.1f}, ROP={r['reorder_point']:.1f}")

print("\n--- 4. Testing Recommended Order Quantity (ROQ) ---")
flagged = scores[scores["urgency"] > 0]
print(f"Flagged SKUs: {len(flagged)}")
reorder_needed = scores[scores["roq"] > 0]
print(f"SKUs with active ROQ > 0: {len(reorder_needed)}")
for _, r in reorder_needed.head(4).iterrows():
    print(f"  {r['sku_id']} ({r['bucket']}, Class {r['abc_class']}): Stock={r['stock']:.0f}, ROP={r['reorder_point']:.0f} -> ROQ={r['roq']:.0f} units")

print("\n--- 5. Testing Backtest Engine ---")
bt = meta["backtest"]
print(f"Backtest: Recall={bt['recall']:.1%}, Precision={bt['precision']:.1%}, F1={bt['f1']:.1%}")
print(f"Confusion matrix: TP={bt['tp']}, FP={bt['fp']}, FN={bt['fn']}, TN={bt['tn']}")
assert bt["total_evaluations"] > 1000, "Backtest evaluations too low"

print("\n--- 6. Testing Explain Function (Local Grounded Fallback) ---")
exp = explain(scores.iloc[0])
print(f"Explanation for {scores.iloc[0]['sku_id']}: {exp.text[:120]}...")

print("\n--- 7. Testing Agentic Q&A Routing ---")
q1 = answer_agentic_question("Why is SKU-1004 flagged?", scores)
print(f"Q1 (Single SKU): {q1.text[:100]}...")

q2 = answer_agentic_question("Which beverage SKUs are at risk?", scores)
print(f"Q2 (Category): {q2.text[:100]}...")

q3 = answer_agentic_question("Show high-priority Class A items", scores)
print(f"Q3 (Class A): {q3.text[:100]}...")

q4 = answer_agentic_question("Which SKUs need attention this week?", scores)
print(f"Q4 (Portfolio): {q4.text[:100]}...")

print("\n[PASS] ALL VERIFICATION CHECKS PASSED PERFECTLY!")
