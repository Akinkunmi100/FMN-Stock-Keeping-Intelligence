"""Command-line runner for scheduled inventory alerts.

Usage examples::

    python monitor.py --dry-run
    python monitor.py --email
    python monitor.py --slack
    python monitor.py --all
"""

from __future__ import annotations

import argparse

from config import DATA_PATH
from core.alerts import (
    build_alert_digest,
    send_email_alert,
    send_slack_alert,
    send_teams_alert,
)
from core.data_pipeline import load_and_prepare_dataset
from core.inventory_engine import score_sku_inventory


def run_pipeline():
    """Load dataset, compute statistical priors, and score all SKUs."""
    sanitized, abc_map, dow_multipliers, cat_cv, cat_kurt = load_and_prepare_dataset(DATA_PATH)

    records = []
    for sku, group in sanitized.groupby("sku_id"):
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

    import pandas as pd
    scores = pd.DataFrame(records).sort_values(
        ["urgency", "risk_score", "days_coverage"],
        ascending=[False, False, True]
    ).reset_index(drop=True)

    meta = {
        "date_min": sanitized["date"].min().date(),
        "date_max": sanitized["date"].max().date(),
        "total_skus": len(scores),
    }
    return scores, meta


def main():
    parser = argparse.ArgumentParser(description="Supply chain alert runner")
    parser.add_argument("--dry-run", action="store_true", help="Simulate alert generation without sending")
    parser.add_argument("--email", action="store_true", help="Send email digest to configured recipients")
    parser.add_argument("--slack", action="store_true", help="Send alert card to Slack webhook")
    parser.add_argument("--teams", action="store_true", help="Send alert card to Microsoft Teams webhook")
    parser.add_argument("--all", action="store_true", help="Dispatch alerts across all configured channels")

    args = parser.parse_args()

    # Default to dry-run if no action specified
    if not (args.email or args.slack or args.teams or args.all):
        args.dry_run = True

    print("========================================================")
    print("  SIGNAL / SUPPLY CHAIN ALERT RUNNER")
    print("========================================================")
    print(f"Loading data from: {DATA_PATH}")

    scores, meta = run_pipeline()
    digest = build_alert_digest(scores, meta)

    print(f"\n[RESULTS] Evaluation Date: {digest['date_max']}")
    print(f"Total Tracked SKUs: {digest['total_skus']}")
    print(f"Flagged SKUs:       {digest['flagged_count']}")
    print(f"Critical Severities:{digest['critical_count']}")
    print(f"Class A at Risk:    {digest['class_a_at_risk']}")
    print(f"Total Reorder Units:{digest['total_reorder_units']:,} units")

    print("\n--- TOP URGENT REPLENISHMENT DEADLINES ---")
    for item in digest["urgent_skus"][:5]:
        print(f"  • {item['sku_id']} ({item['category']}, Class {item['abc_class']}): {item['timing_urgency_badge']} | Order by: {item['order_by_date']} | Suggested order: {item['roq']:,} units")

    # 1. Email Alert
    if args.email or args.all or args.dry_run:
        print("\n[EMAIL DISPATCH]")
        email_res = send_email_alert(digest, dry_run=args.dry_run)
        print(f"  Status: {email_res['status']} | Subject: {email_res.get('subject', '')}")

    # 2. Slack Webhook
    if args.slack or args.all or args.dry_run:
        print("\n[SLACK DISPATCH]")
        slack_res = send_slack_alert(digest, dry_run=args.dry_run)
        print(f"  Status: {slack_res['status']}")

    # 3. Teams Webhook
    if args.teams or args.all or args.dry_run:
        print("\n[TEAMS DISPATCH]")
        teams_res = send_teams_alert(digest, dry_run=args.dry_run)
        print(f"  Status: {teams_res['status']}")

    print("\n========================================================")
    print("  MONITOR RUN COMPLETE")
    print("========================================================")


if __name__ == "__main__":
    main()
