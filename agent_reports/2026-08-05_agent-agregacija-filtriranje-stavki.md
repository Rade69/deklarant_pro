## Datum
2026-08-05

## Agent
Claude Code (Sonnet 5)

## Scope
Novi fajl `services/agent/chat/draft_aggregation_service.py`; izmjene
`services/agent/chat/tool_definitions.py`, `services/agent/chat/tool_policy.py`,
`gui/tabs/agent/services/chat_intent_handler.py` (+ dist_client kopije);
novi test `tests/unit/test_draft_aggregation_service.py` + dopuna `tests/test_tool_use.py`
(gitignored dev fajl).

## Status izvora
Nastavak `agent_reports/2026-08-05_agent-pretraga-stavki-po-nazivu.md`. Korisnik je
delegirao dublju analizu Crush agentu preko `agent_tasks/2026-08-05_agent-tool-coverage-audit.md`
(napisano od mene, izvršio Crush/DeepSeek V4 Pro). Rezultat: `docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md`
— nezavisan, eksteran predlog koda/dizajna, pa je prije prihvatanja urađena laka (ne puna)
nezavisna provjera po AGENTS.md pravilu za "tuđi predlog koda" (vidi "Nezavisna provjera" ispod).

## GitNexus impact
Isti simboli kao u prethodnom `pretrazi_stavke` zadatku (`_dispatch_known_tool`, `TOOL_EFFECTS`)
— već potvrđeno LOW risk, čisto aditivan pattern (nova funkcija + nova `elif` grana + nova
stavka u dict-u). Novi servisni fajl je slobodnostojeći (uvozi se samo iz nove wrapper funkcije).

## Reprodukcija prije izmjene
N/A za ovaj specifičan zadatak — Crush-ov audit je već identifikovao root cause statičkom
analizom implementacije (šta `prikazi` STVARNO vraća LLM-u), potkrijepljeno mojom prethodnom
SUSSINA reprodukcijom u istoj klasi buga. Nije rađena nova live reprodukcija za svaki od 15
upita — umjesto toga, svaki upit iz izvještaja je pretvoren u regresioni test koji dokazuje da
NOVI alat vraća tačan rezultat.

## Šta je urađeno
1. Pročitan `docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md` u cijelosti (10 alata klasifikovano,
   15 konkretnih upita bez determinističkog puta, 2 predložena nova alata rangirana po
   prioritetu).
2. Laka nezavisna provjera (ne puna) — grep za linije funkcija koje izvještaj navodi
   (`_pretrazi_tarifu`, `_pretrazi_stavke`, `_pretrazi_porijeklo`) i za
   `ApplicationContextService.format_html` — sve postoje, linijski brojevi blago pomjereni
   (poznat, već dokumentovan obrazac u ovim audit dokumentima — vidi memoriju), suštinski
   tačno.
3. Korisnik izabrao (AskUserQuestion): implementirati OBA predložena alata odjednom.
4. Napravljen `services/agent/chat/draft_aggregation_service.py` — čist Qt-independent servis:
   - `FIELD_MAP` — mapiranje logičkih naziva polja ("vrijednost", "bruto_masa", "tarifa"...)
     na stvarna Python atributa `InvoiceLine`/`NaimenovanjeDraft`, odvojeno po target-u.
   - `_primijeni_uslove()` — dijeljena filter logika (operatori `=`, `!=`, `prazno`,
     `nije_prazno`), koriste je i `agregiraj()` i `filtriraj()`.
   - `agregiraj(draft, operacija, polje, target, uslovi, top_n)` — SUM/AVG/MAX/MIN/COUNT,
     `top_n` za "top N" upite (vraća listu umjesto skalara kad je >1).
   - `filtriraj(draft, target, uslovi, grupisi_po)` — filtriranje i/ili grupisanje-sa-brojanjem.
5. **Namjerna izmjena u odnosu na Crush-ov predlog**: Crush je predložio `target: "faktura" |
   "naimenovanja" | "all"` za oba alata. Uklonjena je opcija "all" — AGENTS.md eksplicitno
   zabranjuje miješanje `draft.items`/`draft.invoice_lines` ("Potpuno različiti koncepti").
   `target` je ograničen na `"invoice"|"items"`, default `"items"`.
6. Dodata dva nova `TOOLS` unosa u `tool_definitions.py` (`agregiraj_stavke`,
   `filtriraj_stavke`) + 2 nova numerisana pravila i 3 nova primjera u `SYSTEM_PROMPT`
   (renumerisani ostali).
