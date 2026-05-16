from types import SimpleNamespace

from PySide6.QtGui import QGuiApplication

from gui.tabs.agent.widgets.tariff_validation_dialog import TariffValidationDialog


def _match(line_index: int, outcome: str):
    return SimpleNamespace(
        line_index=line_index,
        naziv_robe_original=f"Roba {line_index}",
        naziv_robe_historijski=f"Istorijska roba {line_index}",
        tarifni_broj_historijski=f"3304990{line_index}",
        tarifni_broj_trenutni="33049900",
        usage_count=3,
        source="MEDIKO",
        confidence=0.66,
        decision_reason="Ista tarifna glava; istorija ukazuje na precizniji broj.",
        decision_outcome=outcome,
        decision_score=50,
    )


def test_accept_all_skips_show_weak_matches(qtbot, monkeypatch):
    recorded = []
    monkeypatch.setattr(
        TariffValidationDialog,
        "_record_feedback",
        staticmethod(lambda match, action, mode: recorded.append((match.line_index, action, mode))),
    )
    strong = _match(0, "show_strong")
    weak = _match(1, "show_weak")
    dialog = TariffValidationDialog([strong, weak])
    qtbot.addWidget(dialog)
    accepted = []
    dialog.tariffs_accepted.connect(accepted.append)

    dialog._accept_all()

    assert accepted == [[(0, "33049900")]]
    assert dialog._checkboxes[0][1].isEnabled() is False
    assert dialog._checkboxes[0][2].isEnabled() is False
    assert dialog._checkboxes[1][1].isEnabled() is True
    assert dialog._accept_all_btn.isEnabled() is False
    assert recorded == [(0, "accept", "bulk")]


def test_manual_accept_still_allows_show_weak_match(qtbot, monkeypatch):
    recorded = []
    monkeypatch.setattr(
        TariffValidationDialog,
        "_record_feedback",
        staticmethod(lambda match, action, mode: recorded.append((match.line_index, action, mode))),
    )
    weak = _match(1, "show_weak")
    dialog = TariffValidationDialog([weak])
    qtbot.addWidget(dialog)
    accepted = []
    dialog.tariffs_accepted.connect(accepted.append)
    btn = dialog._checkboxes[1][1]

    dialog._accept_one(weak, btn)

    assert accepted == [[(1, "33049901")]]
    assert btn.isEnabled() is False
    assert dialog._checkboxes[1][2].isEnabled() is False
    assert recorded == [(1, "accept", "manual")]


def test_manual_reject_records_feedback_without_accepting(qtbot, monkeypatch):
    recorded = []
    monkeypatch.setattr(
        TariffValidationDialog,
        "_record_feedback",
        staticmethod(lambda match, action, mode: recorded.append((match.line_index, action, mode))),
    )
    weak = _match(1, "show_weak")
    dialog = TariffValidationDialog([weak])
    qtbot.addWidget(dialog)
    accepted = []
    dialog.tariffs_accepted.connect(accepted.append)
    accept_btn = dialog._checkboxes[1][1]
    reject_btn = dialog._checkboxes[1][2]

    dialog._reject_one(weak, accept_btn, reject_btn)

    assert accepted == []
    assert accept_btn.isEnabled() is False
    assert reject_btn.isEnabled() is False
    assert recorded == [(1, "reject", "manual")]


def test_copy_report_includes_decision_outcome_and_score(qtbot):
    weak = _match(1, "show_weak")
    dialog = TariffValidationDialog([weak])
    qtbot.addWidget(dialog)

    dialog._copy_report()

    report = QGuiApplication.clipboard().text()
    assert "Odluka: show_weak" in report
    assert "Score: 50" in report
    assert "Razlog: Ista tarifna glava; istorija ukazuje na precizniji broj." in report
