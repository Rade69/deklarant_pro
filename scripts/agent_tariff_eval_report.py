from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.draft.draft import InvoiceLine
from services.agent.validation.historical_tariff_search_service import (
    HistoricalTariffSearchService,
    TariffHistoryMatch,
)


DEFAULT_CASES_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "agent"
    / "tariff_validation_cases.json"
)


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def evaluate_case(case: dict) -> list[TariffHistoryMatch]:
    svc = HistoricalTariffSearchService()
    lines = [_invoice_line(line) for line in case["invoice_lines"]]
    history_matches = [_history_match(match) for match in case["history_matches"]]

    def fake_search(naziv, *_):
        return [
            match for match in history_matches
            if match.naziv_robe_original == naziv
        ]

    svc._search_one = fake_search

    return svc.validate_lines(lines)


def metrics_for_cases(cases: list[dict]) -> dict:
    metrics = {
        "true_positive": 0,
        "true_negative": 0,
        "false_positive": 0,
        "false_negative": 0,
        "wrong_tariff": 0,
        "explanation_missing": 0,
    }

    for case in cases:
        matches = evaluate_case(case)
        expected = case["expected"]
        expected_show = expected["action"] == "show"

        if expected_show:
            expected_tariff = expected["tarifni_broj"]
            if not matches:
                metrics["false_negative"] += 1
            elif matches[0].tarifni_broj_historijski == expected_tariff:
                metrics["true_positive"] += 1
            else:
                metrics["wrong_tariff"] += 1
        elif matches:
            metrics["false_positive"] += 1
        else:
            metrics["true_negative"] += 1

        metrics["explanation_missing"] += sum(
            1 for match in matches if not match.decision_reason
        )

    return metrics


def format_report(cases: list[dict]) -> str:
    metrics = metrics_for_cases(cases)
    total = len(cases)
    passed = (
        metrics["false_positive"] == 0
        and metrics["false_negative"] == 0
        and metrics["wrong_tariff"] == 0
        and metrics["explanation_missing"] == 0
    )
    lines = [
        "Agent tariff validation evaluation",
        f"Cases: {total}",
        f"Status: {'OK' if passed else 'CHECK'}",
        "",
        "Metrics:",
    ]
    lines.extend(f"- {key}: {value}" for key, value in metrics.items())

    failed = _failed_cases(cases)
    if failed:
        lines.append("")
        lines.append("Failed cases:")
        lines.extend(f"- {name}: {reason}" for name, reason in failed)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report metrics for agent tariff validation fixtures."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="Path to tariff validation cases JSON.",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases)
    print(format_report(cases))
    return 0 if not _failed_cases(cases) else 1


def _invoice_line(data: dict) -> InvoiceLine:
    return InvoiceLine(
        line_no=data["line_no"],
        naziv_robe=data["naziv_robe"],
        tarifni_broj=data.get("tarifni_broj", ""),
    )


def _history_match(data: dict) -> TariffHistoryMatch:
    return TariffHistoryMatch(
        line_index=-1,
        naziv_robe_original=data["naziv_robe"],
        naziv_robe_historijski=data["naziv_robe"],
        tarifni_broj_historijski=data["tarifni_broj"],
        tarifni_broj_trenutni="",
        supplier_match=False,
        usage_count=data["usage_count"],
        source=data["source"],
        confidence=data["confidence"],
    )


def _failed_cases(cases: list[dict]) -> list[tuple[str, str]]:
    failed = []
    for case in cases:
        matches = evaluate_case(case)
        expected = case["expected"]
        expected_show = expected["action"] == "show"

        if expected_show and not matches:
            failed.append((case["name"], "expected suggestion, got suppress"))
            continue
        if not expected_show and matches:
            failed.append((case["name"], "expected suppress, got suggestion"))
            continue
        if expected_show:
            expected_tariff = expected["tarifni_broj"]
            actual_tariff = matches[0].tarifni_broj_historijski
            if actual_tariff != expected_tariff:
                failed.append((
                    case["name"],
                    f"expected {expected_tariff}, got {actual_tariff}",
                ))
            elif not matches[0].decision_reason:
                failed.append((case["name"], "missing decision_reason"))

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