7. Registrovana oba alata u `tool_policy.py:TOOL_EFFECTS` kao `ToolEffect.READ_ONLY`.
8. Implementirani `_agregiraj_stavke(ctrl, args)` i `_filtriraj_stavke(ctrl, args)` u
   `chat_intent_handler.py` — formatiraju HTML odgovor iz servisnog rezultata (ne LLM),
   ožičeni u `_dispatch_known_tool` elif lancu sa istim "nedostaje parametar" fallback
   obrascem kao ostali alati.
9. 9 unit testova (`tests/unit/test_draft_aggregation_service.py`) — direktno reprodukuju
   upite #1 (sum+filter po tarifi), #2/#12 (max+top_n po bruto masi), #7 (kombinovani prazno
   uslovi na invoice_lines), #14 (grupisanje po tarifi), plus count/avg/edge-case (nepoznato
   polje → error dict ne exception, prazan draft → `rezultat=None` ne crash).
10. 2 dispatch-level testa u `tests/test_tool_use.py` (gitignored) — potvrđuju da
    `_execute_tool` ispravno rutira do novih alata i formatira poruku.
11. `py_compile` na svih 5 novih/izmijenjenih fajlova (root + dist_client) — OK.
12. Puna `pytest tests/ -q -k "not test_db" --ignore=tests/test_origin_intent_routing.py`
    — 1696 passed (+12 u odnosu na prethodni baseline), 2 pre-postojeća fail-a (jedan manje
    nego prije — `test_ima_tacno_12_alata` sada slučajno prolazi jer smo tačno na 12 alata),
    bez regresije.
13. dist_client sync (CRLF očuvan za sve fajlove uključujući 2 nova).
14. `gitnexus_detect_changes` — risk low, `affected_count: 0`. Nekoliko nepovezanih funkcija
    (`_pretrazi_arhiv_za_proizvod`, `_pretrazi_tarifu_po_kodu`) lažno označeno "touched" —
    potvrđen poznat GitNexus line-shift false positive (`git diff --stat` potvrdio 147
    insertions/0 deletions, čisto aditivno).
15. Commit `05e6423`.

## Zašto je urađeno
Korisnik je odobrio implementaciju oba alata odjednom nakon što je nezavisan (Crush) audit
potvrdio da SUSSINA bug nije izolovan slučaj nego sistemski nedostatak u pokrivenosti alata —
15 konkretnih tipova upita (agregacija, brojanje-sa-uslovima, filtriranje, sortiranje,
duplikati) prolazi kroz `prikazi` (sirov tekst) i prisiljava LLM da sam računa.

## Kako je urađeno
Jedan zajednički servis (`draft_aggregation_service.py`) sa dijeljenom filter logikom
(`_primijeni_uslove`) umjesto dvije nezavisne implementacije — Crush-ov predlog je imao
preklapajuće filter-mehanizme između dva alata (`filter_polje`/`filter_vrijednost` kod
agregacije vs `uslovi` liste kod filtriranja); objedinjeno na isti `uslovi` format za oba
alata radi manje duplikacije i konzistentnosti.

## Šta nije dirano
- `pretrazi_stavke` (postojeći alat iz prethodnog zadatka) — nedirano, i dalje radi samo
  tekstualnu pretragu (Prioritet 3 iz Crush-ovog izvještaja — proširenje sa `polje`
  parametrom — NIJE urađeno ovim zadatkom, korisnik nije to tražio, van scope-a).
- `pronadji_slicne_proizvode` summary linija (Prioritet 4, "nizak") — nedirano.
- Stara imena alata / `tests/test_origin_intent_routing.py` — i dalje van scope-a
  (dokumentovano u prethodnom izvještaju).
- `ChatIntentHandler` monolit (3035+ linija) — refaktor ostaje van scope-a, dodavanje 2 nova
  alata u postojeći elif lanac blago povećava fajl (izvještaj je i sam upozorio na ovo kao
  poznat kompromis).

## Verifikacija
`py_compile` OK. 11 novih testova (9 servisnih + 2 dispatch-level), svi prolaze i direktno
reprodukuju konkretne upite iz audit izvještaja (ne generičke happy-path testove). Puna test
suita bez regresije. Agent/LLM-tool promjena — dokaz je testom, ne screenshot-om (nema
promjene u GUI prikazu, samo u dostupnim alatima i njihovim rezultatima).
**Nije verifikovano end-to-end kroz stvaran Groq/Gemini tool-calling poziv** — isto
ograničenje kao prethodni `pretrazi_stavke` zadatak, još uvijek nije potvrđeno da LLM u
praksi bira nove alate za odgovarajuće upite.

