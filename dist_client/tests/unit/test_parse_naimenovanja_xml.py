"""Test za parse_naimenovanja_from_xml() metodu i rub31_builder pomoćne funkcije."""

import tempfile
import os
from services.zaglavlje_service import ZaglavljeService
from services.naimenovanja.rub31_builder import _dedupe, _parse_trade_text


# ASYCUDA World XML format — nested struktura sa Packages, Goods_description,
# Tarification, Valuation_item (matching parser u zaglavlje_service.py)
SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Declaration>
    <Item>
        <Packages>
            <Marks1_of_packages>MARK-001</Marks1_of_packages>
            <Number_of_packages>10</Number_of_packages>
            <Kind_of_packages_code>CT</Kind_of_packages_code>
            <Kind_of_packages_name>Kartonske kutije</Kind_of_packages_name>
        </Packages>
        <Container_number>CONT-001</Container_number>
        <Goods_description>
            <Description_of_goods>Testna roba 1 - elektronika</Description_of_goods>
            <Commercial_Description>Trade Name 1</Commercial_Description>
            <Country_of_origin_code>CN</Country_of_origin_code>
            <Country_of_origin_name>Kina</Country_of_origin_name>
        </Goods_description>
        <Tarification>
            <Commodity_code>85171200</Commodity_code>
            <Precision_1>000</Precision_1>
            <Preference_code>100</Preference_code>
            <Item_price>5000.00</Item_price>
        </Tarification>
        <Valuation_item>
            <Weight_itm>
                <Gross_weight_itm>150.50</Gross_weight_itm>
                <Net_weight_itm>120.30</Net_weight_itm>
            </Weight_itm>
            <Statistical_value>5000.00</Statistical_value>
        </Valuation_item>
    </Item>
    <Item>
        <Packages>
            <Marks1_of_packages>MARK-002</Marks1_of_packages>
            <Number_of_packages>5</Number_of_packages>
            <Kind_of_packages_code>PK</Kind_of_packages_code>
            <Kind_of_packages_name>Paketi</Kind_of_packages_name>
        </Packages>
        <Goods_description>
            <Description_of_goods>Testna roba 2 - tekstil</Description_of_goods>
            <Commercial_Description>Trade Name 2</Commercial_Description>
            <Country_of_origin_code>TR</Country_of_origin_code>
            <Country_of_origin_name>Turska</Country_of_origin_name>
        </Goods_description>
        <Tarification>
            <Commodity_code>62034300</Commodity_code>
            <Precision_1>000</Precision_1>
            <Item_price>3000.00</Item_price>
        </Tarification>
        <Valuation_item>
            <Weight_itm>
                <Gross_weight_itm>80.00</Gross_weight_itm>
                <Net_weight_itm>65.00</Net_weight_itm>
            </Weight_itm>
            <Statistical_value>3000.00</Statistical_value>
        </Valuation_item>
        <Attached_documents>
            <Attached_document_code>N380</Attached_document_code>
            <Attached_document_name>Faktura</Attached_document_name>
            <Attached_document_reference>INV-002</Attached_document_reference>
        </Attached_documents>
    </Item>
