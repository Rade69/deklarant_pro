"""
Karakterizacioni testovi za konsolidaciju _parse_number duplikata (importers/).

Vidi docs/importers/IMPORTERS_BUG_REPORT.md preporuka #1 i
agent_reports/2026-08-04_importers-parse-number-konsolidacija.md.

Grupa A (identična kanonskoj parse_eu_number): blagic_loren, imamoglu
Grupa B (identična jedna drugoj, permisivnija od kanonske): packing_list, invoice_improved
Grupa C (identična jedna drugoj, heuristika za dvosmislene brojeve): generic_pdf_importer,
    cmana (generička), pip_food
Bugfix: sumaprom (vraćao 0.0 za brojeve sa hiljadarskim separatorom),
    leburic (gubio predznak, pogrešno računao brojeve sa oba separatora)
"""

from importers.invoice_line_utils import parse_eu_number
from importers.vendors.blagic.blagic_loren_pdf_parser import _parse_number as blagic_loren_parse
from importers.vendors.imamoglu.imamoglu_pdf_parser import _parse_number as imamoglu_parse
from importers.packing_list_parser import _parse_number as packing_list_parse
from importers.invoice_improved_parser import _parse_number as invoice_improved_parse
from importers.generic_pdf_importer import _parse_number as generic_parse
from importers.vendors.cmana.cmana_pdf_parser import _parse_number as cmana_generic_parse
from importers.vendors.cmana.cmana_pdf_parser import _parse_number_cmana as cmana_specific_parse
from importers.vendors.pip_food.pip_food_parser import _parse_number as pip_food_parse
from importers.vendors.sumaprom.sumaprom_pdf_parser import _parse_number as sumaprom_parse
from importers.vendors.leburic.leburic_pekabesko_importer import _parse_number as leburic_parse


GROUP_A_CASES = [
    ("1.234,56", 1234.56),
    ("1,234.56", 1234.56),
    ("1234,56", 1234.56),
    ("1234.56", 1234.56),
    ("1,234", 1.234),
    ("1.234", 1.234),
    ("12,5", 12.5),
    ("638.500", 638.5),
    ("346,316", 346.316),
    ("1 234,56", 1234.56),
    ("", 0.0),
    ("0", 0.0),
]


class TestGroupA_IdenticalToCanonical:
    """blagic_loren i imamoglu su dokazano identicni parse_eu_number-u."""

    def test_blagic_loren_matches_canonical(self):
        for raw, expected in GROUP_A_CASES:
            assert blagic_loren_parse(raw) == parse_eu_number(raw) == expected, raw

    def test_imamoglu_matches_canonical(self):
        for raw, expected in GROUP_A_CASES:
            assert imamoglu_parse(raw) == parse_eu_number(raw) == expected, raw


GROUP_B_CASES = [
    ("1.234,56", 1234.56),
    ("1,234.56", 1234.56),
    ("1234,56", 1234.56),
    ("1234.56", 1234.56),
    ("1,234", 1.234),
    ("1.234", 1.234),
    ("€1.234,56", 1234.56),
    ("", 0.0),
]


class TestGroupB_PermissiveDuo:
    """packing_list_parser i invoice_improved_parser su dokazano medjusobno identicni."""

    def test_packing_list_matches_invoice_improved(self):
        for raw, expected in GROUP_B_CASES:
            assert packing_list_parse(raw) == invoice_improved_parse(raw) == expected, raw


GROUP_C_CASES = [
    ("1.234,56", 1234.56),
    ("1,234.56", 1234.56),
    ("1234,56", 1234.56),
    ("1234.56", 1234.56),
    ("1,234", 1234.0),   # heuristika: 3 cifre iza zareza = hiljade
    ("1.234", 1234.0),   # heuristika: 3 cifre iza tacke = hiljade
    ("12,5", 12.5),
    ("638.500", 638500.0),
    ("346,316", 346316.0),
    ("€1.234,56", 1234.56),
    ("", 0.0),
]


class TestGroupC_ThousandsHeuristicTrio:
    """generic_pdf_importer, cmana (genericka) i pip_food su dokazano medjusobno identicni."""

    def test_generic_matches_cmana_generic(self):
        for raw, expected in GROUP_C_CASES:
            assert generic_parse(raw) == cmana_generic_parse(raw) == expected, raw

    def test_generic_matches_pip_food(self):
        for raw, expected in GROUP_C_CASES:
            assert generic_parse(raw) == pip_food_parse(raw) == expected, raw


class TestCmanaSpecific_NamjernoNetaknuto:
    """cmana_specific pretpostavlja SAMO evropski format - namjerno drugacije, ne dirati."""

    def test_cmana_specific_assumes_european_only(self):
        # I dalje vazi nakon konsolidacije - ovo NIJE bug, vec vendor-tuning
        assert cmana_specific_parse("12.379,71") == 12379.71
        assert cmana_specific_parse("346,316") == 346.316


class TestSumapromBugfix:
    """Prije fix-a: vracao 0.0 za brojeve sa hiljadarskim separatorom."""

    def test_sumaprom_now_handles_thousands_separator(self):
        assert sumaprom_parse("1.234,56") == 1234.56
        assert sumaprom_parse("1,234.56") == 1234.56
        assert sumaprom_parse("1 234,56") == 1234.56

    def test_sumaprom_still_handles_simple_decimal(self):
        assert sumaprom_parse("1234,56") == 1234.56
        assert sumaprom_parse("1234.56") == 1234.56


class TestLeburicBugfix:
    """Prije fix-a: gubio predznak na negativnim, pogresno racunao sa oba separatora."""

    def test_leburic_preserves_negative_sign(self):
        assert leburic_parse("-12,50") == -12.5

    def test_leburic_handles_both_separators_correctly(self):
        assert leburic_parse("1.234,56") == 1234.56
        assert leburic_parse("1,234.56") == 1234.56

    def test_leburic_still_handles_int_float_passthrough(self):
        assert leburic_parse(12.5) == 12.5
        assert leburic_parse(1234) == 1234.0

    def test_leburic_still_handles_none(self):
        assert leburic_parse(None) == 0.0

    def test_leburic_still_handles_simple_comma_decimal(self):
        assert leburic_parse("12,5") == 12.5