## Nezavisna provjera
- Checker korišćen: DJELIMIČNO — Crush-ov audit je bio nezavisan izvor nalaza (druga
  agent/model sesija), a ja sam uradio laganu (ne punu) provjeru prije prihvatanja predloga
  (grep za citirane funkcije/linije, potvrda da postoje). Nisam nezavisno provjeravao SVAKIH
  15 upita iz izvještaja jedan po jedan prije implementacije — oslonio sam se na to da je
  metodologija (klasifikacija po tome "da li LLM mora sam obrađivati rezultat") zdrava i
  konzistentna sa onim što sam sâm direktno vidio u `_dispatch_prikazi`/`_dispatch_provjeri`
  kodu.
- Razlog za ne-punu provjeru: korisnik eksplicitno zatražio štednju tokena za ovu vrstu
  dubinske analize; GitNexus impact LOW; svaka implementirana funkcija ima sopstveni
  regresioni test koji dokazuje ispravnost NEZAVISNO od tačnosti Crush-ovog opisa problema.

## Pronađeni problemi
Tokom rada, `gui/tabs/agent/services/_review_handlers.py` (WIP fajl od Crush-a, zadržan u
prethodnom zadatku po korisnikovom izboru) je nestao sa diska — najvjerovatnije zato što
Crush aktivno nastavlja svoj "Nivo 3" refaktor u istom working tree-u paralelno sa mojim
radom (i harness je eksplicitno upozorio da je `chat_intent_handler.py` "modified on disk"
van moje sesije u jednom trenutku). Provjereno da moje praćene izmjene (`git diff --stat`)
ostaju čiste i nezavisne od tog fajla — nema konflikta. Ovo je samo zapažanje, ne problem koji
zahtijeva akciju sa moje strane (vidi AGENTS.md "Paralelni agenti").

## Odbačene opcije
- Implementirati `target: "all"` (miješanje invoice_lines i items) kako je Crush predložio —
  odbačeno, direktno krši eksplicitno AGENTS.md pravilo. Dokumentovano u commit poruci kao
  namjerna izmjena, ne previd.
- Dvije odvojene, nezavisne filter implementacije (po Crush-ovom originalnom API dizajnu) —
  odbačeno u korist jedne dijeljene `_primijeni_uslove()` funkcije, manje duplikacije.
- Proširiti `pretrazi_stavke` sa `polje` parametrom u istom zadatku (Crush Prioritet 3) —
  odbačeno, korisnik je tražio implementaciju "oba alata" (misleći na Prioritet 1 i 2 iz
  izvještaja), ne i proširenje postojećeg alata — ostaje mogući follow-up.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `05e6423` | `feat(agent): agregiraj_stavke + filtriraj_stavke — deterministička agregacija/filtriranje` |

## Rizici / ograničenja
Isto ograničenje kao ranije: nije end-to-end testirano kroz stvaran LLM tool-calling poziv —
postoji mala šansa da Groq/Gemini ne prepozna kada treba pozvati koji od sad već 12 alata
(veći broj alata = teže LLM-u da bira ispravno; ovo je poznat trade-off u tool-use dizajnu,
pomenut i u samom Crush izvještaju kao razlog zašto NIJE predložio dodatne, još granularnije
alate). Ako se u praksi pokaže da LLM miješa `agregiraj_stavke` i `filtriraj_stavke`,
trebaće fino podešavanje `SYSTEM_PROMPT` primjera.

## Potreban follow-up
1. **End-to-end test kroz stvarnu GUI chat sesiju** — isprobati par upita iz
   `docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md` (npr. "koja je ukupna vrijednost stavki sa
   tarifom X", "koja stavka ima najveću bruto masu", "koliko stavki nema zemlju porijekla")
   i potvrditi tačne odgovore.
2. Ako se pokaže korisnim: proširiti `pretrazi_stavke` sa `polje` parametrom (Crush Prioritet
   3) i/ili summary liniju za `pronadji_slicne_proizvode` (Prioritet 4) — oba manja, niskog
   rizika.
3. Pratiti `_review_handlers.py`/Crush-ov "Nivo 3" refaktor status — ako se ikad zatraži da
   se dovrši, sada je van mog scope-a i vjerovatno se aktivno mijenja bez mog znanja.

## Potrebna korisnička potvrda
Isprobati u stvarnom Agent chatu upite iz "Potreban follow-up" tačka 1 i potvrditi da LLM
bira ispravan alat i vraća tačan odgovor.
