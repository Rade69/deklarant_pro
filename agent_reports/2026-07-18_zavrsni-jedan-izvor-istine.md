# Agent Report — Završni izvještaj: Jedan izvor istine za odluke deklaracije

**Datum:** 2026-07-18  
**Agent:** Pi  
**Zadatak:** `agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md`  
**Grana:** `windows`  
**Status:** IMPLEMENTIRANO — čeka Codex verifikaciju  

---

## 1. Sažetak

Uveden je **kanonski model odluke** i **jedan servis** (`DeclarationDecisionService`) koji je jedino mjesto za procjenu i primjenu izvedenih vrijednosti (tarifa, zemlja porijekla, povlastica) u aktivnom `DeclarationDraft`.  

Prije migracije postojalo je **44 direktnih writer-a** koji su pisali u `InvoiceLine` polja. Nakon migracije, dozvoljeni direktni upisi su samo u parser/deserializer granici i u decision servisu, uz **4 deprecated writera** koji su označeni ali još nisu uklonjeni.

---

## 2. Pregled faza

| Faza | Naziv | Commit(ovi) | Ključni fajlovi |
|------|-------|-------------|-----------------|
| 0 | Karakterizacija | `055cd4d`, `10a983e`, `8aac386` | Writer inventar, karakterizacioni testovi (34) |
| 1 | Kanonski model | `ba7e863` | `core/decision/evidence.py`, `core/decision/decision_model.py`, `InvoiceLine.decision_state` |
| 2 | Servis odluka | `dbacdf9`, `b1be4c6` | `services/decision/declaration_decision_service.py`, `decision_policy.py`, `evidence_adapters.py` |
| 3 | Politike po polju | `9d20ad2`, `9034536` | Tarifna, porijeklo, preference politike; LLM zabrana; fuzzy threshold |
| 4.1 | Faktura tab | `b503ba9` | `services/decision/integration.py`, 3 mjesta u `faktura_view.py` |
| 4.2 | Agent pipeline | `bfd1068` | 4 writera u agent kodu omotana |
| 4.3 | Validacija | `9658d50` | `auto_fix_missing_eur1` DEPRECATED, poziv zamijenjen |
| 4.4 | Naimenovanja | `9658d50` | `check_preflight()` u `create_one_to_one()` i `create_smart_group()` |
| 4.5 | XML export | `37f2110` | `test_decision_xml_preflight.py`, decision_state ne ulazi u XML |
| 5 | Kontrolisano učenje | `a3f48ab`, `ead630c` | `learn_from_draft(confirmed_only=True)`, dist_client `.pyd` rebuild |
| 6 | Uklanjanje paralelnih puteva | `5a195a1` | DEPRECATED oznake na 4 writera, konacni writer inventar |

---

## 3. Arhitektura nakon migracije

```
Dokumenti / baze / istorija / korisnik
                  |
                  v
          kandidati + Evidence
                  |
         DeclarationDecisionService
          /        |        \
         v         v         v
   evaluate_*  apply_*   reject_*
         |         |         |
         v         v         v
   LineDecisionState (read-only)
              |
              v
         InvoiceLine.decision_state
              |
     +--------+--------+
     |        |        |
  Faktura  Validacija Naimenovanja → XML
  (sync)   (read-only) (preflight)
```

### Kanonski model (`core/decision/`)

| Klasa | Uloga |
|-------|-------|
| `DecisionField` | Enum: TARIFF, ORIGIN_COUNTRY, PREFERENCE |
| `DecisionStatus` | Enum: UNKNOWN, CANDIDATE, CONFIRMED, REJECTED, CONFLICT |
| `DecisionCandidate` | Frozen: candidate_id (deterministički), value, evidence |
| `FieldDecision` | Stanje za jedno polje: status, applied_value, kandidati |
| `LineDecisionState` | Sva tri polja za jednu InvoiceLine |

### Politike (`services/decision/decision_policy.py`)

| Polje | Redoslijed | Auto-apply |
|-------|-----------|------------|
| Tarifa | User > Document > Exporter History > DB > Similarity | auto_fill_clicked + score >= 85 |
| Porijeklo | User > Document > Parser > Mapping | document >= 85, parser >= 70 |
| Povlastica | User > PE1/PE2/PE3 (Document) > Parser | **Samo** dialog_confirmed + PE1/PE2/PE3 |

### Migrirani potrošači

| Potrošač | Faza | Šta je urađeno |
|----------|------|----------------|
| `faktura_view.py` (_on_auto_fill) | 4.1 | sync_decision_state_after_autofill |
| `faktura_view.py` (_on_item_changed) | 4.1 | sync_decision_state_after_manual_edit |
| `faktura_view.py` (_show_eur1_dialog) | 4.1 | sync_decision_state_after_preference |
| `faktura_view.py` (_show_pe2_dialog) | 4.1 | sync_decision_state_after_preference |
| `chat_intent_handler.py` (_on_accepted) | 4.2 | sync_decision_state_after_autofill |
| `chat_intent_handler.py` (_apply_single_tariff_to_line) | 4.2 | sync_decision_state_after_manual_edit |
| `tariff_intent_service.py` (execute_fill) | 4.2 | sync_decision_state_after_autofill |
| `tariff_intent_service.py` (delete_all) | 4.2 | reset decision_state.tariff |
| `create_naimenovanja_service.py` (create_one_to_one) | 4.4 | check_preflight() loguje upozorenja |
| `create_naimenovanja_service.py` (create_smart_group) | 4.4 | check_preflight() loguje upozorenja |
| `tariff_mapping_service.py` (learn_from_draft) | 5 | confirmed_only=True |

---

