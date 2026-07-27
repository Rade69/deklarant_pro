import xml.etree.ElementTree as ET

import pytest

from services.security import safe_xml
from services.security.safe_xml import UnsafeXmlError, safe_parse


def test_obican_xml_se_parsira(tmp_path):
    path = tmp_path / "ok.xml"
    path.write_text("<root><item>vrijednost</item></root>", encoding="utf-8")

    assert safe_parse(path).getroot().findtext("item") == "vrijednost"


@pytest.mark.parametrize("declaration", ["<!DOCTYPE root>", "<!ENTITY x 'boom'>"])
def test_dtd_i_entity_se_odbijaju(tmp_path, declaration):
    path = tmp_path / "unsafe.xml"
    path.write_text(f"{declaration}<root/>", encoding="utf-8")

    with pytest.raises(UnsafeXmlError):
        safe_parse(path)


def test_prevelik_xml_se_odbija(tmp_path, monkeypatch):
    path = tmp_path / "large.xml"
    path.write_text("<root>1234567890</root>", encoding="utf-8")
    monkeypatch.setattr(safe_xml, "MAX_XML_BYTES", 8)

    with pytest.raises(UnsafeXmlError):
        safe_parse(path)


def test_predubok_xml_se_odbija(tmp_path, monkeypatch):
    path = tmp_path / "deep.xml"
    path.write_text("<a><b><c/></b></a>", encoding="utf-8")
    monkeypatch.setattr(safe_xml, "MAX_XML_DEPTH", 2)

    with pytest.raises(UnsafeXmlError):
        safe_parse(path)


def test_previse_elemenata_se_odbija(tmp_path, monkeypatch):
    path = tmp_path / "many.xml"
    root = ET.Element("root")
    for _ in range(4):
        ET.SubElement(root, "item")
    ET.ElementTree(root).write(path, encoding="utf-8")
    monkeypatch.setattr(safe_xml, "MAX_XML_ELEMENTS", 3)

    with pytest.raises(UnsafeXmlError):
        safe_parse(path)
