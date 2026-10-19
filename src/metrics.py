"""Business metrics for the Amazon India dashboard.

Definitions used everywhere (see README, "KPI definitions"):

* Money and unit metrics (sales, profit, average order value, margin, units,
  group summaries, trends) count Delivered + Shipped orders only.
* Order counts and return/cancellation rates count all distinct Order_IDs.
* "Recorded" sales means every order, whatever its status.

All functions take a cleaned DataFrame and never modify it.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .data_cleaning import (
    LOST_STATUSES,
    REVENUE_STATUSES,
    STATUS_ORDER,
    MissingColumnsError,
)

KPI_COLUMNS = ["Order_ID", "Order_Status", "Quantity", "Total_Sales_INR", "Profit_INR"]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def safe_divide(numerator: Any, denominator: Any) -> float:
    """numerator / denominator, or NaN when the result is undefined."""
    if numerator is None or denominator is None:
        return float("nan")
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return float("nan")
    return float(numerator) / float(denominator)


def require_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    """Raise MissingColumnsError if any column is absent."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise MissingColumnsError(missing)


def _sold(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that count towards headline sales: Delivered + Shipped."""
    return df[df["Order_Status"].isin(REVENUE_STATUSES)]


def _distinct_orders_by_status(df: pd.DataFrame) -> Dict[str, int]:
    if df.empty:
        return {}
    counts = df.groupby("Order_Status")["Order_ID"].nunique()
    return {str(status): int(count) for status, count in counts.items()}


# --------------------------------------------------------------------------- #
# Headline KPIs
# --------------------------------------------------------------------------- #
def compute_kpis(df: pd.DataFrame) -> Dict[str, float]:
    """Return every headline KPI as a dictionary (NaN where undefined)."""
    require_columns(df, KPI_COLUMNS)
    sold = _sold(df)
    sales_all = df["Total_Sales_INR"]
    status = df["Order_Status"]

    total_sales = float(sold["Total_Sales_INR"].sum())
    total_profit = float(sold["Profit_INR"].sum())
    sold_orders = int(sold["Order_ID"].nunique())
    total_orders = int(df["Order_ID"].nunique())
    by_status = _distinct_orders_by_status(df)

    recorded_sales = float(sales_all.sum())
    cancelled_sales = float(sales_all[status == "Cancelled"].sum())
    returned_sales = float(sales_all[status == "Returned"].sum())
    lost_sales = cancelled_sales + returned_sales

    returned_orders = by_status.get("Returned", 0)
    cancelled_orders = by_status.get("Cancelled", 0)

    return {
        # Headline (Delivered + Shipped)
        "total_sales": total_sales,
        "total_profit": total_profit,
        "avg_order_value": safe_divide(total_sales, sold_orders),
        "profit_margin_pct": safe_divide(total_profit, total_sales) * 100,
        "units_sold": int(round(float(sold["Quantity"].sum()))),
        "sold_orders": sold_orders,
        # Orders (all statuses)
        "total_orders": total_orders,
        "delivered_orders": by_status.get("Delivered", 0),
        "shipped_orders": by_status.get("Shipped", 0),
        "returned_orders": returned_orders,
        "cancelled_orders": cancelled_orders,
        "return_rate_pct": safe_divide(returned_orders, total_orders) * 100,
        "cancellation_rate_pct": safe_divide(cancelled_orders, total_orders) * 100,
        # Recorded sales and sales lost
        "recorded_sales": recorded_sales,
        "cancelled_sales": cancelled_sales,
        "returned_sales": returned_sales,
        "lost_sales": lost_sales,
        "lost_sales_pct": safe_divide(lost_sales, recorded_sales) * 100,
    }


# --------------------------------------------------------------------------- #
# Trends
# --------------------------------------------------------------------------- #
def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly sales/profit (Delivered + Shipped), in chronological order.

    Months inside the data's date range that have no Delivered/Shipped orders
    are kept with 0 so the line chart does not hide gaps.
    """
    require_columns(df, ["Order_Date", *KPI_COLUMNS])
    columns = ["Month", "Sales", "Profit", "Orders"]
    if df.empty or df["Order_Date"].isna().all():
        return pd.DataFrame(columns=columns)

    sold = _sold(df)
    months = sold["Order_Date"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        sold.groupby(months)
        .agg(
            Sales=("Total_Sales_INR", "sum"),
            Profit=("Profit_INR", "sum"),
            Orders=("Order_ID", "nunique"),
        )
        .sort_index()
    )
    all_months = df["Order_Date"].dropna().dt.to_period("M")
    full_range = pd.period_range(all_months.min(), all_months.max(), freq="M").to_timestamp()
    monthly = monthly.reindex(full_range, fill_value=0)
    monthly.index.name = "Month"
    return monthly.reset_index()[columns]


def trend_change(monthly: pd.DataFrame, window: int = 3) -> Dict[str, float]:
    """% change of the last ``window`` months versus the ``window`` months before.

    Returns NaN values when there are fewer than ``2 * window`` months or the
    earlier period is zero.
    """
    result = {"sales_change_pct": float("nan"), "profit_change_pct": float("nan")}
    if monthly is None or len(monthly) < 2 * window:
        return result
    recent = monthly.tail(window)
    earlier = monthly.iloc[-2 * window : -window]
    for key, column in (("sales_change_pct", "Sales"), ("profit_change_pct", "Profit")):
        before = float(earlier[column].sum())
        now = float(recent[column].sum())
        result[key] = safe_divide(now - before, before) * 100
    return result


# --------------------------------------------------------------------------- #
# Group summaries
# --------------------------------------------------------------------------- #
def summarize_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Sales, profit, units (Delivered + Shipped) and orders (all statuses) per group."""
    require_columns(df, [column, *KPI_COLUMNS])
    sold = _sold(df)
    money = sold.groupby(column).agg(
        Sold_Orders=("Order_ID", "nunique"),
        Sales=("Total_Sales_INR", "sum"),
        Profit=("Profit_INR", "sum"),
        Units=("Quantity", "sum"),
    )
    orders = df.groupby(column)["Order_ID"].nunique().rename("Orders")
    out = orders.to_frame().join(money).fillna(0)
    out["Sold_Orders"] = out["Sold_Orders"].round().astype(int)
    out["Units"] = out["Units"].round().astype(int)
    out["Margin_Pct"] = out["Profit"] / out["Sales"].replace(0, np.nan) * 100
    out.index.name = column
    out = out.reset_index().sort_values("Sales", ascending=False).reset_index(drop=True)
    return out[[column, "Orders", "Sold_Orders", "Sales", "Profit", "Units", "Margin_Pct"]]


def top_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top ``n`` products by Delivered + Shipped sales."""
    require_columns(df, ["Product", "Category", *KPI_COLUMNS])
    sold = _sold(df)
    grouped = (
        sold.groupby(["Product", "Category"])
        .agg(
            Sales=("Total_Sales_INR", "sum"),
            Profit=("Profit_INR", "sum"),
            Units=("Quantity", "sum"),
        )
        .reset_index()
    )
    grouped["Units"] = grouped["Units"].round().astype(int)
    return grouped.sort_values("Sales", ascending=False).head(n).reset_index(drop=True)


def order_status_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Distinct orders per status in a fixed, meaningful order."""
    require_columns(df, ["Order_ID", "Order_Status"])
    counts = (
        df.groupby("Order_Status")["Order_ID"].nunique()
        if not df.empty
        else pd.Series(dtype="int64")
    )
    ordered: List[str] = list(STATUS_ORDER) + [s for s in counts.index if s not in STATUS_ORDER]
    counts = counts.reindex(ordered, fill_value=0)
    return counts.rename_axis("Order_Status").reset_index(name="Orders")


def status_breakdown_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Distinct orders per status for each group, plus within-group rates."""
    require_columns(df, [column, "Order_ID", "Order_Status"])
    out_columns = [
        column,
        "Orders",
        *STATUS_ORDER,
        "Return_Rate_Pct",
        "Cancellation_Rate_Pct",
        "Lost_Orders_Pct",
    ]
    if df.empty:
        return pd.DataFrame(columns=out_columns)

    counts = df.groupby([column, "Order_Status"])["Order_ID"].nunique().unstack(fill_value=0)
    for status in STATUS_ORDER:
        if status not in counts.columns:
            counts[status] = 0
    out = counts[list(STATUS_ORDER)].copy()
    out.columns.name = None
    out.insert(0, "Orders", df.groupby(column)["Order_ID"].nunique())
    out["Return_Rate_Pct"] = out["Returned"] / out["Orders"] * 100
    out["Cancellation_Rate_Pct"] = out["Cancelled"] / out["Orders"] * 100
    out["Lost_Orders_Pct"] = (out["Returned"] + out["Cancelled"]) / out["Orders"] * 100
    out.index.name = column
    out = out.reset_index().sort_values("Orders", ascending=False).reset_index(drop=True)
    return out[out_columns]


def product_health(df: pd.DataFrame) -> pd.DataFrame:
    """Per product: orders lost to returns/cancellations, sales, profit and margin."""
    require_columns(df, ["Product", "Category", *KPI_COLUMNS])
    columns = ["Product", "Category", "Orders", "Lost_Orders_Pct", "Sales", "Profit", "Margin_Pct"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    status = status_breakdown_by(df, "Product")[["Product", "Orders", "Lost_Orders_Pct"]]
    money = summarize_by(df, "Product")[["Product", "Sales", "Profit", "Margin_Pct"]]
    category = df.groupby("Product")["Category"].first().reset_index()
    out = status.merge(money, on="Product", how="left").merge(category, on="Product", how="left")
    return out[columns]


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def apply_filters(
    df: pd.DataFrame,
    *,
    start_date: Any = None,
    end_date: Any = None,
    categories: Optional[Iterable[str]] = None,
    products: Optional[Iterable[str]] = None,
    states: Optional[Iterable[str]] = None,
    statuses: Optional[Iterable[str]] = None,
    payment_methods: Optional[Iterable[str]] = None,
    fulfillment_methods: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Return the rows that match every filter.

    ``None`` means "do not filter on this field". An empty list means "match
    nothing" (the dashboard converts an empty selection to ``None`` itself).
    Both dates are inclusive.
    """
    mask = pd.Series(True, index=df.index)
    if start_date is not None:
        require_columns(df, ["Order_Date"])
        mask &= df["Order_Date"] >= pd.Timestamp(start_date).normalize()
    if end_date is not None:
        require_columns(df, ["Order_Date"])
        mask &= df["Order_Date"] < pd.Timestamp(end_date).normalize() + pd.Timedelta(days=1)
    for column, values in (
        ("Category", categories),
        ("Product", products),
        ("Ship_State", states),
        ("Order_Status", statuses),
        ("Payment_Method", payment_methods),
        ("Fulfillment", fulfillment_methods),
    ):
        if values is not None:
            require_columns(df, [column])
            mask &= df[column].isin(list(values))
    return df[mask].copy()
