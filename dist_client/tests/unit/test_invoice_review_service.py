"""
Testovi za invoice_review_service — Faza 3 (stručna provjera Faktura taba).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.draft.draft import DeclarationDraft, InvoiceLine
from services.agent.validation.finding_model import FindingCode, FindingSeverity
from services.agent.validation.invoice_review_service import provjeri_fakturu


def _make_draft_with_lines(lines=None):
    draft = DeclarationDraft()
    if lines:
        draft.invoice_lines = list(lines)
    return draft


def _make_line(tarifni_broj="08052190", naziv_robe="Test proizvod",
               zemlja_porijekla="DE", bruto_kg=10.0, neto_kg=9.0,
               iznos=100.0, kolicina=5, jm="kom"):
    return InvoiceLine(
        tarifni_broj=tarifni_broj,
        naziv_robe=naziv_robe,
        zemlja_porijekla=zemlja_porijekla,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        iznos=iznos,
        kolicina=kolicina,
        jm=jm,
    )


class TestProvjeriFakturu:

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_prazan_draft_vraca_ready(self, mock_trazi):
        draft = _make_draft_with_lines([])
        summary = provjeri_fakturu(draft)
        assert summary.ready is True
        assert summary.checked_count == 0

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_validna_stavka_nema_blokada(self, mock_trazi):
        mock_trazi.return_value = {"naziv": "Opis tarife"}
        line = _make_line()
        draft = _make_draft_with_lines([line])
        summary = provjeri_fakturu(draft)
        # FakturaItemValidator prolazi, tarifa postoji → nema blokada
        assert summary.ready is True

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_nedostaje_tarifni_broj(self, mock_trazi):
        mock_trazi.return_value = None
        line = _make_line(tarifni_broj="")
        draft = _make_draft_with_lines([line])
        summary = provjeri_fakturu(draft)
        assert summary.ready is False
        assert any(f.code == FindingCode.MISSING_TARIFF for f in summary.findings)

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_tarifa_ne_postoji_u_evidenciji(self, mock_trazi):
        mock_trazi.return_value = None  # ne postoji u zvaničnoj tarifi
        line = _make_line(tarifni_broj="99999999")
        draft = _make_draft_with_lines([line])
        summary = provjeri_fakturu(draft)
        # Upozorenje da tarifa nije pronađena
        assert any(f.code == FindingCode.TARIFF_NOT_FOUND for f in summary.findings)

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_negativna_bruto_tezina(self, mock_trazi):
        mock_trazi.return_value = None
        line = _make_line(bruto_kg=-5.0)
        draft = _make_draft_with_lines([line])
        summary = provjeri_fakturu(draft)
        assert any(f.code == FindingCode.INVALID_WEIGHT for f in summary.findings)

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_neto_vece_od_bruto(self, mock_trazi):
        mock_trazi.return_value = None
        line = _make_line(bruto_kg=5.0, neto_kg=10.0)
        draft = _make_draft_with_lines([line])
        summary = provjeri_fakturu(draft)
        assert any(f.code == FindingCode.GROSS_LESS_THAN_NET for f in summary.findings)

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_duplikat_stavke(self, mock_trazi):
        mock_trazi.return_value = None
        line1 = _make_line(tarifni_broj="08052190", naziv_robe="Duplikat proizvod")
        line1.invoice_number = "INV-001"
        line2 = _make_line(tarifni_broj="08052190", naziv_robe="Duplikat proizvod")
        line2.invoice_number = "INV-001"
        draft = _make_draft_with_lines([line1, line2])
        summary = provjeri_fakturu(draft)
        assert any(f.code == FindingCode.DUPLICATE_INVOICE_LINE for f in summary.findings)

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_scope_all_provjerava_sve(self, mock_trazi):
        mock_trazi.return_value = {"naziv": "Opis"}
        lines = [_make_line(tarifni_broj=f"0805219{i}") for i in range(3)]
        draft = _make_draft_with_lines(lines)
        summary = provjeri_fakturu(draft, scope="all")
        # Validne stavke nemaju nalaza — sve je čisto
        assert summary.ready is True
        assert summary.checks_run == (
            "basic_validation", "tariff_exists", "decision_evidence",
            "weights", "duplicates",
        )

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_draft_revision_zabiljezen(self, mock_trazi):
        mock_trazi.return_value = {"naziv": "Opis"}
        line = _make_line()
        draft = _make_draft_with_lines([line])
        draft.mark_dirty()
        summary = provjeri_fakturu(draft)
        assert summary.draft_revision > 0
