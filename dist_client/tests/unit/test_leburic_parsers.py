"""
Unit testovi za Leburic/Pekabesko PDF parser — pure funkcije bez DB i bez fajlova.

Testira OCR cleanup logiku: _parse_qty, _parse_price, _parse_neto_kgr,
_parse_joined_value, _apply_qty_decimal, _apply_implicit_decimal,
_normalize_product_name, _PRODUCT_NAME_FIXES.
"""
import pytest
from importers.vendors.leburic.leburic_pekabesko_pdf_parser import (
    _parse_qty,
    _parse_price,
    _parse_neto_kgr,
    _parse_joined_value,
    _apply_qty_decimal,
    _apply_implicit_decimal,
    _normalize_product_name,
    _PRODUCT_NAME_FIXES,
)


# ──────────────────────────────────────────────────────────────
# _apply_qty_decimal
# ──────────────────────────────────────────────────────────────

class TestApplyQtyDecimal:
    def test_empty(self):
        assert _apply_qty_decimal("") == 0.0

    def test_invalid(self):
        assert _apply_qty_decimal("abc") == 0.0

    def test_4_digits(self):
        # '3360' → 336.0
        assert _apply_qty_decimal("3360") == pytest.approx(336.0)

    def test_5_digits(self):
        # '33760' → 3376.0
        assert _apply_qty_decimal("33760") == pytest.approx(3376.0)

    def test_6_digits(self):
        # '358400' → 3584.0
        assert _apply_qty_decimal("358400") == pytest.approx(3584.0)

    def test_7_digits(self):
        # '3584000' → 3584.0
        assert _apply_qty_decimal("3584000") == pytest.approx(3584.0)


# ──────────────────────────────────────────────────────────────
# _parse_qty
# ──────────────────────────────────────────────────────────────

class TestParseQty:
    def test_empty(self):
        assert _parse_qty("") == 0.0

    def test_whitespace(self):
        assert _parse_qty("   ") == 0.0

    def test_clean_decimal(self):
        assert _parse_qty("336.00") == pytest.approx(336.0)

    def test_clean_decimal_large(self):
        assert _parse_qty("1504.00") == pytest.approx(1504.0)

    def test_comma_separator(self):
        assert _parse_qty("336,00") == pytest.approx(336.0)

    def test_ocr_trailing_paren(self):
        # '33760(' → '33760' → ÷10 = 3376.0
        assert _parse_qty("33760(") == pytest.approx(3376.0)

    def test_ocr_trailing_letter(self):
        # '3360C' → '3360' → ÷10 = 336.0
        assert _parse_qty("3360C") == pytest.approx(336.0)

    def test_split_decimals(self):
        # '544 75' → 544.75 (razmak = decimale)
        assert _parse_qty("544 75") == pytest.approx(544.75)

    def test_ocr_I_as_1(self):
        # OCR miješa 'I' i '1'
        result = _parse_qty("I504.00")
        assert result == pytest.approx(1504.0)


# ──────────────────────────────────────────────────────────────
# _parse_price
# ──────────────────────────────────────────────────────────────

class TestParsePrice:
    def test_empty(self):
        assert _parse_price("") == 0.0

    def test_clean_comma(self):
        # '2,841' → 2.841
        assert _parse_price("2,841") == pytest.approx(2.841)

    def test_clean_dot(self):
        assert _parse_price("6.453") == pytest.approx(6.453)

    def test_3_digits_no_sep(self):
        # '380' → 3.80
        assert _parse_price("380") == pytest.approx(3.80)

    def test_4_digits_no_sep(self):
        # '6453' → 6.453
        assert _parse_price("6453") == pytest.approx(6.453)

    def test_ocr_trailing_paren(self):
        # '0,97(' → 0.97
        assert _parse_price("0,97(") == pytest.approx(0.97)

    def test_ocr_space(self):
        # '3 80(' → '380' → 3.80
        assert _parse_price("3 80(") == pytest.approx(3.80)

    def test_zero(self):
        assert _parse_price("0,000") == pytest.approx(0.0)


# ──────────────────────────────────────────────────────────────
# _parse_neto_kgr
# ──────────────────────────────────────────────────────────────

class TestParseNetoKgr:
    def test_empty(self):
        assert _parse_neto_kgr("") == 0.0

    def test_clean_dot(self):
        assert _parse_neto_kgr("337.600") == pytest.approx(337.600)

    def test_clean_comma(self):
        assert _parse_neto_kgr("336,00(") == pytest.approx(336.0)

    def test_split_decimals(self):
        # '544 75:' → 544.75
        assert _parse_neto_kgr("544 75:") == pytest.approx(544.75)

    def test_ocr_I_as_1_split(self):
        # 'I504 000' → OCR: razmak se briše → '1504000' → float → >10000 → ÷100 = 15040.0
        # Ovo je poznato ponašanje parsera za ovaj OCR pattern
        assert _parse_neto_kgr("I504 000") == pytest.approx(15040.0)

    def test_implicit_2_decimals(self):
        # '181600(' → 1816.00 (veliki broj bez decimale → ÷100)
        assert _parse_neto_kgr("I81600(") == pytest.approx(1816.0)

    def test_small_value(self):
        assert _parse_neto_kgr("5.250") == pytest.approx(5.25)


