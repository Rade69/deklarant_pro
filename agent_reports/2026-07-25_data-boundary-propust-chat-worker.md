# Data Boundary propust u ChatWorker Zone B2 — otkriveno i popravljeno

## Datum
2026-07-25

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/agent/widgets/chat_worker.py` + `dist_client/` mirror
  (`_build_zaglavlje_zone`)
- `tests/unit/test_chat_worker_zaglavlje_zone_masking.py` (novo)
- `docs/CONTEXT.md` (§61)

## Status izvora
Korisnik je dao dokument "Kontrolisana podatkovna granica za AI agente"
(prijedlog razrađen sa Codexom — allowlist filozofija, Pydantic
`AgentSafeInput` schema, cloud vs lokalni model razlika, forbidden-marker
testovi) i tražio da se pročita i uporedi sa stvarnim stanjem u aplikaciji.
To poređenje je otkrilo konkretan, stvaran propust — ovaj zadatak ga
popravlja.

## GitNexus impact
- `_build_zaglavlje_zone` (upstream): LOW rizik, impactedCount 2, 1 direktan
  pozivalac (`_build_context`).
- `detect_changes(scope=all)` POSLIJE izmjene: risk_level MEDIUM, 2
  affected_processes (oba "Run → _build_zaglavlje_zone") — očekivano,
  tačno odgovara namjeravanoj izmjeni, bez iznenađenja izvan scope-a.

## Šta je urađeno
Poređenje dokumenta sa kodom otkrilo je: `ChatWorker._build_session_zone()`
(Zone B) maskira `izvoznik_naziv`/`primalac_naziv` na osnovu
`self._allow_sensitive_data()` (env flag `SEND_SENSITIVE_DATA`, default
`false`, i FORSIRANO maskiranje ako je aktivni provider cloud — Groq/
Gemini — bez obzira na flag). `ChatWorker._build_zaglavlje_zone()` (Zone
B2), koja se dodaje u ISTI `_build_context()` payload odmah nakon Zone B,
je slala ista polja (plus `deklarant_naziv`, koji Zone B uopšte ne dotiče)
BEZ IKAKVE provjere — partner imena su stizala do cloud LLM-a čak i sa
default (namjerno bezbjednim) podešavanjem.

Fix: `_build_zaglavlje_zone()` sad poziva isti `self._allow_sensitive_
data()` i maskira `izvoznik_naziv`/`primalac_naziv`/`deklarant_naziv`
identičnim stilom poruke ("[ime skriveno — SEND_SENSITIVE_DATA=false]")
kao Zone B.

## Zašto je urađeno
Ovo NIJE hipotetski nalaz iz dokumenta — direktnim čitanjem koda potvrđeno
je da je propust STVARAN i AKTIVAN (Zone B2 se uvijek poziva kad zaglavlje
ima bilo koje od navedenih polja, nezavisno od korisnikovog pitanja).
Ovo je tačan obrazac koji dokument opisuje u §5 ("uvijek možeš zaboraviti
novu vrstu osjetljivog podatka" pri per-zona/blocklist pristupu) — Zone B2
je vjerovatno dodata KASNIJE (docstring: "polja koja agent nije vidio", tj.
naknadno proširenje konteksta) bez revizije postojeće maskirajuće politike
uspostavljene ranije u Zone B za identična polja.

## Kako je urađeno
- Pročitan cijeli `ChatWorker._build_context()` (linije 196-310) da se
  razumije redoslijed i sadržaj svih zona konteksta prije zaključka.
- Upoređene DVIJE zone koje diraju ista polja (`_build_session_zone` vs
  `_build_zaglavlje_zone`) — potvrđeno da samo prva ima masking gate.
- Provjereno da `_allow_sensitive_data()` (staticmethod) FORSIRA
  maskiranje za cloud providere čak i uz eksplicitan `SEND_SENSITIVE_
  DATA=true` — ovo je JAČE od onoga što dokument predlaže (dokument ne
  spominje ovakav "hard override" mehanizam, samo generalnu cloud/local
  razliku).
- Provjereno (grep) da je `SEND_SENSITIVE_DATA` isti flag koji koristi i
  `product_similarity_embedding_service.py` za embedding — potvrđuje
  ustaljenu, cross-cutting politiku, ne izolovan hack.
- GitNexus impact provjeren PRIJE izmjene (LOW), `detect_changes()`
  POSLIJE (MEDIUM, ali fokusirano tačno na namjeravanu funkciju/procese).

## Šta nije dirano
- `_build_session_zone()` (Zone B) — netaknuta, već ispravna.
- `header_attached_documents` (Rb.44 priložene isprave — brojevi
  dokumenata) unutar iste `_build_zaglavlje_zone()` — NIJE maskirano u
  ovom fixu; korisnikov zahtjev i moj raniji nalaz su bili specifično o
  imenima partnera (izvoznik/primalac/deklarant), ne o brojevima
  dokumenata — ostavljeno kao potencijalan follow-up, ne pretpostavljeno.
- `_search_declarations_context()` (pretraga istorijskih XML deklaracija,
  "partner" grana) — već ima ispravan `send_sensitive` gate, provjereno,
  nedirano.
- Formalna Pydantic `AgentSafeInput` schema — plan napisan zasebno
  (`project_rooms/2026-07-25_agent-safe-input-schema-plan.md`), NIJE
  implementirana u ovom zadatku (korisnik je tražio samo plan).

## Verifikacija
- `python -m py_compile` na oba (root + dist_client) — OK.
- 3 nova testa (`tests/unit/test_chat_worker_zaglavlje_zone_masking.py`):
  partneri maskirani kad `send_sensitive=False`, prikazani kad `True`,
  ne-partnerska polja (vrsta deklaracije, valuta/iznos) ostaju vidljiva
  bez obzira na flag (potvrđuje da fix ne maskira previše).
- Pun test suite: 1134 passed (+3 nova). **10 DB-backed testova
  (`test_decision_characterization.py`) trenutno failed** — PostgreSQL
  server (192.168.100.154) nedostupan (`timeout expired`, potvrđeno
  direktnim konekcijskim testom) — infrastrukturni problem, NE regres
  izazvan ovom izmjenom (ti testovi su u potpuno drugom modulu,
  `tariff_mapping_service`, bez ikakve veze sa `chat_worker.py`).
- `gitnexus_detect_changes(scope=all)`: risk MEDIUM, 2 affected_processes,
  oba tačno na izmijenjenu funkciju.
- Root vs dist_client diff nakon mirroringa: identičan sadržaj (razlika
  samo u pre-postojećem BOM karakteru na početku fajla, nepovezano).

## Pronađeni problemi
- PostgreSQL server nedostupan tokom ovog test run-a (vidi Verifikacija) —
  van moje kontrole, nije praćeno dalje (mrežni/server status, ne kod).

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `223d543` | fix(agent): maskiraj imena partnera u Zone B2 (zaglavlje) chat konteksta |

## Rizici / ograničenja
- Fix pokriva samo tri polja imenovana u nalazu (izvoznik/primalac/
  deklarant naziv). Rb.44 priložene isprave (brojevi dokumenata) u istoj
  zoni ostaju nemaskirani — nisu bili dio prijavljenog nalaza, ali
  predstavljaju sličan (manji) rizik ako se smatraju osjetljivim.
- Ovaj fix je TAČKASTA popravka jednog otkrivenog gap-a, ne strukturno
  rješenje — dok kontekst ostaje ad-hoc string building (bez centralne
  scheme/allowlist), ista klasa greške (nova zona zaboravi masking) može
  se ponoviti pri budućem proširenju. Plan za formalnu schemu (sljedeći
  koraci) bi to strukturno riješio.

## Potreban follow-up
- Razmotriti da li Rb.44 (brojevi priloženih isprava) treba isti masking.
- Implementacija formalne Pydantic `AgentSafeInput` scheme — vidi
  `project_rooms/2026-07-25_agent-safe-input-schema-plan.md` (plan,
  zaseban zadatak, čeka korisničku odluku o prioritetu/opsegu).
- Forbidden-marker test suite (dokument §12) — trenutno ne postoji
  generalizovan test koji pokriva CIJELI `_build_context()` odjednom;
  novi testovi pokrivaju samo `_build_zaglavlje_zone()` izolovano.

## Potrebna korisnička potvrda
Nema — nalaz je jasan, fix je uzak i direktno odgovara na prijavljeni
propust.
