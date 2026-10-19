"""Tests for src/metrics.py using a tiny dataset whose answers are worked out by hand.

Hand-made data (6 orders):

id  date        category     product  qty  sales  profit  status     state
O1  2024-01-10  Electronics  Phone    2    1000   200     Delivered  Karnataka
O2  2024-01-20  Electronics  Watch    1     500   100     Shipped    Karnataka
O3  2024-02-05  Apparel      Shirt    3     300    60     Delivered  Delhi
O4  2024-02-15  Apparel      Shirt    1     100     0     Returned   Delhi
O5  2024-03-01  Electronics  Phone    2     800     0     Cancelled  Delhi
O6  2024-03-10  Home         Kettle   4     600   150     Delivered  Kerala

Delivered + Shipped: sales 2400, profit 510, units 10, orders 4.
"""
import math

import pandas as pd
import pytest

from src import metrics
from src.data_cleaning import MissingColumnsError

COLUMNS = [
    "Order_ID", "Order_Date", "Category", "Product", "Quantity", "Total_Sales_INR",
    "Profit_INR", "Payment_Method", "Fulfillment", "Order_Status", "Ship_State",
]
ROWS = [
    ("O1", "2024-01-10", "Electronics", "Phone", 2, 1000.0, 200.0, "UPI", "Amazon (FBA)", "Delivered", "Karnataka"),
    ("O2", "2024-01-20", "Electronics", "Watch", 1, 500.0, 100.0, "COD", "Amazon (FBA)", "Shipped", "Karnataka"),
    ("O3", "2024-02-05", "Apparel", "Shirt", 3, 300.0, 60.0, "UPI", "Merchant (FBM)", "Delivered", "Delhi"),
    ("O4", "2024-02-15", "Apparel", "Shirt", 1, 100.0, 0.0, "UPI", "Merchant (FBM)", "Returned", "Delhi"),
    ("O5", "2024-03-01", "Electronics", "Phone", 2, 800.0, 0.0, "COD", "Amazon (FBA)", "Cancelled", "Delhi"),
    ("O6", "2024-03-10", "Home", "Kettle", 4, 600.0, 150.0, "Card", "Seller Flex", "Delivered", "Kerala"),
]


@pytest.fixture
def df():
    frame = pd.DataFrame(ROWS, columns=COLUMNS)
    frame["Order_Date"] = pd.to_datetime(frame["Order_Date"])
    return frame


@pytest.fixture
def kpis(df):
    return metrics.compute_kpis(df)


# ---------------------------------------------------------------- KPIs ----
def test_total_sales_counts_delivered_and_shipped_only(kpis):
    assert kpis["total_sales"] == 2400.0


def test_total_profit(kpis):
    assert kpis["total_profit"] == 510.0


def test_unique_order_counts(kpis):
    assert kpis["total_orders"] == 6
    assert kpis["sold_orders"] == 4


def test_total_units_sold(kpis):
    assert kpis["units_sold"] == 10


def test_average_order_value(kpis):
    assert kpis["avg_order_value"] == pytest.approx(2400 / 4)


def test_profit_margin_is_weighted_not_average_of_rows(kpis):
    assert kpis["profit_margin_pct"] == pytest.approx(510 / 2400 * 100)  # 21.25


def test_recorded_and_lost_sales(kpis):
    assert kpis["recorded_sales"] == 3300.0
    assert kpis["cancelled_sales"] == 800.0
    assert kpis["returned_sales"] == 100.0
    assert kpis["lost_sales"] == 900.0
    assert kpis["lost_sales_pct"] == pytest.approx(900 / 3300 * 100)


def test_recorded_sales_equals_sales_plus_lost(kpis):
    assert kpis["recorded_sales"] == pytest.approx(kpis["total_sales"] + kpis["lost_sales"])


def test_status_order_counts(kpis):
    assert kpis["delivered_orders"] == 3
    assert kpis["shipped_orders"] == 1
    assert kpis["returned_orders"] == 1
    assert kpis["cancelled_orders"] == 1


def test_return_and_cancellation_rate_use_all_orders(kpis):
    assert kpis["return_rate_pct"] == pytest.approx(1 / 6 * 100)
    assert kpis["cancellation_rate_pct"] == pytest.approx(1 / 6 * 100)


# --------------------------------------------------------- aggregations ----
def test_category_aggregation(df):
    result = metrics.summarize_by(df, "Category").set_index("Category")
    assert result.loc["Electronics", "Sales"] == 1500.0
    assert result.loc["Electronics", "Profit"] == 300.0
    assert result.loc["Electronics", "Units"] == 3
    assert result.loc["Electronics", "Orders"] == 3  # O1, O2, O5 (all statuses)
    assert result.loc["Apparel", "Sales"] == 300.0
    assert result.loc["Apparel", "Orders"] == 2
    assert result.loc["Home", "Sales"] == 600.0
    assert result.loc["Home", "Margin_Pct"] == pytest.approx(25.0)
    assert list(metrics.summarize_by(df, "Category")["Category"]) == ["Electronics", "Home", "Apparel"]


