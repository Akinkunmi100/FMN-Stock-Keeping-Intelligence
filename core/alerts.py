"""
core/alerts.py — Proactive Notification Engine (Email, Slack, Teams, Webhooks)
==============================================================================
Provides automated alert dispatch so operators and procurement teams do not need
to sit continuously watching the dashboard.

Supports:
1. Daily executive digest (summary of critical risks, order-by deadlines, ROQ units)
2. Immediate critical alert (dispatched when high-priority Class A items breach safety stock)
3. Webhook integration (Slack incoming webhooks, Microsoft Teams connectors, generic JSON)
4. Safe dry-run testing mode for zero-configuration verification
"""

from __future__ import annotations

import json
import smtplib
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import pandas as pd

from config import ALERT_CONFIG


# ─────────────────────────────────────────────────────────────────────────────
# 1. DIGEST PAYLOAD BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_alert_digest(scores: pd.DataFrame, meta: dict[str, Any]) -> dict[str, Any]:
    """
    Synthesize operational health metrics and urgent action items into a structured digest.
    """
    flagged = scores[scores["urgency"] > 0]
    critical = scores[scores["severity"] == "Critical"]
    order_soon = scores[scores["bucket"] == "Order soon"]
    overstock = scores[scores["bucket"] == "Overstock risk"]
    class_a_risk = scores[(scores["abc_class"] == "A") & (scores["urgency"] > 0)]

    # Top 5 most urgent SKUs by order deadline
    urgent_skus: list[dict[str, Any]] = []
    for _, r in flagged.head(6).iterrows():
        urgent_skus.append({
            "sku_id": r["sku_id"],
            "category": r["category"],
            "abc_class": r["abc_class"],
            "severity": r["severity"],
            "stock": int(r["stock"]),
            "days_coverage": round(float(r["days_coverage"]), 1),
            "lead_time": int(r["lead_time"]),
            "roq": int(r["roq"]),
            "order_by_date": str(r["order_by_date"]),
            "timing_urgency_badge": r["timing_urgency_badge"],
            "timing_urgency_msg": r["timing_urgency_msg"],
        })

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date_max": str(meta.get("date_max", "")),
        "total_skus": len(scores),
        "flagged_count": len(flagged),
        "critical_count": len(critical),
        "order_soon_count": len(order_soon),
        "overstock_count": len(overstock),
        "class_a_at_risk": len(class_a_risk),
        "total_reorder_units": int(scores["roq"].sum()),
        "urgent_skus": urgent_skus,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. EMAIL NOTIFICATIONS (SMTP)
# ─────────────────────────────────────────────────────────────────────────────

