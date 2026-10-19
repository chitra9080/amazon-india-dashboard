"""Tests for src/formatting.py (Indian digit grouping, lakh/crore, N/A handling)."""
from src.formatting import format_inr, format_inr_full, format_int, format_pct, group_indian


def test_indian_grouping():
    assert group_indian(999) == "999"
    assert group_indian(1000) == "1,000"
    assert group_indian(100000) == "1,00,000"
    assert group_indian(155789894) == "15,57,89,894"
    assert group_indian(-1234567) == "-12,34,567"


def test_compact_rupee_formats():
    assert format_inr(155_789_893.89) == "\u20b915.58 Cr"
    assert format_inr(7_688_159) == "\u20b976.88 Lakh"
    assert format_inr(15_544.4) == "\u20b915,544"
    assert format_inr(-250_000) == "-\u20b92.50 Lakh"
    assert format_inr_full(155_789_893.89) == "\u20b915,57,89,894"


def test_missing_values_show_na():
    nan = float("nan")
    assert format_inr(nan) == "N/A"
    assert format_inr_full(None) == "N/A"
    assert format_int(nan) == "N/A"
    assert format_pct(nan) == "N/A"


def test_integers_and_percentages():
    assert format_int(24926) == "24,926"
    assert format_int(1234567.4) == "12,34,567"
    assert format_pct(23.6712) == "23.67%"
    assert format_pct(4.86, decimals=1) == "4.9%"
