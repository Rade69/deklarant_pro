"""
Testovi za ChatWorker._search_declarations_context() — "Pretraga po
partneru" grana (Faza 5, project_rooms/2026-07-25_agent-safe-input-schema-
plan.md). Imena izvoznika/primaoca iz istorijskih XML deklaracija sad idu
kroz AgentContextAdapter.mask_partner() umjesto ručnog ternary po polju —
isti obrazac kao Zone B/B2.

JIB prikaz je NAMJERNO nedirano ostavljen (otvoreno pitanje u planu) — ovaj
fajl provjerava SAMO da postojeće JIB ponašanje nije slučajno promijenjeno,
ne da je "ispravno" po Zone B standardu.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from gui.tabs.agent.widgets.chat_worker import ChatWorker


def _fake_worker(draft=None, send_sensitive: bool = False):
    fake = type("FakeChatWorker", (), {})()
    fake.draft = draft
    fake._allow_sensitive_data = lambda: send_sensitive
    fake._extract_tariff_code = lambda q: ""
    fake._extract_country_code = lambda q: ""
    fake._search_pg_partners = lambda q: []
    return fake


def _mock_service(partner_results):
    svc = MagicMock()
    svc.get_stats.return_value = {"declarations": 1, "items": 1, "unique_tariffs": 1}
    svc.search_by_tariff.return_value = []
    svc.search_by_goods.return_value = []
    svc.search_by_partner.return_value = partner_results
    svc.search_by_country.return_value = []
    return svc


def test_partner_search_maskira_imena_kad_je_iskljuceno():
    partner_results = [{
        "exporter_name": "TAJNI IZVOZNIK DOO",
        "consignee_name": "TAJNI PRIMALAC DOO",
        "consignee_jib": "4200000000001",
    }]
    fake = _fake_worker(send_sensitive=False)

    with patch(
        "services.agent.chat.declaration_search_service.DeclarationSearchService",
        return_value=_mock_service(partner_results),
    ):
        ctx = ChatWorker._search_declarations_context(fake, "koji je nas izvoznik")
    text = "\n".join(ctx)

    assert "TAJNI IZVOZNIK DOO" not in text
    assert "TAJNI PRIMALAC DOO" not in text
    assert "ime skriveno" in text


def test_partner_search_prikazuje_imena_kad_je_ukljuceno():
    partner_results = [{
        "exporter_name": "IZVOZNIK DOO",
        "consignee_name": "PRIMALAC DOO",
        "consignee_jib": "4200000000001",
    }]
    fake = _fake_worker(send_sensitive=True)

    with patch(
        "services.agent.chat.declaration_search_service.DeclarationSearchService",
        return_value=_mock_service(partner_results),
    ):
        ctx = ChatWorker._search_declarations_context(fake, "koji je nas izvoznik")
    text = "\n".join(ctx)

    assert "IZVOZNIK DOO" in text
    assert "PRIMALAC DOO" in text
