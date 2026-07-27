from core.draft.draft import AttachedDocument, DeclarationDraft, NaimenovanjeDraft
from gui.tabs.naimenovanja_view import (
    NaimenovanjaView,
    _clear_secondary_pe_documents,
    _normalize_pe_document_text,
)
from gui.tabs.zaglavlje_controller import ZaglavljeController


def test_clears_stale_secondary_pe_when_master_has_pe2():
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        preference_code="EUPR",
        attached_document1="PE1",
        attached_document4="PE2 266VP-2026",
    )

    changed = _clear_secondary_pe_documents(item)

    assert changed is True
    assert item.attached_document1 == ""
    assert item.attached_document4 == "PE2 266VP-2026"


def test_normalizes_duplicate_pe_prefix_in_master_doc():
    assert _normalize_pe_document_text("PE1 PE1 A") == "PE1 A"
    assert _normalize_pe_document_text("PE2 PE2 266VP-2026") == "PE2 266VP-2026"
    assert _normalize_pe_document_text("PE1 PE1") == "PE1"
    assert _normalize_pe_document_text("N380 268VP-2026") == "N380 268VP-2026"


def test_clears_stale_secondary_pe_and_normalizes_master_doc():
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        preference_code="EUPR",
        attached_document1="PE1",
        attached_document4="PE1 PE1 A",
    )

    changed = _clear_secondary_pe_documents(item)

    assert changed is True
    assert item.attached_document1 == ""
    assert item.attached_document4 == "PE1 A"


def test_pd_codes_does_not_show_pe1_when_item_has_pe2_master_doc():
    view = NaimenovanjaView.__new__(NaimenovanjaView)
    view.draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        preference_code="EUPR",
        attached_document4="PE2 266VP-2026",
    )
    view.draft.header_attached_documents = [
        AttachedDocument(code="PE1", name="EUR.1 obrazac", number="A", from_rule=True),
        AttachedDocument(code="N380", name="Faktura", number="266VP-2026", from_rule=True),
    ]

    assert view._compute_pd_codes(item) == "N380"


def test_pd_codes_uses_item_attached_documents_in_single_rb44_line():
    view = NaimenovanjaView.__new__(NaimenovanjaView)
    view.draft = DeclarationDraft()
    item = NaimenovanjeDraft(item_id="1", ordinal_no=1)
    item.attached_documents = [
        AttachedDocument(code="OST", name="Prethodni dokument", number="SP1", from_rule=False),
        AttachedDocument(code="N380", name="Faktura", number="1", from_rule=True),
        AttachedDocument(code="DIS", name="Dispozicija", number="D1", from_rule=True),
        AttachedDocument(code="PE1", name="EUR.1", number="A", from_rule=True),
        AttachedDocument(code="N853", name="Uvjerenje", number="U1", from_rule=True),
    ]

    assert view._compute_pd_codes(item) == "N380 DIS N853"


def test_xml_import_global_documents_apply_to_all_preferential_items():
    view = NaimenovanjaView.__new__(NaimenovanjaView)
    view.draft = DeclarationDraft()
    items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=1,
            preference_code="EUPR",
            attached_document4="PE1 A",
            attached_documents=[
                AttachedDocument(code="PE1", name="EUR.1", number="A", from_rule=True),
                AttachedDocument(code="N853", name="Uvjerenje", number="1", from_rule=True),
            ],
        ),
        NaimenovanjeDraft(item_id="2", ordinal_no=2, preference_code="EUPR"),
    ]

    view._apply_xml_import_global_documents(items)

    assert items[1].attached_document4 == "PE1 A"
    assert view._compute_pd_codes(items[1]) == "N853"


def test_zaglavlje_sync_prefers_master_pe_doc_over_stale_secondary_pe():
    controller = ZaglavljeController.__new__(ZaglavljeController)
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=1,
            attached_document1="PE1",
            attached_document4="PE2 266VP-2026",
        )
    ]

    controller._sync_pe_docs_from_items_to_header(draft)

    assert [(d.code, d.number) for d in draft.header_attached_documents] == [
        ("PE2", "266VP-2026")
    ]
