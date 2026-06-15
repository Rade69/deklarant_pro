# Agent report — ComplianceCheckService broken import fix

## Datum
2026-06-15

## Agent
Claude Sonnet 4.6

## Scope
- `gui/tabs/agent/services/chat_intent_handler.py` (`_compliance_check`, linija ~2486)
- `dist_client/gui/tabs/agent/services/chat_intent_handler.py` (identičan mirror)

## GitNexus impact
`gitnexus_impact(_compliance_check, upstream)` → **risk LOW**, 6 pogođenih simbola
(direct: 3 — `ChatIntentHandler.compliance_check`, `_execute_tool`,
`_handle_message_regex_fallback`), 0 execution flows pogođeno. Izmjena je
samo ispravka import putanje unutar postojećeg `try/except` bloka, bez
promjene signature ili ponašanja funkcije.

`gitnexus_detect_changes(unstaged)` prije komita → `risk_level: low`,
`affected_count: 0`, jedino `_compliance_check` (gui + dist_client) prijavljen
kao "touched".

## Šta je urađeno
Popravljen pokvaren import u `_compliance_check()`:
```python
# prije (modul ne postoji)
from services.agent.compliance_check_service import ComplianceCheckService
# sada
from services.agent.validation.declaration_validator_service import ComplianceCheckService
```
Identična izmjena u `gui/` i `dist_client/` kopiji.

## Zašto je urađeno
Korisnik je pitao da li bi dobro došlo ASYCUDA-stil dugme za "krajnju
provjeru deklaracije" (prolazak kroz sva naimenovanja, zaglavlje, priložene
dokumente i fakturu radi traženja grešaka). Pregled
`services/agent/validation/declaration_validator_service.py` je otkrio da
TAKAV sistem već postoji — `ComplianceCheckService` (7 provjera: tarifni
brojevi, zemlja porijekla, težine uklj. Faktura vs Naimenovanja mismatch,
EUR.1/povlastica, kompletnost naimenovanja, fuzzy-match izvoznik/uvoznik,
priloženi dokumenti) — ali se poziva SAMO iz AI chata preko
`_compliance_check()`, čiji import na `services.agent.compliance_check_service`
cilja modul koji ne postoji (premješten u `validation/declaration_validator_service.py`
prilikom ranijeg refaktora agent servisa, re-export ostavljen u
`services/agent/__init__.py`, ali stari import path u
`chat_intent_handler.py` nije ažuriran).

Posljedica: chat komande "provjeri sve" / "kompletnost" /
"validacija deklaracije" / "compliance" su uvijek padale na
`ModuleNotFoundError`, uhvaćen tihim `except Exception` (linija 2519) → korisnik
je dobijao samo poruku o grešci bez ikakvog rezultata provjere.

## Kako je urađeno
Jednostavna izmjena import putanje na 1 liniju u oba fajla
(`gui/` + `dist_client/`), bez dodatnih izmjena logike.

## Šta nije dirano
- `DeclarationValidatorService` ("Provjeri" dugme u Zaglavlju) — netaknuto.
- Faktura "Provjeri" dugme (`_on_validate_all`, per-row validacija) — netaknuto.
- Predloženi **Korak 2** (novo vidljivo dugme "Završna provjera" koje
  kombinuje `DeclarationValidatorService` + `ComplianceCheckService` i
  opciono blokira "Izvezi XML" na ERROR) — NIJE implementiran, čeka odgovor
  korisnika.
- Nepovezane WIP izmjene u `AGENTS.md`/`CLAUDE.md`/`templates/agent-md/CLAUDE.md`
  (vidljive u `gitnexus_detect_changes` kao "touched" iz prethodne sesije) —
  nisu dio ovog commita.

## Verifikacija
- `python -m py_compile` na oba izmijenjena fajla → OK.
- `python -c "from services.agent.validation.declaration_validator_service import ComplianceCheckService"` → OK.
- `ComplianceCheckService().check(DeclarationDraft())` end-to-end na praznom
  draftu → vraća `ComplianceResult(is_ok=True, errors=0, warnings=1)` bez
  exception-a.

## Pronađeni problemi
Nema (bug je bio jednoznačan — stale import path, jedna linija po fajlu).

## Commitovi
| Hash | Poruka |
|------|--------|
| `bb07d0d` | fix(agent): popravi pokvaren import ComplianceCheckService u chat compliance provjeri |

## Rizici / ograničenja
Nema novih rizika — popravka vraća postojeću, ranije radnu funkcionalnost u
ispravno stanje. `ComplianceReportDialog` (GUI dio) nije testiran u stvarnoj
app (zahtijeva QApplication + otvoren chat).

## Potreban follow-up
- Korak 2 (dogovoreno sa korisnikom, na čekanju): vidljivo dugme "Završna
  provjera" koje kombinuje `DeclarationValidatorService` + `ComplianceCheckService`,
  prikazuje kombinovani izvještaj, i opciono blokira "Izvezi ASYCUDA XML" na
  ERROR (WARNING/INFO/SUGGESTION ostaju informativni).

## Potrebna korisnička potvrda
- Testirati u stvarnoj app: u AI chatu otkucati "provjeri sve" (ili
  "validacija deklaracije"/"kompletnost") nad učitanom deklaracijom i
  potvrditi da se otvara `ComplianceReportDialog` sa rezultatima umjesto
  poruke o grešci.
