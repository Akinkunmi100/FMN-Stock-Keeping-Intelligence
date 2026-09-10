"""
ui/charts.py — Reusable Interactive Plotly Visualizations
=========================================================
Builds high-impact, interactive charts for executives, planners, and operators:
1. Portfolio Risk Donut: High-level status breakdown
2. ABC Pareto Bar: Volume concentration by tier
3. Stock Trajectory Line: Historical inventory vs. ROP and Safety Stock
4. Demand & Receipts Timeline: Sales velocity vs. incoming deliveries
5. Risk Score Speedometer Gauge: 0–100 composite risk with color zones
6. Backtest Confusion Heatmap: Visual validation matrix (TP/FP/FN/TN)
7. Coverage Countdown Bar: Days of supply vs. supplier lead time
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from config import COLORS


# ─────────────────────────────────────────────────────────────────────────────
# 1. PORTFOLIO RISK DONUT CHART
# ─────────────────────────────────────────────────────────────────────────────

def build_portfolio_risk_donut(scores: pd.DataFrame) -> go.Figure:
    """Build an interactive donut chart showing portfolio distribution across severities."""
    severity_order = ["Critical", "High", "Medium", "Low"]
    color_map = {
        "Critical": COLORS["critical"],
        "High": COLORS["high"],
        "Medium": COLORS["medium"],
        "Low": COLORS["low"],
    }
    
    counts = scores["severity"].value_counts()
    labels = [s for s in severity_order if s in counts]
    values = [counts[s] for s in labels]
    chart_colors = [color_map[s] for s in labels]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=chart_colors, line=dict(color=COLORS["paper"], width=2)),
                textinfo="label+value",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        title=dict(text="<b>Portfolio Risk Distribution</b>", font=dict(family="Manrope", size=14)),
        margin=dict(l=10, r=10, t=40, b=10),
        height=260,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. ABC PARETO VOLUME BAR CHART
# ─────────────────────────────────────────────────────────────────────────────

def build_abc_pareto_bar(scores: pd.DataFrame) -> go.Figure:
    """Build a bar chart showing demand volume and SKU count by ABC tier."""
    tier_order = ["A", "B", "C"]
    abc_summary = scores.groupby("abc_class")["daily_demand"].sum()
    sku_counts = scores.groupby("abc_class")["sku_id"].count()

    labels = [f"Class {t}" for t in tier_order if t in abc_summary]
    volumes = [abc_summary.get(t, 0) for t in tier_order if t in abc_summary]
    counts = [sku_counts.get(t, 0) for t in tier_order if t in sku_counts]
    colors = [COLORS["abc_a"], COLORS["abc_b"], COLORS["abc_c"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=volumes,
            marker_color=colors,
            text=[f"{v:,.0f} u/d<br>({c} SKUs)" for v, c in zip(volumes, counts)],
            textposition="auto",
            hovertemplate="<b>%{x}</b><br>Daily Volume: %{y:,.0f} units/day<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="<b>Daily Volume by ABC Pareto Tier</b>", font=dict(family="Manrope", size=14)),
        yaxis=dict(title="Daily Demand (Units)", showgrid=True, gridcolor=COLORS["line"]),
        xaxis=dict(title=""),
        margin=dict(l=10, r=10, t=40, b=10),
        height=260,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. STOCK TRAJECTORY WITH THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

def build_stock_trajectory_chart(
    sku_history: pd.DataFrame,
    reorder_point: float,
    safety_stock: float,
) -> go.Figure:
    """Interactive line chart showing on-hand inventory vs ROP and Safety Stock lines."""
    df = sku_history.sort_values("date")

    fig = go.Figure()

    # Closing Stock Line
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["closing_stock"],
            mode="lines+markers",
            name="Closing Stock",
            line=dict(color=COLORS["ink"], width=2.2),
            marker=dict(size=4),
            hovertemplate="Date: %{x|%Y-%m-%d}<br>Stock: %{y:,.0f} units<extra></extra>",
        )
    )

    # Reorder Point (ROP)
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=[reorder_point] * len(df),
            mode="lines",
            name=f"Reorder Point ({reorder_point:,.0f})",
            line=dict(color=COLORS["critical"], width=2, dash="dash"),
            hovertemplate="Reorder Point: %{y:,.0f} units<extra></extra>",
        )
    )

    # Safety Stock
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=[safety_stock] * len(df),
            mode="lines",
            name=f"Safety Stock ({safety_stock:,.0f})",
            line=dict(color=COLORS["high"], width=1.8, dash="dot"),
            hovertemplate="Safety Stock: %{y:,.0f} units<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text="<b>Historical Inventory Trajectory vs. Policy Thresholds</b>", font=dict(family="Manrope", size=14)),
        xaxis=dict(title="Date", showgrid=True, gridcolor=COLORS["line"]),
        yaxis=dict(title="Units On Hand", showgrid=True, gridcolor=COLORS["line"]),
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. DEMAND & RECEIPTS TIMELINE
# ─────────────────────────────────────────────────────────────────────────────

def build_demand_and_receipts_chart(sku_history: pd.DataFrame) -> go.Figure:
    """Area/bar chart showing daily customer demand and incoming replenishment shipments."""
    df = sku_history.sort_values("date")

    fig = go.Figure()

    # Units Sold (Demand Area)
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["units_sold"],
            mode="lines",
            name="Daily Units Sold",
            fill="tozeroy",
            fillcolor="rgba(74, 122, 135, 0.18)",
            line=dict(color=COLORS["chart_series"], width=1.8),
            hovertemplate="Date: %{x|%Y-%m-%d}<br>Demand: %{y:,.0f} units<extra></extra>",
        )
    )

    # Units Received (Replenishment Spikes)
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["units_received"],
            name="Units Received (Inflow)",
            marker_color=COLORS["low"],
            opacity=0.75,
            hovertemplate="Date: %{x|%Y-%m-%d}<br>Shipment: %{y:,.0f} units<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text="<b>Daily Demand (Outflow) & Receipts (Inflow)</b>", font=dict(family="Manrope", size=14)),
        xaxis=dict(title="Date", showgrid=True, gridcolor=COLORS["line"]),
        yaxis=dict(title="Units", showgrid=True, gridcolor=COLORS["line"]),
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. SPEEDOMETER RISK SCORE GAUGE
# ─────────────────────────────────────────────────────────────────────────────

def build_risk_gauge(risk_score: float, severity: str) -> go.Figure:
    """Build a calibrated speedometer-style gauge for the 0–100 risk score."""
    color = (
        COLORS["critical"] if risk_score >= 75 else
        COLORS["high"] if risk_score >= 50 else
        COLORS["medium"] if risk_score >= 30 else
        COLORS["low"]
    )

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=risk_score,
            number=dict(suffix="/100", font=dict(size=36, family="Manrope", color=COLORS["ink"])),
            title=dict(text=f"<b>Risk Score: {severity.upper()}</b>", font=dict(size=14, family="Manrope")),
            gauge=dict(
                axis=dict(range=[0, 100], tickwidth=1, tickcolor=COLORS["line"]),
                bar=dict(color=color, thickness=0.3),
                bgcolor="white",
                borderwidth=1,
                bordercolor=COLORS["line"],
                steps=[
                    dict(range=[0, 30], color="#EAFAF1"),
                    dict(range=[30, 50], color="#FEF9E7"),
                    dict(range=[50, 75], color="#FEF5E7"),
                    dict(range=[75, 100], color="#FDEDEC"),
                ],
                threshold=dict(
                    line=dict(color=COLORS["ink"], width=3),
                    thickness=0.75,
                    value=risk_score,
                ),
            ),
        )
    )
    fig.update_layout(
        height=220,
        margin=dict(l=15, r=15, t=35, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 6. BACKTEST CONFUSION MATRIX HEATMAP
# ─────────────────────────────────────────────────────────────────────────────

def build_backtest_heatmap(tp: int, fp: int, fn: int, tn: int) -> go.Figure:
    """Visual confusion matrix heatmap with True Positives, False Positives, FN, TN."""
    matrix = [[tp, fp], [fn, tn]]
    total = tp + fp + fn + tn
    x_labels = ["Alarm Triggered (Predicted Risk)", "No Alarm (Predicted Safe)"]
    y_labels = ["Actual Stockout Occurred", "Adequate Stock (No Stockout)"]

    annotations = [
        [
            f"<b>True Positives (TP)</b><br>{tp:,}<br>({tp/total:.1%})<br><i>Crisis Caught</i>",
            f"<b>False Alarms (FP)</b><br>{fp:,}<br>({fp/total:.1%})<br><i>Early Review</i>",
        ],
        [
            f"<b>Missed Crises (FN)</b><br>{fn:,}<br>({fn/total:.1%})<br><i>Uncaught Stockout</i>",
            f"<b>True Negatives (TN)</b><br>{tn:,}<br>({tn/total:.1%})<br><i>Safe Inventory</i>",
        ],
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=x_labels,
            y=y_labels,
            colorscale=[
                [0.0, "#FDEDEC"],
                [0.2, "#FEF5E7"],
                [0.5, "#D4EFDF"],
                [1.0, "#1E8449"],
            ],
            showscale=False,
            hoverinfo="none",
        )
    )

    for i in range(2):
        for j in range(2):
            fig.add_annotation(
                x=x_labels[j],
                y=y_labels[i],
                text=annotations[i][j],
                showarrow=False,
                font=dict(family="Manrope", size=13, color=COLORS["ink"]),
            )

    fig.update_layout(
        title=dict(text="<b>Empirical Validation Confusion Matrix</b>", font=dict(family="Manrope", size=14)),
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        xaxis=dict(side="top"),
        yaxis=dict(autorange="reversed"),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 7. COVERAGE COUNTDOWN BAR CHART
# ─────────────────────────────────────────────────────────────────────────────

def build_coverage_countdown_bar(flagged_df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart showing Days of Coverage vs. Supplier Lead Time
    for top urgent SKUs to make stockout horizons immediately intuitive.
    """
    top_items = flagged_df.head(8).iloc[::-1]  # Reverse for clean top-to-bottom display
    
    sku_labels = [f"{r['sku_id']} ({r['category']})" for _, r in top_items.iterrows()]
    days_cov = top_items["days_coverage"].tolist()
    lead_times = top_items["lead_time"].tolist()

    # If coverage < lead time, color red (stockout before delivery is possible)
    bar_colors = [COLORS["critical"] if cov <= lt else COLORS["high"] for cov, lt in zip(days_cov, lead_times)]

    fig = go.Figure()
    
    # Days of coverage bar
    fig.add_trace(
        go.Bar(
            y=sku_labels,
            x=days_cov,
            orientation="h",
            name="Days of Coverage On Hand",
            marker_color=bar_colors,
            text=[f"{c:.1f} days" for c in days_cov],
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>Coverage: %{x:.1f} days<extra></extra>",
        )
    )

    # Lead time markers
    fig.add_trace(
        go.Scatter(
            y=sku_labels,
            x=lead_times,
            mode="markers",
            name="Supplier Lead Time",
            marker=dict(symbol="line-ns", size=18, line=dict(color=COLORS["ink"], width=3)),
            hovertemplate="Lead Time: %{x:.0f} days<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text="<b>Stockout Countdown vs. Replenishment Lead Time</b>", font=dict(family="Manrope", size=14)),
        xaxis=dict(title="Days", showgrid=True, gridcolor=COLORS["line"]),
        yaxis=dict(title=""),
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
