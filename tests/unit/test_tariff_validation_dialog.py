import re
from types import SimpleNamespace

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel

from gui.tabs.agent.widgets.tariff_validation_dialog import TariffValidationDialog
from services.agent.validation.evidence_model import (
    DecisionConfidence,
    DecisionSource,
    build_evidence,
    evidence_badge_colors,
)


def _match(line_index: int, outcome: str, evidence=None, decision_score: int = 50):
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
        decision_score=decision_score,
        evidence=evidence,
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


def test_unknown_evidence_blocks_accept_all_and_shows_unknown_label(qtbot):
    evidence = build_evidence(
        DecisionSource.TARIFF_DATABASE,
        DecisionConfidence.UNKNOWN,
        "Istorijski zapis nema poznat izvor.",
    )
    match = _match(0, "show_strong", evidence=evidence)
    match.source = "HISTORIJA"

    dialog = TariffValidationDialog([match])
    qtbot.addWidget(dialog)

    assert dialog._can_accept_all(match) is False
    assert dialog._accept_all_btn.isEnabled() is False
    labels = [label.text() for label in dialog.findChildren(QLabel)]
    rendered = "\n".join(labels)
    assert "izvor nepoznat" in rendered
    assert "nepoznat" in rendered


def test_confirmed_exporter_history_shows_jak_label(qtbot):
    evidence = build_evidence(
        DecisionSource.EXPORTER_HISTORY,
        DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
        "Potvrdjeno iz istorije istog izvoznika.",
    )
    match = _match(0, "show_strong", evidence=evidence)

    dialog = TariffValidationDialog([match])
    qtbot.addWidget(dialog)

    labels = [label.text() for label in dialog.findChildren(QLabel)]
    rendered = "\n".join(labels)
    assert "Sigurnost preporuke" in rendered
    assert "jak" in rendered


def test_evidence_badge_shows_score_and_differs_strong_vs_weak(qtbot):
    """
    Faza 5/6 + Faza D-precision fix (2026-07-21): jak i slab prijedlog ne smiju
    imati isti badge. Prikazani procenat je match.decision_score (stvaran,
    promjenjiv izračun iz decide_tariff_match) — NE evidence.score (fiksna
    konstanta po kategoriji) — zato dva prijedloga s različitim decision_score
    moraju pokazati različite brojeve čak i unutar iste kategorije.
    """
    strong = build_evidence(
        DecisionSource.EXPORTER_HISTORY,
        DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
        "Potvrdjeno iz istorije istog izvoznika.",
    )
    weak = build_evidence(
        DecisionSource.SIMILARITY,
        DecisionConfidence.WEAK_GUESS,
        "Slabiji prijedlog.",
    )
    strong_match = _match(0, "show_strong", evidence=strong, decision_score=82)
    weak_match = _match(1, "show_weak", evidence=weak, decision_score=47)

    dialog = TariffValidationDialog([strong_match, weak_match])
    qtbot.addWidget(dialog)

    labels = [label.text() for label in dialog.findChildren(QLabel)]
    strong_label = next(t for t in labels if "Sigurnost preporuke" in t and "jak" in t)
    weak_label = next(t for t in labels if "Sigurnost preporuke" in t and "slab" in t)

    assert "82%" in strong_label
    assert "47%" in weak_label

    badge_pattern = r"background:(#[0-9a-fA-F]+); color:(#[0-9a-fA-F]+)"
    strong_bg, strong_color = re.search(badge_pattern, strong_label).groups()
    weak_bg, _ = re.search(badge_pattern, weak_label).groups()
    assert strong_bg != weak_bg
    assert (strong_color, strong_bg) == evidence_badge_colors(strong)
