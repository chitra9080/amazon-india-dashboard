"""Plotly chart builders. Every function returns a ready-to-display figure.

Money charts are drawn in rupee lakh (1 lakh = 100,000) so axis labels stay
short and readable for a non-technical audience.
"""
from __future__ import annotations

from typing import Dict, Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

LAKH = 100_000.0

ORANGE = "#FF9900"
NAVY = "#232F3E"
BLUE = "#146EB4"
GREEN = "#2E7D32"
AMBER = "#F0A30A"
RED = "#C62828"
GRID = "#E7E7E7"

STATUS_COLORS = {
    "Delivered": GREEN,
    "Shipped": BLUE,
    "Returned": AMBER,
    "Cancelled": RED,
}
CATEGORY_PALETTE = [BLUE, ORANGE, GREEN, "#7B1FA2", RED, "#00838F", "#5D4037"]


def category_color_map(categories: Iterable[str]) -> Dict[str, str]:
    """Stable colour per category (same colour in every chart)."""
    return {
        name: CATEGORY_PALETTE[index % len(CATEGORY_PALETTE)]
        for index, name in enumerate(sorted(set(categories)))
    }


def _base_layout(fig: go.Figure, title: str, height: int | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, x=0, xanchor="left", font=dict(size=16, color=NAVY)),
        font=dict(family="Arial, Helvetica, sans-serif", size=12, color="#0F1111"),
        margin=dict(l=10, r=20, t=60, b=20),
        hoverlabel=dict(font_size=13),
        height=height,
    )
    return fig


