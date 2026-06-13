import xml.etree.ElementTree as ET
from unittest.mock import patch

from core.draft import AttachedDocument, DeclarationDraft, InvoiceLine, NaimenovanjeDraft
from exporters.asycuda_xml_builder import AsycudaXMLBuilder
from services.naimenovanja.rub31_builder import build_asycuda_rub31


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

    goods_desc = builder._build_description_of_goods(item, 280)
    desc = builder._build_commercial_description(item, 280)

    assert goods_desc == "Ostali gotovi tekstilni proizvodi"
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
    assert "Faktura: 893/26 (rb. 12, 13, 15, 20)" in desc
    assert "..." in desc
    assert desc.endswith("Faktura: 893/26 (rb. 12, 13, 15, 20)")


def test_commercial_description_includes_all_names_when_they_fit():
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

    builder = AsycudaXMLBuilder(draft)
    goods_desc = builder._build_description_of_goods(item, 280)
    desc = builder._build_commercial_description(item, 280)

    assert goods_desc == "Kobasice i sl.proizvodi od mesa;ostalo,ostalo"
    assert desc.startswith("Kobasice i sl.proizvodi od mesa;ostalo,ostalo")


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

    builder = AsycudaXMLBuilder(draft)
    goods_desc = builder._build_description_of_goods(item, 280)
    desc = builder._build_commercial_description(item, 280)

    # Description_of_goods je skraćen na _MAX_LINE (ASYCUDA Rub.31 editor
    # gubi sadržaj polja kad je u jednoj liniji duže od ~55 karaktera) —
    # zato je identičan prvoj liniji commercial_description.
    assert goods_desc == "Prehrambeni proizvodi koji nisu spomenuti niti uklju..."
    assert desc == (
        "Prehrambeni proizvodi koji nisu spomenuti niti uklju...\n"
        "SUSSINA 650 tbl., SUSSINA 200 tbl., SUSSINA 1200 tbl...\n"
        "Faktura: 893/26 (rb. 1, 2, 17, 26)"
    )
    assert desc.startswith(goods_desc)


def test_rub31_builder_splits_tariff_description_from_invoice_goods():
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=13,
        goods_description="brtve,podlošci i ostali proizvodi za brtvljenje",
        tariff_description2="- - zaptivci, podlošci i ostali proizvodi za zaptivanje",
        goods_trade_name=(
            "brtve,podlošci i ostali proizvodi za brtvljenje\n"
            "TUNEL GUMA CANDY 117CY22 GSK016CY CY3035; TUNEL GUMA CANDY 117CY22 GSK016CY CY3036\n"
            "TUNEL GUMA CANDY 117CY22 GSK016CY CY3035; TUNEL GUMA CANDY 117CY22 GSK016CY CY3036\n"
            "Faktura: 266VP-2026 (rb. 10, 11)"
        ),
    )

    rub31 = build_asycuda_rub31(item)

    assert rub31.description_of_goods == "brtve,podlošci i ostali proizvodi za brtvljenje"
    assert rub31.commercial_description == (
        "brtve,podlošci i ostali proizvodi za brtvljenje\n"
        "TUNEL GUMA CANDY 117CY22 GSK016CY CY3035, TUNEL GUMA...\n"
        "Faktura: 266VP-2026 (rb. 10, 11)"
    )


def test_rub31_builder_does_not_duplicate_product_names_from_imported_xml():
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=2,
        tariff_description2="brtve,podlošci i ostali proizvodi za brtvljenje",
        goods_trade_name=(
            "TUNEL GUMA CANDY 117CY22 GSK016CY CY3035, TUNEL GUMA CANDY 117CY22 GSK016CY CY3036\n"
            "TUNEL GUMA CANDY 117CY22 GSK016CY CY3035, TUNEL GUMA CANDY 117CY22 GSK016CY CY3036\n"
            "Faktura: 266VP-2026 (rb. 10, 11)"
        ),
    )

    rub31 = build_asycuda_rub31(item)

    assert rub31.description_of_goods == "brtve,podlošci i ostali proizvodi za brtvljenje"
    assert rub31.commercial_description.count("TUNEL GUMA CANDY") == 1
    assert rub31.commercial_description.endswith("Faktura: 266VP-2026 (rb. 10, 11)")


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


def test_dict_attached_document_exports_without_crash():
    draft = DeclarationDraft()
    draft.header_attached_documents = [
        {
            "code": "N380",
            "name": "Faktura",
            "number": "893/26",
            "from_rule": True,
        }
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


def test_export_defaults_empty_package_type_to_pp_komad():
    draft = DeclarationDraft()
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1, package_qty=3)]

    root = AsycudaXMLBuilder(draft).build()

    assert root.findtext("./Item/Packages/Kind_of_packages_code") == "PP"
    assert root.findtext("./Item/Packages/Kind_of_packages_name") == "Komad"


