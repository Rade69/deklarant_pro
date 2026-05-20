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


def test_tariff_heading_normalizes_en_dash_to_hyphen():
    # Tarifna baza čuva – (U+2013) i − (U+2212) kao hijerarhijske indentatore.
    # ASYCUDA World ne prikazuje ih ispravno — u XML-u se pojavljuju kao â artefakti.
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="3005100000",
        tariff_description2="– – ljepljivi zavoji i ostali proizvodi",
    )

    heading = AsycudaXMLBuilder(draft)._tariff_heading(item)

    assert "–" not in heading
    assert "−" not in heading
    assert "- - ljepljivi zavoji" in heading


def test_commercial_description_truncates_to_max_chars():
    builder, item = _builder_with_assigned_line()
    item.tariff_description2 = "Vrlo dug tarifni opis " * 10

    desc = builder._build_commercial_description(item, 90)

    assert len(desc) <= 90


def test_commercial_description_never_exceeds_3_lines_or_55_chars_per_line():
    # ASYCUDA World odbaci polje pri kliku ako ima >3 linije ili >55 karaktera po liniji
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_description2="Ostali gotovi tekstilni i odjevni predmeti raznih vrsta",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(line_no=i, invoice_number="893/26", naziv_robe=f"Proizvod dugi naziv {i} extra tekst", assigned_naimenovanje_ordinal=1)
        for i in range(1, 8)
    ]

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 280)

    lines = desc.split("\n")
    assert len(lines) <= 3, f"Previše linija: {len(lines)}"
    for line in lines:
        assert len(line) <= 55, f"Linija predugačka ({len(line)}): {line!r}"


def test_commercial_description_preserves_heading_and_invoice_when_names_are_long():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=4,
        tariff_code="39269097",
        tariff_description2="- - ostalo",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(
            line_no=12,
            invoice_number="893/26",
            naziv_robe="GW GEL PODUPIRAC PRST. DESNI a1 102691500",
            assigned_naimenovanje_ordinal=4,
        ),
        InvoiceLine(
            line_no=13,
            invoice_number="893/26",
            naziv_robe="GW GEL STITNIK CUKLJEVA MALI PRST G 102693500",
            assigned_naimenovanje_ordinal=4,
        ),
        InvoiceLine(
            line_no=15,
            invoice_number="893/26",
            naziv_robe="GW GEL RASTAVLJAC a3 Mali 102680900",
            assigned_naimenovanje_ordinal=4,
        ),
        InvoiceLine(
            line_no=20,
            invoice_number="893/26",
            naziv_robe="OHP SOFT CEPOVI ZA USI a10",
            assigned_naimenovanje_ordinal=4,
        ),
    ]

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 150)

    assert len(desc) <= 150
    assert desc.startswith("- - ostalo")
    assert "Faktura: 893/26 (rb. 12, 13, 15, 20)" in desc
    assert "..." in desc
    assert desc.endswith("Faktura: 893/26 (rb. 12, 13, 15, 20)")


def test_commercial_description_includes_all_names_when_they_fit():
    # ASYCUDA format: tačno 3 linije — nazivi se spajaju comma-separated na jednoj liniji
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_description2="- - ostalo",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(
            line_no=1,
            invoice_number="893/26",
            naziv_robe="Roba A",
            assigned_naimenovanje_ordinal=1,
        ),
        InvoiceLine(
            line_no=2,
            invoice_number="893/26",
            naziv_robe="Roba B",
            assigned_naimenovanje_ordinal=1,
        ),
    ]

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 120)

    assert desc == "- - ostalo\nRoba A, Roba B\nFaktura: 893/26 (rb. 1, 2)"


def test_commercial_description_prefers_precise_tariff_summary():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_description1="Kobasice i sl.proizvodi od mesa;ostalo,ostalo",
        tariff_description2="- - ostalo",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(
            line_no=1,
            invoice_number="0504-3-2000-00016",
            naziv_robe="ŠUNKA,PICA ŠUNKA",
            assigned_naimenovanje_ordinal=1,
        ),
    ]

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 280)

    assert desc.splitlines()[0] == "Kobasice i sl.proizvodi od mesa;ostalo,ostalo"


def test_commercial_description_compacts_existing_multiline_trade_name():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        goods_description="Prehrambeni proizvodi koji nisu spomenuti niti uključeni na drugom mjestu:",
        tariff_description2="- - - ostali",
        goods_trade_name=(
            "Prehrambeni proizvodi koji nisu spomenuti niti uključeni na drugom mjestu:\n"
            "SUSSINA 650 tbl.\n"
            "SUSSINA 200 tbl.\n"
            "SUSSINA 1200 tbl\n"
            "SUSSINA STEVIA a200 tbl\n"
            "Faktura: 893/26 (rb. 1, 2, 17, 26)"
        ),
    )

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 280)

    lines = desc.split("\n")
    assert len(lines) <= 3
    assert lines[0] == "Prehrambeni proizvodi koji nisu spomenuti niti uklju..."
    assert lines[1] == "SUSSINA 650 tbl., SUSSINA 200 tbl., SUSSINA 1200 tbl..."
    assert lines[2] == "Faktura: 893/26 (rb. 1, 2, 17, 26)"
    for line in lines:
        assert len(line) <= 55


