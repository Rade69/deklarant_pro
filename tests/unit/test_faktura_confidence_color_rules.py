"""
Karakterizacioni testovi za pravila bojenja Zemlja porijekla / Povlastica.

Ova oblast ima istoriju 6 nezavisnih bugova (vidi memory:
2026-06-07_neutralna-boja-zemlje-bez-povlastice.md i srodne) - svi
otkriveni preko korisnickog screenshot-a, nikad testom. Ovaj fajl
zakljucava tacno binarno pravilo iz te istorije PRIJE ekstrakcije
u ValidationService (Faza 5), da se sprijeci tiha promjena pravila.

Kljucno pravilo (memory, "Krug 3", finalna verzija):
Boja/ikonica na koloni Zemlja porijekla prati ISKLJUCIVO da li je
povlastica eksplicitno potvrdjena (povlastica + PE1/PE2/PE3 dokaz) -
NIKAD country_confidence, NIKAD "teorijska podobnost" zemlje.
"""
from core.draft import InvoiceLine
from services.faktura.validation_service import ValidationService


def _line(**kwargs) -> InvoiceLine:
    defaults = dict(
        line_no=1, tarifni_broj="08052190", naziv_robe="Test",
        zemlja_porijekla="", povlastica="", bruto_kg=1.0, neto_kg=1.0,
        iznos=1.0, kolicina=1, jm="kom",
    )
    defaults.update(kwargs)
    return InvoiceLine(**defaults)


class TestCountryConfidenceStyle:
    def test_bez_country_confidence_vraca_none(self):
        item = _line(country_confidence="")
        assert ValidationService.country_confidence_style(item) is None

    def test_high_confidence_potvrdjena_povlastica_eur1_zeleno_sa_kvacicom(self):
        item = _line(
            country_confidence="HIGH", zemlja_porijekla="DE",
            povlastica="EUP", eur1_number="EUR1-123",
        )
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == "#d4edda"
        assert style["icon"] == "✅"
        assert not any("nije eksplicitno potvrđena" in t for t in style["tooltip_parts"])

    def test_cefta_zemlja_bez_dokaza_je_neutralna_ne_zelena(self):
        """Krug 2: teorijska podobnost (RS=CEFTA) BEZ dokaza NE smije biti zelena."""
        item = _line(
            country_confidence="HIGH", zemlja_porijekla="RS",
            povlastica="CEFTAP",  # postavljena samo na osnovu zemlje - weak guess
        )
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == ValidationService._NEUTRAL_COUNTRY_COLOR
        assert style["icon"] == ""

    def test_zemlja_bez_povlastice_mogucnosti_ista_neutralna_boja(self):
        """Krug 1: CN (nema mogucnost povlastice) - NE smije dobiti posebnu ikonicu/boju."""
        item = _line(country_confidence="HIGH", zemlja_porijekla="CN", povlastica="")
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == ValidationService._NEUTRAL_COUNTRY_COLOR
        assert style["icon"] == ""

    def test_medium_confidence_bez_potvrde_i_dalje_neutralna_ne_medium_boja(self):
        """Krug 3: neutralna boja mora vazit za SVE nivoe confidence, ne samo HIGH."""
        item = _line(country_confidence="MEDIUM", zemlja_porijekla="RS", povlastica="")
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == ValidationService._NEUTRAL_COUNTRY_COLOR
        assert style["color_hex"] != ValidationService._COUNTRY_CONFIDENCE_COLORS["MEDIUM"]

    def test_conflict_confidence_tooltip_sadrzi_detalje(self):
        item = _line(
            country_confidence="CONFLICT", zemlja_porijekla="DE",
            country_conflict_details="PDF=DE, baza=FR",
        )
        style = ValidationService.country_confidence_style(item)
        assert any("PDF=DE, baza=FR" in t for t in style["tooltip_parts"])


class TestPreferenceConfidenceStyle:
    def test_pdf_oznaka_bez_povlastice_eligible_zemlja_zuto(self):
        item = _line(
            country_source="PDF_OZNAKA", zemlja_porijekla="RS", povlastica="",
        )
        style = ValidationService.preference_confidence_style(item)
        assert style is not None
        assert style["color_hex"] == "#fff3cd"

    def test_pdf_oznaka_bez_povlastice_neeligible_zemlja_bez_upozorenja(self):
        """CN nikad nece imati povlasticu - upozorenje 'provjerite rucno' je besmisleno."""
        item = _line(
            country_source="PDF_OZNAKA", zemlja_porijekla="CN", povlastica="",
        )
        style = ValidationService.preference_confidence_style(item)
        assert style is None

    def test_potvrdjena_povlastica_eur1_zeleno(self):
        item = _line(
            zemlja_porijekla="DE", povlastica="EUP", eur1_number="EUR1-1",
        )
        style = ValidationService.preference_confidence_style(item)
        assert style is not None
        assert style["color_hex"] == "#d4edda"

    def test_povlastica_bez_dokaza_ne_dobija_zeleno(self):
        item = _line(
            country_source="MATCH", zemlja_porijekla="RS", povlastica="CEFTAP",
        )
        style = ValidationService.preference_confidence_style(item)
        assert style is None
