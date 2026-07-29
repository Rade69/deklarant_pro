from __future__ import annotations

import pytest

from services.faktura.faktura_service import FakturaService


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1234.56", 1234.56),
        ("1234,56", 1234.56),
        ("", 0.0),
        ("nije broj", 0.0),
    ],
)
def test_parse_number_matches_faktura_view_formats(raw, expected):
    assert FakturaService.parse_number(raw) == pytest.approx(expected)
    assert FakturaService.parse_weight_input(raw) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("weight", "expected"),
    [
        (0.0, "0"),
        (2.383, "2.383"),
        (1234.56, "1,234.56"),
        (1234567.891, "1,234,567.891"),
    ],
)
def test_format_weight_preserves_precision(weight, expected):
    assert FakturaService.format_weight(weight) == expected


def test_format_issue_counts_matches_view_summary_style():
    counts = {
        "bez zemlje": 1,
        "bez tarife": 3,
        "bruto < neto": 2,
        "bez naziva robe": 1,
    }

    assert (
        FakturaService.format_issue_counts(counts)
        == "3 bez tarife | 2 bruto < neto | 1 bez naziva robe | +1 tip"
    )
