"""
Testovi za ChatWorker._build_session_zone() (Zone B) — maskiranje
pošiljaoca/uvoznika, sada preko AgentContextAdapter.mask_partner()
(Faza 2, project_rooms/2026-07-25_agent-safe-input-schema-plan.md).

Prije ove sesije nije postojao test koji provjerava stvaran sadržaj ove
zone (samo monkeypatch na prazan output u test_tool_use_offline.py) — ovi
testovi pokrivaju i "postoji JIB ali nema imena" ivicu koja NIJE bila u
ranijem test_chat_worker_zaglavlje_zone_masking.py.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gui.tabs.agent.widgets.chat_worker import ChatWorker

# find_xml_for_pair je PostgreSQL upit (services/agent/learning/
# exporter_xml_indexer.py) - nepovezano sa maskiranjem koje ovi testovi
# provjeravaju, ali bez mocka svaki test čeka na DB konekcijski timeout
# (spor i zavisan od dostupnosti servera). Auto-primjenjuje se na sve
# testove u ovom fajlu.
pytestmark = pytest.mark.usefixtures("_mock_xml_lookup")


@pytest.fixture
def _mock_xml_lookup():
    with patch(
        "services.agent.learning.exporter_xml_indexer.find_xml_for_pair",
        return_value=None,
    ):
        yield


def _fake_worker(draft, send_sensitive: bool):
    fake = type("FakeChatWorker", (), {})()
    fake.draft = draft
    fake._allow_sensitive_data = lambda: send_sensitive
    return fake


def _line_with_exporter(name: str):
    return SimpleNamespace(exporter=SimpleNamespace(name=name))


def _draft(**kwargs) -> SimpleNamespace:
    defaults = dict(primalac_id="", primalac_naziv="", izvoznik_id="")
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_session_zone_maskira_posiljaoca_i_uvoznika_kad_je_iskljuceno():
    lines = [_line_with_exporter("TAJNI POSILJALAC DOO")]
    d = _draft(primalac_naziv="TAJNI UVOZNIK DOO")
    fake = _fake_worker(d, send_sensitive=False)

    result = ChatWorker._build_session_zone(fake, lines)
    text = "\n".join(result)

    assert "TAJNI POSILJALAC DOO" not in text
    assert "TAJNI UVOZNIK DOO" not in text
    assert "ime skriveno" in text


def test_session_zone_prikazuje_kad_je_ukljuceno():
    lines = [_line_with_exporter("POSILJALAC DOO")]
    d = _draft(primalac_naziv="UVOZNIK DOO")
    fake = _fake_worker(d, send_sensitive=True)

    result = ChatWorker._build_session_zone(fake, lines)
    text = "\n".join(result)

    assert "POSILJALAC DOO" in text
    assert "UVOZNIK DOO" in text
    assert "ime skriveno" not in text


def test_session_zone_jib_bez_imena_prikazuje_placeholder_kad_ukljuceno():
    """Ivica: primalac_id (JIB) postoji ali primalac_naziv ne — 'postoji, ime nije dostupno', ne masking poruka."""
    lines = [_line_with_exporter("POSILJALAC DOO")]
    d = _draft(primalac_id="4200000000001", primalac_naziv="")
    fake = _fake_worker(d, send_sensitive=True)

    result = ChatWorker._build_session_zone(fake, lines)
    text = "\n".join(result)

    assert "postoji, ime nije dostupno" in text
    assert "4200000000001" not in text  # JIB se nikad ne salje


def test_session_zone_jib_bez_imena_maskira_kad_iskljuceno():
    lines = [_line_with_exporter("POSILJALAC DOO")]
    d = _draft(primalac_id="4200000000001", primalac_naziv="")
    fake = _fake_worker(d, send_sensitive=False)

    result = ChatWorker._build_session_zone(fake, lines)
    text = "\n".join(result)

    assert "postoji, ime nije dostupno" not in text
    assert "ime skriveno" in text


def test_session_zone_prazan_bez_partnera_vraca_prazno():
    fake = _fake_worker(_draft(), send_sensitive=True)
    result = ChatWorker._build_session_zone(fake, [])
    assert result == []