def test_tariff_heading_falls_back_to_4digit_when_specific_is_generic():
    # Specifičan pod-tarifni opis je "-- ostali" (generički).
    # 4-cifreni heading (8516) treba biti korišten kao fallback.
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="85168080",
    )

    db_responses = {
        "85168080": {"naziv": "-- ostali"},
        "851680": {"naziv": "- ostali"},
        "8516": {"naziv": "Električni bojleri, grijači prostorija i tla"},
    }

    with patch("services.tariff.tarifa_service.trazi_po_kodu", side_effect=lambda k: db_responses.get(k)):
        heading = AsycudaXMLBuilder(draft)._tariff_heading(item)

    assert heading == "Električni bojleri, grijači prostorija i tla"


def test_tariff_heading_prefers_non_generic_over_4digit():
    # Ako postoji specifičan non-generički opis, ne smiješmo ga zamijeniti 4-cifrenim.
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="85164000",
    )

    db_responses = {
        "85164000": {"naziv": "Pegle na struju"},
        "851640": {"naziv": "Pegle na struju"},
        "8516": {"naziv": "Električni bojleri, grijači prostorija i tla"},
    }

    with patch("services.tariff.tarifa_service.trazi_po_kodu", side_effect=lambda k: db_responses.get(k)):
        heading = AsycudaXMLBuilder(draft)._tariff_heading(item)

    assert heading == "Pegle na struju"


def test_tariff_heading_uses_non_generic_from_item_fields_without_db():
    # tariff_description2 je non-generički → nema DB lookup-a
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="85168080",
        tariff_description2="Električni grijači za vodu",
    )

    with patch("services.tariff.tarifa_service.trazi_po_kodu") as mock_db:
        heading = AsycudaXMLBuilder(draft)._tariff_heading(item)
        mock_db.assert_not_called()

    assert heading == "Električni grijači za vodu"


def test_tariff_heading_triggers_db_lookup_when_item_field_is_generic():
    # tariff_description2 je generički ("-- ostali") → mora pokušati DB lookup
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        tariff_code="85168080",
        tariff_description2="-- ostali",
    )

    db_responses = {
        "85168080": {"naziv": "-- ostali"},
        "851680": {"naziv": "- ostali"},
        "8516": {"naziv": "Električni bojleri, grijači prostorija i tla"},
    }

    with patch("services.tariff.tarifa_service.trazi_po_kodu", side_effect=lambda k: db_responses.get(k)):
        heading = AsycudaXMLBuilder(draft)._tariff_heading(item)

    assert heading == "Električni bojleri, grijači prostorija i tla"


# ── _choose_tariff_description: autorizovana tarifna polja ──────────────────


def test_choose_tariff_description_not_filtered_when_contains_numbers():
    """tariff_description2 s brojevima ne smije biti filtriran kao naziv proizvoda.
    Primjer: kod 39173100 → "savitljive cijevi...27,6 Mpa" sadrži cifre,
    ali to je tarifni opis, ne naziv proizvoda."""
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=10,
        tariff_code="39173100",
        tariff_description2=(
            "– – savitljive cijevi i crijeva, koji mogu podnijeti "
            "pritisak od 27,6 Mpa ili veći"
        ),
        goods_trade_name=(
            "– – savitljive cijevi i crijeva, koji mogu podnijeti pritisak od 27,6 Mpa ili veći\n"
            "POLIETILENSKA SAVITLJIVA CIJEV 63mm; POLIETILENSKA SAVITLJIVA CIJEV 90mm\n"
            "Faktura: F-2026/45 (rb. 10)"
        ),
    )

    rub31 = build_asycuda_rub31(item)

    # "27,6" je dio dužeg tarifnog opisa — description_of_goods je skraćen
    # na _MAX_LINE, ali ova provjera potvrđuje da kandidat sa "27,6" nije
    # filtriran kao naziv proizvoda (inače bi description_of_goods bio
    # drugačiji tekst ili ".").
    assert rub31.description_of_goods == "- - savitljive cijevi i crijeva, koji mogu podnijeti..."
    assert rub31.description_of_goods != "."


