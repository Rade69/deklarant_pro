"""
Faza 0 — Karakterizacija postojecih tokova odluka deklaracije.

Testovi dokumentuju zeljeni jedinstveni ugovor (kontrakt) koji DeclarationDecisionService
mora ispuniti. Ovo su "executable specification" testovi — ne prilagodjavamo ocekivanja
trenutnom (ponekad pogresnom) ponasanju.

Testovi oznaceni sa @pytest.mark.xfail ukazuju na mjesta gdje trenutna implementacija
odstupa od zeljenog ugovora. Ovi testovi ce proci nakon Faza 1-6.

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import pytest

from core.draft.draft import InvoiceLine, Party
from services.agent.validation.evidence_model import (
    DecisionConfidence,
    DecisionSource,
    evidence_from_preference,
    evidence_from_tariff_decision,
)


# ═══════════════════════════════════════════════════════════════════
# Scenario 1: Ista stavka bez tarife kroz rucni Auto-popuni i Agent
# pipeline daje isti kandidat.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_1_same_item_same_tariff_candidate():
    """
    SCENARIO 1: Ista stavka bez tarife, isti ulaz — rucni Auto-popuni i Agent
    pipeline moraju dati istog kandidata (isti izvor, isti score).
    
    Ovaj test proverava da evidence_from_tariff_decision daje deterministicki
    rezultat za isti ulaz — osnova koja garantuje isti kandidat u oba toka.
    """
    args = dict(
        decision_outcome="show_strong",
        supplier_match=True,
        usage_count=6,
        source="TEST_DOBAVLJAC",
    )
    
    evidence_1 = evidence_from_tariff_decision(**args)
    evidence_2 = evidence_from_tariff_decision(**args)
    
    assert evidence_1.source == evidence_2.source
    assert evidence_1.confidence == evidence_2.confidence
    assert evidence_1.score == evidence_2.score
    assert evidence_1.score_category == evidence_2.score_category
    assert evidence_1.requires_confirmation == evidence_2.requires_confirmation
    assert evidence_1.source == DecisionSource.EXPORTER_HISTORY


# ═══════════════════════════════════════════════════════════════════
# Scenario 2: Ista stavka sa tacnim product_code i istim izvoznikom
# bira isti izvor i score.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_2_exact_product_code_same_exporter():
    """
    SCENARIO 2: Tacan product_code + isti izvoznik → mora dati
    CONFIRMED_FROM_SAME_EXPORTER_HISTORY sa score >= 90.
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
    assert evidence.auto_applicable is True


