"""
Forbidden-marker test za ChatWorker._build_context() (plan §8,
project_rooms/2026-07-25_agent-safe-input-schema-plan.md) — Kontrolisana
podatkovna granica za AI agente, §12.

Umjesto da se maskiranje provjerava polje-po-polje u zasebnim testovima za
svaku zonu, ovaj test ubaci lažne, prepoznatljive markere u SVA partner
polja (Zone B izvor: invoice_lines[].exporter.name; Zone B2 izvor: draft
Zaglavlje polja) i provjeri da se NIJEDAN ne pojavi u cjelokupnom
_build_context() outputu kad je SEND_SENSITIVE_DATA=false — nezavisno od
toga koja je zona "kriva" ako nešto procuri. Ovo bi automatski uhvatilo
propust istog tipa kao onaj popravljen u §61 (Zone B2 zaobilazila masking
iz Zone B), bez čekanja na ručno poređenje sa eksternim dokumentom.
"""
from __future__ import annotations

from unittest.mock import patch

from core.draft.draft import DeclarationDraft, InvoiceLine, Party
from gui.tabs.agent.widgets.chat_worker import ChatWorker

FORBIDDEN_MARKERS = [
    "EXPORTER_NAME_SHOULD_NOT_LEAK",
    "CONSIGNEE_NAME_SHOULD_NOT_LEAK",
    "DECLARANT_NAME_SHOULD_NOT_LEAK",
    "CONSIGNEE_JIB_SHOULD_NOT_LEAK",
]


def _worker_with_markers(send_sensitive: bool) -> ChatWorker:
    draft = DeclarationDraft()
    draft.izvoznik_naziv = "EXPORTER_NAME_SHOULD_NOT_LEAK"
    draft.izvoznik_drzava = "DE"
    draft.primalac_naziv = "CONSIGNEE_NAME_SHOULD_NOT_LEAK"
    draft.primalac_id = "CONSIGNEE_JIB_SHOULD_NOT_LEAK"
    draft.deklarant_naziv = "DECLARANT_NAME_SHOULD_NOT_LEAK"

    line = InvoiceLine(tarifni_broj="12345678", zemlja_porijekla="DE", naziv_robe="ROBA")
    line.exporter = Party(name="EXPORTER_NAME_SHOULD_NOT_LEAK")
    draft.invoice_lines = [line]

    worker = ChatWorker.__new__(ChatWorker)
    worker.draft = draft
    worker.message = "Pregledaj stanje drafta"
    worker._allow_sensitive_data = lambda: send_sensitive
    worker._determine_context_zones = lambda _: set()
    worker._fetch_pg_tariff_descriptions = lambda _: {}
    worker._is_regulatory_question = lambda _: False
    return worker


def test_build_context_ne_curi_markere_kad_je_sensitive_iskljuceno():
    worker = _worker_with_markers(send_sensitive=False)

    with patch(
        "services.agent.learning.exporter_xml_indexer.find_xml_for_pair",
        return_value=None,
    ):
        context = worker._build_context()

    for marker in FORBIDDEN_MARKERS:
        assert marker not in context, f"Forbidden marker leaked: {marker}"


def test_build_context_prikazuje_markere_kad_je_sensitive_ukljuceno():
    """Kontrolni test — potvrđuje da prethodni test ne prolazi lažno (markeri BI se pojavili da masking ne radi)."""
    worker = _worker_with_markers(send_sensitive=True)

    with patch(
        "services.agent.learning.exporter_xml_indexer.find_xml_for_pair",
        return_value=None,
    ):
        context = worker._build_context()

    assert "EXPORTER_NAME_SHOULD_NOT_LEAK" in context
    assert "CONSIGNEE_NAME_SHOULD_NOT_LEAK" in context
    assert "DECLARANT_NAME_SHOULD_NOT_LEAK" in context
    # JIB se NIKAD ne šalje LLM-u, bez obzira na sensitive flag (nedirano, Zone B).
    assert "CONSIGNEE_JIB_SHOULD_NOT_LEAK" not in context
