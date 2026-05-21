from core.draft import DeclarationDraft, InvoiceLine
from services.naimenovanja.create_naimenovanja_service import (
    MAX_ASYCUDA_ITEMS,
    CreateNaimenovanjaService,
)


def _line(idx: int) -> InvoiceLine:
    return InvoiceLine(
        line_no=idx,
        naziv_robe=f"Roba {idx}",
        tarifni_broj=f"{idx:08d}",
        zemlja_porijekla="TR",
        povlastica="TRP",
        kolicina=1,
        iznos=10,
        bruto_kg=2,
        neto_kg=1,
        valuta="EUR",
    )


def test_create_smart_group_limits_current_declaration_to_99_items():
    draft = DeclarationDraft()
    draft.invoice_lines = [_line(i) for i in range(1, 105)]

    service = CreateNaimenovanjaService(draft)
    count = service.create_smart_group()

    assert count == MAX_ASYCUDA_ITEMS
    assert len(draft.items) == MAX_ASYCUDA_ITEMS
    assert len(draft.invoice_lines) == MAX_ASYCUDA_ITEMS
    assert draft.items[-1].ordinal_no == MAX_ASYCUDA_ITEMS
    assert hasattr(draft, "pending_next_declaration")
    assert len(draft.pending_next_declaration.invoice_lines) == 5
    assert draft.pending_next_declaration.items == []


def test_create_smart_group_keeps_grouped_count_under_limit_without_pending_draft():
    draft = DeclarationDraft()
    draft.invoice_lines = [_line(i) for i in range(1, 20)]
    for line in draft.invoice_lines:
        line.tarifni_broj = "84189900"

    service = CreateNaimenovanjaService(draft)
    count = service.create_smart_group()

    assert count == 1
    assert len(draft.invoice_lines) == 19
    assert not hasattr(draft, "pending_next_declaration")


def test_created_naimenovanja_default_to_pp_komadi_packaging():
    draft = DeclarationDraft()
    draft.invoice_lines = [_line(1), _line(2)]

    service = CreateNaimenovanjaService(draft)
    service.create_one_to_one()

    assert {item.package_code for item in draft.items} == {"PP"}
    assert {item.package_name for item in draft.items} == {"Komadi"}