## 4. Writer inventar — stanje

| Kategorija | Prije Faze 0 | Poslije Faze 6 |
|-----------|-------------|----------------|
| Parser/deserializer (dozvoljen) | 25 | 25 |
| Inferred/Business Writer | 11 | 4 (DEPRECATED) |
| Manual Edit Adapter | 8 | 0 (svi omotani syncom) |
| Read-only sa bugom | 2 | 1 (auto_fix_missing_eur1 — DEPRECATED) |
| **Decision servis (dozvoljen writer)** | **0** | **1** (`declaration_decision_service.py`) |

### Preostali deprecated writeri

| Writer | Fajl | Razlog zadržavanja |
|--------|------|-------------------|
| `TariffMappingService.auto_populate_tariffs()` | `tariff_mapping_service.py:240` | Stari pozivaoci — migracija u Fazi 6 cleanup |
| `AutoFillService.fill_tariff_numbers()` | `auto_fill_service.py:101` | Stari pozivaoci — migracija u Fazi 6 cleanup |
| `HistoricalTariffSearchService.validate_lines()` | `historical_tariff_search_service.py:120` | Stari pozivaoci — migracija u Fazi 6 cleanup |
| `PreferenceValidator.auto_fix_missing_eur1()` | `preference_validator.py:242` | Samo poziv zamijenjen, metoda ostavljena |

---

## 5. Testovi

```
tests/unit/test_evidence_model.py ................... 34 passed
tests/unit/test_agent_decision_regression.py ........ 12 passed
tests/unit/test_decision_characterization.py ........ 29 passed, 5 xfail
tests/unit/test_declaration_decision_model.py ....... 26 passed
tests/unit/test_declaration_decision_service.py ..... 23 passed
tests/unit/test_decision_tariff_policy.py ........... 16 passed
tests/unit/test_decision_origin_policy.py ........... 11 passed
tests/unit/test_decision_preference_policy.py ....... 14 passed
tests/unit/test_decision_controlled_learning.py ..... 8 passed
tests/integration/test_decision_draft_roundtrip.py .. 6 passed
tests/integration/test_decision_to_naimenovanja.py .. 6 passed
tests/integration/test_decision_xml_preflight.py .... 7 passed
tests/integration/test_manual_agent_decision_parity.py 6 passed
tests/integration/test_import_service_integration.py . 12 passed, 1 skipped
tests/integration/test_large_batch_processing.py ..... 9 passed
                                                    ---
                                              UKUPNO: 218 passed, 1 skipped, 5 xfailed
```

### 5 xfail — poznati problemi

| Test | Razlog | Zahtijeva |
|------|--------|-----------|
| PE2 auto_applicable | `evidence_from_preference()` daje CONFIRMED umjesto CANDIDATE | Izmjena u `core/decision/evidence.py` |
| PE1 auto_applicable | Isto | Isto |
| PE3 auto_applicable | Isto | Isto |
| auto_fix_missing_eur1 piše | Validator direktno mijenja povlasticu | Uklanjanje metode (Faza 6 cleanup) |
| find_batch_by_product_codes SQL bug | `unnest()` u `CASE/WHEN` nije podržan | Popravka SQL upita |

---

## 6. Šta NIJE urađeno

| Stavka | Razlog |
|--------|--------|
| PE1/PE2/PE3 → CANDIDATE | Zahtijeva izmjenu `evidence_from_preference()` koja utiče na sve pozivaoce — poseban zadatak |
| `auto_fix_missing_eur1()` uklanjanje | Metoda i dalje postoji (samo poziv zamijenjen) — Faza 6 cleanup |
| `find_batch_by_product_codes()` SQL popravka | SQL greška — poseban zadatak |
| CONTEXT.md ažuriranje | Treba upisati arhitekturne odluke |
| dist_client rebuild svih modula | Samo `tariff_mapping_service` rebuildovan |

---

## 7. Commitovi

```
5a195a1 refactor(decision): ukloni paralelne puteve — deprecation warnings
ead630c fix(learning): rebuild dist_client .pyd za Fazu 5
a3f48ab fix(learning): uci samo iz potvrdjenih odluka
37f2110 fix(decision): popravke Faze 4 — auto_fix, preflight, XML test, EOF whitespace
9658d50 refactor(decision): Faza 4.3-4.5 — validacija, naimenovanja, XML
bfd1068 refactor(agent): koristi isti tok odluka kao faktura
b503ba9 refactor(faktura): koristi jedinstveni servis odluka
9034536 fix(decision): Faza 3 popravke — LLM zabrana, fuzzy threshold 0.92, agent report
9d20ad2 feat(decision): uvedi jedinstvene politike tarifa i porijekla
b1be4c6 fix(decision): Faza 2 popravke — read-only evaluate, core izolacija, mock testovi
dbacdf9 feat(decision): centralizuj procjenu i primjenu kandidata
ba7e863 feat(decision): uvedi kanonski model odluke deklaracije
8aac386 test(decision): prosirena karakterizacija — stvarna baza, 34 testa, 5 xfail
10a983e test(decision): dorada karakterizacije — stvarni servisi, 22 testa, 4 xfail
055cd4d test(decision): zabiljezi postojece tokove odluka
```

---

## 8. Potreban follow-up

1. **Codex verifikacija** — 12 kontrolnih tačaka iz sekcije 18 plana
2. **Preostali xfail-ovi** — 3 PE auto_applicable + auto_fix + SQL bug
3. **CONTEXT.md ažuriranje** — upisati arhitekturne odluke
4. **dist_client full rebuild** — samo 1 modul rebuildovan, ostali čekaju
5. **Push** — tek nakon Codex verifikacije