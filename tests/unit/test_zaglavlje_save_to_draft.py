"""Test da save_to_draft pravilno čuva header_attached_documents."""

from services.zaglavlje_service import ZaglavljeService
from core.draft.draft import DeclarationDraft


def test_save_to_draft_preserves_attached_documents():
    """
    Kada se priloženi dokumenti učitaju iz XML-a u formu,
    save_to_draft mora da ih sačuva u draft.header_attached_documents.
    """
    service = ZaglavljeService()
    draft = DeclarationDraft()

    view_data = {
        "deklaracija_1": "IM",
        "deklaracija_oznaka": "H",
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
        "valuta": "EUR",
        "iznos": "1500.00",
        "attached_documents": [
            {"code": "N380", "name": "Faktura", "number": "INV-001", "from_rule": False},
            {"code": "N730", "name": "EUR.1", "number": "EUR-123", "from_rule": False},
        ],
    }

    result = service.save_to_draft(draft, view_data)

    assert len(result.header_attached_documents) == 2
    assert result.header_attached_documents[0].code == "N380"
    assert result.header_attached_documents[0].number == "INV-001"
    assert result.header_attached_documents[1].code == "N730"
    assert result.header_attached_documents[1].number == "EUR-123"


def test_save_to_draft_clears_empty_attached_documents():
    """Kada je attached_documents prazna lista, očisti draft."""
    service = ZaglavljeService()
    draft = DeclarationDraft()

    view_data = {
        "deklaracija_1": "IM",
        "deklaracija_oznaka": "H",
        "deklaracija_a": "Z",
        "izvoznik_r1": "Test",
        "izvoznik_r3": "Test",
        "izvoznik_r5": "BA",
        "primalac_r1": "Test",
        "primalac_r2": "Test",
        "primalac_r3": "Test",
        "primalac_r5": "RS",
        "deklarant_r1": "Test",
        "deklarant_r2": "Test",
        "deklarant_r3": "Test",
        "transport_id": "E25A456",
        "aktivno_transport": "E25A456",
        "vid_25": "1",
        "uslovi_kod": "FOB",
        "uslovi_mjesto": "Luka",
        "valuta": "EUR",
        "iznos": "100.00",
        "attached_documents": [],  # Eksplicitno prazno
    }

    result = service.save_to_draft(draft, view_data)

    assert result.header_attached_documents == []