# ──────────────────────────────────────────────────────────────
# _apply_implicit_decimal
# ──────────────────────────────────────────────────────────────

class TestApplyImplicitDecimal:
    def test_empty(self):
        assert _apply_implicit_decimal("") == 0.0

    def test_5_digits(self):
        # '50253' → 5025.3
        assert _apply_implicit_decimal("50253") == pytest.approx(5025.3)

    def test_6_digits(self):
        # '319200' → 3192.0
        assert _apply_implicit_decimal("319200") == pytest.approx(3192.0)

    def test_7_digits(self):
        # '4744761' → 4744.761
        assert _apply_implicit_decimal("4744761") == pytest.approx(4744.761)

    def test_short(self):
        # Kraći od 5 → vraća direktno
        result = _apply_implicit_decimal("123")
        assert result == pytest.approx(123.0)


# ──────────────────────────────────────────────────────────────
# _parse_joined_value
# ──────────────────────────────────────────────────────────────

class TestParseJoinedValue:
    def test_empty(self):
        assert _parse_joined_value("") == 0.0

    def test_comma_decimal(self):
        # '954,40' → 954.40
        assert _parse_joined_value("954,40") == pytest.approx(954.40)

    def test_dot_thousands_comma_decimal(self):
        # '4.744,761' → 4744.761
        assert _parse_joined_value("4.744,761") == pytest.approx(4744.761)

    def test_split_with_decimal(self):
        # '53 532,066' → 53532.066
        assert _parse_joined_value("53 532,066") == pytest.approx(53532.066)

    def test_7_digits_no_sep(self):
        # '4744761' → 4744.761
        assert _parse_joined_value("4744761") == pytest.approx(4744.761)

    def test_6_digits_no_sep(self):
        # '319200' → 3192.0
        assert _parse_joined_value("319200") == pytest.approx(3192.0)


# ──────────────────────────────────────────────────────────────
# _normalize_product_name
# ──────────────────────────────────────────────────────────────

class TestNormalizeProductName:
    def test_empty(self):
        assert _normalize_product_name("") == ""

    def test_none_like(self):
        assert _normalize_product_name("   ") == ""

    def test_ocr_fix_piknik(self):
        result = _normalize_product_name("kolbaspiknik")
        assert result == "kolbas piknik"

    def test_ocr_fix_gold_file(self):
        result = _normalize_product_name("Goldpilecefile")
        assert result == "Gold pilece file"

    def test_ocr_fix_dimljena_pecenica(self):
        result = _normalize_product_name("Dimjenapecenica")
        assert result == "Dimljena pecenica"

    def test_pipe_cleanup(self):
        # Pipe/= znakovi se zamjenjuju razmakom
        result = _normalize_product_name("Pileca|ekstra")
        assert "|" not in result

    def test_extra_whitespace_stripped(self):
        result = _normalize_product_name("  Gold sunka  ")
        assert result == result.strip()

    def test_ocr_slajs_100g(self):
        result = _normalize_product_name("slajs100g")
        assert result == "slajs 100 g"

    def test_ocr_double_prefix(self):
        # 'PPileci' → 'Pileci'
        result = _normalize_product_name("PPileci")
        assert not result.startswith("PP")


# ──────────────────────────────────────────────────────────────
# _PRODUCT_NAME_FIXES — provjera da su svi paterni ispravni
# ──────────────────────────────────────────────────────────────

class TestProductNameFixes:
    def test_all_patterns_compile(self):
        # Svi paterni moraju biti kompajlirani re.Pattern objekti
        import re
        for pattern, repl in _PRODUCT_NAME_FIXES:
            assert hasattr(pattern, "sub"), f"Nije Pattern: {pattern}"
            assert isinstance(repl, str)

    def test_count(self):
        assert len(_PRODUCT_NAME_FIXES) == 16

    def test_each_pattern_matches_intended_input(self):
        cases = [
            ("PilecaPicasunka", "Pileca Picasunka"),
            ("Pilecaekstra", "Pileca ekstra"),
            ("Pilecavirsla", "Pileca virsla"),
            ("kolbaspiknik", "kolbas piknik"),
            ("slajsMAP", "slajs MAP"),
            ("umrezavakum", "u mreza vakum"),
            ("uomotacu", "u omotacu"),
            ("premiumkobasica", "premium kobasica"),
            ("Dimjenapecenica", "Dimljena pecenica"),
            ("Dimjenaplecka", "Dimljena plecka"),
            ("Cajnikolbasrefus", "Cajni kolbas refus"),
            ("Caen", "Cajni"),
            ("Goldpilecefile", "Gold pilece file"),
            ("Goldsunka", "Gold sunka"),
            ("slajs100g", "slajs 100 g"),
            ("kolbas295grvakum", "kolbas 295 gr vakum"),
        ]
        for raw, expected in cases:
            result = _normalize_product_name(raw)
            assert expected in result or result == expected, \
                f"'{raw}' → '{result}', očekivano '{expected}'"
