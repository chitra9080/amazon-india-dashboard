"""Validation and cleaning of the raw Amazon India sales data.

Principles (also documented in the README):
* The original Excel file and the raw DataFrame are never modified.
* Missing numbers are never invented (no imputation); they stay missing.
* Rows are removed only when they cannot be used safely (no Order_ID or no
  valid date) or when they are exact duplicates. Every removal is counted in
  the returned report.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

REQUIRED_COLUMNS: List[str] = [
    "Order_ID",
    "Order_Date",
    "Category",
    "Product",
    "Quantity",
    "Unit_Price_INR",
    "Discount_Pct",
    "Total_Sales_INR",
    "Profit_INR",
    "Payment_Method",
    "Fulfillment",
    "Order_Status",
    "Ship_State",
]
TEXT_COLUMNS: List[str] = [
    "Order_ID",
    "Category",
    "Product",
    "Payment_Method",
    "Fulfillment",
    "Order_Status",
    "Ship_State",
]
NUMERIC_COLUMNS: List[str] = [
    "Quantity",
    "Unit_Price_INR",
    "Discount_Pct",
    "Total_Sales_INR",
    "Profit_INR",
]
# These can never be negative. Profit CAN be negative (a loss), so it is not listed.
NON_NEGATIVE_COLUMNS: List[str] = ["Quantity", "Unit_Price_INR", "Total_Sales_INR"]

STATUS_ORDER = ("Delivered", "Shipped", "Returned", "Cancelled")
REVENUE_STATUSES = ("Delivered", "Shipped")  # orders counted in headline sales/profit
LOST_STATUSES = ("Returned", "Cancelled")  # orders whose sales are "lost"
UNKNOWN_LABEL = "Unknown"


class MissingColumnsError(ValueError):
    """Raised when required columns are absent from the dataset."""

    def __init__(self, missing: List[str]):
        self.missing = list(missing)
        super().__init__(
            "The dataset is missing required column(s): " + ", ".join(self.missing)
        )


def validate_columns(df: pd.DataFrame, required: List[str] = REQUIRED_COLUMNS) -> None:
    """Raise MissingColumnsError if any required column is absent."""
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise MissingColumnsError(missing)


def _clean_text(series: pd.Series) -> pd.Series:
    """Trim spaces, collapse repeated spaces and turn blanks into missing values."""

    def _strip(value: Any) -> Any:
        if pd.isna(value):
            return None
        text = " ".join(str(value).split())
        return text if text else None

    return series.map(_strip).astype("object")


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse dates (ISO ``YYYY-MM-DD`` first, then a tolerant fallback)."""
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    leftover = parsed.isna() & series.notna()
    if leftover.any():
        parsed.loc[leftover] = pd.to_datetime(
            series[leftover], errors="coerce", dayfirst=True
        )
    return parsed.dt.normalize()


def clean_data(raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Return ``(clean_dataframe, report)``. The input frame is not modified."""
    df = raw.copy()
    df.columns = [str(column).strip() for column in df.columns]
    validate_columns(df)

    report: Dict[str, Any] = {"rows_in": int(len(df))}

    # 1. Text columns: trim whitespace; make status labels consistent.
    for column in TEXT_COLUMNS:
        df[column] = _clean_text(df[column])
    df["Order_Status"] = df["Order_Status"].str.title().replace({"Canceled": "Cancelled"})

    # 2. Rows without an Order_ID cannot be counted safely.
    missing_id = df["Order_ID"].isna()
    report["rows_dropped_missing_order_id"] = int(missing_id.sum())
    df = df[~missing_id].copy()

    # 3. Dates: real dates are required for trends and the date filter.
    df["Order_Date"] = _parse_dates(df["Order_Date"])
    bad_date = df["Order_Date"].isna()
    report["rows_dropped_invalid_date"] = int(bad_date.sum())
    df = df[~bad_date].copy()

    # 4. Missing labels become "Unknown" (a label, not an invented number).
    filled: Dict[str, int] = {}
    for column in TEXT_COLUMNS:
        if column == "Order_ID":
            continue
        count = int(df[column].isna().sum())
        if count:
            filled[column] = count
            df[column] = df[column].fillna(UNKNOWN_LABEL)
    report["missing_text_filled_with_unknown"] = filled

    # 5. Numbers: convert safely; never impute.
    not_numeric: Dict[str, int] = {}
    negative: Dict[str, int] = {}
    for column in NUMERIC_COLUMNS:
        original = df[column]
        numeric = pd.to_numeric(original, errors="coerce")
        bad = int((numeric.isna() & original.notna()).sum())
        if bad:
            not_numeric[column] = bad
        if column in NON_NEGATIVE_COLUMNS:
            below_zero = numeric < 0
            if below_zero.any():
                negative[column] = int(below_zero.sum())
                numeric = numeric.mask(below_zero)
        df[column] = numeric.astype(float)
    report["non_numeric_values_set_to_missing"] = not_numeric
    report["negative_values_set_to_missing"] = negative
    report["missing_numeric_values_remaining"] = {
        column: int(df[column].isna().sum())
        for column in NUMERIC_COLUMNS
        if df[column].isna().any()
    }

    # 6. Duplicates: only rows identical in EVERY column are removed.
    #    Same Order_ID with different content is kept (could be a multi-item
    #    order); order counts always use distinct Order_IDs.
    duplicated = df.duplicated(keep="first")
    report["exact_duplicate_rows_removed"] = int(duplicated.sum())
    df = df[~duplicated].copy()
    report["repeated_order_ids_kept"] = int(df["Order_ID"].duplicated().sum())

    # 7. Summary facts for the "About the data" tab.
    df = df.reset_index(drop=True)
    report["rows_out"] = int(len(df))
    report["unique_orders"] = int(df["Order_ID"].nunique())
    report["date_min"] = None if df.empty else df["Order_Date"].min().strftime("%Y-%m-%d")
    report["date_max"] = None if df.empty else df["Order_Date"].max().strftime("%Y-%m-%d")
    report["unrecognised_order_statuses"] = sorted(
        set(df["Order_Status"].unique()) - set(STATUS_ORDER)
    )
    return df, report
