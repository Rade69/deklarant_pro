"""Testovi za ZaglavljeService.validate() metodu."""

import pytest
from services.zaglavlje_service import ZaglavljeService
from core.draft.draft import DeclarationDraft, InvoiceLine, AttachedDocument


@pytest.fixture
def service():
    return ZaglavljeService()


@pytest.fixture
def empty_draft():
    draft = DeclarationDraft()
    return draft


@pytest.fixture
def populated_draft():
    draft = DeclarationDraft()
    draft.valuta = "EUR"
    draft.iznos = 1500.0
    draft.items = []
    draft.invoice_lines = [
        InvoiceLine(line_no=1, iznos=1000.0, valuta="EUR"),
        InvoiceLine(line_no=2, iznos=500.0, valuta="EUR"),
    ]
    return draft


@pytest.fixture
def draft_with_attached_docs():
    draft = DeclarationDraft()
    draft.valuta = "EUR"
    draft.iznos = 1500.0
    draft.items = []
    draft.invoice_lines = [
        InvoiceLine(line_no=1, iznos=1000.0, valuta="EUR"),
        InvoiceLine(line_no=2, iznos=500.0, valuta="EUR"),
    ]
    draft.header_attached_documents = [
        AttachedDocument(code="N380", name="Faktura", number="INV-001"),
        AttachedDocument(code="N730", name="EUR.1", number="EUR-123"),
    ]
    return draft


def _base_view_data():
    """Minimalni valid view data."""
    return {
        "iznos": "1500.00",
        "valuta": "EUR",
        "deklaracija_1": "IM",
        "deklaracija_oznaka": "Z",
        "deklaracija_a": "Z",
        "izvoznik_r1": "Test Exports DOO",
        "izvoznik_r3": "Sarajevo",
        "izvoznik_r5": "BA",
        "primalac_r1": "Test Imports DOO",
        "primalac_r2": "Import Ave 2",
        "primalac_r3": "Belgrade",
        "primalac_r5": "RS",
        "deklarant_r1": "Customs Agent",
        "deklarant_r2": "Agent St 3",
        "deklarant_r3": "Banja Luka",
        "transport_id": "E25A456",
        "aktivno_transport": "E25A456",
        "vid_25": "1",
        "uslovi_kod": "FOB",
        "uslovi_mjesto": "Luka Koper",
    }


# ============================================================
# Test 1: Prazan draft — treba imati greške
# ============================================================
def test_empty_draft_has_errors(service, empty_draft):
    view_data = {}
    result = service.validate(view_data, empty_draft)

    assert result["valid"] is False
    assert result["error_count"] > 0
    assert "Iznos fakture" in [e["field"] for e in result["errors"]]


# ============================================================
# Test 2: Sinhronizacija iznosa — mismatch detekcija
# ============================================================
def test_iznos_mismatch_detected(service, populated_draft):
    view_data = _base_view_data()
    view_data["iznos"] = "999.00"  # Namjerno pogrešno
    result = service.validate(view_data, populated_draft)

    # Treba detektovati mismatch iznosa
    iznos_errors = [
        e for e in result["errors"] if e.get("fix_action") == "auto_update_iznos"
    ]
    assert len(iznos_errors) == 1
    assert "999.00" in iznos_errors[0]["message"]
    assert "1500.00" in iznos_errors[0]["message"]


# ============================================================
# Test 3: Valuta mismatch
# ============================================================
def test_valuta_mismatch_detected(service, populated_draft):
    view_data = _base_view_data()
    view_data["valuta"] = "USD"  # Pogrešna valuta
    view_data["izvoznik_r2"] = "Test"
    result = service.validate(view_data, populated_draft)

    valuta_warnings = [
        w for w in result["warnings"] if w.get("fix_action") == "auto_update_valuta"
    ]
    assert len(valuta_warnings) == 1
    assert "USD" in valuta_warnings[0]["message"]
    assert "EUR" in valuta_warnings[0]["message"]


# ============================================================
# Test 4: Neispravna oznaka deklaracije
# ============================================================
def test_ex_im_inconsistency(service, empty_draft):
    # deklaracija_oznaka mora biti A, Z ili B — "H" je neispravno
    view_data = {
        "deklaracija_1": "IM",
        "deklaracija_oznaka": "H",  # Neispravno — dozvoljeno je samo A/Z/B
    }
    result = service.validate(view_data, empty_draft)

    combo_errors = [
        e for e in result["errors"] if "Neispravna oznaka deklaracije" in e["message"]
    ]
    assert len(combo_errors) == 1


