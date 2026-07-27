from core.draft.draft import AttachedDocument, DeclarationDraft
from gui.tabs.zaglavlje_controller import ZaglavljeController


def test_import_merge_skips_imported_ost_without_current_ost():
    controller = ZaglavljeController.__new__(ZaglavljeController)

    merged = controller._merge_import_docs_add_only_missing(
        existing_docs=[],
        draft_header_docs=[],
        imported_docs=[
            {
                "code": "OST",
                "name": "Posebna dokumenta za carinjenje",
                "number": "SP-STARI",
            },
            {
                "code": "N380",
                "name": "Faktura",
                "number": "893/26",
            },
        ],
    )

    assert [doc["code"] for doc in merged] == ["N380"]


def test_import_merge_preserves_current_ost_from_draft():
    controller = ZaglavljeController.__new__(ZaglavljeController)

    merged = controller._merge_import_docs_add_only_missing(
        existing_docs=[],
        draft_header_docs=[
            AttachedDocument(
                code="OST",
                name="Ostali prateći dokumenti",
                number="SP-NOVI",
            )
        ],
        imported_docs=[
            {
                "code": "OST",
                "name": "Posebna dokumenta za carinjenje",
                "number": "SP-STARI",
            }
        ],
    )

    assert merged == [
        {
            "code": "OST",
            "name": "Ostali prateći dokumenti",
            "number": "SP-NOVI",
            "from_rule": False,
        }
    ]


def test_sync_ost_doc_from_rb40_adds_current_reference():
    controller = ZaglavljeController.__new__(ZaglavljeController)
    draft = DeclarationDraft()

    controller._sync_ost_doc_from_rb40(draft, "SP-NOVI")

    assert len(draft.header_attached_documents) == 1
    ost = draft.header_attached_documents[0]
    assert ost.code == "OST"
    assert ost.name == "Ostali prateći dokumenti"
    assert ost.number == "SP-NOVI"