def test_state_wise_order_counts(df):
    result = metrics.summarize_by(df, "Ship_State").set_index("Ship_State")["Orders"].to_dict()
    assert result == {"Delhi": 3, "Karnataka": 2, "Kerala": 1}


def test_payment_and_fulfilment_aggregation(df):
    payment = metrics.summarize_by(df, "Payment_Method").set_index("Payment_Method")
    assert payment.loc["UPI", "Sales"] == 1300.0  # O1 + O3 (O4 returned)
    assert payment.loc["COD", "Sales"] == 500.0  # O2 only (O5 cancelled)
    fulfilment = metrics.summarize_by(df, "Fulfillment").set_index("Fulfillment")
    assert fulfilment.loc["Amazon (FBA)", "Profit"] == 300.0


def test_monthly_aggregation_is_chronological(df):
    monthly = metrics.monthly_trend(df)
    assert list(monthly["Month"]) == list(pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))
    assert list(monthly["Sales"]) == [1500.0, 300.0, 600.0]
    assert list(monthly["Profit"]) == [300.0, 60.0, 150.0]
    assert monthly["Month"].is_monotonic_increasing


def test_monthly_trend_keeps_empty_months_as_zero(df):
    # No February rows at all: the month is still listed, with 0 sales.
    without_february = df[df["Order_Date"].dt.month != 2]
    monthly = metrics.monthly_trend(without_february)
    assert len(monthly) == 3
    assert list(monthly["Sales"]) == [1500.0, 0.0, 600.0]
    # February has only a Returned order: it appears as 0 Delivered/Shipped sales.
    only_some = metrics.monthly_trend(df[df["Order_ID"].isin(["O1", "O4", "O6"])])
    assert list(only_some["Sales"]) == [1000.0, 0.0, 600.0]


def test_months_are_not_sorted_alphabetically(df):
    shifted = df.copy()
    shifted.loc[shifted["Order_ID"] == "O1", "Order_Date"] = pd.Timestamp("2023-12-30")
    months = list(metrics.monthly_trend(shifted)["Month"])
    assert months == sorted(months)
    assert months[0] == pd.Timestamp("2023-12-01")


def test_category_status_breakdown(df):
    result = metrics.status_breakdown_by(df, "Category").set_index("Category")
    assert result.loc["Electronics", "Delivered"] == 1
    assert result.loc["Electronics", "Shipped"] == 1
    assert result.loc["Electronics", "Cancelled"] == 1
    assert result.loc["Electronics", "Returned"] == 0
    assert result.loc["Electronics", "Cancellation_Rate_Pct"] == pytest.approx(100 / 3)
    assert result.loc["Apparel", "Returned"] == 1
    assert result.loc["Apparel", "Return_Rate_Pct"] == pytest.approx(50.0)


def test_order_status_counts_fixed_order(df):
    result = metrics.order_status_counts(df)
    assert list(result["Order_Status"]) == ["Delivered", "Shipped", "Returned", "Cancelled"]
    assert list(result["Orders"]) == [3, 1, 1, 1]


def test_top_products_sorted_and_limited(df):
    top = metrics.top_products(df, n=3)
    assert list(top["Product"]) == ["Phone", "Kettle", "Watch"]
    assert list(top["Sales"]) == [1000.0, 600.0, 500.0]  # cancelled Phone order excluded
    assert len(metrics.top_products(df, n=1)) == 1


def test_product_health_flags_lost_orders(df):
    health = metrics.product_health(df).set_index("Product")
    assert health.loc["Shirt", "Lost_Orders_Pct"] == pytest.approx(50.0)  # O4 returned of O3+O4
    assert health.loc["Phone", "Lost_Orders_Pct"] == pytest.approx(50.0)  # O5 cancelled of O1+O5


def test_trend_change_percentages():
    monthly = pd.DataFrame(
        {"Sales": [100, 100, 100, 200, 200, 200], "Profit": [10, 10, 10, 10, 10, 10]}
    )
    change = metrics.trend_change(monthly, window=3)
    assert change["sales_change_pct"] == pytest.approx(100.0)
    assert change["profit_change_pct"] == pytest.approx(0.0)


def test_trend_change_needs_enough_months_and_nonzero_base():
    short = pd.DataFrame({"Sales": [1, 2, 3], "Profit": [1, 1, 1]})
    assert math.isnan(metrics.trend_change(short)["sales_change_pct"])
    zero_base = pd.DataFrame({"Sales": [0, 0, 0, 5, 5, 5], "Profit": [0, 0, 0, 1, 1, 1]})
    assert math.isnan(metrics.trend_change(zero_base)["sales_change_pct"])


