import xml.etree.ElementTree as ET

from core.draft import AttachedDocument, DeclarationDraft, InvoiceLine, NaimenovanjeDraft
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


def test_commercial_description_multiline_format_for_asycuda_rb31():
    builder, item = _builder_with_assigned_line()

    desc = builder._build_commercial_description(item, 280)

    # ASYCUDA format: heading\nnaziv\nFaktura: — newline-separated
    assert desc.startswith("Ostali gotovi tekstilni proizvodi")
    assert "BORT 112900 B.R.Z.palac lev XL" in desc
    assert "Faktura: 893/26 (rb. 58)" in desc
    assert "\n" in desc


def test_tariff_heading_uses_description1_when_description2_is_empty():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="40169900",
        tariff_description1="Ostali proizvodi od vulkanizovane gume",
    )

    assert AsycudaXMLBuilder(draft)._tariff_heading(item) == "Ostali proizvodi od vulkanizovane gume"


def test_commercial_description_truncates_to_max_chars():
    builder, item = _builder_with_assigned_line()
    item.tariff_description2 = "Vrlo dug tarifni opis " * 10

    desc = builder._build_commercial_description(item, 90)

    assert len(desc) <= 90


def test_description_of_goods_returns_dot_not_tariff_code_when_no_heading():
    # Kada nema opisa, vraća "." — ne tarifni kod koji ASYCUDA ne prepoznaje kao tekst
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="40199090",
    )

    desc = AsycudaXMLBuilder(draft)._build_description_of_goods(item)

    assert desc
    assert desc != "40199090"  # Nikada ne upisati sam tarifni kod kao opis


def test_valuation_total_invoice_uses_foreign_currency_and_total_weight_uses_gross():
    draft = DeclarationDraft()
    draft.iznos = 9521.50
    draft.kurs = 1.95583
    draft.valuta = "EUR"
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=1,
            gross_mass_kg=170.0,
            net_mass_kg=154.91,
            item_value=9521.50,
        )
    ]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Valuation/Total/Total_invoice") == "9521.50"
    assert root.findtext("./Valuation/Gs_Invoice/Amount_national_currency") == "18622.44"
    assert root.findtext("./Valuation/Total/Total_weight") == "170.00"
    assert root.findtext("./Valuation/Weight/Gross_weight") == "170.00"


def test_multiple_origin_header_exports_many_marker():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(item_id="1", ordinal_no=1, origin_country_code="DE"),
        NaimenovanjeDraft(item_id="2", ordinal_no=2, origin_country_code="FR"),
    ]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./General_information/Country/Country_of_origin_name") == "MNOGO"


def test_from_rule_attached_document_exports_flag():
    draft = DeclarationDraft()
    draft.header_attached_documents = [
        AttachedDocument(code="N380", name="Faktura", number="893/26", from_rule=True)
    ]
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]

    root = AsycudaXMLBuilder(draft).build()
    doc = root.find("./Item/Attached_documents")

    assert doc is not None
    assert doc.findtext("Attached_document_code") == "N380"
    assert doc.findtext("Attached_document_reference") == "893/26"
    assert doc.findtext("Attached_document_from_rule") == "1"


def test_export_warns_but_does_not_block_unknown_tariff_code():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=5,
            tariff_code="40199090",
        )
    ]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item/Tarification/HScode/Commodity_code") == "40199090"
    assert any("40199090" in warning for warning in draft.warnings)


def test_export_warns_but_does_not_block_attached_document_without_reference():
    draft = DeclarationDraft()
    draft.header_attached_documents = [
        AttachedDocument(code="N380", name="Faktura", number="")
    ]
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item/Attached_documents/Attached_document_code") == "N380"
    assert any("N380" in warning for warning in draft.warnings)
