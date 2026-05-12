"""Test za parse_naimenovanja_from_xml() metodu."""

import tempfile
import os
from services.zaglavlje_service import ZaglavljeService


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