# ----------------------------------------------------- duplicate IDs ------
def test_multi_line_order_is_counted_once_but_units_and_sales_add_up(df):
    extra = pd.DataFrame(
        [("O1", "2024-01-10", "Electronics", "Case", 1, 100.0, 20.0, "UPI", "Amazon (FBA)", "Delivered", "Karnataka")],
        columns=COLUMNS,
    )
    extra["Order_Date"] = pd.to_datetime(extra["Order_Date"])
    combined = pd.concat([df, extra], ignore_index=True)
    k = metrics.compute_kpis(combined)
    assert k["total_orders"] == 6  # O1 still one order
    assert k["sold_orders"] == 4
    assert k["units_sold"] == 11
    assert k["total_sales"] == 2500.0
    assert k["avg_order_value"] == pytest.approx(2500 / 4)
    state = metrics.summarize_by(combined, "Ship_State").set_index("Ship_State")
    assert state.loc["Karnataka", "Orders"] == 2


# ----------------------------------------------------- missing values ------
def test_missing_profit_is_not_invented(df):
    holed = df.copy()
    holed.loc[holed["Order_ID"] == "O2", "Profit_INR"] = float("nan")
    k = metrics.compute_kpis(holed)
    assert k["total_profit"] == 410.0  # 510 - 100, missing value skipped (not estimated)
    assert k["total_sales"] == 2400.0


# ------------------------------------------- division by zero / empty ------
def test_safe_divide():
    assert metrics.safe_divide(10, 4) == 2.5
    assert math.isnan(metrics.safe_divide(1, 0))
    assert math.isnan(metrics.safe_divide(None, 5))
    assert math.isnan(metrics.safe_divide(5, float("nan")))


def test_only_cancelled_orders_gives_na_not_a_crash(df):
    cancelled = df[df["Order_Status"] == "Cancelled"]
    k = metrics.compute_kpis(cancelled)
    assert k["total_sales"] == 0.0
    assert math.isnan(k["avg_order_value"])
    assert math.isnan(k["profit_margin_pct"])
    assert k["cancellation_rate_pct"] == pytest.approx(100.0)
    assert k["recorded_sales"] == 800.0


def test_empty_dataset_does_not_crash(df):
    empty = df.iloc[0:0]
    k = metrics.compute_kpis(empty)
    assert k["total_orders"] == 0 and k["total_sales"] == 0.0 and k["units_sold"] == 0
    assert math.isnan(k["return_rate_pct"]) and math.isnan(k["cancellation_rate_pct"])
    assert metrics.monthly_trend(empty).empty
    assert metrics.summarize_by(empty, "Category").empty
    assert metrics.top_products(empty).empty
    assert metrics.status_breakdown_by(empty, "Category").empty
    assert metrics.product_health(empty).empty
    assert list(metrics.order_status_counts(empty)["Orders"]) == [0, 0, 0, 0]


# ------------------------------------------------------ missing columns ----
def test_missing_column_raises_clear_error(df):
    with pytest.raises(MissingColumnsError) as error:
        metrics.compute_kpis(df.drop(columns=["Profit_INR"]))
    assert "Profit_INR" in str(error.value)
    with pytest.raises(MissingColumnsError):
        metrics.summarize_by(df, "Region")


# ------------------------------------------------------------- filters ----
def test_filter_with_no_matching_rows_returns_empty_and_kpis_still_work(df):
    result = metrics.apply_filters(df, categories=["Nonexistent"])
    assert result.empty
    assert metrics.compute_kpis(result)["total_orders"] == 0


def test_empty_selection_list_matches_nothing_while_none_means_all(df):
    assert metrics.apply_filters(df, states=[]).empty
    assert len(metrics.apply_filters(df, states=None)) == len(df)


def test_date_filter_is_inclusive_on_both_ends(df):
    result = metrics.apply_filters(df, start_date="2024-01-20", end_date="2024-02-05")
    assert list(result["Order_ID"]) == ["O2", "O3"]
    same_day = metrics.apply_filters(df, start_date="2024-02-05", end_date="2024-02-05")
    assert list(same_day["Order_ID"]) == ["O3"]


def test_combined_filters_and_original_is_untouched(df):
    before = df.copy()
    result = metrics.apply_filters(
        df, categories=["Electronics"], statuses=["Delivered", "Shipped"], states=["Karnataka"]
    )
    assert list(result["Order_ID"]) == ["O1", "O2"]
    pd.testing.assert_frame_equal(df, before)


def test_filter_changes_kpis(df):
    k = metrics.compute_kpis(metrics.apply_filters(df, categories=["Home"]))
    assert k["total_sales"] == 600.0 and k["total_orders"] == 1