def test_commercial_description_uses_goods_description_when_tariff_heading_is_generic():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        goods_description="Prehrambeni proizvodi koji nisu spomenuti niti uključeni na drugom mjestu:",
        tariff_description2="- - - ostali",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(
            line_no=1,
            invoice_number="893/26",
            naziv_robe="SUSSINA 650 tbl.",
            assigned_naimenovanje_ordinal=1,
        ),
        InvoiceLine(
            line_no=2,
            invoice_number="893/26",
            naziv_robe="SUSSINA 200 tbl.",
            assigned_naimenovanje_ordinal=1,
        ),
        InvoiceLine(
            line_no=17,
            invoice_number="893/26",
            naziv_robe="SUSSINA 1200 tbl",
            assigned_naimenovanje_ordinal=1,
        ),
        InvoiceLine(
            line_no=26,
            invoice_number="893/26",
            naziv_robe="SUSSINA STEVIA a200 tbl",
            assigned_naimenovanje_ordinal=1,
        ),
    ]

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 280)

    assert desc == (
        "Prehrambeni proizvodi koji nisu spomenuti niti uklju...\n"
        "SUSSINA 650 tbl., SUSSINA 200 tbl., SUSSINA 1200 tbl...\n"
        "Faktura: 893/26 (rb. 1, 2, 17, 26)"
    )


def test_commercial_description_does_not_use_product_name_as_tariff_summary():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=9,
        tariff_description1="GREJAC RERNE GORENJE 1100W PERLA 616021 (GP1127) UZI",
        tariff_description2="- - ostali",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(
            line_no=2,
            invoice_number="266VP-2026",
            naziv_robe="GREJAC RERNE GORENJE 1100W PERLA 616021 (GP1127) UZI",
            assigned_naimenovanje_ordinal=9,
        )
    ]

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 280)

    assert desc == (
        "- - ostali\n"
        "GREJAC RERNE GORENJE 1100W PERLA 616021 (GP1127) UZI\n"
        "Faktura: 266VP-2026 (rb. 2)"
    )


def test_commercial_description_deduplicates_product_names_by_normalized_text():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=12,
        tariff_description1="TUNEL GUMA GORENJE 576363 PS-15 OEM",
        tariff_description2="- - zaptivci, podlošci i ostali proizvodi za zaptivanje",
    )
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(
            line_no=9,
            invoice_number="266VP-2026",
            naziv_robe="TUNEL GUMA GORENJE 576363 PS-15 OEM",
            assigned_naimenovanje_ordinal=12,
        ),
        InvoiceLine(
            line_no=10,
            invoice_number="266VP-2026",
            naziv_robe="TUNEL  GUMA GORENJE 576363 PS-15 OEM",
            assigned_naimenovanje_ordinal=12,
        ),
    ]

    desc = AsycudaXMLBuilder(draft)._build_commercial_description(item, 280)

    assert desc == (
        "- - zaptivci, podlošci i ostali proizvodi za zaptivanje\n"
        "TUNEL GUMA GORENJE 576363 PS-15 OEM\n"
        "Faktura: 266VP-2026 (rb. 9, 10)"
    )


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


def test_free_text_1_keeps_pe_document_code_and_reference():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=1,
            attached_document4="PE1 A",
            attached_document2="N380 893/26",
        )
    ]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item/Free_text_1") == "PE1 A"


def test_free_text_1_keeps_pe2_and_pe3_references():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(item_id="1", ordinal_no=1, attached_document4="PE2 893/26"),
        NaimenovanjeDraft(item_id="2", ordinal_no=2, attached_document4="PE3 AUTH-1"),
    ]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item[1]/Free_text_1") == "PE2 893/26"
    assert root.findtext("./Item[2]/Free_text_1") == "PE3 AUTH-1"


def test_pe_attached_document_exports_code_and_number_as_name():
    draft = DeclarationDraft()
    draft.header_attached_documents = [
        AttachedDocument(code="PE1", name="EUR.1 obrazac", number="A", from_rule=True)
    ]
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]

    root = AsycudaXMLBuilder(draft).build()
    doc = root.find("./Item/Attached_documents")

    assert doc is not None
    assert doc.findtext("Attached_document_code") == "PE1"
    assert doc.findtext("Attached_document_name") == "A"
    assert doc.findtext("Attached_document_reference") == "A"


def test_export_replaces_known_invalid_tariff_code():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=5,
            tariff_code="40199090",
        )
    ]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item/Tarification/HScode/Commodity_code") == "39269097"
    assert draft.items[0].tariff_code == "39269097"
    assert any("40199090" in warning and "39269097" in warning for warning in draft.warnings)


def test_export_replaces_known_invalid_bort_tariff_code():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=16,
            tariff_code="63079099",
        )
    ]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item/Tarification/HScode/Commodity_code") == "63079098"
    assert draft.items[0].tariff_code == "63079098"
    assert any("63079099" in warning and "63079098" in warning for warning in draft.warnings)


def test_export_warns_but_does_not_block_attached_document_without_reference():
    draft = DeclarationDraft()
    draft.header_attached_documents = [
        AttachedDocument(code="N380", name="Faktura", number="")
    ]
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item/Attached_documents/Attached_document_code") == "N380"
    assert any("N380" in warning for warning in draft.warnings)
