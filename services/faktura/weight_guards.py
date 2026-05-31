from typing import Any


def normalize_invoice_key(invoice_number: Any) -> str:
    if invoice_number is None:
        return ""
    return "".join(str(invoice_number).split()).casefold()


def normalized_invoice_weights(invoice_weights: dict) -> dict:
    normalized = {}
    for key, value in (invoice_weights or {}).items():
        norm_key = normalize_invoice_key(key)
        if norm_key:
            normalized[norm_key] = value
    return normalized


def group_lines_by_invoice(lines: list) -> tuple[dict, list, dict]:
    invoice_groups = {}
    invoice_labels = {}
    no_invoice_lines = []

    for line in lines:
        raw_key = (getattr(line, "invoice_number", "") or "").strip()
        key = normalize_invoice_key(raw_key)
        if key:
            invoice_groups.setdefault(key, []).append(line)
            invoice_labels.setdefault(key, raw_key)
        else:
            no_invoice_lines.append(line)

    return invoice_groups, no_invoice_lines, invoice_labels


def is_suspicious_fallback(invoice_groups: dict, no_invoice_lines: list) -> bool:
    return bool(invoice_groups and no_invoice_lines)


def find_mass_total_mismatches(
    invoice_groups: dict,
    invoice_weights: dict,
    invoice_labels: dict | None = None,
) -> list[dict]:
    mismatches = []
    invoice_labels = invoice_labels or {}

    for key, lines in invoice_groups.items():
        if key not in invoice_weights:
            continue

        expected_bruto, expected_neto = invoice_weights[key]
        actual_bruto = sum((getattr(line, "bruto_kg", 0.0) or 0.0) for line in lines)
        actual_neto = sum((getattr(line, "neto_kg", 0.0) or 0.0) for line in lines)
        tolerance = max(0.05, len(lines) * 0.001)

        if expected_bruto > 0 and abs(actual_bruto - expected_bruto) > tolerance:
            mismatches.append({
                "invoice": invoice_labels.get(key, key),
                "field": "bruto",
                "expected": expected_bruto,
                "actual": actual_bruto,
                "difference": actual_bruto - expected_bruto,
            })

        if expected_neto > 0 and abs(actual_neto - expected_neto) > tolerance:
            mismatches.append({
                "invoice": invoice_labels.get(key, key),
                "field": "neto",
                "expected": expected_neto,
                "actual": actual_neto,
                "difference": actual_neto - expected_neto,
            })

    return mismatches
