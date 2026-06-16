import xml.etree.ElementTree as ET

import pytest

from core.draft.draft import AttachedDocument, DeclarationDraft, InvoiceLine, NaimenovanjeDraft, Party
from services.declaration_draft_service import (
    DRAFT_ROOT_TAG,
    DeclarationDraftService,
    deserialize_draft,
    is_draft_file,
    serialize_draft,
    suggested_filename,
    suggested_title,
)


def _sample_draft():
    draft = DeclarationDraft(ref_br="REF-77", invoice_weights={"F-1": (12.5, 11.0)})
    draft.invoice_lines = [
        InvoiceLine(
            line_no=1,
            invoice_number="F-1",
            naziv_robe="Test roba",
            exporter=Party(name="Izvoznik"),
        )
    ]
    draft.items = [
        NaimenovanjeDraft(
            item_id="item-1",
            ordinal_no=1,
            tariff_code="85168020",
            attached_documents=[AttachedDocument(code="N380", number="F-1")],
        )
    ]
    draft.header_attached_documents = [AttachedDocument(code="N730", number="TL-1")]
    return draft


def test_draft_round_trip_preserves_nested_data():
    restored = deserialize_draft(serialize_draft(_sample_draft()))

    assert restored.ref_br == "REF-77"
    assert restored.invoice_weights["F-1"] == (12.5, 11.0)
    assert restored.invoice_lines[0].exporter.name == "Izvoznik"
    assert restored.items[0].attached_documents[0].code == "N380"
    assert restored.header_attached_documents[0].number == "TL-1"


def test_file_round_trip_uses_deklarant_pro_xml(tmp_path):
    path = DeclarationDraftService().save(_sample_draft(), tmp_path / "radni nacrt")

    assert path.suffix == ".xml"
    assert ET.parse(path).getroot().tag == DRAFT_ROOT_TAG
    assert is_draft_file(path)
    assert DeclarationDraftService().load(path).invoice_lines[0].invoice_number == "F-1"


def test_load_rejects_regular_xml(tmp_path):
    path = tmp_path / "asycuda.xml"
    path.write_text("<ASYCUDA />", encoding="utf-8")

    with pytest.raises(ValueError, match="nije Deklarant Pro nacrt"):
        DeclarationDraftService().load(path)


def test_suggested_names_prefer_invoice_numbers():
    draft = _sample_draft()

    assert suggested_title(draft) == "Deklaracija F-1"
    assert suggested_filename(draft) == "Deklaracija F-1.xml"