def generate_email_html(digest: dict[str, Any]) -> tuple[str, str]:
    """
    Generate plain-text and rich HTML email bodies for the executive digest.
    """
    subject = f"[SUPPLY CHAIN ALERT] {digest['critical_count']} Critical Risks | {digest['class_a_at_risk']} Class-A SKUs at Risk"
    
    sku_rows_html = ""
    for item in digest["urgent_skus"]:
        sku_rows_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">{item['sku_id']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{item['category']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">Class {item['abc_class']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #e74c3c; font-weight: bold;">{item['timing_urgency_badge']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{item['order_by_date']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right; font-weight: bold;">{item['roq']:,} units</td>
        </tr>
        """

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #17211f; background-color: #f6f7f3; padding: 20px;">
        <div style="max-width: 650px; margin: 0 auto; background: #ffffff; padding: 25px; border-radius: 6px; border: 1px solid #dfe5de;">
            <h2 style="color: #17211f; margin-top: 0;">Daily Supply Chain Early Warning Digest</h2>
            <p style="color: #69736f; font-size: 14px;">Automated replenishment & stockout risk report generated on {digest['timestamp']}.</p>
            
            <div style="display: flex; gap: 15px; margin: 20px 0;">
                <div style="flex: 1; background: #fdedec; border-left: 4px solid #e74c3c; padding: 12px;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #69736f;">Critical Items</div>
                    <div style="font-size: 22px; font-weight: bold; color: #e74c3c;">{digest['critical_count']}</div>
                </div>
                <div style="flex: 1; background: #fef5e7; border-left: 4px solid #e67e22; padding: 12px;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #69736f;">Class-A at Risk</div>
                    <div style="font-size: 22px; font-weight: bold; color: #e67e22;">{digest['class_a_at_risk']}</div>
                </div>
                <div style="flex: 1; background: #eafaf1; border-left: 4px solid #27ae60; padding: 12px;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #69736f;">Total Reorder Need</div>
                    <div style="font-size: 22px; font-weight: bold; color: #27ae60;">{digest['total_reorder_units']:,} u</div>
                </div>
            </div>

            <h3 style="margin-top: 25px;">Top Urgent SKUs Requiring Immediate Procurement</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #eef2ea; text-align: left;">
                        <th style="padding: 8px;">SKU</th>
                        <th style="padding: 8px;">Category</th>
                        <th style="padding: 8px; text-align: center;">ABC</th>
                        <th style="padding: 8px;">Urgency</th>
                        <th style="padding: 8px;">Order By Date</th>
                        <th style="padding: 8px; text-align: right;">ROQ</th>
                    </tr>
                </thead>
                <tbody>
                    {sku_rows_html}
                </tbody>
            </table>

            <p style="margin-top: 25px; font-size: 13px; color: #69736f;">
                Please access the live Supply Chain Control Room dashboard to execute purchase orders or simulate supplier delays.
            </p>
        </div>
    </body>
    </html>
    """

    return subject, html


def send_email_alert(
    digest: dict[str, Any],
    recipients: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Dispatch daily digest or critical alert via SMTP.
    If dry_run is True or SMTP is unconfigured, logs the output safely without failing.
    """
    subject, html_content = generate_email_html(digest)
    target_recipients = recipients or ALERT_CONFIG.get("email_recipients", [])

    if dry_run or not target_recipients or not ALERT_CONFIG.get("smtp_user"):
        return {
            "status": "dry_run",
            "subject": subject,
            "recipients": target_recipients or ["<simulated_procurement_team@fmn.com>"],
            "message": "Email alert successfully simulated (dry-run mode). Set SMTP credentials to enable live sending.",
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = ALERT_CONFIG["smtp_user"]
        msg["To"] = ", ".join(target_recipients)
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(ALERT_CONFIG["smtp_server"], ALERT_CONFIG["smtp_port"]) as server:
            server.starttls()
            server.login(ALERT_CONFIG["smtp_user"], ALERT_CONFIG["smtp_password"])
            server.sendmail(ALERT_CONFIG["smtp_user"], target_recipients, msg.as_string())

        return {"status": "success", "recipients": target_recipients, "subject": subject}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 3. WEBHOOK NOTIFICATIONS (SLACK, TEAMS, GENERIC)
# ─────────────────────────────────────────────────────────────────────────────

def send_slack_alert(
    digest: dict[str, Any],
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Post a formatted alert card to a Slack channel via Incoming Webhook.
    """
    url = webhook_url or ALERT_CONFIG.get("slack_webhook_url", "")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Supply Chain Alert: {digest['critical_count']} Critical SKUs",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Critical Severities:*\n{digest['critical_count']}"},
                {"type": "mrkdwn", "text": f"*Class-A at Risk:*\n{digest['class_a_at_risk']}"},
                {"type": "mrkdwn", "text": f"*Total Reorder Units:*\n{digest['total_reorder_units']:,}"},
                {"type": "mrkdwn", "text": f"*Generated:*\n{digest['timestamp']}"},
            ],
        },
    ]

    payload = {"blocks": blocks}

    if dry_run or not url:
        return {
            "status": "dry_run",
            "platform": "slack",
            "payload": payload,
            "message": "Slack alert payload successfully constructed (dry-run mode).",
        }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return {"status": "success", "platform": "slack", "http_code": response.status}
    except Exception as exc:
        return {"status": "error", "platform": "slack", "error": str(exc)}


def send_teams_alert(
    digest: dict[str, Any],
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Post an alert message to a Microsoft Teams channel via Webhook connector.
    """
    url = webhook_url or ALERT_CONFIG.get("teams_webhook_url", "")
    
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "E74C3C" if digest["critical_count"] > 0 else "27AE60",
        "summary": f"Supply Chain Alert: {digest['critical_count']} Critical SKUs",
        "sections": [{
            "activityTitle": "Supply Chain Control Room - Urgent Replenishment Notice",
            "activitySubtitle": f"Report generated: {digest['timestamp']}",
            "facts": [
                {"name": "Critical SKUs", "value": str(digest["critical_count"])},
                {"name": "Class-A SKUs at Risk", "value": str(digest["class_a_at_risk"])},
                {"name": "Total Units to Reorder", "value": f"{digest['total_reorder_units']:,}"},
            ],
            "markdown": True,
        }],
    }

    if dry_run or not url:
        return {
            "status": "dry_run",
            "platform": "teams",
            "payload": payload,
            "message": "Teams alert payload successfully constructed (dry-run mode).",
        }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return {"status": "success", "platform": "teams", "http_code": response.status}
    except Exception as exc:
        return {"status": "error", "platform": "teams", "error": str(exc)}
