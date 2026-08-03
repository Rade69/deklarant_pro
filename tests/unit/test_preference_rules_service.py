"""
Testovi za services/faktura/preference_rules_service.py.

country_preference_group() dodata 2026-08-02 (korisnicki zahtjev: bojenje
Zemlja/Povlastica kolone po GRUPI zemlje - EU/CEFTA/ostale-povlascene/
nikad-povlascene - umjesto jedne flat neutralne boje za sve). Testovi za
suggest_preference_by_country() su REGRESIONI - EU_COUNTRIES/CEFTA_COUNTRIES
su promovisani iz lokalnih varijabli u modul-nivo konstante (dijeljene sa
country_preference_group), ovo potvrdjuje da refaktor nije promijenio
postojece ponasanje.
"""
from services.faktura.preference_rules_service import (
    country_preference_group,
    suggest_preference_by_country,
    EU_COUNTRIES,
    CEFTA_COUNTRIES,
    OTHER_PREFERENTIAL_COUNTRIES,
)


class TestCountryPreferenceGroup:
    def test_eu_zemlja_vraca_eu(self):
        assert country_preference_group("DE") == "EU"
        assert country_preference_group("IT") == "EU"

    def test_cefta_zemlja_vraca_cefta(self):
        assert country_preference_group("RS") == "CEFTA"
        assert country_preference_group("BA") == "CEFTA"

    def test_tr_ir_vracaju_other_pref(self):
        assert country_preference_group("TR") == "OTHER_PREF"
        assert country_preference_group("IR") == "OTHER_PREF"

    def test_nikad_povlascena_zemlja_vraca_none(self):
        assert country_preference_group("CN") == "NONE"
        assert country_preference_group("TW") == "NONE"
        assert country_preference_group("BR") == "NONE"
        assert country_preference_group("US") == "NONE"

    def test_prazan_kod_vraca_none(self):
        assert country_preference_group("") == "NONE"
        assert country_preference_group(None) == "NONE"

    def test_case_insensitive(self):
        assert country_preference_group("de") == "EU"
        assert country_preference_group("rs") == "CEFTA"

    def test_grupe_se_ne_preklapaju(self):
        assert EU_COUNTRIES.isdisjoint(CEFTA_COUNTRIES)
        assert EU_COUNTRIES.isdisjoint(OTHER_PREFERENTIAL_COUNTRIES)
        assert CEFTA_COUNTRIES.isdisjoint(OTHER_PREFERENTIAL_COUNTRIES)


class TestSuggestPreferenceByCountryRegresija:
    """Regresija nakon promocije eu_countries/cefta_countries u modul konstante."""

    def test_eu_zemlja_vraca_eup(self):
        assert suggest_preference_by_country("DE") == "EUP"

    def test_cefta_zemlja_vraca_ceftap(self):
        assert suggest_preference_by_country("RS") == "CEFTAP"

    def test_turska_vraca_trp(self):
        assert suggest_preference_by_country("TR") == "TRP"

    def test_iran_vraca_irp(self):
        assert suggest_preference_by_country("IR") == "IRP"

    def test_nepovlascena_zemlja_vraca_prazno(self):
        assert suggest_preference_by_country("CN") == ""
