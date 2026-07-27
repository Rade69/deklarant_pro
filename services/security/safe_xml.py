import os
import xml.etree.ElementTree as ET
from pathlib import Path


MAX_XML_BYTES = int(os.getenv("MAX_XML_BYTES", str(25 * 1024 * 1024)))
MAX_XML_ELEMENTS = int(os.getenv("MAX_XML_ELEMENTS", "200000"))
MAX_XML_DEPTH = int(os.getenv("MAX_XML_DEPTH", "128"))


class UnsafeXmlError(ValueError):
    pass


def _read_xml_bytes(path: str | Path) -> bytes:
    xml_path = Path(path)
    if xml_path.stat().st_size > MAX_XML_BYTES:
        raise UnsafeXmlError(
            f"XML fajl prelazi dozvoljeni limit od {MAX_XML_BYTES} bajtova"
        )
    data = xml_path.read_bytes()
    probe = data.upper()
    if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
        raise UnsafeXmlError("DTD i ENTITY deklaracije nisu dozvoljene")
    return data


def _validate_tree(root) -> None:
    count = 0
    stack = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        count += 1
        if count > MAX_XML_ELEMENTS:
            raise UnsafeXmlError("XML ima previše elemenata")
        if depth > MAX_XML_DEPTH:
            raise UnsafeXmlError("XML struktura je preduboka")
        stack.extend((child, depth + 1) for child in element)


def safe_parse(path: str | Path) -> ET.ElementTree:
    root = ET.fromstring(_read_xml_bytes(path))
    _validate_tree(root)
    return ET.ElementTree(root)


def safe_lxml_parse(path: str | Path):
    from lxml import etree

    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=False,
        recover=False,
    )
    root = etree.fromstring(_read_xml_bytes(path), parser=parser)
    _validate_tree(root)
    return etree.ElementTree(root)
