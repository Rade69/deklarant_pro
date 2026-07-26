"""
Testovi za invoice_validation_adapter — Faza 2 (validacioni ugovor).
"""
from __future__ import annotations

from services.agent.validation.finding_model import FindingCode, FindingSeverity
from services.agent.validation.invoice_validation_adapter import adapt_invoice_validation


class _MockError:
    def __init__(self, level, field, message, suggestion=""):
        self.level = level
        self.field = field
        self.message = message
        self.suggestion = suggestion


class _MockValidationResult:
    def __init__(self, errors=None, warnings=None):
        self.errors = errors or []
        self.warnings = warnings or []


class _MockLevel:
    def __init__(self, name):
        self.name = name


def test_adaptira_critical_error():
    result = _MockValidationResult(errors=[
        _MockError(level=_MockLevel("CRITICAL"), field="tarifni_broj",
                   message="Nedostaje tarifni broj")
    ])
    findings = adapt_invoice_validation(result, row_index=0)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.BLOCKING
    assert findings[0].code == FindingCode.MISSING_TARIFF
    assert findings[0].blocking is True


def test_adaptira_warning():
    result = _MockValidationResult(warnings=[
        _MockError(level=_MockLevel("WARNING"), field="kolicina",
                   message="Količina je nula")
    ])
    findings = adapt_invoice_validation(result, row_index=0)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.WARNING
    assert findings[0].blocking is False


def test_adaptira_vise_gresaka():
    result = _MockValidationResult(
        errors=[
            _MockError(level=_MockLevel("ERROR"), field="naziv_robe", message="Prazan naziv"),
            _MockError(level=_MockLevel("CRITICAL"), field="zemlja_porijekla", message="Nema zemlje"),
        ],
        warnings=[
            _MockError(level=_MockLevel("WARNING"), field="kolicina", message="Mala količina"),
        ]
    )
    findings = adapt_invoice_validation(result, row_index=2)
    assert len(findings) == 3
    assert sum(1 for f in findings if f.blocking) == 2
    assert sum(1 for f in findings if f.severity == FindingSeverity.WARNING) == 1
    # location sadrži row_index
    assert all("stavka 3" in f.location for f in findings)


def test_prazan_rezultat():
    result = _MockValidationResult()
    findings = adapt_invoice_validation(result)
    assert findings == []
