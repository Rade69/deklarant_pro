# Faza 2 — Povlastice i porijeklo bez dokaza (2026-06-10)

## Šta je urađeno

Implementirana Faza 2 iz `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`,
dva dijela kako je dogovoreno ("Da, oba dijela"):

1. **Bug fix**: agent mod više ne potvrđuje povlasticu (Rub.36) za EU/CEFTA/TR/IR
   stavke koje nemaju EUR.1 broj niti izjavu o porijeklu — povlastica ostaje
   neutralna (prazna) dok korisnik ne potvrdi PE1/PE2/PE3.
2. **Evidence wiring**: nova funkcija `evidence_from_preference()` (Faza 1
   vokabular — `Evidence`/`DecisionSource`/`DecisionConfidence`) primijenjena
   na povlastice, ukomponovana u `ComplianceCheckService._check_eur1_povlastica()`.

Sve izmjene mirrorovane u `dist_client/`. Dodati testovi za PE1/PE2/PE3,
EU-bez-dokumenta i CN scenarije.

## Kako je urađeno

### Dio 1 — `_auto_handle_povlastice_agent` (gui/tabs/faktura_view.py)

**Prije**: za stavke bez izjave o porijeklu (`has_origin_statement=False`,
EUR1 grana), funkcija je pozivala `_suggest_preference_by_country(zemlja)` i,
ako je vratila nešto (npr. `'EUP'` za DE), odmah postavljala
`item.povlastica = pov` — iako ne postoji nikakav dokaz (EUR.1 broj ili izjava).

To je gušilo postojeću žutu oznaku "provjerite ručno" iz
`_apply_preference_confidence_color` (06-07 fix), jer je uslov
`source == "PDF_OZNAKA" and not has_pref and eligible_for_pref` bio `False`
(`has_pref` je već bilo `True` zbog lažnog auto-popunjavanja).

**Sada**: u EUR1 grani se `item.povlastica` više **ne postavlja**. `eur1_pending`
se i dalje računa (uslov: `pov` postoji, a `povlastica` i `eur1_number` su prazni)
— pa se EUR.1 dijalog i dalje otvara isto kao prije za stavke koje ga čekaju.
Stavke koje su VEĆ ranije potvrđene (PE1/PE2 dijalogom, imaju `eur1_number`)
ostaju netaknute i ne ulaze u `eur1_pending`.

CN i ostale nepreferencijalne zemlje su nepromijenjene —
`_suggest_preference_by_country('CN')` već vraća `''`, pa ni prije ni sada
ništa ne postavlja.

Uklonjen `updated_eur1`/`'eur1'` brojač iz povratnog dict-a (ništa više ne
postavlja, postao je mrtav kod) i odgovarajući `logger.info(...)` poziv u
`_on_import_finished`. Povratni dict: `{'pe2': int, 'eur1_pending': int}`
(bilo i `'eur1'`).

### Dio 2 — `evidence_from_preference()` (services/agent/validation/evidence_model.py)

Nova pure funkcija (ne dira `InvoiceLine` — nema serijalizacionog rizika):

| Uslov na stavci | DecisionConfidence | DecisionSource | requires_confirmation |
| --- | --- | --- | --- |
| `has_origin_statement and is_authorized_exporter` (PE3) | `confirmed_from_document` | `DOCUMENT` | `False` |
| `has_origin_statement` (PE2) | `confirmed_from_document` | `DOCUMENT` | `False` |
| `eur1_number` postavljen (PE1) | `confirmed_from_document` | `DOCUMENT` | `False` |
| `povlastica` postavljen, bez PE dokaza | `weak_guess` | `SIMILARITY` | `True` |
| ništa postavljeno | `unknown` | `TARIFF_DATABASE` | `True` |

`ComplianceCheckService._check_eur1_povlastica()` je prepravljen sa inline
`not has_origin_statement and not eur1_number` na
`evidence_from_preference(l).requires_confirmation` — funkcionalno
ekvivalentno (isti skup pogođenih stavki), ali sad izraženo kroz zajednički
Evidence vokabular iz Faze 1, spremno za Fazu 6 (bogatiji UI prikaz).

### GitNexus impact analiza (prije izmjene)

| Simbol | Risk | Napomena |
| --- | --- | --- |
| `_auto_handle_povlastice_agent` | LOW (1 direktan caller, `_on_import_finished`) | |
| `_check_eur1_povlastica` | LOW (1 direktan caller, `check`) | |

`gitnexus_detect_changes(scope=all)` nakon izmjene: `risk_level: low`,
`affected_processes: []`.

