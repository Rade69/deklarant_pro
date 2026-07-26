# JIB u partner-search grani usklađen sa Zone B pravilom

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/agent/widgets/chat_worker.py` — `_search_declarations_context` (partner-search grana)
- `dist_client/gui/tabs/agent/widgets/chat_worker.py` — ista funkcija, mirror
- `tests/unit/test_chat_worker_declarations_partner_search_masking.py`
- `docs/CONTEXT.md` — §66

## Status izvora
Follow-up stavka je bila eksplicitno zapisana kao "otvoreno pitanje, čeka
korisničku odluku" u:
- `agent_reports/2026-07-26_agent-safe-context-faze-2-5.md`
- `docs/CONTEXT.md` §62-63
- memorija `2026-07-26_sesija-pregled-agent-safe-context-tarifna-politika.md`

Svi izvori aktivni i konzistentni — nije bilo konflikta.

## GitNexus impact
`_search_declarations_context` upstream: **LOW** (2 pogođena simbola —
`_build_context` poziva je, `run` poziva `_build_context`; 1 proces
pogođen). `detect_changes(scope=all)` poslije izmjene potvrdio **LOW**
rizik, 0 affected_processes, samo "touched" na `ChatWorker` klasi i
funkciji u oba fajla (root + dist_client mirror).

## Šta je urađeno
U partner-search grani `_search_declarations_context`, `jib_display` je
sad UVIJEK `"[JIB skriven]"`, bez obzira na `send_sensitive`
(`_allow_sensitive_data()`). Prije se pokazivao stvaran
`consignee_jib` kad je korisnik eksplicitno postavio
`SEND_SENSITIVE_DATA=true` I koristio lokalni LLM provider (ollama) —
cloud provideri su i ranije bili forsirano maskirani.

Uklonjen zastario komentar koji je opisivao ovo kao "otvoreno pitanje,
nedirano" — zamijenjen kratkom referencom na ovaj izvještaj.

## Zašto je urađeno
Korisnička odluka: JIB se nikad ne šalje LLM-u ni u jednoj grani konteksta,
čak ni uz eksplicitni opt-in na lokalnom modelu. Razlog: jedno apsolutno
pravilo je manje sklono grešci nego uslovni izuzetak koji zavisi od
kombinacije dvije env-varijable/postavke providera. Ovo je isti princip
koji je već primijenjen u Zone B (`_build_session_zone`) i u tarifnoj
politici iz §65 (izvor-nepoznat-nikad-prikazan) — kad je rizik "stvarno
osjetljiv podatak procuri", stroža strana pobjeđuje.

## Kako je urađeno
Jedna linija promijenjena u obje kopije fajla (`jib_display = r.get(...)
if send_sensitive else "[JIB skriven]"` → `jib_display = "[JIB skriven]"`).
Ime izvoznika/primaoca ostaju nepromijenjeni — i dalje idu kroz
`AgentContextAdapter.mask_partner()`, koji već ispravno poštuje
`send_sensitive` za imena (ta logika nije dio ovog pitanja).

## Šta nije dirano
- `AgentContextAdapter.mask_partner()` logika za imena — nepromijenjena.
- Zone B (`_build_session_zone`) — već je bila ispravna, služila je kao
  referentni standard.
- `_allow_sensitive_data()` — nepromijenjena, i dalje kontroliše
  maskiranje imena u ovoj grani.

## Verifikacija
- `python -m py_compile` na oba fajla + test fajla — čisto.
- `pytest tests/unit/test_chat_worker_declarations_partner_search_masking.py -q`
  — 3 passed (2 postojeća + 1 nov).
- Nov test `test_partner_search_jib_nikad_ne_ide_u_kontekst` provjerava da
  `consignee_jib` string nikad ne uđe u kontekst, za oba stanja
  `send_sensitive` (True/False).
- `gitnexus_detect_changes(scope=all)` — LOW risk, 0 affected_processes.

## Pronađeni problemi
Nema — čisto planirana izmjena po eksplicitnoj korisničkoj odluci.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (sljedeći commit) | `fix(agent): uskladi JIB prikaz u partner-search grani sa Zone B pravilom` |

## Rizici / ograničenja
Nema poznatih — izmjena strože ograničava podatke koji idu LLM-u, ne
proširuje ih.

## Potreban follow-up
Nema novog. Preostali follow-up iz prošle sesije (zastarjeli docs,
retroaktivno popunjavanje supplier/source, UUID u naziv_robe,
TariffLLMWorker migracija) i dalje otvoren, van scope-a ovog zadatka.

## Potrebna korisnička potvrda
Nema — odluka je već eksplicitno data prije implementacije.