</Declaration>
"""


def test_parse_naimenovanja_from_xml():
    """Test da se XML pravilno parsira u NaimenovanjeDraft objekte."""
    service = ZaglavljeService()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(SAMPLE_XML)
        f.flush()
        filepath = f.name

    try:
        items = service.parse_naimenovanja_from_xml(filepath)

        assert len(items) == 2

        # Prvi item
        item1 = items[0]
        assert item1.ordinal_no == 1
        assert item1.package_marks == "MARK-001"
        assert item1.package_qty == 10.0
        assert item1.package_code == "CT"
        assert item1.package_name == "Kartonske kutije"
        assert "elektronika" in item1.goods_description
        assert item1.goods_trade_name == "Trade Name 1"
        assert item1.tariff_code == "85171200"
        assert item1.tariff_suffix == "000"
        assert item1.origin_country_code == "CN"
        assert item1.origin_country_name == "Kina"
        assert item1.preference_code == "100"
        assert item1.gross_mass_kg == 150.50
        assert item1.net_mass_kg == 120.30
        assert item1.item_value == 5000.00
        assert item1.currency == "EUR"
        assert item1.statistical_value == 5000.00
        assert item1.container_number1 == "CONT-001"

        # Drugi item
        item2 = items[1]
        assert item2.ordinal_no == 2
        assert item2.tariff_code == "62034300"
        assert item2.origin_country_code == "TR"
        assert item2.item_value == 3000.00
        assert len(item2.attached_documents) == 1
        assert item2.attached_documents[0].code == "N380"
        assert item2.attached_documents[0].number == "INV-002"

    finally:
        os.unlink(filepath)


def test_parse_naimenovanja_file_not_found():
    """Test da FileNotFoundError za nepostojeći fajl."""
    service = ZaglavljeService()

    try:
        service.parse_naimenovanja_from_xml("/nonexistent/path/file.xml")
        assert False, "Treba baciti FileNotFoundError"
    except FileNotFoundError:
        pass  # Očekivano


def test_parse_naimenovanja_invalid_xml():
    """Test da ValueError za nevalidan XML."""
    service = ZaglavljeService()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write("ovo nije xml <><><>")
        f.flush()
        filepath = f.name

    try:
        service.parse_naimenovanja_from_xml(filepath)
        assert False, "Treba baciti ValueError"
    except ValueError:
        pass  # Očekivano
    finally:
        os.unlink(filepath)


def test_parse_naimenovanja_empty_xml():
    """Test da prazan XML vraća praznu listu."""
    service = ZaglavljeService()

    empty_xml = '<?xml version="1.0"?><Declaration></Declaration>'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(empty_xml)
        f.flush()
        filepath = f.name

    try:
        items = service.parse_naimenovanja_from_xml(filepath)
        assert items == []
    finally:
        os.unlink(filepath)


def test_parse_naimenovanja_uses_description_as_trade_name_when_commercial_missing():
    service = ZaglavljeService()

    xml = """<?xml version="1.0"?>
<Declaration>
    <Item>
        <Goods_description>
            <Description_of_goods>Opis robe iz XML-a</Description_of_goods>
            <Country_of_origin_code>AT</Country_of_origin_code>
        </Goods_description>
        <Tarification>
            <Commodity_code>21069098</Commodity_code>
        </Tarification>
    </Item>
</Declaration>
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml)
        f.flush()
        filepath = f.name

    try:
        items = service.parse_naimenovanja_from_xml(filepath)

        assert len(items) == 1
        assert items[0].goods_description == "Opis robe iz XML-a"
        assert items[0].goods_trade_name == "Opis robe iz XML-a"
    finally:
        os.unlink(filepath)


def test_parse_naimenovanja_maps_pe_document_to_master_rub44_field():
    service = ZaglavljeService()

    xml = """<?xml version="1.0"?>
<Declaration>
    <Item>
        <Goods_description>
            <Description_of_goods>Opis robe</Description_of_goods>
        </Goods_description>
        <Attached_documents>
            <Attached_document_code>N003</Attached_document_code>
            <Attached_document_name>Kontrola</Attached_document_name>
            <Attached_document_reference>1</Attached_document_reference>
        </Attached_documents>
        <Attached_documents>
            <Attached_document_code>PE1</Attached_document_code>
            <Attached_document_name>EUR.1 obrazac</Attached_document_name>
            <Attached_document_reference>123</Attached_document_reference>
        </Attached_documents>
        <Attached_documents>
            <Attached_document_code>AGL</Attached_document_code>
            <Attached_document_name>Dozvola</Attached_document_name>
            <Attached_document_reference>1</Attached_document_reference>
        </Attached_documents>
    </Item>
</Declaration>
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml)
        f.flush()
        filepath = f.name

    try:
        items = service.parse_naimenovanja_from_xml(filepath)
        item = items[0]

        assert item.attached_document1 == "N003 (1)"
        assert item.attached_document2 == "AGL (1)"
        assert item.attached_document4 == "PE1 123"
    finally:
        os.unlink(filepath)


def test_parse_naimenovanja_marks_attached_doc_item_codes_as_from_rule():
    service = ZaglavljeService()

    xml = """<?xml version="1.0"?>
