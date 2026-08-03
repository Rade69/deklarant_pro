"""
Karakterizacioni testovi za pravila bojenja Zemlja porijekla / Povlastica.

Ova oblast ima istoriju 6 nezavisnih bugova (vidi memory:
2026-06-07_neutralna-boja-zemlje-bez-povlastice.md i srodne) - svi
otkriveni preko korisnickog screenshot-a, nikad testom. Ovaj fajl
zakljucava tacno binarno pravilo iz te istorije PRIJE ekstrakcije
u ValidationService (Faza 5), da se sprijeci tiha promjena pravila.

Kljucno pravilo (memory, "Krug 3", finalna verzija) - I DALJE VAZI:
✅/zelena (potvrdjena povlastica) prati ISKLJUCIVO da li je povlastica
eksplicitno potvrdjena (povlastica + PE1/PE2/PE3 dokaz) - NIKAD
country_confidence sam po sebi, NIKAD "teorijska podobnost" zemlje kao
DOKAZ potvrde.

IZMJENA 2026-08-02 (korisnicki zahtjev, GUI screenshot): kad povlastica
NIJE potvrdjena, boja vise NIJE jedna flat neutralna nijansa za SVE zemlje
- sada prati STATICKU grupu zemlje (EU/CEFTA/ostale povlascene/nikad
povlascene, vidi ValidationService.country_group_color). Ovo NE krsi
gornje pravilo (grupa je cisto vizuelna kategorizacija po kodu zemlje,
NIJE tvrdnja o potvrdjenoj povlastici, ✅/zelena i dalje idu SAMO uz
stvarni dokaz) - samo precizira KOJU nijansu "nepotvrdjeno" stanje dobija.
CN/TW/BR/US i dalje dobijaju istu (staru neutralnu) boju medjusobno; RS
(CEFTA) i DE (EU) sada dobijaju MEDJUSOBNO RAZLICITE boje od CN i jedne
od drugih, umjesto da sve tri budu identicne kao ranije.
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
    def test_bez_zemlje_vraca_none(self):
        """Nema sta obojiti bez zemlje porijekla - jedini slucaj koji i dalje vraca None."""
        item = _line(zemlja_porijekla="", country_confidence="")
        assert ValidationService.country_confidence_style(item) is None

    def test_bez_country_confidence_ali_sa_zemljom_ipak_boji_po_grupi(self):
        """IZMJENA 2026-08-02: ranije je bez country_confidence CIJELA kolona
        ostajala neobojena (bug prijavljen na Assembly/master-list uvozu, koji
        cesto nema country_confidence popunjen) - sad se boji po grupi zemlje
        cak i bez confidence podatka, jer je grupa staticka cinjenica o kodu
        zemlje, ne zavisi od pouzdanosti detekcije."""
        item = _line(country_confidence="", zemlja_porijekla="DE", povlastica="")
        style = ValidationService.country_confidence_style(item)
        assert style is not None
        assert style["color_hex"] == ValidationService._COUNTRY_GROUP_COLORS["EU"]
        assert style["icon"] == ""

    def test_high_confidence_potvrdjena_povlastica_eur1_zeleno_sa_kvacicom(self):
        item = _line(
            country_confidence="HIGH", zemlja_porijekla="DE",
            povlastica="EUP", eur1_number="EUR1-123",
        )
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == "#d4edda"
        assert style["icon"] == "✅"
        assert not any("nije eksplicitno potvrđena" in t for t in style["tooltip_parts"])

    def test_cefta_zemlja_bez_dokaza_nije_zelena_nego_cefta_grupa(self):
        """Krug 2 i dalje vazi (NE smije biti zelena bez dokaza), ALI od 2026-08-02
        RS (CEFTA) dobija SVOJU (CEFTA) grupnu boju, ne vise istu flat neutralnu
        kao CN — to je bas ono sto je korisnik trazio (razlikovati EU/CEFTA
        potencijalno-podobne zemlje od nikad-podobnih)."""
        item = _line(
            country_confidence="HIGH", zemlja_porijekla="RS",
            povlastica="CEFTAP",  # postavljena samo na osnovu zemlje - weak guess
        )
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == ValidationService._COUNTRY_GROUP_COLORS["CEFTA"]
        assert style["color_hex"] != ValidationService._COUNTRY_CONFIDENCE_COLORS["HIGH"]  # i dalje ne zelena
        assert style["icon"] == ""

    def test_zemlja_bez_povlastice_mogucnosti_ista_neutralna_boja(self):
        """Krug 1: CN (nema mogucnost povlastice, NONE grupa) - NE smije dobiti
        posebnu ikonicu/boju, ostaje na staroj neutralnoj (NONE grupa == stara
        _NEUTRAL_COUNTRY_COLOR vrijednost, nepromijenjeno ponasanje za CN)."""
        item = _line(country_confidence="HIGH", zemlja_porijekla="CN", povlastica="")
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == ValidationService._NEUTRAL_COUNTRY_COLOR
        assert style["icon"] == ""

    def test_medium_confidence_bez_potvrde_i_dalje_ne_zavisi_od_confidence_nivoa(self):
        """Krug 3 i dalje vazi u sustini (boja ne smije zavisiti od NIVOA
        pouzdanosti kad povlastica nije potvrdjena) - RS dobija CEFTA grupnu
        boju kod SVAKOG nivoa confidence (HIGH ili MEDIUM), nikad MEDIUM-
        specificnu zutu boju."""
        item = _line(country_confidence="MEDIUM", zemlja_porijekla="RS", povlastica="")
        style = ValidationService.country_confidence_style(item)
        assert style["color_hex"] == ValidationService._COUNTRY_GROUP_COLORS["CEFTA"]
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
        """Naziv testa i dalje tacno opisuje sta se provjerava - NE zeleno.
        Od 2026-08-02 cell ipak dobija CEFTA grupnu boju (umjesto None) da
        prati Zemlja kolonu — i dalje NIJE zeleno/potvrdjeno."""
        item = _line(
            country_source="MATCH", zemlja_porijekla="RS", povlastica="CEFTAP",
        )
        style = ValidationService.preference_confidence_style(item)
        assert style is not None
        assert style["color_hex"] == ValidationService._COUNTRY_GROUP_COLORS["CEFTA"]
        assert style["color_hex"] != "#d4edda"  # i dalje ne zeleno/potvrdjeno

    def test_povlastica_nepodobna_zemlja_bez_pokusaja_ostaje_none(self):
        """CN (NONE grupa) nema sta da se istakne na Povlastica koloni -
        ostaje None, isti obrazac kao test_pdf_oznaka_bez_povlastice_
        neeligible_zemlja_bez_upozorenja iznad."""
        item = _line(country_source="MATCH", zemlja_porijekla="CN", povlastica="")
        style = ValidationService.preference_confidence_style(item)
        assert style is None
