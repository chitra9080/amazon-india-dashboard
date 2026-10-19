"""Amazon India Sales & Profit Dashboard (Streamlit).

Run from the project folder with:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import html
import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import charts, metrics  # noqa: E402
from src.data_cleaning import MissingColumnsError, clean_data  # noqa: E402
from src.data_loader import DataLoadError, get_default_data_path, load_raw_data  # noqa: E402
from src.formatting import format_inr, format_inr_full, format_int, format_pct  # noqa: E402

st.set_page_config(
    page_title="Amazon India Sales & Profit Dashboard",
    page_icon="\U0001F4CA",
    layout="wide",
)

CSS = """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px;}
.app-header {background: linear-gradient(90deg, #131A22 0%, #232F3E 100%);
  padding: 1.1rem 1.4rem; border-radius: 10px; border-bottom: 4px solid #FF9900;
  margin-bottom: 0.9rem;}
.app-header h1 {color: #FFFFFF; font-size: 1.75rem; margin: 0; padding: 0;}
.app-header p {color: #D5D9D9; margin: 0.3rem 0 0 0; font-size: 0.95rem;}
.app-header p.range {color: #FF9900; font-weight: 600;}
.kpi-card {background: #FFFFFF; border: 1px solid #D5D9D9; border-left: 5px solid #FF9900;
  border-radius: 8px; padding: 0.75rem 1rem; min-height: 120px; margin-bottom: 0.7rem;}
.kpi-card.blue {border-left-color: #146EB4;}
.kpi-card.green {border-left-color: #2E7D32;}
.kpi-card.amber {border-left-color: #F0A30A;}
.kpi-card.red {border-left-color: #C62828;}
.kpi-label {font-size: 0.76rem; color: #565959; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.03em;}
.kpi-value {font-size: 1.6rem; font-weight: 700; color: #0F1111; line-height: 1.3;}
.kpi-sub {font-size: 0.78rem; color: #565959;}
</style>
"""

DEFINITIONS = """
**Basis used everywhere on this dashboard**

* **Sales, profit, average order value, profit margin and units sold** count **Delivered + Shipped** orders only.
* **Order counts and return / cancellation rates** count **all distinct orders** (every status).
* **Total Recorded Sales** is the sales value of *all* orders, including Returned and Cancelled ones.
  Total Recorded Sales = Total Sales + Sales in Cancelled orders + Sales in Returned orders.

| KPI | Formula |
|---|---|
| Total Sales | Sum of `Total_Sales_INR` for Delivered + Shipped orders |
| Total Profit | Sum of `Profit_INR` for Delivered + Shipped orders |
| Average Order Value | Total Sales ÷ number of distinct Delivered + Shipped orders |
| Profit Margin % | Total Profit ÷ Total Sales × 100 |
| Total Orders | Number of distinct `Order_ID` values (all statuses) |
| Total Units Sold | Sum of `Quantity` for Delivered + Shipped orders |
| Return Rate % | Returned orders ÷ all orders × 100 |
| Cancellation Rate % | Cancelled orders ÷ all orders × 100 |
| Share of Recorded Sales Lost | (Sales in Cancelled + Returned orders) ÷ Total Recorded Sales × 100 |

Where a calculation is impossible (for example, dividing by zero when a filter leaves no
Delivered or Shipped orders) the dashboard shows **N/A** instead of a misleading number.
"""

LIMITATIONS = """
* The dataset has one row per order and one product per order; there are no multi-item orders.
* The profit field is exactly zero for every Cancelled and Returned order, so profit is only
  recorded for Delivered and Shipped orders.
* Shipped orders are still in transit; they are counted as sales but may later be returned.
* Order dates run from January 2024 to August 2026, so 2026 is a partial year. Compare months, not calendar years.
* Unit prices overlap heavily inside a category (for example, every Electronics product ranges
  from a few hundred to about ₹35,000), so the data looks synthetic. Product rankings should be
  read as a demonstration of the dashboard, not as real business conclusions.
* Only the shipping state is available (10 states), so there is no city-level or map view.
"""


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading and cleaning the dataset...")
def _load_default(path_str: str, modified_time: float):
    """Cached load of the project dataset (re-read if the file changes)."""
    return clean_data(load_raw_data(path_str))


@st.cache_data(show_spinner="Loading and cleaning the uploaded file...")
def _load_uploaded(file_bytes: bytes):
    return clean_data(load_raw_data(io.BytesIO(file_bytes)))


def load_data():
    """Return (clean_df, cleaning_report, source_name). Never invents data."""
    path = get_default_data_path()
    try:
        if path.exists():
            frame, report = _load_default(str(path), path.stat().st_mtime)
            return frame, report, path.name
        st.warning(
            f"The dataset was not found at `{path}`. Copy 'Amazon_Sales_Data_India.xlsx' "
            "into the project's `data` folder, or upload the Excel file below."
        )
        uploaded = st.file_uploader("Upload the Excel dataset (.xlsx)", type=["xlsx"])
        if uploaded is None:
            st.stop()
        frame, report = _load_uploaded(uploaded.getvalue())
        return frame, report, uploaded.name
    except (DataLoadError, MissingColumnsError) as error:
        st.error(f"The dataset could not be loaded.\n\n{error}")
        st.stop()


# --------------------------------------------------------------------------- #
# Small UI helpers
# --------------------------------------------------------------------------- #
def kpi_card(label: str, value: str, sub: str = "", tone: str = "orange") -> str:
    return (
        f'<div class="kpi-card {tone}">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{html.escape(value)}</div>'
        f'<div class="kpi-sub">{html.escape(sub)}</div></div>'
    )


def render_cards(cards) -> None:
    """cards: list of (label, value, sub, tone) shown side by side."""
    columns = st.columns(len(cards))
    for column, card in zip(columns, cards):
        column.markdown(kpi_card(*card), unsafe_allow_html=True)


def leader_text(summary: pd.DataFrame, label_col: str, value_col: str, noun: str, money: bool = True):
    """Sentence naming the top group and its share of the total (None if no data)."""
    if summary is None or summary.empty or summary[value_col].sum() <= 0:
        return None
    top = summary.sort_values(value_col, ascending=False).iloc[0]
    share = metrics.safe_divide(top[value_col], summary[value_col].sum()) * 100
    shown = format_inr(top[value_col]) if money else format_int(top[value_col])
    return f"**{top[label_col]}** is the top {noun}: {shown} ({share:.1f}% of the total)."


def show_insights(*lines) -> None:
    lines = [line for line in lines if line]
    if lines:
        st.info("\n\n".join(lines))


def _reset_filters() -> None:
    st.session_state["reset_count"] = st.session_state.get("reset_count", 0) + 1


# --------------------------------------------------------------------------- #
# Sidebar filters
# --------------------------------------------------------------------------- #
def sidebar_filters(df: pd.DataFrame):
    """Draw the filters and return (filtered_df, start_date, end_date, active_filter_names)."""
    st.sidebar.header("Filters")
    st.sidebar.caption("Leave a filter empty to include everything.")
    st.sidebar.button("Reset all filters", on_click=_reset_filters)
    n = st.session_state.get("reset_count", 0)  # new widget keys after each reset

    min_date = df["Order_Date"].min().date()
    max_date = df["Order_Date"].max().date()
    chosen = st.sidebar.date_input(
        "Order date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY",
        key=f"f_date_{n}",
    )
    if isinstance(chosen, (tuple, list)):
        if len(chosen) == 2:
            start, end = chosen
        elif len(chosen) == 1:
            start = end = chosen[0]
            st.sidebar.caption("Pick an end date to finish the date range.")
        else:
            start, end = min_date, max_date
    else:
        start = end = chosen

    categories = st.sidebar.multiselect(
        "Product category",
        sorted(df["Category"].unique()),
        placeholder="All categories",
        key=f"f_category_{n}",
    )
    product_pool_df = df[df["Category"].isin(categories)] if categories else df
    product_pool = sorted(product_pool_df["Product"].unique())
    signature = hashlib.md5("|".join(product_pool).encode("utf-8")).hexdigest()[:8]
    products = st.sidebar.multiselect(
        "Product name",
        product_pool,
        placeholder="All products",
        key=f"f_product_{n}_{signature}",
    )
    states = st.sidebar.multiselect(
        "State", sorted(df["Ship_State"].unique()), placeholder="All states", key=f"f_state_{n}"
    )
    statuses = st.sidebar.multiselect(
        "Order status",
        sorted(df["Order_Status"].unique()),
        placeholder="All statuses",
        key=f"f_status_{n}",
    )
    payments = st.sidebar.multiselect(
        "Payment method",
        sorted(df["Payment_Method"].unique()),
        placeholder="All payment methods",
        key=f"f_payment_{n}",
    )
    fulfilments = st.sidebar.multiselect(
        "Fulfillment method",
        sorted(df["Fulfillment"].unique()),
        placeholder="All fulfillment methods",
        key=f"f_fulfillment_{n}",
    )

    filtered = metrics.apply_filters(
        df,
        start_date=start,
        end_date=end,
        categories=categories or None,
        products=products or None,
        states=states or None,
        statuses=statuses or None,
        payment_methods=payments or None,
        fulfillment_methods=fulfilments or None,
    )
    active = [
        name
        for name, values in (
            ("Category", categories),
            ("Product", products),
            ("State", states),
            ("Order status", statuses),
            ("Payment method", payments),
            ("Fulfillment", fulfilments),
        )
        if values
    ]
    return filtered, start, end, active


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
def render_overview(df: pd.DataFrame, k: dict) -> None:
    st.subheader("1) Overall Sales & Profit Performance")
    st.caption("Business question: How is the business performing overall?")

    render_cards(
        [
            ("Total Sales", format_inr(k["total_sales"]),
             f"Delivered + Shipped · {format_inr_full(k['total_sales'])}", "orange"),
            ("Total Profit", format_inr(k["total_profit"]),
             f"Delivered + Shipped · {format_inr_full(k['total_profit'])}", "green"),
            ("Average Order Value", format_inr(k["avg_order_value"]),
             "Total Sales ÷ Delivered + Shipped orders", "blue"),
        ]
    )
    render_cards(
        [
            ("Profit Margin", format_pct(k["profit_margin_pct"]),
             "Total Profit ÷ Total Sales", "green"),
            ("Total Orders", format_int(k["total_orders"]),
             f"All statuses · {format_int(k['sold_orders'])} Delivered + Shipped", "blue"),
            ("Total Units Sold", format_int(k["units_sold"]),
             "Delivered + Shipped orders", "orange"),
        ]
    )

    st.markdown("##### Recorded sales vs. sales lost to cancellations and returns")
    render_cards(
        [
            ("Total Recorded Sales (all orders)", format_inr(k["recorded_sales"]),
             "Delivered + Shipped + Returned + Cancelled", "blue"),
            ("Sales in Cancelled Orders", format_inr(k["cancelled_sales"]),
             f"{format_int(k['cancelled_orders'])} orders · not in Total Sales", "red"),
            ("Sales in Returned Orders", format_inr(k["returned_sales"]),
             f"{format_int(k['returned_orders'])} orders · not in Total Sales", "amber"),
            ("Share of Recorded Sales Lost", format_pct(k["lost_sales_pct"]),
             "(Cancelled + Returned) ÷ Recorded sales", "red"),
        ]
    )

    monthly = metrics.monthly_trend(df)
    st.plotly_chart(charts.monthly_trend_chart(monthly), key="chart_monthly_trend")

    change = metrics.trend_change(monthly)
    sales_change, profit_change = change["sales_change_pct"], change["profit_change_pct"]
    if pd.isna(sales_change) or pd.isna(profit_change):
        show_insights(
            "Choose a date range of at least 6 months to see whether sales and profit "
            "are improving or declining."
        )
    else:
        def word(value: float) -> str:
            return "up" if value >= 0 else "down"

        show_insights(
            "**Trend:** comparing the last 3 months with the 3 months before, sales are "
            f"{word(sales_change)} {abs(sales_change):.1f}% and profit is "
            f"{word(profit_change)} {abs(profit_change):.1f}%."
        )

    with st.expander("View the monthly numbers"):
        table = monthly.assign(
            Month=monthly["Month"].dt.strftime("%b %Y"),
            Sales=monthly["Sales"].round(2),
            Profit=monthly["Profit"].round(2),
        ).rename(columns={"Sales": "Sales (₹)", "Profit": "Profit (₹)", "Orders": "Delivered + Shipped orders"})
        st.dataframe(table, hide_index=True)


def render_products(df: pd.DataFrame) -> None:
    st.subheader("2) Category & Product Performance")
    st.caption("Business question: Which products and categories are driving the business?")

    category = metrics.summarize_by(df, "Category")
    col1, col2, col3 = st.columns(3)
    col1.plotly_chart(
        charts.horizontal_bar(category, "Category", "Sales", "Category-wise Sales (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.ORANGE),
        key="chart_cat_sales",
    )
    col2.plotly_chart(
        charts.horizontal_bar(category, "Category", "Profit", "Category-wise Profit (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.GREEN),
        key="chart_cat_profit",
    )
    col3.plotly_chart(
        charts.horizontal_bar(category, "Category", "Units", "Category-wise Units Sold",
                              unit="count", axis_title="Units", color=charts.BLUE),
        key="chart_cat_units",
    )

    top = metrics.top_products(df, 10)
    st.plotly_chart(charts.top_products_chart(top), key="chart_top_products")

    show_insights(
        leader_text(category, "Category", "Sales", "category by sales"),
        leader_text(top, "Product", "Sales", "product by sales") if not top.empty else None,
    )

    st.markdown("##### Products that may need attention")
    health = metrics.product_health(df)
    if health.empty:
        st.write("No products to show for the current filters.")
        return
    left, right = st.columns(2)
    most_lost = (
        health.sort_values("Lost_Orders_Pct", ascending=False)
        .head(5)[["Product", "Category", "Orders", "Lost_Orders_Pct"]]
        .rename(columns={"Lost_Orders_Pct": "Returned + cancelled orders (%)"})
        .round({"Returned + cancelled orders (%)": 2})
    )
    left.markdown("**Highest share of returned + cancelled orders**")
    left.dataframe(most_lost, hide_index=True)
    lowest_margin = (
        health[health["Sales"] > 0]
        .sort_values("Margin_Pct")
        .head(5)
        .assign(Sales_Lakh=lambda d: (d["Sales"] / charts.LAKH).round(2))[
            ["Product", "Category", "Margin_Pct", "Sales_Lakh"]
        ]
        .rename(columns={"Margin_Pct": "Profit margin (%)", "Sales_Lakh": "Sales (₹ lakh)"})
        .round({"Profit margin (%)": 2})
    )
    right.markdown("**Lowest profit margin (Delivered + Shipped)**")
    right.dataframe(lowest_margin, hide_index=True)


def render_order_status(df: pd.DataFrame, k: dict) -> None:
    st.subheader("3) Order Status & Revenue Loss")
    st.caption("Business question: How many orders are successfully completed and how many are being lost?")

    total = k["total_orders"]

    def share(count: int) -> str:
        return f"{format_pct(metrics.safe_divide(count, total) * 100, 1)} of all orders"

    render_cards(
        [
            ("Delivered Orders", format_int(k["delivered_orders"]), share(k["delivered_orders"]), "green"),
            ("Shipped Orders", format_int(k["shipped_orders"]), share(k["shipped_orders"]), "blue"),
            ("Returned Orders", format_int(k["returned_orders"]), share(k["returned_orders"]), "amber"),
            ("Cancelled Orders", format_int(k["cancelled_orders"]), share(k["cancelled_orders"]), "red"),
        ]
    )
    render_cards(
        [
            ("Return Rate", format_pct(k["return_rate_pct"]), "Returned orders ÷ all orders", "amber"),
            ("Cancellation Rate", format_pct(k["cancellation_rate_pct"]), "Cancelled orders ÷ all orders", "red"),
            ("Sales in Returned + Cancelled Orders", format_inr(k["lost_sales"]),
             f"{format_pct(k['lost_sales_pct'])} of Total Recorded Sales", "red"),
        ]
    )

    status_counts = metrics.order_status_counts(df)
    breakdown = metrics.status_breakdown_by(df, "Category")
    left, right = st.columns(2)
    left.plotly_chart(charts.status_donut(status_counts), key="chart_status_donut")
    right.plotly_chart(charts.category_status_chart(breakdown, "Category"), key="chart_category_status")

    lost_orders = k["returned_orders"] + k["cancelled_orders"]
    lost_share = metrics.safe_divide(lost_orders, total) * 100
    if not pd.isna(lost_share):
        show_insights(
            f"About **{lost_share:.1f} out of every 100 orders** are returned or cancelled, "
            f"tying up **{format_inr(k['lost_sales'])}** of recorded sales "
            f"({format_pct(k['lost_sales_pct'], 1)})."
        )

    with st.expander("View returns and cancellations by category"):
        table = breakdown.rename(
            columns={
                "Return_Rate_Pct": "Return rate (%)",
                "Cancellation_Rate_Pct": "Cancellation rate (%)",
                "Lost_Orders_Pct": "Returned + cancelled (%)",
            }
        ).round(2)
        st.dataframe(table, hide_index=True)


def render_geography(df: pd.DataFrame) -> None:
    st.subheader("4) Payment, Fulfillment & Geographic Performance")
    st.caption("Business question: Which payment methods, fulfillment methods and states are generating business?")

    payment = metrics.summarize_by(df, "Payment_Method")
    fulfilment = metrics.summarize_by(df, "Fulfillment")
    states = metrics.summarize_by(df, "Ship_State")

    st.markdown("##### Payment method")
    a, b = st.columns(2)
    a.plotly_chart(
        charts.horizontal_bar(payment, "Payment_Method", "Sales", "Sales by Payment Method (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.ORANGE),
        key="chart_pay_sales",
    )
    b.plotly_chart(
        charts.horizontal_bar(payment, "Payment_Method", "Profit", "Profit by Payment Method (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.GREEN),
        key="chart_pay_profit",
    )

    st.markdown("##### Fulfillment method")
    c, d = st.columns(2)
    c.plotly_chart(
        charts.horizontal_bar(fulfilment, "Fulfillment", "Sales", "Sales by Fulfillment Method (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.ORANGE),
        key="chart_ful_sales",
    )
    d.plotly_chart(
        charts.horizontal_bar(fulfilment, "Fulfillment", "Profit", "Profit by Fulfillment Method (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.GREEN),
        key="chart_ful_profit",
    )

    st.markdown("##### State")
    e, f, g = st.columns(3)
    e.plotly_chart(
        charts.horizontal_bar(states, "Ship_State", "Sales", "State-wise Sales (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.ORANGE),
        key="chart_state_sales",
    )
    f.plotly_chart(
        charts.horizontal_bar(states, "Ship_State", "Profit", "State-wise Profit (₹ lakh)",
                              unit="lakh", axis_title="₹ lakh", color=charts.GREEN),
        key="chart_state_profit",
    )
    g.plotly_chart(
        charts.horizontal_bar(states, "Ship_State", "Orders", "State-wise Orders (all statuses)",
                              unit="count", axis_title="Orders", color=charts.BLUE),
        key="chart_state_orders",
    )
    st.caption(
        "Sales and profit charts count Delivered + Shipped orders. State-wise Orders counts "
        "all orders of every status. A map is not shown because only the state name is "
        "available and no state boundary file is bundled with the app."
    )

    show_insights(
        leader_text(states, "Ship_State", "Sales", "state by sales"),
        leader_text(payment, "Payment_Method", "Sales", "payment method by sales"),
        leader_text(fulfilment, "Fulfillment", "Sales", "fulfillment method by sales"),
    )


def render_about(report: dict, source_name: str) -> None:
    st.subheader("About the data and the numbers")
    st.markdown(DEFINITIONS)

    st.markdown("##### Data cleaning report")
    st.caption(f"Source file: {source_name}")
    rows = [
        ("Rows read from the Excel file", report["rows_in"]),
        ("Rows removed: missing Order_ID", report["rows_dropped_missing_order_id"]),
        ("Rows removed: invalid or missing date", report["rows_dropped_invalid_date"]),
        ("Rows removed: exact duplicates", report["exact_duplicate_rows_removed"]),
        ("Rows kept after cleaning", report["rows_out"]),
        ("Distinct orders", report["unique_orders"]),
        ("Repeated Order_IDs kept (different content)", report["repeated_order_ids_kept"]),
        ("Date range", f"{report['date_min']} to {report['date_max']}"),
        ("Missing labels filled with 'Unknown'", str(report["missing_text_filled_with_unknown"] or "None")),
        ("Non-numeric values set to missing", str(report["non_numeric_values_set_to_missing"] or "None")),
        ("Negative values set to missing", str(report["negative_values_set_to_missing"] or "None")),
        ("Missing numeric values remaining (not estimated)", str(report["missing_numeric_values_remaining"] or "None")),
        ("Unrecognised order statuses", ", ".join(report["unrecognised_order_statuses"]) or "None"),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Check", "Result"]).astype(str), hide_index=True)

    st.markdown("##### Limitations of the dataset")
    st.markdown(LIMITATIONS)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    df, report, source_name = load_data()
    if df.empty:
        st.error("The dataset has no usable rows after cleaning. See the cleaning report in the README.")
        st.stop()

    filtered, start, end, active = sidebar_filters(df)

    orders_shown = int(filtered["Order_ID"].nunique())
    filter_note = "Extra filters: " + ", ".join(active) if active else "No extra filters applied"
    st.markdown(
        f"""
        <div class="app-header">
          <h1>Amazon India Sales &amp; Profit Dashboard</h1>
          <p>One-page management view of sales, profit, products, orders, payments,
             fulfillment and states.</p>
          <p class="range">Showing orders from {start:%d %b %Y} to {end:%d %b %Y}
             · {orders_shown:,} orders · {html.escape(filter_note)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.warning(
            "No orders match the current filters. Widen the date range, remove a filter, "
            "or click **Reset all filters** in the sidebar."
        )
        st.stop()

    st.info(
        "**How to read this dashboard:** sales, profit, average order value, margin and units count "
        "**Delivered + Shipped** orders only. Order counts and return / cancellation rates count "
        "**all orders**. Total Recorded Sales (all statuses) is shown separately."
    )

    kpis = metrics.compute_kpis(filtered)
    tabs = st.tabs(
        [
            "1) Overall performance",
            "2) Category & product",
            "3) Order status & loss",
            "4) Payment, fulfillment & states",
            "About the data",
        ]
    )
    with tabs[0]:
        render_overview(filtered, kpis)
    with tabs[1]:
        render_products(filtered)
    with tabs[2]:
        render_order_status(filtered, kpis)
    with tabs[3]:
        render_geography(filtered)
    with tabs[4]:
        render_about(report, source_name)


main()
