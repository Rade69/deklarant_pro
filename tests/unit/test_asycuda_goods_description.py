from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
from exporters.asycuda_xml_builder import AsycudaXMLBuilder


def _builder_with_assigned_line() -> tuple[AsycudaXMLBuilder, NaimenovanjeDraft]:
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=58,
        tariff_code="63079090",
        tariff_description2="Ostali gotovi tekstilni proizvodi",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(
            line_no=58,
            invoice_number="893/26",
            naziv_robe="BORT 112900 B.R.Z.palac lev XL",
            assigned_naimenovanje_ordinal=58,
        )
    ]
    return AsycudaXMLBuilder(draft), item


def test_commercial_description_starts_with_tariff_heading_for_asycuda_rb31():
    builder, item = _builder_with_assigned_line()

    desc = builder._build_commercial_description(item, 280)

    assert desc.startswith("Ostali gotovi tekstilni proizvodi")
    assert "BORT 112900 B.R.Z.palac lev XL" in desc
    assert "Faktura: 893/26 (rb. 58)" in desc


def test_tariff_heading_uses_description1_when_description2_is_empty():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="40169900",
        tariff_description1="Ostali proizvodi od vulkanizovane gume",
    )

    assert AsycudaXMLBuilder(draft)._tariff_heading(item) == "Ostali proizvodi od vulkanizovane gume"


def test_commercial_description_truncates_without_losing_invoice_reference():
    builder, item = _builder_with_assigned_line()
    item.tariff_description2 = "Vrlo dug tarifni opis " * 10

    desc = builder._build_commercial_description(item, 90)

    assert len(desc) <= 90
    assert "Faktura: 893/26 (rb. 58)" in desc
