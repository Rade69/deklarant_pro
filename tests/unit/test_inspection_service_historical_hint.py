"""
Testovi za InspectionService.historical_hint() i HistoricalDocumentHint.

Ne mokuje se PostgreSQL konekcija (zabranjeno po AGENTS.md) — testiraju se
putanje koje ne dotiču bazu (prazan/prekratak tarifni broj, _pg_available
False) i čisto dataclass ponašanje. Stvarni DB upit se ne može testirati
bez žive baze (vidi project_rooms/2026-07-22_istorijska-napomena-inspekcije.md).
"""
from services.inspection_service import HistoricalDocumentHint, InspectionService


def _service_without_pg() -> InspectionService:
    svc = InspectionService.__new__(InspectionService)
    svc._pg_available = False
    return svc


def _service_with_pg_stub() -> InspectionService:
    svc = InspectionService.__new__(InspectionService)
    svc._pg_available = True
    svc._get_conn = None  # ne poziva se jer normalize/len guard vraca ranije
    return svc


def test_historical_hint_prazna_lista_kad_pg_nedostupan():
    svc = _service_without_pg()
    assert svc.historical_hint("21069098") == []


def test_historical_hint_prazna_lista_za_prazan_tarifni_broj():
    svc = _service_with_pg_stub()
    assert svc.historical_hint("") == []


def test_historical_hint_prazna_lista_za_prekratak_tarifni_broj():
    svc = _service_with_pg_stub()
    assert svc.historical_hint("2106") == []


def test_historical_document_hint_label_koristi_inspection_labels():
    hint = HistoricalDocumentHint(
        inspection_type="market_inspection",
        document_name="Uvjerenje o kvalitetu robe",
        usage_count=86,
    )
    assert hint.label == "Tržna inspekcija"


def test_historical_document_hint_icon_fallback_za_nepoznat_tip():
    hint = HistoricalDocumentHint(
        inspection_type="nepoznat_tip",
        document_name="X",
        usage_count=1,
    )
    assert hint.icon == "🔍"