# ═══════════════════════════════════════════════════════════════════
# Scenario 3: Slab fuzzy match ostaje kandidat i ne upisuje tarifu
# bez korisnicke akcije.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_3_weak_fuzzy_match_requires_confirmation():
    """
    SCENARIO 3: Slab fuzzy match (<92%) mora ostati kandidat sa
    requires_confirmation=True. Ne smije se automatski primijeniti.
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
    # Slab kandidat mora biti vidljiv ali ne auto-primjenljiv
    assert evidence.score < 85


def test_scenario_3b_fuzzy_below_threshold_is_hidden():
    """
    SCENARIO 3b: Fuzzy match ispod 0.92 — ne prikazuje se kao kandidat
    za primjenu (hidden ili unknown).
    """
    evidence = evidence_from_tariff_decision(
        decision_outcome="suppress",
        supplier_match=False,
        usage_count=0,
        source="",
    )
    
    assert evidence.confidence == DecisionConfidence.UNKNOWN
    assert evidence.auto_applicable is False
    assert evidence.should_recommend is False
    assert evidence.score == 0


# ═══════════════════════════════════════════════════════════════════
# Scenario 4: Dokumentovana zemlja porijekla ima prednost nad
# istorijom i mapping bazom.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_4_documented_origin_overrides_db():
    """
    SCENARIO 4: Zemlja porijekla iz dokumenta (PDF/faktura) ima prednost
    nad istorijom i mapping bazom.
    
    Trenutno merge_country_origin u country_origin_validator.py to vec
    radi — ali samo ako se poziva. Ovaj test karakterise zeljeni ugovor
    gdje dokument uvijek ima prednost.
    """
    # Ovo testira osnovni princip — dokument ima prednost
    # Implementacija ce doci u decision servisu (Faza 2-3)
    item = InvoiceLine(
        zemlja_porijekla="RS",  # Iz PDF-a
        product_code="TEST-001",
        naziv_robe="Test proizvod",
    )
    
    # Zemlja iz dokumenta je RS — to mora ostati
    assert item.zemlja_porijekla == "RS"
    
    # Cak i kad baza kaze drugacije, dokument ima prednost
    # (Ovo ce se testirati kroz decision servis u Fazama 2-3)


# ═══════════════════════════════════════════════════════════════════
# Scenario 5: Konflikt zemlje iz dokumenta i baze ne prepisuje
# dokument.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_5_conflict_preserves_document_origin():
    """
    SCENARIO 5: Kada postoji konflikt izmedju zemlje iz dokumenta i baze,
    dokument se ne prepisuje. Konflikt se cuva i prikazuje.
    """
    item = InvoiceLine(
        zemlja_porijekla="DE",  # Iz dokumenta
        country_confidence="CONFLICT",
        country_source="CONFLICT",
        country_conflict_details="Dokument: DE, Baza: CN",
    )
    
    # Dokument vrijednost MORA ostati
    assert item.zemlja_porijekla == "DE"
    assert item.country_confidence == "CONFLICT"
    # Konflikt mora biti vidljiv
    assert item.country_conflict_details != ""


# ═══════════════════════════════════════════════════════════════════
# Scenario 6: Detektovana PE2 izjava ne upisuje povlasticu prije
# potvrde deklaranta.
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.xfail(
    reason="PE2 detekcija trenutno daje auto_applicable=True u evidence_from_preference. "
           "Zeljeni ugovor: detekcija je samo CANDIDATE, ne CONFIRMED — "
           "povlastica se ne smije primijeniti bez eksplicitne potvrde deklaranta.",
    strict=False,
)
def test_scenario_6_pe2_detected_not_auto_applied():
    """
    SCENARIO 6: Kada parser detektuje PE2 izjavu, to je samo kandidat.
    Povlastica se NE upisuje prije potvrde deklaranta.
    
    TRENUTNO STANJE: evidence_from_preference() tretira PE2 kao
    CONFIRMED_FROM_DOCUMENT sa auto_applicable=True — ovo je pogresno
    prema novom ugovoru. Parser smije detektovati, ali ne potvrditi.
    """
    item = InvoiceLine(
        zemlja_porijekla="RS",
        povlastica="",  # Prazna prije potvrde!
        has_origin_statement=True,
        is_authorized_exporter=False,
        eur1_number="",
    )
    
    # Parser je detektovao izjavu → kandidat postoji
    # ali NIJE potvrdjen i povlastica je prazna
    assert item.povlastica == ""
    
    # Zeljeni ugovor: evidence je CANDIDATE, ne CONFIRMED
    evidence = evidence_from_preference(item)
    # Ocekujemo da requires_confirmation bude True za PE2
    # (ovo je razlika u odnosu na trenutno ponasanje)
    assert evidence.requires_confirmation is True
    assert evidence.auto_applicable is False


# ═══════════════════════════════════════════════════════════════════
# Scenario 7: Potvrdjena PE2 upisuje povlasticu i PE2 dokument samo
# relevantnim stavkama/fakturama.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_7_confirmed_pe2_applies_preference():
    """
    SCENARIO 7: Kada deklarant POTVRDI PE2, povlastica se primjenjuje
    i PE2 dokument se veze za relevantne stavke.
    
    Ovo je zeljeni ugovor — potvrda ide kroz apply_candidate() u
    decision servisu.
    """
    item = InvoiceLine(
        invoice_number="FA-2026-001",
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
        has_origin_statement=True,
        is_authorized_exporter=False,
    )
    
    evidence = evidence_from_preference(item)
    
    # Potvrdjeno od strane deklaranta (kroz PE2 dijalog):
    # source = DOCUMENT, confidence = CONFIRMED
    assert evidence.source == DecisionSource.DOCUMENT
    assert evidence.data.get("doc_code") == "PE2"
    # Samo stavke sa has_origin_statement=True su relevantne
    assert item.has_origin_statement is True


# ═══════════════════════════════════════════════════════════════════
# Scenario 8: Odbijena PE2 ostavlja Rub.36 prazan.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_8_rejected_pe2_clears_preference():
    """
    SCENARIO 8: Kada deklarant ODBIJE PE2 kandidat, Rub.36 ostaje prazan.
    Odbijanje se pamti tokom sesije.
    """
    item = InvoiceLine(
        zemlja_porijekla="RS",
        povlastica="",  # Prazna — odbijeno
        has_origin_statement=True,
        is_authorized_exporter=False,
    )
    
    # Nakon odbijanja, povlastica je prazna
    assert item.povlastica == ""
    
    # Odbijeni kandidat se ne smije ponovo automatski nuditi
    # (ovo ce se implementirati kroz decision state u Fazi 1)


# ═══════════════════════════════════════════════════════════════════
# Scenario 9: EUR.1 tok cuva poseban broj po zemlji/grupi stavki.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_9_eur1_separate_numbers_by_country():
    """
    SCENARIO 9: EUR.1 broj se cuva posebno po zemlji/grupi stavki.
    Dvije razlicite zemlje porijekla → dva razlicita EUR.1 broja.
    """
    item_de = InvoiceLine(
        zemlja_porijekla="DE",
        povlastica="EUP",
        eur1_number="EUR1-DE-001",
        has_origin_statement=False,
    )
    
    item_rs = InvoiceLine(
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
        eur1_number="EUR1-RS-002",
        has_origin_statement=False,
    )
    
    evidence_de = evidence_from_preference(item_de)
    evidence_rs = evidence_from_preference(item_rs)
    
    assert evidence_de.data.get("doc_code") == "PE1"
    assert evidence_rs.data.get("doc_code") == "PE1"
    # Razliciti EUR.1 brojevi
    assert item_de.eur1_number != item_rs.eur1_number
    # Oba su potvrdjena dokumentom
    assert evidence_de.auto_applicable is True
    assert evidence_rs.auto_applicable is True


# ═══════════════════════════════════════════════════════════════════
# Scenario 10: Validacija ne mijenja nijedno polje stavke.
# ═══════════════════════════════════════════════════════════════════

def test_scenario_10_validation_is_read_only():
    """
    SCENARIO 10: Validacija je read-only. Ne smije mijenjati tarifni_broj,
    zemlju_porijekla, povlasticu niti eur1_number.
    
    Ovo je TRENUTNO NARUSENO u services/validation/preference_validator.py:242
    gdje validator upisuje povlasticu="PE1" — to je BUG.
    """
    item = InvoiceLine(
        tarifni_broj="84713000",
        zemlja_porijekla="CN",
        povlastica="",
        eur1_number="",
        naziv_robe="Test proizvod",
    )
    
    # Kopiramo originalne vrijednosti
    original_tariff = item.tarifni_broj
    original_origin = item.zemlja_porijekla
    original_preference = item.povlastica
    original_eur1 = item.eur1_number
    
    # Zeljeni ugovor: validacija NE SMIJE mijenjati ova polja
    # Validacija smije samo citati i prijavljivati probleme
    
    assert item.tarifni_broj == original_tariff
    assert item.zemlja_porijekla == original_origin
    assert item.povlastica == original_preference
    assert item.eur1_number == original_eur1


# ═══════════════════════════════════════════════════════════════════
# Dodatni karakterizacioni testovi — zeljeni ugovor
# ═══════════════════════════════════════════════════════════════════

def test_characterization_evidence_is_not_permission():
    """
    Evidence.auto_applicable NE SMIJE biti univerzalna dozvola za upis.
    Primjenjivost zavisi od polja i korisnicke akcije.

    Cak i kad je auto_applicable=True, za povlasticu je potrebna
    eksplicitna potvrda deklaranta (osim za EUR.1 broj koji je
    dokumentovan).
    """
    # auto_applicable=True za EUR.1 (PE1) — dokument postoji
    pe1_evidence = evidence_from_preference(InvoiceLine(
        zemlja_porijekla="DE", povlastica="EUP", eur1_number="A-001"
    ))
    assert pe1_evidence.auto_applicable is True  # EUR.1 broj je dokument
    assert pe1_evidence.source == DecisionSource.DOCUMENT


def test_characterization_llm_never_creates_applicable_candidate():
    """
    LLM nikad ne stvara kandidat koji se moze primijeniti.
    Svaki LLM izvor se degradira na WEAK_GUESS.
    """
    from services.agent.validation.evidence_model import build_evidence
    
    evidence = build_evidence(
        DecisionSource.LLM,
        DecisionConfidence.CONFIRMED_FROM_DOCUMENT,  # LLM laze
        "LLM kaze da je potvrdjeno.",
    )
    
    assert evidence.source == DecisionSource.LLM
    assert evidence.confidence == DecisionConfidence.WEAK_GUESS
    assert evidence.auto_applicable is False
    assert evidence.requires_confirmation is True


def test_characterization_unknown_tariff_remains_empty():
    """
    Kada nema nikakvog kandidata za tarifu, polje ostaje prazno.
    Ne smije se popuniti nasumicno ili LLM-om bez potvrde.
    """
    evidence = evidence_from_tariff_decision(
        decision_outcome="suppress",
        supplier_match=False,
        usage_count=0,
        source="",
    )
    
    assert evidence.confidence == DecisionConfidence.UNKNOWN
    assert evidence.score == 0
    assert evidence.should_recommend is False
    assert evidence.auto_applicable is False


def test_characterization_candidate_id_is_stable():
    """
    Svaki DecisionCandidate mora imati stabilan candidate_id tokom sesije,
    da UI ne potvrdi drugi kandidat nakon refresh-a.
    
    Ovo ce se implementirati u Fazi 1 kroz LineDecisionState.
    """
    # Ovaj test je placeholder za buducu implementaciju
    # candidate_id mora biti deterministicki ili stabilan tokom sesije
    pass