def test_choose_tariff_description_not_filtered_when_description1_contains_numbers():
    """tariff_description1 s brojevima ne smije biti filtriran."""
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=22,
        tariff_code="73102990",
        tariff_description1="– – – debljine zida od 0,5 mm ili veće",
        goods_trade_name=(
            "– – – debljine zida od 0,5 mm ili veće\n"
            "ČELIČNA CIJEV DN50; ČELIČNA CIJEV DN100\n"
            "Faktura: F-2026/22 (rb. 22)"
        ),
    )

    rub31 = build_asycuda_rub31(item)

    assert "0,5 mm" in rub31.description_of_goods
    assert rub31.description_of_goods != "."


def test_choose_tariff_description_returns_description2_when_description1_absent():
    """tariff_description2 s brojevima se koristi kad tariff_description1 nije postavljen."""
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=25,
        tariff_code="85322500",
        tariff_description2="– – dielektrični, od papira ili plastične mase",
        goods_trade_name=(
            "– – dielektrični, od papira ili plastične mase\n"
            "KONDENZATOR 470uF 25V; KONDENZATOR 100uF 16V\n"
            "Faktura: F-2026/25 (rb. 25)"
        ),
    )

    rub31 = build_asycuda_rub31(item)

    assert "dielektrični" in rub31.description_of_goods
    assert rub31.description_of_goods != "."


# ── Bug: goods_description s "(+N više)" prolazi product filter ──────────────

def test_overflow_marker_in_goods_description_is_filtered_as_product():
    """goods_description s '; ... (+2 više)' sufiksom treba biti prepoznat kao
    produkt tekst i filtriran iz opisa — čak i kad overflow marker 'kvari' listu."""
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=6,
        tariff_code="40169300",
        tariff_description2="- - zaptivci, podlošci i ostali proizvodi za zaptivanje",
        goods_description=(
            "TUNEL GUMA HISENSE HK1913550; TUNEL GUMA HISENSE HK1913551; "
            "TUNEL GUMA HISENSE HK2080355; ... (+2 više)"
        ),
    )
    invoice_lines = [
        InvoiceLine(
            line_no=i,
            invoice_number="264VP-2026",
            naziv_robe=naziv,
            assigned_naimenovanje_ordinal=6,
        )
        for i, naziv in enumerate(
            [
                "TUNEL GUMA HISENSE HK1913550",
                "TUNEL GUMA HISENSE HK1913551",
                "TUNEL GUMA HISENSE HK2080355",
                "TUNEL GUMA HISENSE HK4567890",
                "TUNEL GUMA HISENSE HK3456789",
            ],
            start=1,
        )
    ]

    rub31 = build_asycuda_rub31(item, invoice_lines=invoice_lines)

    assert "zaptivci" in rub31.description_of_goods
    assert "TUNEL GUMA" not in rub31.description_of_goods


# ── Bug: kratki fragment opisi bez parent heading konteksta ───────────────────

def test_heading_fragment_yields_to_richer_tariff_heading():
    """'- šarke' je fragment bez konteksta — kad postoji bogatiji tariff_heading,
    taj treba biti vraćen kao opis."""
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=8,
        tariff_code="83021000",
        tariff_description2="- šarke",
        goods_description="SARKA VRATA RERNE GORENJE 166670",
    )
    invoice_lines = [
        InvoiceLine(
            line_no=1,
            invoice_number="266VP-2026",
            naziv_robe="SARKA VRATA RERNE GORENJE 166670",
            assigned_naimenovanje_ordinal=8,
        )
    ]

    rub31 = build_asycuda_rub31(
        item,
        invoice_lines=invoice_lines,
        tariff_heading="Šarke, zglobovi i sl. pribor od prostih metala",
    )

    assert "Šarke, zglobovi" in rub31.description_of_goods
    assert rub31.description_of_goods != "- šarke"


def test_long_specific_description_not_treated_as_fragment():
    """'- - savitljive cijevi...' je dugačak specifičan opis — ne smije biti
    zamijenjen kraćim tariff_heading čak i kad postoji."""
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=3,
        tariff_code="39173100",
        tariff_description2=(
            "- - savitljive cijevi i crijeva, koji mogu podnijeti "
            "pritisak od 27,6 Mpa ili veće"
        ),
    )

    rub31 = build_asycuda_rub31(
        item,
        tariff_heading="Cijevi i crijeva od polimera etilena",
    )

    assert "savitljive cijevi" in rub31.description_of_goods
    assert "polimera etilena" not in rub31.description_of_goods


def test_fragment_fallback_when_no_tariff_heading():
    """Kad nema bogatijeg headinga, fragment se ipak vraća kao fallback."""
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=8,
        tariff_code="83021000",
        tariff_description2="- šarke",
    )

    rub31 = build_asycuda_rub31(item, tariff_heading="")

    assert rub31.description_of_goods == "- šarke"
