"""
Testovi za items_review_service — Faza 4.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
from services.agent.validation.finding_model import FindingCode, FindingSeverity
from services.agent.validation.items_review_service import provjeri_naimenovanja


def _make_draft_with_items(items=None):
    draft = DeclarationDraft()
    if items:
        draft.items = list(items)
    return draft


def _make_item(tariff_code="08052190", goods_description="Test proizvod",
               origin_country_code="DE", preference_code="",
               gross_mass_kg=100.0, net_mass_kg=90.0, item_id="1", ordinal_no=1):
    return NaimenovanjeDraft(
        item_id=item_id,
        ordinal_no=ordinal_no,
        tariff_code=tariff_code,
        goods_description=goods_description,
        origin_country_code=origin_country_code,
        preference_code=preference_code,
        gross_mass_kg=gross_mass_kg,
        net_mass_kg=net_mass_kg,
    )


class TestProvjeriNaimenovanja:

    def test_prazan_draft_vraca_ready(self):
        draft = _make_draft_with_items([])
        summary = provjeri_naimenovanja(draft)
        assert summary.ready is True

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_validno_naimenovanje_nema_blokada(self, mock_trazi):
        mock_trazi.return_value = {"naziv": "Opis tarife"}
        item = _make_item()
        draft = _make_draft_with_items([item])
        summary = provjeri_naimenovanja(draft)
        assert summary.ready is True

    def test_nedostaje_tarifni_broj(self):
        item = _make_item(tariff_code="")
        draft = _make_draft_with_items([item])
        summary = provjeri_naimenovanja(draft)
        assert any(f.code == FindingCode.MISSING_TARIFF for f in summary.findings)

    def test_nedostaje_zemlja_porijekla(self):
        item = _make_item(origin_country_code="")
        draft = _make_draft_with_items([item])
        summary = provjeri_naimenovanja(draft)
        assert any(f.code == FindingCode.MISSING_ORIGIN for f in summary.findings)

    def test_limit_99_blokira(self):
        items = [_make_item(item_id=str(i), ordinal_no=i) for i in range(1, 100)]
        draft = _make_draft_with_items(items)
        summary = provjeri_naimenovanja(draft)
        assert any(f.code == FindingCode.ASYCUDA_ITEM_LIMIT and f.blocking for f in summary.findings)

    def test_blizu_limita_upozorava(self):
        items = [_make_item(item_id=str(i), ordinal_no=i) for i in range(1, 96)]
        draft = _make_draft_with_items(items)
        summary = provjeri_naimenovanja(draft)
        assert any(f.code == FindingCode.ASYCUDA_ITEM_LIMIT and not f.blocking for f in summary.findings)

    def test_rub31_prekoracenje(self):
        item = _make_item(goods_description="x" * 300)
        draft = _make_draft_with_items([item])
        summary = provjeri_naimenovanja(draft)
        assert any(f.code == FindingCode.INVALID_RUB31 for f in summary.findings)

    def test_mase_nedostaju(self):
        item = _make_item(gross_mass_kg=0.0, net_mass_kg=0.0)
        draft = _make_draft_with_items([item])
        summary = provjeri_naimenovanja(draft)
        assert any(f.code == FindingCode.INVALID_WEIGHT for f in summary.findings)
