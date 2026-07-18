# Agent Report — Faza 4: Migracija potrošača na jedinstveni servis odluka

**Datum:** 2026-07-18
**Agent:** Pi
**Scope:** `services/decision/integration.py`, `gui/tabs/faktura_view.py`, integration testovi
**Commit:** `b503ba9` (4.1) + popravke

---

## Šta je urađeno

### 4.1 Faktura tab — migracija (dovršeno)

**Integracioni sloj** (`services/decision/integration.py`):
- `sync_decision_state_after_autofill()` — sinhronizacija nakon auto-popune tarifa
- `sync_decision_state_after_preference()` — sinhronizacija nakon EUR.1/PE2 dijaloga
- `sync_decision_state_after_manual_edit()` — sinhronizacija nakon ručne izmjene u tabeli
- `sync_all_lines_after_draft_restore()` — sinhronizacija nakon restore-a drafta
- `evaluate_line_for_display()` — evaluacija za UI prikaz (badge boje, labele)

**Greške se više ne gutaju** — sve `except Exception` sada loguju kroz `logger.warning(..., exc_info=True)`.

**FakturaView integracija:**
- `_on_auto_fill`: poziva `sync_decision_state_after_autofill()` nakon uspješnog popunjavanja
- `_item_changed`: poziva `sync_decision_state_after_manual_edit()` za kolone tarife (4), zemlje (9) i povlastice (10)
- `_show_eur1_dialog`: poziva `sync_decision_state_after_preference()` za svaku liniju sa povlasticom
- `_show_pe2_dialog`: poziva `sync_decision_state_after_preference()` za svaku liniju sa povlasticom

**Pristup:** Wrapping — postojeći kod **nije diran**. `decision_state` se ažurira kao paralelni sloj uz postojeće ponašanje.

### Integration testovi (novi)

| Test fajl | Broj | Opis |
|-----------|------|------|
| `tests/integration/test_manual_agent_decision_parity.py` | 6 | Paritet ručnog i Agent toka, idempotentnost, preference bez dijaloga |
| `tests/integration/test_decision_draft_roundtrip.py` | 6 | Serializacija/deserijalizacija decision_state kroz from_any(), JSON, legacy dict |
| `tests/integration/test_decision_to_naimenovanja.py` | 6 | CONFIRMED vs CANDIDATE provjera, all_confirmed flag, grouping key |

---

## Šta NIJE urađeno (prelazi u naredne iteracije)

| Podfaza | Status | Razlog |
|---------|--------|--------|
| 4.2 Agent pipeline | ✅ MIGRIRAN | `chat_intent_handler.py` (2 writera) + `tariff_intent_service.py` (2 writera) — svi omotani decision syncom |
| 4.3 Validacija | ✅ MIGRIRAN | `auto_fix_missing_eur1()` zamijenjen direktnim pozivom `DeclarationDecisionService.confirm_manual_value()` u FakturaView; metoda oznacena DEPRECATED |
| 4.4 Naimenovanja | ✅ MIGRIRAN | `check_preflight()` dodat i povezan u `create_one_to_one()` i `create_smart_group()` — loguje upozorenja prije kreiranja |
| 4.5 XML export | ✅ TESTIRAN | Decision_state metadata NE ulazi u XML po dizajnu; XML preflight test (6 testova) dodan; preflight provjera se oslanja na `check_preflight()` iz CreateNaimenovanjaService |
| Uklanjanje direktnih writera | ❌ Nije urađeno | 11 inferred writera i dalje direktno pišu u `InvoiceLine` (biće omotani u Fazi 6) |

---

## Preostali direktni writeri (inventar)

Ovi writeri JOŠ NISU omotani decision servisom:

| Writer | Fajl | Prioritet | Status |
|--------|------|-----------|--------|
| `AutoFillService.fill_tariff_numbers()` | `services/faktura/auto_fill_service.py:96-112` | HIGH | ❌ Jos direktno pise |
| `TariffMappingService.auto_populate_tariffs()` | `services/tariff/tariff_mapping_service.py:234-268` | HIGH | ❌ Jos direktno pise |
| `TariffIntentService` (agent) | `services/agent/chat/tariff_intent_service.py:387,414` | HIGH | ✅ Omotan decision syncom |
| `HistoricalTariffSearchService` | `services/agent/validation/historical_tariff_search_service.py:120` | MEDIUM | ❌ Jos direktno pise |
| `chat_intent_handler.py` | `gui/tabs/agent/services/chat_intent_handler.py:1964,2124` | HIGH | ✅ Omotan decision syncom |
| `PreferenceValidator.auto_fix_missing_eur1()` | `services/validation/preference_validator.py:242` | HIGH (bug) | ✅ Zamijenjen decision servisom u FakturaView; oznacen DEPRECATED |
| `DeclarationAssembly` | `services/naimenovanja/declaration_assembly.py:66-81` | MEDIUM | ❌ Jos direktno pise |
| `ProductMasterList` | `services/tariff/product_master_list.py:227-230` | LOW | ❌ Jos direktno pise |
| `ImportService` | `services/import_service.py:203` | LOW (parser granica) | ❌ Jos direktno pise |
| `OCR parser` | `importers/pdf/ocr_invoice_parser.py:544,562` | LOW | ❌ Jos direktno pise |
| `KG Fashion` | `importers/vendors/kg_fashion/kg_fashion_importer.py:453,464` | LOW | ❌ Jos direktno pise |

---

## Test rezultati

```powershell
python -m pytest tests/unit/test_declaration_decision_service.py tests/unit/test_declaration_decision_model.py tests/unit/test_decision_tariff_policy.py tests/unit/test_evidence_model.py tests/integration/ -q
```

**137 passed, 1 skipped**

---

## dist_client mirror

- `services/decision/integration.py` ✅ identičan
- `gui/tabs/faktura_view.py` ✅ identičan

---

## Rizici

1. **Agent pipeline (4.2)** je najrizičnija podfaza — `chat_intent_handler.py` ima 2000+ linija i duboko je isprepletan sa agent logikom
2. **Validacija (4.3)** — `auto_fix_missing_eur1()` je bug koji aktivno mijenja podatke; uklanjanje zahtijeva refaktor svih pozivalaca
3. **Wrapper pristup** — decision_state se trenutno samo "ogleda" uz postojeće stanje; nije jedini izvor istine dok se svi writeri ne migriraju