# ============================================================
# Test 5: Validan unos — nema grešaka (sa svim obaveznim dokumentima)
# ============================================================
def test_valid_entry_no_errors(service, populated_draft):
    view_data = _base_view_data()
    view_data["attached_documents"] = [
        {"code": "VOZ", "name": "Vozarina", "number": "VOZ-001"},
        {"code": "OST", "name": "Ostalo", "number": "OST-001"},
        {"code": "PZT", "name": "Prateći zahtjev", "number": "PZT-001"},
        {"code": "N730", "name": "Tovarni list", "number": "N730-001"},
        {"code": "N380", "name": "Faktura", "number": "INV-001"},
        {"code": "DIS", "name": "DIS", "number": "DIS-001"},
        {"code": "DV1", "name": "DV1", "number": "DV1-001"},
    ]
    result = service.validate(view_data, populated_draft)

    assert result["valid"] is True
    assert result["error_count"] == 0


# ============================================================
# Test 6: Priloženi dokumenti — matching sa import snapshot-om (nema warning)
# ============================================================
def test_attached_docs_matching_no_warning(service, populated_draft):
    import_snapshot = [
        {"code": "N380", "name": "Faktura", "number": "INV-001"},
        {"code": "N730", "name": "EUR.1", "number": "EUR-123"},
    ]
    view_data = _base_view_data()
    view_data["attached_documents"] = list(import_snapshot)
    result = service.validate(view_data, populated_draft, import_snapshot)

    # Nema warning-a za priložene dokumente
    doc_warnings = [
        w for w in result["warnings"] if "Priložene isprave" in w.get("field", "")
    ]
    assert len(doc_warnings) == 0


# ============================================================
# Test 7: Priloženi dokumenti — prazna referenca blokira export
# ============================================================
def test_attached_docs_mismatch_warning(service, populated_draft):
    # PZT je prisutan ali bez reference → mora blokirati export
    view_data = _base_view_data()
    view_data["attached_documents"] = [
        {"code": "VOZ", "name": "Vozarina", "number": "VOZ-001"},
        {"code": "PZT", "name": "Prateći zahtjev", "number": ""},  # Prazna referenca
        {"code": "N380", "name": "Faktura", "number": "INV-001"},
        {"code": "DIS", "name": "DIS", "number": ""},
        {"code": "DV1", "name": "DV1", "number": "DV1-001"},
    ]
    result = service.validate(view_data, populated_draft)

    doc_errors = [
        e for e in result["errors"] if "Priloženi dokumenti" in e.get("field", "")
    ]
    assert len(doc_errors) >= 1
    assert result["valid"] is False


# ============================================================
# Test 8: Bez import snapshot-a — nema warning (nije bilo import-a)
# ============================================================
def test_attached_docs_no_import_no_warning(service, populated_draft):
    view_data = _base_view_data()
    view_data["attached_documents"] = []
    # import_attached_docs=None (nije proslijeđen)
    result = service.validate(view_data, populated_draft)

    doc_warnings = [
        w for w in result["warnings"] if "Priložene isprave" in w.get("field", "")
    ]
    assert len(doc_warnings) == 0


# ============================================================
# Test 9: Adresa izvoznika nije obavezna
# ============================================================
def test_izvoznik_adresa_not_required(service, populated_draft):
    view_data = _base_view_data()
    # Namjerno bez izvoznik_r2
    view_data.pop("izvoznik_r2", None)
    result = service.validate(view_data, populated_draft)

    # Ne treba grešku za adresu
    address_errors = [
        e for e in result["errors"] if "Adresa izvoznika" in e.get("field", "")
    ]
    assert len(address_errors) == 0


# ============================================================
# Test 10: Export sa greškama treba biti blokiran
# ============================================================
def test_export_blocked_when_validation_fails(service, empty_draft):
    """
    Ako validacija ima greške, export treba biti blokiran.
    Ovo testira da service.validate() vraća valid=False.
    """
    view_data = {}  # Prazni podaci
    result = service.validate(view_data, empty_draft)

    # Controller bi trebao blokirati export kad je valid=False
    assert result["valid"] is False
    assert result["error_count"] > 0
