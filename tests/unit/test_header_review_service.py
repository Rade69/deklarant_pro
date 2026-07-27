"""
Testovi za header_review_service — Faza 5.
"""
from __future__ import annotations

from core.draft.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
from services.agent.validation.finding_model import FindingCode
from services.agent.validation.header_review_service import (
    provjeri_zaglavlje,
    provjeri_usklađenost_tabova,
)


def _draft():
    d = DeclarationDraft()
    d.deklaracija_tip = "IM"
    d.izvoznik_naziv = "Exporter"
    d.primalac_naziv = "Importer"
    d.deklarant_naziv = "Deklarant"
    d.valuta = "EUR"
    return d


class TestProvjeriZaglavlje:

    def test_prazan_draft_ima_blokade(self):
        d = DeclarationDraft()
        summary = provjeri_zaglavlje(d)
        assert summary.ready is False
        assert summary.blocking_count >= 3  # tip, izvoznik, primalac, deklarant

    def test_popunjen_draft_nema_blokada(self):
        d = _draft()
        summary = provjeri_zaglavlje(d)
        assert summary.ready is True

    def test_nedostaje_valuta(self):
        d = _draft()
        d.valuta = ""
        summary = provjeri_zaglavlje(d)
        assert any(f.code == FindingCode.HEADER_REQUIRED_FIELD and not f.blocking for f in summary.findings)


class TestProvjeriUskladjenostTabova:

    def test_prazan_draft(self):
        d = DeclarationDraft()
        summary = provjeri_usklađenost_tabova(d)
        # Potpuno prazan draft (bez faktura) → nema upozorenja
        assert summary.ready is True

    def test_fakture_bez_naimenovanja(self):
        d = DeclarationDraft()
        d.invoice_lines = [InvoiceLine(naziv_robe="Test", iznos=100.0)]
        summary = provjeri_usklađenost_tabova(d)
        assert any(f.code == FindingCode.ITEM_GROUPING_MISMATCH for f in summary.findings)

    def test_iznosi_se_poklapaju(self):
        d = DeclarationDraft()
        d.invoice_lines = [InvoiceLine(naziv_robe="Test", iznos=100.0)]
        d.items = [NaimenovanjeDraft(
            item_id="1", ordinal_no=1, goods_description="Test",
            statistical_value=100.0,
        )]
        summary = provjeri_usklađenost_tabova(d)
        # Iznosi se poklapaju → nema CROSS_TAB_MISMATCH
        assert not any(f.code == FindingCode.CROSS_TAB_MISMATCH for f in summary.findings)

    def test_iznosi_se_razlikuju(self):
        d = DeclarationDraft()
        d.invoice_lines = [InvoiceLine(naziv_robe="Test", iznos=100.0)]
        d.items = [NaimenovanjeDraft(
            item_id="1", ordinal_no=1, goods_description="Test",
            statistical_value=200.0,
        )]
        summary = provjeri_usklađenost_tabova(d)
        assert any(f.code == FindingCode.CROSS_TAB_MISMATCH for f in summary.findings)
