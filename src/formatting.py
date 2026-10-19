"""Number formatting helpers (Indian digit grouping, lakh / crore units)."""
from __future__ import annotations

from typing import Any

RUPEE = "\u20b9"
NOT_AVAILABLE = "N/A"


def _is_missing(value: Any) -> bool:
    # NaN is the only value that is not equal to itself.
    return value is None or value != value


def group_indian(number: int) -> str:
    """12345678 -> '1,23,45,678'."""
    sign = "-" if number < 0 else ""
    digits = str(abs(int(number)))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return sign + ",".join(parts + [tail])


def format_int(value: Any) -> str:
    """Whole number with Indian grouping, or 'N/A' if missing."""
    if _is_missing(value):
        return NOT_AVAILABLE
    return group_indian(int(round(float(value))))


def format_inr_full(value: Any) -> str:
    """Full rupee amount, e.g. '₹15,57,89,894'."""
    if _is_missing(value):
        return NOT_AVAILABLE
    rounded = int(round(float(value)))
    sign = "-" if rounded < 0 else ""
    return f"{sign}{RUPEE}{group_indian(abs(rounded))}"


def format_inr(value: Any, decimals: int = 2) -> str:
    """Compact rupee amount: '₹15.58 Cr', '₹7.69 Lakh' or '₹15,544'."""
    if _is_missing(value):
        return NOT_AVAILABLE
    number = float(value)
    sign = "-" if number < 0 else ""
    magnitude = abs(number)
    if magnitude >= 1e7:
        return f"{sign}{RUPEE}{magnitude / 1e7:.{decimals}f} Cr"
    if magnitude >= 1e5:
        return f"{sign}{RUPEE}{magnitude / 1e5:.{decimals}f} Lakh"
    return format_inr_full(number)


def format_pct(value: Any, decimals: int = 2) -> str:
    """Percentage with fixed decimals, or 'N/A' if missing."""
    if _is_missing(value):
        return NOT_AVAILABLE
    return f"{float(value):.{decimals}f}%"