### Testovi

- `tests/unit/test_evidence_model.py` — dodato 5 novih testova za
  `evidence_from_preference`: PE1, PE2, PE3, EU-bez-dokumenta (weak_guess),
  CN-bez-povlastice (unknown).
- `tests/unit/test_auto_handle_povlastice_agent.py` (novi fajl) — 4 testa za
  `_auto_handle_povlastice_agent`. Poziva metod kao **unbound** preko
  `FakturaView._auto_handle_povlastice_agent(fake_self, ...)`, gdje je
  `fake_self` `types.SimpleNamespace(draft=...)` sa `_suggest_preference_by_country`
  vezanim preko `types.MethodType` — bez instanciranja QWidget-a.
  Pokriva: EU-bez-dokumenta (neutralna+pending), CN (bez povlastice/pending),
  PE2 (povlastica se postavlja), već-potvrđena EUR1 stavka (ne ulazi u pending).

```
python -m py_compile <8 izmijenjenih/novih .py fajlova>  -> OK
pytest tests/unit/test_evidence_model.py tests/unit/test_auto_handle_povlastice_agent.py \
       tests/unit/test_declaration_validator_tariff_lookup.py -> 16/16 PASSED
pytest tests/unit/ -> 440 passed, 15 failed (pre-existing, provjereno na git stash —
       isti failovi i PRIJE ovih izmjena: UnicodeEncodeError charmap, ModuleNotFoundError
       google.genai, blagic_loren/master_frigo/declaration_search/parse_naimenovanja —
       nepovezano sa Fazom 2)
```

## Zašto

Plan zahtijeva da povlastica (Rub.36) bude potvrđena samo dokazom (EUR.1/izjava),
ne pukom pretpostavkom po zemlji — inače carinik može naići na povlasticu u
deklaraciji bez priloženog dokumenta. Postojeća žuta oznaka iz 06-07 fix-a je
bila ispravna logika koja je zbog ovog bug-a nikad nije okidala u agent modu za
EU/CEFTA/TR/IR stavke. `evidence_from_preference()` slijedi isti `Evidence`
vokabular kao Faza 1 (`evidence_from_tariff_decision`), tako da Faza 6 (bogatiji
UI prikaz izvora/pouzdanosti) može jednoobrazno prikazivati i tarifne i
preferencijalne odluke.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `5f6e455` | chore(gitnexus): osvjezi indeks brojeve |
| `048534e` | fix(agent): povlastica za EU/CEFTA/TR/IR se ne potvrdjuje bez PE1/PE2/PE3 dokaza |
| `7f790cd` | feat(agent): evidence_from_preference za povlasticu + compliance check wiring |

## Šta nije urađeno / sljedeći koraci

- **Vokabular povlastica i dalje nekonzistentan** (pre-existing, van scope-a):
  `derive_preference()` (services/tariff/country_origin_validator.py) vraća
  `"EUPR"/"CEFTAR"/"EFTA1R"/...`, dok `_suggest_preference_by_country()` /
  `_suggest_preference()` (eur1/pe2 dijalozi) vraćaju `"EUP"/"CEFTAP"/"TRP"/"IRP"`,
  a `PreferenceValidator.PREFERENCE_CODES = {'CEFTAP','EUP','TRP','PE1','PE2','PE3'}`
  ne pokriva ni jedan skup u potpunosti (npr. `"EUPR"` ne bi prošao
  `PreferenceValidator.validate()`). Nije dirano — flagovano za buduću fazu.
- **Mogući mrtav kod** u `merge_country_origin()` (country_origin_validator.py):
  SLUČAJ 4 (`if pdf_clean and baza_clean:` za MATCH/CONFLICT) izgleda nedostižan
  jer SLUČAJ 1+2 već pokrivaju sve `pdf_clean`-truthy slučajeve. Nije potvrđeno
  testom, nije dirano.
- `_show_eur1_dialog()` je i dalje modalni `QDialog.exec()` pozvan iz agent moda
  (`_on_import_finished`) kad `eur1_pending > 0` — moguća kontradikcija sa
  "agent mod = nema blokirajućih dijaloga", ali pre-existing ponašanje, van
  scope-a Faze 2 (Faza 4+8 — tool-first tok — će vjerovatno adresirati ovo).

Faza 3 (istorijski prijedlozi striktno po izvozniku), Faza 4+8 (tool-first +
402/429 LLM fallback), Faza 6 (UI prikaz izvora/pouzdanosti — može iskoristiti
`evidence_from_preference()`) slijede u zasebnim commitovima.
