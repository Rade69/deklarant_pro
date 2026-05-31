from pathlib import Path

import pytest

from services.agent.learning import exporter_xml_indexer as indexer


def _write_xml(path: Path, exporter: str, consignee: str, jib: str = "4200000000000"):
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<ASYCUDA>
  <Identification>
    <Assessment>
      <Date>4/16/2026</Date>
    </Assessment>
  </Identification>
  <Traders>
    <Exporter>
      <Exporter_name>{exporter}</Exporter_name>
    </Exporter>
    <Consignee>
      <Consignee_name>{consignee}</Consignee_name>
      <Consignee_code>{jib}</Consignee_code>
    </Consignee>
  </Traders>
</ASYCUDA>
""",
        encoding="utf-8",
    )


def test_normalize_exporter_name_removes_legal_suffixes():
    assert indexer.normalize_exporter_name("ENMON d.o.o.") == "ENMON"
    assert indexer.normalize_exporter_name("Šumaprom Commerce D.O.O.") == "ŠUMAPROM COMMERCE"


def test_extract_parties_from_xml(tmp_path):
    xml_path = tmp_path / "test.xml"
    _write_xml(xml_path, "ENMON d.o.o.", "IPEK d.o.o.", "1234567890123")

    exporter, consignee, jib, declaration_date = indexer.extract_parties_from_xml(xml_path)

    assert exporter == "ENMON d.o.o."
    assert consignee == "IPEK d.o.o."
    assert jib == "1234567890123"
    assert declaration_date.year == 2026


def test_scan_xml_folder_keeps_latest_per_exporter_consignee(tmp_path, monkeypatch):
    old_xml = tmp_path / "old.xml"
    new_xml = tmp_path / "new.xml"
    _write_xml(old_xml, "ENMON d.o.o.", "IPEK d.o.o.", "123")
    _write_xml(new_xml, "ENMON d.o.o.", "IPEK d.o.o.", "123")
    old_xml.write_text(old_xml.read_text(encoding="utf-8").replace("4/16/2026", "4/16/2024"), encoding="utf-8")

    monkeypatch.setattr(indexer, "XML_FOLDER", tmp_path)

    pairs = indexer.scan_xml_folder()

    assert len(pairs) == 1
    entry = next(iter(pairs.values()))
    assert Path(entry.xml_filepath).name == "new.xml"


def test_fuzzy_threshold_is_project_standard():
    assert indexer.FUZZY_MATCH_THRESHOLD == 0.92


class _FailingInsertCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if "INSERT INTO catalogs.exporter_xml_index" in sql:
            raise RuntimeError("insert failed")


class _FakeConnection:
    def __init__(self):
        self.cursor_obj = _FailingInsertCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_reindex_rolls_back_when_save_fails(monkeypatch):
    fake_conn = _FakeConnection()
    entry = indexer.ExporterEntry(
        exporter_normalized="ENMON",
        consignee_normalized="IPEK",
        consignee_jib="123",
        exporter_original="ENMON",
        consignee_original="IPEK",
        xml_filepath="/tmp/example.xml",
    )

    monkeypatch.setattr(indexer, "scan_xml_folder", lambda: {("ENMON", "123"): entry})
    monkeypatch.setattr(indexer, "get_db_connection", lambda: fake_conn)

    with pytest.raises(RuntimeError):
        indexer.reindex()

    assert fake_conn.rolled_back is True
    assert fake_conn.committed is False
    assert fake_conn.closed is True
    assert any("DELETE FROM catalogs.exporter_xml_index" in sql for sql in fake_conn.cursor_obj.executed)


def test_reindex_does_not_clear_existing_index_when_scan_is_empty(monkeypatch):
    fake_conn = _FakeConnection()

    monkeypatch.setattr(indexer, "scan_xml_folder", lambda: {})
    monkeypatch.setattr(indexer, "get_db_connection", lambda: fake_conn)

    assert indexer.reindex() == 0
    assert fake_conn.cursor_obj.executed == []
    assert fake_conn.committed is False
    assert fake_conn.rolled_back is False
