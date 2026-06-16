"""
Unit testovi za asycuda_xml_builder helper funkcije — bez DB, bez fajlova.

Testira: _null, _text, _val, _fmt_party_name, _parse_cost, _fmt_thousands.
"""
import xml.etree.ElementTree as ET
import pytest
from exporters.asycuda_xml_builder import (
    _null,
    _text,
    _val,
    _fmt_party_name,
    _parse_cost,
    _fmt_thousands,
)


# ──────────────────────────────────────────────────────────────
# _parse_cost
# ──────────────────────────────────────────────────────────────

class TestParseCost:
    def test_float_string(self):
        assert _parse_cost("1500.50") == pytest.approx(1500.50)

    def test_comma_decimal(self):
        assert _parse_cost("1500,50") == pytest.approx(1500.50)

    def test_space_in_number(self):
        assert _parse_cost("1 500.50") == pytest.approx(1500.50)

    def test_integer_string(self):
        assert _parse_cost("200") == pytest.approx(200.0)

    def test_empty(self):
        assert _parse_cost("") == 0.0

    def test_none_like(self):
        assert _parse_cost(None) == 0.0

    def test_invalid(self):
        assert _parse_cost("abc") == 0.0

    def test_zero(self):
        assert _parse_cost("0") == 0.0

    def test_float_value(self):
        assert _parse_cost(1234.56) == pytest.approx(1234.56)


# ──────────────────────────────────────────────────────────────
# _fmt_thousands
# ──────────────────────────────────────────────────────────────

class TestFmtThousands:
    def test_below_1000(self):
        assert _fmt_thousands(500.0) == "500.00"

    def test_exactly_1000(self):
        assert _fmt_thousands(1000.0) == "1,000.00"

    def test_large_number(self):
        assert _fmt_thousands(1056.01) == "1,056.01"

    def test_large_number_many_thousands(self):
        assert _fmt_thousands(18500.00) == "18,500.00"

    def test_two_decimals_rounded(self):
        # 999.999 < 1000 → else grana → "1000.00" (bez zareza)
        assert _fmt_thousands(999.999) == "1000.00"

    def test_zero(self):
        assert _fmt_thousands(0.0) == "0.00"


# ──────────────────────────────────────────────────────────────
# _fmt_party_name
# ──────────────────────────────────────────────────────────────

class TestFmtPartyName:
    def test_single_part(self):
        assert _fmt_party_name("MASTER TOOLS DOO") == "MASTER TOOLS DOO"

    def test_multiple_parts(self):
        result = _fmt_party_name("MASTER TOOLS DOO", "BEOGRAD", "Ul. Mira 5")
        assert result == "MASTER TOOLS DOO\nBEOGRAD\nUl. Mira 5"

    def test_empty_parts_skipped(self):
        result = _fmt_party_name("MASTER TOOLS DOO", "", "Ul. Mira 5")
        assert result == "MASTER TOOLS DOO\nUl. Mira 5"

    def test_whitespace_only_skipped(self):
        result = _fmt_party_name("MASTER TOOLS DOO", "   ", "Beograd")
        assert result == "MASTER TOOLS DOO\nBeograd"

    def test_all_empty(self):
        assert _fmt_party_name("", "  ", "") == ""

    def test_strips_whitespace(self):
        result = _fmt_party_name("  MASTER TOOLS  ", "  BEOGRAD  ")
        assert result == "MASTER TOOLS\nBEOGRAD"


# ──────────────────────────────────────────────────────────────
# _null
# ──────────────────────────────────────────────────────────────

class TestNull:
    def setup_method(self):
        self.root = ET.Element("root")

    def test_creates_child_with_null(self):
        elem = _null(self.root, "MyTag")
        assert elem.tag == "MyTag"
        children = list(elem)
        assert len(children) == 1
        assert children[0].tag == "null"

    def test_null_has_no_text(self):
        elem = _null(self.root, "MyTag")
        assert elem.text is None

    def test_appended_to_parent(self):
        _null(self.root, "TagA")
        _null(self.root, "TagB")
        tags = [c.tag for c in self.root]
        assert "TagA" in tags
        assert "TagB" in tags


# ──────────────────────────────────────────────────────────────
# _text
# ──────────────────────────────────────────────────────────────

class TestText:
    def setup_method(self):
        self.root = ET.Element("root")

    def test_with_value(self):
        elem = _text(self.root, "Name", "ACME DOO")
        assert elem.text == "ACME DOO"
        assert len(list(elem)) == 0  # nema null child-a

    def test_empty_string_gives_null(self):
        elem = _text(self.root, "Name", "")
        assert elem.text is None
        children = list(elem)
        assert len(children) == 1
        assert children[0].tag == "null"

    def test_whitespace_only_gives_null(self):
        elem = _text(self.root, "Name", "   ")
        children = list(elem)
        assert len(children) == 1
        assert children[0].tag == "null"

    def test_none_gives_null(self):
        elem = _text(self.root, "Name", None)
        children = list(elem)
        assert len(children) == 1
        assert children[0].tag == "null"


# ──────────────────────────────────────────────────────────────
# _val
# ──────────────────────────────────────────────────────────────

class TestVal:
    def setup_method(self):
        self.root = ET.Element("root")

    def test_with_value(self):
        elem = _val(self.root, "Code", "EUR")
        assert elem.text == "EUR"

    def test_empty_string(self):
        elem = _val(self.root, "Code", "")
        assert elem.text == ""
        assert len(list(elem)) == 0  # nema null — _val ne koristi null

    def test_none_gives_empty(self):
        elem = _val(self.root, "Code", None)
        assert elem.text == ""
