## Datum
2026-08-05

## Agent
Claude Code (Sonnet 5)

## Scope
`services/agent/chat/tool_definitions.py`, `services/agent/chat/tool_policy.py`,
`gui/tabs/agent/services/chat_intent_handler.py` (+ dist_client kopije),
`tests/test_tool_use.py` (gitignored, lokalni dev test — vidi napomenu ispod).

## Reprodukcija prije izmjene
Korisnik dostavio stvaran chat transkript: na pitanje "Koliko ima proizvoda SUSSINA"
agent je odgovorio sa 3 stavke, ali je opis samoprotivrečan (na kraju pominje "4 različite
fakturne linije") i promašio je stvarnu stavku br.2 koja je takođe SUSSINA. Ovo je
konkretan, dokumentovan dokaz greške — nije bila potrebna dodatna reprodukcija.

## GitNexus impact
`_dispatch_known_tool` (upstream): risk LOW, 1 direktan pozivalac (`_execute_tool`),
`affected_processes: []`. `TOOL_EFFECTS` (upstream): risk LOW, 0 impacted. Čisto aditivna
izmjena (nova grana u postojećem elif lancu, nova stavka u dict-u, nova funkcija) — nije
mijenjan nijedan postojeći tok.

## Šta je urađeno
1. Analiza `services/agent/chat/tool_definitions.py` — `prikazi`/`provjeri` (jedina dva
   alata koja pipaju stavke) primaju samo `target`/`scope`/`ordinals`, BEZ parametra za
   tekstualnu pretragu. Kad korisnik pita "koliko ima X", LLM dobije snapshot cijelog
   drafta kao tekst i mora sâm brojati/skenirati — nepouzdano po definiciji.
2. Uzgredni nalaz: `tests/test_tool_use.py::test_svi_ocekivani_alati_postoje` i
   `tests/test_tool_use_offline.py::TestToolSchema::test_ima_tacno_12_alata` su već
   PRE-POSTOJEĆE failing (od ranije u sesiji, nepovezano) — testiraju STARA imena alata
   (`prikazi_naimenovanja`, `provjeri_naimenovanja`, `provjeri_tarife`,
   `validuj_deklaraciju`) koja su namjerno uklonjena iz `TOOLS` tokom "Faza 1
   konsolidacije" (vidi komentar u `tool_policy.py`: "Stara imena (aliasi) — zadržana radi
   kompatibilnosti"). Executor grane za njih i dalje postoje u `_dispatch_known_tool` i
   `TOOL_EFFECTS` (backward-compat), samo nisu više izložene LLM-u. Ovo NIJE bag vezan za
   SUSSINA slučaj — provjereno i namjerno ostavljeno netaknuto (stale test očekivanja, ne
   moj scope).
3. Dodat novi alat `pretrazi_stavke(upit, target)` u `TOOLS` — deterministička server-side
   pretraga (case-insensitive substring) kroz `draft.invoice_lines[].naziv_robe` i
   `draft.items[].goods_description`/`goods_trade_name`, vraća tačan broj + listu (Faktura
   red + naziv + tarifa; Rb. naimenovanja + naziv + tarifa). LLM više ne smije ručno brojati
   — SYSTEM_PROMPT eksplicitno instruira da se za "koliko ima X" uvijek zove ovaj alat.
4. Registrovan `pretrazi_stavke` kao `ToolEffect.READ_ONLY` u `tool_policy.py`
   (`TOOL_EFFECTS` — bez ovoga bi `_execute_tool` odbio alat fail-closed čak i da je u
   TOOLS i ima dispatch granu).
5. Implementiran `_pretrazi_stavke(ctrl, upit, target)` u `chat_intent_handler.py`, ožičen
   u `_dispatch_known_tool` elif lancu, sa istim "prazan upit" fallback obrascem kao
   `pretrazi_tarifu`/`pretrazi_porijeklo`.
6. Regresioni test `test_pretrazi_stavke_broji_sve_podudarne_stavke` u
   `tests/test_tool_use.py` — reprodukuje SUSSINA scenario (2 fakturne linije + 1
   naimenovanje sa case-insensitive matchom "Sussina Stevia"), potvrđuje tačan broj (3) i
   da su OBJE fakturne linije i naimenovanje pronađeni.
7. `py_compile` na svih 6 fajlova (root + dist_client) — OK.
8. `pytest tests/unit/test_tool_policy.py tests/test_tool_use.py tests/test_tool_use_offline.py`
   — isti pre-postojeći 2 fail-a (stara imena alata, vidi tačku 2), moj novi test PROŠAO.
9. Puna `pytest tests/ -q -k "not test_db" --ignore=tests/test_origin_intent_routing.py` —
   1684 passed, isti 3 pre-postojeća fail-a + 1 pre-postojeći error, BEZ regresije.
   `tests/test_origin_intent_routing.py` isključen iz run-a — vidi "Pronađeni problemi".
10. dist_client sync (CRLF očuvan, sadržajna identičnost potvrđena za sva 3 fajla).
11. `gitnexus_detect_changes` — risk low, scope tačno kao očekivano (samo moje 3+3 fajla,
    plus pre-postojeći nepovezan WIP na AGENTS.md/CLAUDE.md/dist_client UI fajlovima).
12. Commit `2c28ed5`.

## Zašto je urađeno
Korisnikov stvaran chat primjer je pokazao pogrešno/nepotpuno brojanje stavki po nazivu —
korisnik je eksplicitno odobrio dodavanje determinističkog alata ("Da, dodaj alat sada").

## Kako je urađeno
Minimalna, aditivna izmjena — nova stavka u `TOOLS` listi, novi red u `TOOL_EFFECTS` dict-u,
nova funkcija + jedna nova `elif` grana u postojećem dispatch lancu. Nijedan postojeći alat
nije mijenjan.

## Šta nije dirano
- `prikazi`/`provjeri` alati i njihova dispatch logika — nedirano.
- Stara imena alata (`prikazi_naimenovanja` i sl.) i njihov pre-postojeći failing test —
  namjerno neriješeno, van scope-a ovog zadatka (vidi tačku 2 gore).
- `tests/test_origin_intent_routing.py` — nije praćen gitom (gitignored, `test_*.py`
  pattern), lokalni WIP fajl (najvjerovatnije od paralelnog Crush agenta koji radi na istom
  working tree-u danas — vidi AGENTS.md "Paralelni agenti"). Ima grešku pri importu
  (`from ._tariff_handlers import TariffHandlerMixin` puca kad se fajl učita preko
  `importlib.util.spec_from_file_location` umjesto normalnog paket importa) — potvrđeno da
  je pre-postojeća i nepovezana sa mojom izmjenom (import na liniji 144 je već bio u HEAD-u
  prije bilo kakve moje izmjene danas). Nisam je popravljao — nije moj fajl niti moj scope.

## Verifikacija
`py_compile` OK. Ciljani testovi + puna test suita (isti pre-postojeći fail-ovi, bez
regresije). Novi regresioni test direktno reprodukuje prijavljeni bug scenario i prolazi.
Ovo je Agent/LLM-tool promjena, ne GUI vizuelna izmjena — dokaz je testom, ne screenshot-om
(nema promjene u samom prikazu, samo u tome koji alat LLM bira i šta taj alat vraća).
**Nije verifikovano end-to-end kroz stvaran Groq/Gemini tool-calling poziv** (zahtijeva
pokretanje GUI aplikacije i pravu chat interakciju) — vidi "Potreban follow-up".

## Nezavisna provjera
- Checker korišćen: NE.
- Razlog: GitNexus impact LOW, čisto aditivna izmjena, pokrivena regresionim testom koji
  direktno reprodukuje prijavljeni bug. Ne dira bazu, tarifno mapiranje, ni XML export.

## Pronađeni problemi
1. `tests/test_tool_use.py::test_svi_ocekivani_alati_postoje` i
   `test_tool_use_offline.py::TestToolSchema::test_ima_tacno_12_alata` — pre-postojeći,
   testiraju stara/uklonjena imena alata (vidi tačku 2 u "Šta je urađeno"). Vrijedi
   ažurirati ta dva testa da odražavaju "Faza 1 konsolidaciju" (ili ih obrisati ako su
   potpuno zastarjeli) — nisam to radio jer nije vezano za ovaj zadatak.
2. `tests/test_origin_intent_routing.py` (negitovan, lokalni fajl) ima trajno slomljen
   import zbog načina učitavanja modula — vjerovatno WIP od paralelnog agenta (Crush),
   pominje se u kontekstu "Nivo 3" refaktora vidljivog u git logu. Nisam dirao — nije moj
   fajl.
3. Slučajna epizoda tokom ovog zadatka: pokušaj provjere da li je import greška
   pre-postojeća doveo je do greške sa `git stash` — `git stash push -- <pathspec>` je
   djelimično omanuo (dva gitignored test fajla), a naknadni `git stash pop` je pokupio
   TUĐI stariji stash ("backup prije ciscenja nakon windows gui commita") umjesto praznog.
   Merge je stao na konfliktu (AGENTS.md/CLAUDE.md netaknuti), ali je 8 fajlova iz tog
   starog stasha materijalizovano na disk. Korisnik je pregledao listu, potvrdio da je
   `gui/tabs/agent/services/_review_handlers.py` (Crush-ov WIP, ReviewHandlerMixin iz
   Nivo 3 refaktora) legitiman i treba ga zadržati, a ostalih 7 (dist_client/.gitattributes,
   .github/, agent_reports/, agent_tasks/, 2× build skripta, scripts/create_dist_client.bat)
   obrisano — originalni stash je i dalje netaknut u `git stash list`
   ("backup prije ciscenja nakon windows gui commita"), ništa nije izgubljeno. **Pouka:
   NIKAD ne koristiti `git stash pop` za istraživanje/provjeru hipoteze — koristiti
   `git show HEAD:<path>` ili `git log` umjesto toga.**

## Odbačene opcije
- Popravljanje pre-postojećih stale testova (stara imena alata) u istom zadatku — odbačeno,
  van scope-a, ne miješati sa funkcionalnom izmjenom (AGENTS.md).
- Dirati `tests/test_origin_intent_routing.py` — odbačeno, tuđi fajl/WIP.

## Konflikti / kontradiktorni izvori
Nema za samu `pretrazi_stavke` izmjenu.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `2c28ed5` | `feat(agent): novi alat pretrazi_stavke — determinisitička pretraga/brojanje stavki po nazivu` |

## Rizici / ograničenja
Pretraga je case-insensitive substring, BEZ dijakritik-normalizacije ni fuzzy matchinga —
"Sušina" se neće naći pretragom "Susina" (ovo je namjerna, minimalna implementacija; može se
proširiti kasnije ako se pokaže potrebno). Nije end-to-end testirano kroz stvaran LLM
tool-calling poziv (samo direktan poziv executora) — postoji mala šansa da Groq/Gemini ne
prepozna kada treba pozvati novi alat uprkos ažuriranom SYSTEM_PROMPT-u; ako se to desi u
praksi, trebaće fino podešavanje opisa/primjera u prompt-u.

## Potreban follow-up
1. End-to-end test kroz stvarnu GUI chat sesiju sa pravim Groq pozivom — potvrditi da LLM
   zaista bira `pretrazi_stavke` za upite tipa "koliko ima X".
2. Razmotriti ažuriranje/brisanje pre-postojećih stale testova za stara imena alata
   (nalaz #1 gore) — poseban, mali zadatak.
3. `tests/test_origin_intent_routing.py` uskladiti sa Crush-ovim "Nivo 3" refaktorom kad
   taj rad bude gotov — nije nešto što ja treba da radim.

## Potrebna korisnička potvrda
Isprobati u stvarnom Agent chatu: "koliko ima proizvoda SUSSINA" (ili sličan upit za bilo
koji proizvod u aktivnoj deklaraciji) i potvrditi da odgovor sada daje tačan, konzistentan
broj.
