from core.draft.draft import AttachedDocument, DeclarationDraft, NaimenovanjeDraft
from gui.tabs.naimenovanja_view import NaimenovanjaView, _clear_secondary_pe_documents
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
