"""
Integracioni testovi za sigurnosnu kapiju _execute_tool (Faza A).

Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §5

Provjerava da fail-closed gate na ulazu u _execute_tool radi nezavisno
od pojedinačnih tool grana (koje su detaljnije pokrivene u
tests/test_tool_use_offline.py::TestExecuteToolMapping /
TestUpisUKolonuMutationGate).
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from gui.tabs.agent.services.chat_intent_handler import _execute_tool


@pytest.fixture
def mock_ctrl():
    ctrl = MagicMock()
    ctrl.view = MagicMock()
    ctrl.view.get_chat_panel = MagicMock()
    ctrl.draft = MagicMock()
    ctrl.draft.invoice_lines = [MagicMock(line_no=1)]
    ctrl.naim_intent_svc = MagicMock()
    return ctrl


def test_nepoznat_alat_ne_dolazi_do_if_elif_lanca(mock_ctrl):
    """
    Alat koji nije u ToolPolicy registry-ju se odbija PRIJE dispatch-a —
    čak i kada bi ime slučajno postojalo u nekoj if/elif grani (fail-closed
    po imenu, ne po slučajnom podudaranju koda).
    """
    _execute_tool(mock_ctrl, "izmisljeni_alat_koji_ne_postoji", {})

    chat = mock_ctrl.view.get_chat_panel()
    chat.add_agent_message.assert_called_once()
    rendered = chat.add_agent_message.call_args[0][0]
    assert "Nepoznata akcija" in rendered
    # Nijedan servis nije pozvan.
    mock_ctrl.naim_intent_svc.execute.assert_not_called()
    chat.show_proposal_card.assert_not_called()


def test_read_only_alat_ne_otvara_proposal_karticu(mock_ctrl):
    """READ_ONLY alat (npr. provjeri_tarife) izvršava se odmah, bez proposal kartice."""
    _execute_tool(mock_ctrl, "provjeri_tarife", {})

    chat = mock_ctrl.view.get_chat_panel()
    chat.show_proposal_card.assert_not_called()


def test_mutate_alat_ne_poziva_execute_direktno(mock_ctrl):
    """upisi_u_kolonu (MUTATE) nikad ne poziva naim_intent_svc.execute() unutar _execute_tool."""
    mock_ctrl.naim_intent_svc._resolve_kolona.return_value = ("povlastica", "faktura")

    _execute_tool(mock_ctrl, "upisi_u_kolonu", {"kolona": "povlastica", "vrijednost": "EUP"})

    mock_ctrl.naim_intent_svc.execute.assert_not_called()
    mock_ctrl.view.get_chat_panel().show_proposal_card.assert_called_once()


@pytest.mark.xfail(
    reason=(
        "Poznat preostali gap (nije riješen u ovom prolazu Faze A): _on_proposal_confirmed "
        "nema operation_id, pa dvije uzastopne eksplicitne invokacije iste potvrde IZVRŠE "
        "mutaciju dva puta. U stvarnom GUI toku ProposalCardWidget se uništava odmah nakon "
        "prvog klika (deleteLater), što sprječava doslovan dvostruki klik na isti widget — "
        "ali to ne štiti od reprodukovanog/replay signala. Vidi plan §5.3 i agent report."
    ),
    strict=True,
)
def test_dvostruka_potvrda_ne_izvrsava_mutaciju_dvaput(mock_ctrl):
    from gui.tabs.agent.services.chat_intent_handler import (
        _propose_kolona_upis, _on_proposal_confirmed,
    )

    _propose_kolona_upis(mock_ctrl, "povlastica", "EUP", tab="faktura")
    _on_proposal_confirmed(mock_ctrl, {"povlastica": "EUP"})
    _on_proposal_confirmed(mock_ctrl, {"povlastica": "EUP"})

    mock_ctrl.naim_intent_svc.execute.assert_called_once_with("povlastica", "EUP", tab="faktura")
