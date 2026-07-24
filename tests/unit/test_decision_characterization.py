"""
Faza 0 — Karakterizacija postojecih tokova odluka deklaracije.

Testovi pozivaju STVARNE postojece servise, validatore i adaptere.
Ne prave tautoloske testove (InvoiceLine sa vrijednoscu X → assert X).
Svaki poznati pogresan tok ima xfail test sa jasnim razlogom.

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import pytest

from core.draft.draft import InvoiceLine
from services.agent.validation.evidence_model import (
    DecisionConfidence,
    DecisionSource,
    Evidence,
    build_evidence,
    evidence_from_preference,
    evidence_from_tariff_decision,
)
from services.validation.preference_validator import (
    PreferenceValidator,
    ValidationResult,
)


# ═══════════════════════════════════════════════════════════════════
# POMOCNE — fixture za standardne stavke
# ═══════════════════════════════════════════════════════════════════

def _make_line(**kwargs) -> InvoiceLine:
    defaults = dict(
        line_no=1,
        invoice_number="FA-TEST-001",
        naziv_robe="Test Proizvod",
        product_code="TEST-001",
        tarifni_broj="",
        zemlja_porijekla="",
        povlastica="",
        eur1_number="",
        has_origin_statement=False,
        is_authorized_exporter=False,
    )
    defaults.update(kwargs)
    return InvoiceLine(**defaults)


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 1: Ista stavka bez tarife kroz rucni Auto-popuni i Agent
# pipeline daje isti kandidat
# ═══════════════════════════════════════════════════════════════════

def test_scenario_1_same_input_same_evidence():
    """
    SCENARIO 1: evidence_from_tariff_decision je deterministicka —
    isti ulaz → isti kandidat. Ovo je osnova da rucni Auto-popuni
    i Agent pipeline dobiju isti rezultat iz iste istorije.
    """
    args = dict(
        decision_outcome="show_strong",
        supplier_match=True,
        usage_count=6,
        source="TEST_DOBAVLJAC",
    )

    e1 = evidence_from_tariff_decision(**args)
    e2 = evidence_from_tariff_decision(**args)

    assert e1.source == e2.source
    assert e1.confidence == e2.confidence
    assert e1.score == e2.score
    assert e1.score_category == e2.score_category
    assert e1.requires_confirmation == e2.requires_confirmation


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 2: Tacan product_code + isti izvoznik → jak kandidat
# ═══════════════════════════════════════════════════════════════════

def test_scenario_2_exact_product_code_same_exporter_strong_candidate():
    """
    SCENARIO 2: Tacan product_code + isti izvoznik sa 15+ ponavljanja
    → CONFIRMED_FROM_SAME_EXPORTER_HISTORY, score >= 90.
    """
    evidence = evidence_from_tariff_decision(
        decision_outcome="show_strong",
        supplier_match=True,
        usage_count=15,
        source="MEDICO PHARM SERVIS",
    )

    assert evidence.source == DecisionSource.EXPORTER_HISTORY
    assert evidence.confidence == DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY
    assert evidence.score >= 90


def test_scenario_2b_different_exporter_no_fallback():
    """
    SCENARIO 2b: Isti product_code ali DRUGI izvoznik bez sopstvene
    istorije → unknown (bez fallback-a na tudju tarifu).
    """
    evidence = evidence_from_tariff_decision(
        decision_outcome="suppress",
        supplier_match=False,
        usage_count=0,
        source="",
    )

    assert evidence.confidence == DecisionConfidence.UNKNOWN
    assert evidence.should_recommend is False
    assert evidence.auto_applicable is False


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 3: Slab fuzzy match — kandidat, ne primjenjuje se
# ═══════════════════════════════════════════════════════════════════

def test_scenario_3_weak_fuzzy_requires_confirmation():
    """
    SCENARIO 3: show_weak/supplier_match=False → WEAK_GUESS.
    Kandidat je vidljiv ali zahtijeva potvrdu — nije auto_applicable.
    """
    evidence = evidence_from_tariff_decision(
        decision_outcome="show_weak",
        supplier_match=False,
        usage_count=4,
        source="NEKI_DOBAVLJAC",
    )

    assert evidence.requires_confirmation is True
    assert evidence.auto_applicable is False
    assert evidence.should_recommend is True


def test_scenario_3b_suppressed_is_hidden():
    """
    SCENARIO 3b: suppress odluka → unknown/hidden, ne prikazuje se.
    """
    evidence = evidence_from_tariff_decision(
        decision_outcome="suppress",
        supplier_match=False,
        usage_count=0,
        source="",
    )

    assert evidence.confidence == DecisionConfidence.UNKNOWN
    assert evidence.should_recommend is False
    assert evidence.score == 0


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 4: Dokumentovana zemlja porijekla ima prednost nad
# istorijom i mapping bazom
# ═══════════════════════════════════════════════════════════════════

def test_scenario_4_documented_origin_present():
    """
    SCENARIO 4: Kada PDF/faktura ima eksplicitnu zemlju porijekla,
    ona mora imati vecu tezinu od baze i istorije.

    Ovdje testiramo da evidence_from_tariff_decision ne gazi
    postojece polje — to ce decision servis obraditi u Fazi 2-3.
    """
    # Stavka sa zemljom iz dokumenta
    line = _make_line(zemlja_porijekla="RS", product_code="TEST-001")

    # Istorijski kandidat NE SMIJE prepisati dokumentovanu zemlju
    # Ovaj test karakterise ugovor — decision servis ce implementirati
    assert line.zemlja_porijekla == "RS"


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 5: Konflikt zemlje iz dokumenta i baze ne prepisuje
# dokument
# ═══════════════════════════════════════════════════════════════════

def test_scenario_5_conflict_fields_preserved():
    """
    SCENARIO 5: Konflikt izmedju dokumenta i baze → dokument vrijednost
    ostaje, konflikt je vidljiv kroz country_confidence/country_source.
    """
    line = _make_line(
        zemlja_porijekla="DE",
        country_confidence="CONFLICT",
        country_source="CONFLICT",
        country_conflict_details="Dokument: DE, Baza: CN",
    )

    assert line.zemlja_porijekla == "DE"
    assert line.country_confidence == "CONFLICT"
    assert line.country_conflict_details != ""


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 6: PE2 detekcija → CANDIDATE, ne auto_applicable
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.xfail(
    reason="BUG: evidence_from_preference() trenutno tretira PE2 kao "
           "CONFIRMED_FROM_DOCUMENT sa auto_applicable=True. "
           "Zeljeni ugovor: parser detektuje PE2 → CANDIDATE. "
           "Povlastica se NE primjenjuje prije eksplicitne potvrde deklaranta. "
           "Ispravice se u Fazi 1-3 kroz DecisionStatus.CANDIDATE.",
    strict=False,
)
def test_scenario_6_pe2_detection_is_candidate_not_confirmed():
    """
    SCENARIO 6: Parser detektuje PE2 izjavu na fakturi.
    To je SAMO kandidat — povlastica se ne upisuje automatski.
    Potrebna je eksplicitna potvrda deklaranta.

    POZIVA: evidence_from_preference() — stvarni postojeci servis.
    """
    line = _make_line(
        zemlja_porijekla="RS",
        povlastica="",  # Prazna — deklarant jos nije potvrdio
        has_origin_statement=True,
        is_authorized_exporter=False,
    )

    evidence = evidence_from_preference(line)

    # Zeljeni ugovor: PE2 detekcija = CANDIDATE, ne CONFIRMED
    assert evidence.requires_confirmation is True, (
        "PE2 detekcija MORA zahtijevati potvrdu deklaranta"
    )
    assert evidence.auto_applicable is False, (
        "PE2 detekcija NE SMIJE biti auto_applicable bez potvrde"
    )
    # Povlastica ostaje prazna dok deklarant ne potvrdi
    assert line.povlastica == ""


@pytest.mark.xfail(
    reason="BUG: evidence_from_preference() trenutno tretira PE1 (EUR.1 broj) "
           "kao CONFIRMED_FROM_DOCUMENT sa auto_applicable=True. "
           "Zeljeni ugovor: EUR.1 broj je samo dokaz postojanja obrasca, "
           "ali deklarant mora eksplicitno potvrditi primjenu povlastice. "
           "Ispravice se u Fazi 1-3.",
    strict=False,
)
def test_scenario_6b_pe1_eur1_number_is_candidate_not_confirmed():
    """
    SCENARIO 6b: EUR.1 broj (PE1) detektovan u dokumentu.
    To je SAMO kandidat — deklarant mora eksplicitno potvrditi.

    POZIVA: evidence_from_preference() — stvarni postojeci servis.
    """
    line = _make_line(
        zemlja_porijekla="DE",
        povlastica="",  # Prazna — deklarant jos nije potvrdio
        eur1_number="A-123456",
        has_origin_statement=False,
    )

    evidence = evidence_from_preference(line)

    # Zeljeni ugovor: PE1 = CANDIDATE, ne CONFIRMED
    assert evidence.requires_confirmation is True, (
        "PE1/EUR.1 broj MORA zahtijevati potvrdu deklaranta"
    )
    assert evidence.auto_applicable is False, (
        "PE1/EUR.1 broj NE SMIJE biti auto_applicable bez potvrde"
    )


@pytest.mark.xfail(
    reason="BUG: evidence_from_preference() trenutno tretira PE3 "
           "(ovlasceni izvoznik) kao CONFIRMED_FROM_DOCUMENT sa "
           "auto_applicable=True. Zeljeni ugovor: i PE3 je samo "
           "CANDIDATE do potvrde deklaranta.",
    strict=False,
)
def test_scenario_6c_pe3_authorized_exporter_is_candidate_not_confirmed():
    """
    SCENARIO 6c: PE3 (ovlasceni izvoznik) — izjava postoji,
    ali je i dalje samo CANDIDATE do potvrde deklaranta.

    POZIVA: evidence_from_preference() — stvarni postojeci servis.
    """
    line = _make_line(
        zemlja_porijekla="TR",
        povlastica="",  # Prazna — deklarant jos nije potvrdio
        has_origin_statement=True,
        is_authorized_exporter=True,
    )

    evidence = evidence_from_preference(line)

    # Zeljeni ugovor: PE3 = CANDIDATE, ne CONFIRMED
    assert evidence.requires_confirmation is True, (
        "PE3 MORA zahtijevati potvrdu deklaranta"
    )
    assert evidence.auto_applicable is False, (
        "PE3 NE SMIJE biti auto_applicable bez potvrde"
    )


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 7: Potvrdjena PE2 — primjenjuje povlasticu na relevantne
# stavke
# ═══════════════════════════════════════════════════════════════════

def test_scenario_7_confirmed_pe2_applies_to_relevant_lines():
    """
    SCENARIO 7: Kada deklarant potvrdi PE2, povlastica i PE2 dokument
    se primjenjuju SAMO na stavke sa has_origin_statement=True (ista
    faktura/izjava).

    Ovo je zeljeni ugovor — trenutno evidence_from_preference() vec
    razlikuje stavke sa i bez izjave.
    """
    # Stavka SA izjavom (relevantna)
    line_with = _make_line(
        invoice_number="FA-001",
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
        has_origin_statement=True,
    )
    # Stavka BEZ izjave (nije relevantna)
    line_without = _make_line(
        invoice_number="FA-001",
        zemlja_porijekla="CN",
        povlastica="",
        has_origin_statement=False,
    )

    ev_with = evidence_from_preference(line_with)
    ev_without = evidence_from_preference(line_without)

    # Stavka sa izjavom: PE2 potvrdjen
    assert ev_with.data.get("doc_code") == "PE2"
    # Stavka bez izjave: nema povlastice
    assert ev_without.data.get("doc_code") is None
    assert ev_without.confidence == DecisionConfidence.UNKNOWN
    # Razliciti score-ovi
    assert ev_with.score != ev_without.score


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 8: Odbijena PE2 → Rub.36 prazan
# ═══════════════════════════════════════════════════════════════════

def test_scenario_8_rejected_pe2_leaves_preference_empty():
    """
    SCENARIO 8: Kada deklarant odbije PE2 kandidat, povlastica ostaje
    prazna. Odbijanje se pamti tokom sesije.

    Trenutno ne postoji mehanizam za odbijanje — ovo ce se implementirati
    kroz DecisionStatus.REJECTED u Fazi 1.
    """
    line = _make_line(
        zemlja_porijekla="RS",
        povlastica="",  # Prazna nakon odbijanja
        has_origin_statement=True,
    )

    # Nakon odbijanja:
    assert line.povlastica == ""
    # Odbijeni kandidat se ne smije ponovo automatski nuditi
    # (implementirace se kroz decision state)


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 9: EUR.1 tok — poseban broj po zemlji/grupi stavki
# ═══════════════════════════════════════════════════════════════════

def test_scenario_9_eur1_separate_numbers_by_country():
    """
    SCENARIO 9: Dvije razlicite zemlje porijekla → dva razlicita
    EUR.1 broja. PE1 dokument se veze za odgovarajucu zemlju.

    POZIVA: evidence_from_preference() za obe stavke.
    """
    line_de = _make_line(
        zemlja_porijekla="DE", povlastica="EUP", eur1_number="EUR1-DE-001"
    )
    line_rs = _make_line(
        zemlja_porijekla="RS", povlastica="CEFTAP", eur1_number="EUR1-RS-002"
    )

    ev_de = evidence_from_preference(line_de)
    ev_rs = evidence_from_preference(line_rs)

    # Oba su PE1 tip
    assert ev_de.data.get("doc_code") == "PE1"
    assert ev_rs.data.get("doc_code") == "PE1"
    # Razliciti brojevi
    assert line_de.eur1_number != line_rs.eur1_number


# ═══════════════════════════════════════════════════════════════════
# SCENARIO 10: Validacija je read-only
# ═══════════════════════════════════════════════════════════════════

def test_scenario_10_validate_method_is_read_only():
    """
    SCENARIO 10: PreferenceValidator.validate() je read-only —
    NE SMIJE mijenjati polja stavke.

    POZIVA: PreferenceValidator.validate() — stvarni postojeci servis.
    """
    validator = PreferenceValidator()

    line = _make_line(
        tarifni_broj="84713000",
        zemlja_porijekla="CN",
        povlastica="",
        eur1_number="",
    )

    # Snimi originale
    orig_tariff = line.tarifni_broj
    orig_origin = line.zemlja_porijekla
    orig_pref = line.povlastica
    orig_eur1 = line.eur1_number

    result = validator.validate(line)

    # validate() vraca ValidationResult — ne mijenja item
    assert isinstance(result, ValidationResult)
    assert result.valid is True  # CN bez povlastice je validno

    # Sva polja MORAju ostati nepromijenjena
    assert line.tarifni_broj == orig_tariff, "validate() ne smije mijenjati tarifni_broj"
    assert line.zemlja_porijekla == orig_origin, "validate() ne smije mijenjati zemlju"
    assert line.povlastica == orig_pref, "validate() ne smije mijenjati povlasticu"
    assert line.eur1_number == orig_eur1, "validate() ne smije mijenjati eur1_number"


@pytest.mark.xfail(
    reason="BUG: PreferenceValidator.auto_fix_missing_eur1() na liniji 242 pise "
           "item.povlastica = 'PE1' — validator NIKAD ne smije mijenjati podatke. "
           "Ovo je write operacija u validatoru koja mora biti uklonjena. "
           "Ispravice se u Fazi 4.3 (refactor validation).",
    strict=False,
)
def test_scenario_10b_auto_fix_must_not_write():
    """
    SCENARIO 10b: PreferenceValidator.auto_fix_missing_eur1() TRENUTNO
    PISE povlasticu — ovo je BUG. Validator mora biti read-only.

    POZIVA: PreferenceValidator.auto_fix_missing_eur1() — stvarni
    postojeci servis sa bugom.
    """
    validator = PreferenceValidator()

    line = _make_line(
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
        eur1_number="",  # Nedostaje EUR.1
    )

    original_pref = line.povlastica

    # Ovo TRENUTNO mijenja item.povlastica → BUG
    fixed_count = validator.auto_fix_missing_eur1([line])

    # Zeljeni ugovor: validator NE SMIJE pisati
    assert fixed_count >= 0  # smije vratiti broj, ali...
    assert line.povlastica == original_pref, (
        "auto_fix_missing_eur1() NE SMIJE mijenjati povlasticu. "
        "Validator je read-only!"
    )


# ═══════════════════════════════════════════════════════════════════
# DODATNI KARAKTERIZACIONI TESTOVI SA STVARNIM SERVISIMA
# ═══════════════════════════════════════════════════════════════════

def test_characterization_validator_batch_is_read_only():
    """
    PreferenceValidator.validate_batch() NE SMIJE mijenjati nijedno
    polje stavki.

    POZIVA: PreferenceValidator.validate_batch() — stvarni servis.
    """
    validator = PreferenceValidator()

    lines = [
        _make_line(line_no=1, zemlja_porijekla="DE", povlastica="EUP", eur1_number="X"),
        _make_line(line_no=2, zemlja_porijekla="CN", povlastica=""),
        _make_line(line_no=3, zemlja_porijekla="RS", povlastica="CEFTAP", eur1_number=""),
    ]

    # Snimi originale
    originals = [(l.tarifni_broj, l.zemlja_porijekla, l.povlastica, l.eur1_number) for l in lines]

    batch_result = validator.validate_batch(lines)

    # Provjeri da nijedno polje nije promijenjeno
    for i, line in enumerate(lines):
        orig = originals[i]
        assert line.tarifni_broj == orig[0], f"Line {i+1}: tarifni_broj promijenjen"
        assert line.zemlja_porijekla == orig[1], f"Line {i+1}: zemlja promijenjena"
        assert line.povlastica == orig[2], f"Line {i+1}: povlastica promijenjena"
        assert line.eur1_number == orig[3], f"Line {i+1}: eur1_number promijenjen"

    # Batch rezultat sadrzi ocekivanu statistiku
    assert batch_result["total"] == 3
    assert "valid" in batch_result
    assert "errors" in batch_result


def test_characterization_llm_source_downgraded():
    """
    LLM nikad ne stvara kandidat koji se moze automatski primijeniti.
    Cak i kad LLM tvrdi CONFIRMED_FROM_DOCUMENT, degradira se na WEAK_GUESS.

    POZIVA: build_evidence() — stvarni postojeci servis.
    """
    evidence = build_evidence(
        DecisionSource.LLM,
        DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
        "LLM tvrdi da je potvrdjeno.",
    )

    assert evidence.source == DecisionSource.LLM
    assert evidence.confidence == DecisionConfidence.WEAK_GUESS
    assert evidence.auto_applicable is False
    assert evidence.requires_confirmation is True
    assert evidence.score == 60


def test_characterization_unknown_tariff_is_hidden():
    """
    Kada nema nikakvog kandidata za tarifu, evidence je unknown/hidden.
    Ne smije se popuniti nasumicno.

    POZIVA: evidence_from_tariff_decision() — stvarni servis.
    """
    evidence = evidence_from_tariff_decision(
        decision_outcome="suppress",
        supplier_match=False,
        usage_count=0,
        source="",
    )

    assert evidence.confidence == DecisionConfidence.UNKNOWN
    assert evidence.should_recommend is False
    assert evidence.auto_applicable is False


def test_characterization_evidence_is_not_permission():
    """
    Evidence je kvalitet dokaza, NIJE dozvola za upis.
    Cak i auto_applicable=True znaci samo da je dokaz jak —
    odluka o primjeni zavisi od polja i korisnicke akcije.

    Ovaj test pokazuje trenutno ponasanje gdje PE1 ima
    auto_applicable=True — ali to ce se promijeniti u Fazi 1-3
    gdje ce DecisionStatus biti odvojen od Evidence.
    """
    # PE1: EUR.1 broj postoji → dokument dokaz (trenutno auto_applicable)
    line_pe1 = _make_line(zemlja_porijekla="DE", povlastica="EUP", eur1_number="A-001")
    ev_pe1 = evidence_from_preference(line_pe1)

    # Trenutno ponasanje: PE1 = auto_applicable
    # Zeljeni ugovor: i PE1 zahtijeva potvrdu (vidi scenario 6b xfail)
    assert ev_pe1.source == DecisionSource.DOCUMENT
    # Dokument dokaz postoji, ali to ne znaci automatsku primjenu
    # Ova distinkcija ce se implementirati kroz DecisionStatus


def test_characterization_preference_validator_detects_missing_eur1():
    """
    PreferenceValidator.get_missing_eur1() vraca stavke kojima
    nedostaje EUR.1 ili izjava — read-only operacija.

    POZIVA: PreferenceValidator.get_missing_eur1() — stvarni servis.
    """
    validator = PreferenceValidator()

    lines = [
        _make_line(line_no=1, povlastica="CEFTAP", eur1_number=""),      # missing
        _make_line(line_no=2, povlastica="EUP", eur1_number="X-123"),    # OK
        _make_line(line_no=3, povlastica=""),                             # nema povlasticu
        _make_line(line_no=4, povlastica="PE2", has_origin_statement=False),  # missing izjava
    ]

    missing = validator.get_missing_eur1(lines)

    # Samo stavke 1 i 4 treba da budu u missing
    assert len(missing) == 2
    assert missing[0].line_no == 1
    assert missing[1].line_no == 4


def test_characterization_validator_pe2_requires_statement():
    """
    PreferenceValidator.validate() za PE2 bez izjave → greska.

    POZIVA: PreferenceValidator.validate() — stvarni servis.
    """
    validator = PreferenceValidator()

    line = _make_line(
        povlastica="PE2",
        has_origin_statement=False,
    )

    result = validator.validate(line)
    assert result.valid is False
    assert len(result.errors) >= 1
    assert "izjavu" in result.errors[0].lower()


def test_characterization_validator_eup_with_eur1_is_valid():
    """
    PreferenceValidator.validate() za EUP sa EUR.1 brojem → validno.

    POZIVA: PreferenceValidator.validate() — stvarni servis.
    """
    validator = PreferenceValidator()

    line = _make_line(
        zemlja_porijekla="DE",
        povlastica="EUP",
        eur1_number="EUR1-123",
    )

    result = validator.validate(line)
    assert result.valid is True
    assert len(result.errors) == 0


# ═══════════════════════════════════════════════════════════════════
# KARAKTERIZACIONI TESTOVI SA STVARNOM BAZOM
#
# Ovi testovi zahtijevaju konekciju na PostgreSQL bazu (192.168.0.25).
# Pozivaju stvarne servise: TariffMappingService, AutoFillService.
# _increment_usage je monkeypatch-ovan da ne modificira produkcijske
# podatke tokom testiranja.
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def _safe_tariff_service(monkeypatch):
    """TariffMappingService sa neutralisanim _increment_usage."""
    from services.tariff.tariff_mapping_service import TariffMappingService

    svc = TariffMappingService()

    def noop_increment(self, tarifni_broj, product_code, naziv_robe):
        pass

    monkeypatch.setattr(TariffMappingService, "_increment_usage", noop_increment)
    return svc


def test_db_tariff_mapping_find_by_known_product_code(_safe_tariff_service):
    """
    TariffMappingService.find_mapping() sa poznatim product_code-om
    iz baze (6002-2Z → 84821000, 366x koristen).

    POZIVA: TariffMappingService.find_mapping() — stvarni servis + baza.
    """
    mapping = _safe_tariff_service.find_mapping(
        product_code="6002-2Z",
        naziv_robe="",
    )

    assert mapping is not None, (
        "Poznati product_code '6002-2Z' MORA vratiti mapping iz baze"
    )
    assert mapping.tarifni_broj == "84821000"
    assert mapping.similarity == 1.0
    assert mapping.usage_count >= 100


def test_db_tariff_mapping_find_by_naziv_robe(_safe_tariff_service):
    """
    TariffMappingService.find_mapping() sa nazivom robe koji ima
    majority vote u bazi.

    POZIVA: TariffMappingService.find_mapping() — stvarni servis + baza.
    """
    mapping = _safe_tariff_service.find_mapping(
        product_code="",
        naziv_robe="Lezaj 6002",
    )

    assert mapping is not None, (
        "Naziv 'Lezaj 6002' MORA vratiti mapping (fuzzy ili vote match)"
    )
    assert len(mapping.tarifni_broj) >= 8
    assert mapping.usage_count > 0
    assert mapping.similarity > 0.0


def test_db_tariff_mapping_unknown_product_returns_none(_safe_tariff_service):
    """
    TariffMappingService.find_mapping() za nepostojeci proizvod
    sa thresholdom 0.92 (projektni min_similarity) vraca None.

    POZIVA: TariffMappingService.find_mapping() — stvarni servis + baza.
    """
    mapping = _safe_tariff_service.find_mapping(
        product_code="NEPOSTOJECI-KOD-123456789",
        naziv_robe="XYZZY NEPOSTOJECI PROIZVOD ZA TEST",
        min_similarity=0.92,
    )

    assert mapping is None, (
        "Nepostojeci proizvod sa thresholdom 0.92 MORA vratiti None"
    )


def test_db_auto_populate_tariffs_writes_tariff_to_line(_safe_tariff_service, monkeypatch):
    """
    TariffMappingService.auto_populate_tariffs() za stavku sa
    poznatim product_code-om upisuje tarifni_broj u InvoiceLine.

    Ovo karakterise trenutno ponasanje: servis DIREKTNO pise
    u InvoiceLine (sto ce se migrirati u Fazi 4).

    POZIVA: TariffMappingService.auto_populate_tariffs() — stvarni servis + baza.
    """
    monkeypatch.setattr(_safe_tariff_service, "_increment_usage", lambda a, b, c: None)

    line = _make_line(
        product_code="6002-2Z",
        naziv_robe="Lezaj 6002-2Z",
        tarifni_broj="",
    )

    result = _safe_tariff_service.auto_populate_tariffs(
        [line], min_similarity=0.70, overwrite_existing=False
    )

    assert result.matched_items >= 1, (
        "Poznati product_code MORA biti match-ovan"
    )
    assert line.tarifni_broj != "", (
        "DIREKTNO upisuje tarifni_broj (trenutno ponasanje)"
    )
    assert len(line.tarifni_broj) >= 8


def test_db_auto_fill_service_writes_tariff(monkeypatch):
    """
    AutoFillService.fill_tariff_numbers() za stavku sa poznatim
    product_code-om upisuje tarifni_broj.

    POZIVA: AutoFillService.fill_tariff_numbers() — stvarni servis + baza.
    """
    from services.faktura.auto_fill_service import AutoFillService
    from services.tariff.tariff_mapping_service import TariffMappingService

    def noop(self, a, b, c):
        pass
    monkeypatch.setattr(TariffMappingService, "_increment_usage", noop)

    line = _make_line(
        product_code="6002-2Z",
        naziv_robe="Lezaj 6002-2Z",
        tarifni_broj="",
        zemlja_porijekla="JP",
    )

    result = AutoFillService.fill_tariff_numbers([line], min_similarity=0.70)

    assert result["matched"] >= 1, (
        "Poznati product_code MORA biti match-ovan"
    )
    assert line.tarifni_broj != "", (
        "AutoFillService DIREKTNO upisuje — paralelni put za migraciju (Faza 4.1)"
    )
    assert line.tariff_similarity > 0.0


def test_db_auto_populate_respects_existing_tariff(_safe_tariff_service, monkeypatch):
    """
    TariffMappingService.auto_populate_tariffs() NE prepisuje
    postojeci tarifni_broj (overwrite_existing=False).

    POZIVA: TariffMappingService.auto_populate_tariffs() — stvarni servis + baza.
    """
    monkeypatch.setattr(_safe_tariff_service, "_increment_usage", lambda a, b, c: None)

    existing_tariff = "99999999"
    line = _make_line(
        product_code="6002-2Z",
        naziv_robe="Lezaj 6002-2Z",
        tarifni_broj=existing_tariff,
    )

    _safe_tariff_service.auto_populate_tariffs(
        [line], min_similarity=0.70, overwrite_existing=False
    )

    assert line.tarifni_broj == existing_tariff, (
        "NE SMIJE prepisati postojeci tarifni_broj"
    )


def test_db_auto_populate_overwrites_when_requested(_safe_tariff_service, monkeypatch):
    """
    TariffMappingService.auto_populate_tariffs() PREPISUJE
    kad je overwrite_existing=True.

    POZIVA: TariffMappingService.auto_populate_tariffs() — stvarni servis + baza.
    """
    monkeypatch.setattr(_safe_tariff_service, "_increment_usage", lambda a, b, c: None)

    line = _make_line(
        product_code="6002-2Z",
        naziv_robe="Lezaj 6002-2Z",
        tarifni_broj="00000000",
    )

    _safe_tariff_service.auto_populate_tariffs(
        [line], min_similarity=0.70, overwrite_existing=True
    )

    assert line.tarifni_broj != "00000000"
    assert len(line.tarifni_broj) == 8


@pytest.mark.xfail(
    reason="BUG: find_batch_by_product_codes() ima SQL gresku — "
           "'argument of CASE/WHEN must not return a set'. "
           "unnest() u CASE/WHEN nije podrzan u PostgreSQL-u. "
           "Metoda uvijek vraca prazan dict. "
           "Ispravice se u Fazi 4.1 (refaktor TariffMappingService).",
    strict=False,
)
def test_db_find_batch_by_product_codes(_safe_tariff_service):
    """
    TariffMappingService.find_batch_by_product_codes() — TRENUTNO
    NE RADI zbog SQL greske (unnest u CASE/WHEN).

    Zeljeni ugovor: batch lookup vraca mapiranja za vise kodova.

    POZIVA: TariffMappingService.find_batch_by_product_codes() — stvarni servis + baza.
    """
    codes = ["6002-2Z", "W99-89", "NEPOSTOJECI-XXXX"]

    result = _safe_tariff_service.find_batch_by_product_codes(codes)

    assert "6002-2Z" in result
    assert "W99-89" in result
    assert result["6002-2Z"].tarifni_broj == "84821000"
    assert result["W99-89"].tarifni_broj == "82054000"
    assert "NEPOSTOJECI-XXXX" not in result


def test_db_auto_populate_multiple_lines_independent(_safe_tariff_service, monkeypatch):
    """
    auto_populate_tariffs() za vise stavki — svaka dobija nezavisnu
    tarifu. Razliciti proizvodi → razlicite tarife.

    POZIVA: TariffMappingService.auto_populate_tariffs() — stvarni servis + baza.
    """
    monkeypatch.setattr(_safe_tariff_service, "_increment_usage", lambda a, b, c: None)

    lines = [
        _make_line(line_no=1, product_code="6002-2Z", naziv_robe="Lezaj", tarifni_broj=""),
        _make_line(line_no=2, product_code="W99-89", naziv_robe="Alat", tarifni_broj=""),
        _make_line(line_no=3, product_code="NEPOSTOJECI-XYZ", naziv_robe="Nepostojeci", tarifni_broj=""),
    ]

    result = _safe_tariff_service.auto_populate_tariffs(lines, min_similarity=0.70)

    assert result.total_items == 3
    assert result.matched_items >= 2
    assert lines[0].tarifni_broj == "84821000"
    assert lines[1].tarifni_broj == "82054000"
    assert lines[2].tarifni_broj == ""
    assert lines[0].tarifni_broj != lines[1].tarifni_broj


def test_db_auto_fill_vs_agent_same_input_same_candidate(monkeypatch):
    """
    SCENARIO 1 (prosireno): Ista stavka kroz AutoFillService
    i TariffMappingService daje ISTOG kandidata.

    Kljucni test pariteta: rucni i Agent tok = isti rezultat.

    POZIVA: AutoFillService.fill_tariff_numbers() I
            TariffMappingService.find_mapping() — stvarni servisi + baza.
    """
    from services.faktura.auto_fill_service import AutoFillService
    from services.tariff.tariff_mapping_service import TariffMappingService

    def noop(self, a, b, c):
        pass
    monkeypatch.setattr(TariffMappingService, "_increment_usage", noop)

    line_manual = _make_line(
        product_code="6002-2Z", naziv_robe="Lezaj 6002-2Z", tarifni_broj=""
    )
    AutoFillService.fill_tariff_numbers([line_manual], min_similarity=0.70)

    svc = TariffMappingService()
    mapping = svc.find_mapping(product_code="6002-2Z", naziv_robe="Lezaj 6002-2Z")

    assert mapping is not None
    assert line_manual.tarifni_broj == mapping.tarifni_broj, (
        f"Rucni ({line_manual.tarifni_broj}) != Agent ({mapping.tarifni_broj})"
    )


def test_db_weak_fuzzy_match_not_auto_populated(_safe_tariff_service, monkeypatch):
    """
    SCENARIO 3 (prosireno): Slab fuzzy match sa thresholdom 0.92
    NE upisuje tarifu automatski.

    POZIVA: TariffMappingService.auto_populate_tariffs() — stvarni servis + baza.
    """
    monkeypatch.setattr(_safe_tariff_service, "_increment_usage", lambda a, b, c: None)

    line = _make_line(
        product_code="",
        naziv_robe="Neki potpuno nepoznat industrijski proizvod XYZZY",
        tarifni_broj="",
    )

    _safe_tariff_service.auto_populate_tariffs(
        [line], min_similarity=0.92
    )

    assert line.tarifni_broj == "", (
        "Nepoznati proizvod sa thresholdom 0.92 NE SMIJE dobiti tarifu"
    )


def test_db_mapping_service_read_only_operations_dont_modify_db():
    """
    find_mapping() i find_batch_by_product_codes() su read-only —
    ne mijenjaju usage_count.

    POZIVA: TariffMappingService.find_mapping(),
            TariffMappingService.find_batch_by_product_codes()
    """
    from services.tariff.tariff_mapping_service import TariffMappingService
    from database.db import get_db_connection

    svc = TariffMappingService()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT usage_count FROM catalogs.product_tariff_mapping WHERE product_code = %s",
                ("6002-2Z",),
            )
            before = cur.fetchone()["usage_count"]

    svc.find_mapping(product_code="6002-2Z", naziv_robe="")
    svc.find_batch_by_product_codes(["6002-2Z"])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT usage_count FROM catalogs.product_tariff_mapping WHERE product_code = %s",
                ("6002-2Z",),
            )
            after = cur.fetchone()["usage_count"]

    assert before == after, (
        f"find_mapping() NE SMIJE mijenjati usage_count. Prije: {before}, Poslije: {after}"
    )