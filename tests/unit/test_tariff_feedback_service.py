from types import SimpleNamespace

import pytest

from services.agent.validation import tariff_feedback_service as service


class _Cursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class _ConnectionManager:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return _Connection(self._cursor)

    def __exit__(self, exc_type, exc, tb):
        return False


def _match():
    return SimpleNamespace(
        line_index=4,
        naziv_robe_original="Krema za lice",
        naziv_robe_historijski="Krema kozmeticka",
        tarifni_broj_trenutni="3304.99.00",
        tarifni_broj_historijski="33049901",
        usage_count=6,
        source="MEDIKO",
        confidence=0.82,
        decision_outcome="show_strong",
        decision_score=78,
        decision_reason="Ista tarifna glava.",
    )


def test_record_tariff_validation_feedback_inserts_user_feedback(monkeypatch):
    cursor = _Cursor()
    monkeypatch.setattr(service, "get_db_connection", lambda: _ConnectionManager(cursor))

    assert service.record_tariff_validation_feedback(_match(), "accept", "manual") is True

    assert len(cursor.calls) == 1
    _, params = cursor.calls[0]
    assert params[1] == "accept"
    assert params[2] == "tariff_validation"
    assert params[3].startswith("tariff_validation:")
    assert params[4] == "3304.99.00"
    assert params[5] == "33049901"
    assert params[6] == 0.82
    assert params[7].adapted["decision_outcome"] == "show_strong"
    assert params[7].adapted["decision_score"] == 78
    assert params[7].adapted["accept_mode"] == "manual"


def test_record_tariff_validation_feedback_rejects_unknown_action():
    with pytest.raises(ValueError):
        service.record_tariff_validation_feedback(_match(), "maybe")
