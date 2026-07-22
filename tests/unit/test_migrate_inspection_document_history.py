"""
Testovi za database/migrate_inspection_document_history.py — scan_xml_archive().

Koristi stvarne privremene XML fajlove (pravi ET parser, bez mockovanja) —
provjerava agregaciju, mapiranje starih/novih kodova i preskakanje
neispravnih/nepodržanih zapisa.
"""
from pathlib import Path

from database.migrate_inspection_document_history import scan_xml_archive

_ITEM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<ASYCUDA>
  <Item>
    <Tarification>
      <HScode>
        <Commodity_code>{tarif}</Commodity_code>
      </HScode>
    </Tarification>
    <Attached_documents>
      <Attached_document_code>{code}</Attached_document_code>
      <Attached_document_name>{name}</Attached_document_name>
    </Attached_documents>
  </Item>
</ASYCUDA>
"""


def _write_xml(dirpath: Path, filename: str, tarif: str, code: str, name: str) -> None:
    (dirpath / filename).write_text(
        _ITEM_TEMPLATE.format(tarif=tarif, code=code, name=name),
        encoding="utf-8",
    )


def test_scan_xml_archive_agregira_isti_tarif_i_tip(tmp_path):
    _write_xml(tmp_path, "d1.xml", "21069098", "SAN", "Sanitarno - zdravstveno uvjerenje")
    _write_xml(tmp_path, "d2.xml", "21069098", "SAN", "Sanitarno - zdravstveno uvjerenje")

    result = scan_xml_archive(tmp_path)

    assert result[("21069098", "sanitary")]["usage_count"] == 2
    assert result[("21069098", "sanitary")]["document_code"] == "SAN"


def test_scan_xml_archive_stari_i_novi_kod_ista_kategorija(tmp_path):
    _write_xml(tmp_path, "old.xml", "16010099", "UVK", "Uvjerenje o kvalitetu robe")
    _write_xml(tmp_path, "new.xml", "16010099", "N003", "Uvjerenje o kvaliteti robe")

    result = scan_xml_archive(tmp_path)

    assert result[("16010099", "market_inspection")]["usage_count"] == 2


def test_scan_xml_archive_preskace_nepoznat_kod(tmp_path):
    _write_xml(tmp_path, "nepoznat.xml", "21069098", "XYZ", "Nepoznat dokument")

    result = scan_xml_archive(tmp_path)

    assert result == {}


def test_scan_xml_archive_preskace_nevalidan_tarifni_broj(tmp_path):
    _write_xml(tmp_path, "kratak.xml", "123", "SAN", "Sanitarno - zdravstveno uvjerenje")

    result = scan_xml_archive(tmp_path)

    assert result == {}


def test_scan_xml_archive_preskace_pokvaren_xml(tmp_path):
    (tmp_path / "pokvaren.xml").write_text("<ASYCUDA><Item>", encoding="utf-8")
    _write_xml(tmp_path, "ok.xml", "21069098", "VET", "Veterinarsko uvjerenje")

    result = scan_xml_archive(tmp_path)

    assert result[("21069098", "veterinary")]["usage_count"] == 1
