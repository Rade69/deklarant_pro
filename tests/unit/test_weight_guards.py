from core.draft.draft import InvoiceLine
from services.faktura.weight_guards import (
    find_mass_total_mismatches,
    group_lines_by_invoice,
    is_suspicious_fallback,
    normalize_invoice_key,
    normalized_invoice_weights,
)


def make_line(invoice_number="", bruto_kg=0.0, neto_kg=0.0) -> InvoiceLine:
    return InvoiceLine(
        naziv_robe="Test",
        invoice_number=invoice_number,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
    )


def test_normalize_invoice_key_ignores_spaces_and_case():
    assert normalize_invoice_key("  Ab 123 / 25 ") == "ab123/25"


def test_normalized_invoice_weights_allows_lookup_by_normalized_key():
    weights = normalized_invoice_weights({"  AB 123 ": (20.0, 19.0)})
    assert weights["ab123"] == (20.0, 19.0)


def test_group_lines_by_invoice_keeps_labels_and_no_invoice_lines():
    groups, no_invoice_lines, labels = group_lines_by_invoice([
        make_line(" AB 123 "),
        make_line("ab123"),
        make_line(""),
    ])

    assert len(groups["ab123"]) == 2
    assert labels["ab123"] == "AB 123"
    assert len(no_invoice_lines) == 1


def test_suspicious_fallback_only_when_mixed_invoice_state():
    groups, no_invoice_lines, _ = group_lines_by_invoice([
        make_line("A-1"),
        make_line(""),
    ])

    assert is_suspicious_fallback(groups, no_invoice_lines) is True
    assert is_suspicious_fallback(groups, []) is False
    assert is_suspicious_fallback({}, no_invoice_lines) is False


def test_find_mass_total_mismatches_accepts_rounding_tolerance():
    groups, _, labels = group_lines_by_invoice([
        make_line("A-1", bruto_kg=9.999, neto_kg=9.499),
    ])
    weights = normalized_invoice_weights({"A-1": (10.0, 9.5)})

    assert find_mass_total_mismatches(groups, weights, labels) == []


def test_find_mass_total_mismatches_reports_real_difference():
    groups, _, labels = group_lines_by_invoice([
        make_line("A-1", bruto_kg=8.0, neto_kg=7.0),
    ])
    weights = normalized_invoice_weights({"A-1": (10.0, 9.5)})

    mismatches = find_mass_total_mismatches(groups, weights, labels)

    assert [m["field"] for m in mismatches] == ["bruto", "neto"]
    assert mismatches[0]["invoice"] == "A-1"