<Declaration>
    <Item>
        <Tarification>
            <Attached_doc_item>N380 DIS N853</Attached_doc_item>
        </Tarification>
        <Attached_documents>
            <Attached_document_code>N380</Attached_document_code>
            <Attached_document_name>Faktura</Attached_document_name>
            <Attached_document_reference>893/26</Attached_document_reference>
        </Attached_documents>
        <Attached_documents>
            <Attached_document_code>OST</Attached_document_code>
            <Attached_document_name>Prethodni dokument</Attached_document_name>
            <Attached_document_reference>SP1</Attached_document_reference>
        </Attached_documents>
    </Item>
</Declaration>
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml)
        f.flush()
        filepath = f.name

    try:
        item = service.parse_naimenovanja_from_xml(filepath)[0]

        docs = {doc.code: doc.from_rule for doc in item.attached_documents}
        assert docs["N380"] is True
        assert docs["OST"] is False
    finally:
        os.unlink(filepath)


def test_dedupe_skips_comma_composite_when_parts_already_seen():
    """Stari format 'A; B\nA, B' → _dedupe vraća ['A', 'B'], preskače 'A, B'."""
    result = _dedupe(["CREVO A", "CREVO B", "CREVO A, CREVO B"])
    assert result == ["CREVO A", "CREVO B"]


def test_dedupe_keeps_composite_when_parts_not_all_seen():
    """'A, B' se zadržava ako B još nije viđen."""
    result = _dedupe(["CREVO A", "CREVO A, CREVO B"])
    assert result == ["CREVO A", "CREVO A, CREVO B"]


def test_dedupe_normal_no_duplicates():
    """Normalan slučaj bez duplikata — sve vrijednosti se čuvaju."""
    result = _dedupe(["A", "B", "C"])
    assert result == ["A", "B", "C"]


def test_dedupe_exact_duplicate_removed():
    """Tačan duplikat se uvijek uklanja."""
    result = _dedupe(["KONDENZATOR 14mf", "KONDENZATOR 14mf", "KONDENZATOR 40mf"])
    assert result == ["KONDENZATOR 14mf", "KONDENZATOR 40mf"]


def test_parse_trade_text_old_format_eliminates_comma_line():
    """Stari goods_trade_name format (tačka-zarez linija + zarez linija) → bez duplikata u trade_parts."""
    old_format = (
        "DOVODNO CREVO VES MASINE 1.5m; CREVO 4x6mm 4m\n"
        "DOVODNO CREVO VES MASINE 1.5m, CREVO 4x6mm 4m\n"
        "Faktura: 266VP-2026 (rb. 3, 6)"
    )
    trade_parts, invoice_text = _parse_trade_text(old_format)

    assert "DOVODNO CREVO VES MASINE 1.5m" in trade_parts
    assert "CREVO 4x6mm 4m" in trade_parts
    # Kompozitna zarez-linija mora biti eliminisana
    assert not any("," in p for p in trade_parts), \
        f"Kompozitna linija nije eliminisana: {trade_parts}"
    assert "Faktura:" in invoice_text


def test_parse_naimenovanja_compacts_multiline_commercial_description_for_rb31():
    service = ZaglavljeService()

    xml = """<?xml version="1.0"?>
<Declaration>
    <Item>
        <Goods_description>
            <Description_of_goods>- - - ostali</Description_of_goods>
            <Commercial_Description>Prehrambeni proizvodi koji nisu spomenuti niti uključeni na drugom mjestu:
SUSSINA 650 tbl.
SUSSINA 200 tbl.
SUSSINA 1200 tbl
SUSSINA STEVIA a200 tbl
Faktura: 893/26 (rb. 1, 2, 17, 26)</Commercial_Description>
        </Goods_description>
        <Tarification>
            <Commodity_code>21069098</Commodity_code>
        </Tarification>
    </Item>
</Declaration>
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml)
        f.flush()
        filepath = f.name

    try:
        item = service.parse_naimenovanja_from_xml(filepath)[0]

        lines = item.goods_trade_name.splitlines()
        assert lines == [
            "Prehrambeni proizvodi koji nisu spomenuti niti uklju...",
            "SUSSINA 650 tbl., SUSSINA 200 tbl., SUSSINA 1200 tbl...",
            "Faktura: 893/26 (rb. 1, 2, 17, 26)",
        ]
        for line in lines:
            assert len(line) <= 55
    finally:
        os.unlink(filepath)