def empty_figure(message: str = "No data to display for the current filters.", title: str = "") -> go.Figure:
    """Placeholder figure shown when there is nothing to plot."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=14, color="#565959"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base_layout(fig, title, height=300)


def monthly_trend_chart(monthly: pd.DataFrame) -> go.Figure:
    """Line chart of monthly sales and profit."""
    title = "Monthly Sales & Profit (Delivered + Shipped orders)"
    if monthly is None or monthly.empty:
        return empty_figure(title=title)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=monthly["Month"],
            y=monthly["Sales"] / LAKH,
            name="Sales",
            mode="lines+markers",
            line=dict(color=ORANGE, width=3),
            marker=dict(size=6),
            hovertemplate="Sales: \u20b9%{y:,.2f} lakh<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["Month"],
            y=monthly["Profit"] / LAKH,
            name="Profit",
            mode="lines+markers",
            line=dict(color=BLUE, width=3),
            marker=dict(size=6),
            hovertemplate="Profit: \u20b9%{y:,.2f} lakh<extra></extra>",
        )
    )
    _base_layout(fig, title, height=420)
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title_text="Month", tickformat="%b %Y", hoverformat="%b %Y", gridcolor=GRID)
    fig.update_yaxes(title_text="\u20b9 lakh", rangemode="tozero", gridcolor=GRID)
    return fig


def horizontal_bar(
    data: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    *,
    unit: str = "count",
    axis_title: str = "Count",
    color: str = ORANGE,
) -> go.Figure:
    """Horizontal bar chart, largest bar on top. ``unit`` is 'lakh' or 'count'."""
    if data is None or data.empty:
        return empty_figure(title=title)
    frame = data.sort_values(value_col, ascending=True)
    if unit == "lakh":
        values = frame[value_col] / LAKH
        labels = [f"{v:,.1f}" for v in values]
        hover = "<b>%{y}</b><br>\u20b9%{x:,.2f} lakh<extra></extra>"
    else:
        values = frame[value_col]
        labels = [f"{v:,.0f}" for v in values]
        hover = "<b>%{y}</b><br>%{x:,.0f}<extra></extra>"
    fig = go.Figure(
        go.Bar(
            x=values,
            y=frame[label_col],
            orientation="h",
            marker_color=color,
            text=labels,
            textposition="outside",
            cliponaxis=False,
            hovertemplate=hover,
        )
    )
    _base_layout(fig, title, height=max(260, 90 + 40 * len(frame)))
    top = float(values.max()) if len(values) else 0.0
    fig.update_xaxes(
        title_text=axis_title,
        gridcolor=GRID,
        range=[0, top * 1.2 if top > 0 else 1],
    )
    fig.update_yaxes(title_text="", automargin=True)
    return fig


def top_products_chart(top: pd.DataFrame) -> go.Figure:
    """Horizontal bars for the top products, coloured by category."""
    title = "Top 10 Products by Sales (Delivered + Shipped)"
    if top is None or top.empty:
        return empty_figure(title=title)
    frame = top.assign(Sales_Lakh=top["Sales"] / LAKH, Profit_Lakh=top["Profit"] / LAKH)
    fig = px.bar(
        frame,
        x="Sales_Lakh",
        y="Product",
        color="Category",
        orientation="h",
        color_discrete_map=category_color_map(frame["Category"]),
        custom_data=["Category", "Profit_Lakh", "Units"],
    )
    fig.update_traces(
        texttemplate="%{x:,.1f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>Category: %{customdata[0]}<br>"
            "Sales: \u20b9%{x:,.2f} lakh<br>Profit: \u20b9%{customdata[1]:,.2f} lakh<br>"
            "Units: %{customdata[2]:,}<extra></extra>"
        ),
    )
    _base_layout(fig, title, height=max(380, 110 + 42 * len(frame)))
    top_value = float(frame["Sales_Lakh"].max())
    fig.update_xaxes(
        title_text="Sales (\u20b9 lakh)",
        gridcolor=GRID,
        range=[0, top_value * 1.2 if top_value > 0 else 1],
    )
    fig.update_yaxes(title_text="", categoryorder="total ascending", automargin=True)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, title_text=""))
    return fig


def status_donut(status_counts: pd.DataFrame) -> go.Figure:
    """Donut chart of orders by status."""
    title = "Order Status (share of all orders)"
    if status_counts is None or status_counts.empty or status_counts["Orders"].sum() == 0:
        return empty_figure(title=title)
    colors = [STATUS_COLORS.get(status, "#9E9E9E") for status in status_counts["Order_Status"]]
    total = int(status_counts["Orders"].sum())
    fig = go.Figure(
        go.Pie(
            labels=status_counts["Order_Status"],
            values=status_counts["Orders"],
            hole=0.55,
            sort=False,
            marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
            textinfo="percent",
            textposition="outside",
            automargin=True,
            hovertemplate="<b>%{label}</b><br>%{value:,} orders (%{percent})<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{total:,}</b><br>orders", x=0.5, y=0.5, showarrow=False, font=dict(size=16)
    )
    _base_layout(fig, title, height=400)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5),
    )
    return fig


def category_status_chart(breakdown: pd.DataFrame, column: str = "Category") -> go.Figure:
    """Returned vs cancelled orders for each category."""
    title = "Returned & Cancelled Orders by Category"
    if breakdown is None or breakdown.empty:
        return empty_figure(title=title)
    frame = breakdown.assign(Lost=breakdown["Returned"] + breakdown["Cancelled"]).sort_values(
        "Lost", ascending=True
    )
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=frame[column],
            x=frame["Returned"],
            name="Returned",
            orientation="h",
            marker_color=AMBER,
            customdata=frame["Return_Rate_Pct"],
            hovertemplate=(
                "<b>%{y}</b><br>Returned orders: %{x:,}<br>"
                "Return rate within category: %{customdata:.2f}%<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            y=frame[column],
            x=frame["Cancelled"],
            name="Cancelled",
            orientation="h",
            marker_color=RED,
            customdata=frame["Cancellation_Rate_Pct"],
            hovertemplate=(
                "<b>%{y}</b><br>Cancelled orders: %{x:,}<br>"
                "Cancellation rate within category: %{customdata:.2f}%<extra></extra>"
            ),
        )
    )
    _base_layout(fig, title, height=max(320, 120 + 60 * len(frame)))
    fig.update_layout(
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title_text="Number of orders", gridcolor=GRID)
    fig.update_yaxes(title_text="", automargin=True)
    return fig
