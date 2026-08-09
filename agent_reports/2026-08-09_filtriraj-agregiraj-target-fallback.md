## Datum
2026-08-09

## Agent
Claude Sonnet 5 (Claude Code)

## Scope
`services/agent/chat/draft_aggregation_service.py`, `services/agent/chat/
tool_definitions.py`, `gui/tabs/agent/services/chat_intent_handler.py`
(+ `dist_client/` kopije sva tri), `tests/unit/test_draft_aggregation_
service.py` (+ dist_client kopija).

## Status izvora
Nastavak istrage otvorene ranije istog dana ("agent pametniji" pitanje) —
`docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md` (Crush, 2026-08-05) i memorija
`agent-agregacija-filtriranje-stavki`/`agent-pretraga-stavki-po-nazivu`
korišćeni kao osnova za razumijevanje postojeće arhitekture alata — status:
aktuelni, `agregiraj_stavke`/`filtriraj_stavke` iz tog audita su bili
implementirani i rade, ali ovaj KONKRETAN bug (target default) nije bio
pokriven tim auditom.

## Impact analiza
GitNexus `impact()` za `filtriraj()` (`draft_aggregation_service.py`):
**HIGH**, 6 povezanih simbola (root+dist_client duplikat lanca
`_filtriraj_stavke` → `_dispatch_known_tool` → `_execute_tool`).
`agregiraj()` strukturno identično ali GitNexus ocijenio LOW — tretirano
identično objema funkcijama zbog iste klase problema i dijeljenog koda.
Korisnik obaviješten po AGENTS.md "Handoff visokog rizika" formatu prije
izmjene (u razgovoru), `project_rooms/2026-08-09_filtriraj-agregiraj-
target-fallback.md` napravljen prije izmjene, sada spojen u ovaj izvještaj
i obrisan.

## Reprodukcija prije izmjene
Korisnikov stvaran chat primjer (screenshot): pitao "Pronađi mi sve
proizvode bez tarifnog broja" dok je Faktura status bedž pokazivao "19 bez
tarife"; agent odgovorio "🔎 Pronađeno 1 naimenovanja: Rb.1: —". Reprodukcija
u kodu: `filtriraj(draft, uslovi=[{polje:"tarifa", operator:"prazno"}])`
(bez eksplicitnog target-a) na draftu sa praznim `items` i 19 `invoice_
lines` bez tarife → prije fix-a bi koristio default `target="items"` i
vratio 0-1 umjesto 19. Root cause potvrđen praćenjem odgovora formata
("🔎 Pronađeno N naimenovanja:") do `_filtriraj_stavke`, zatim do
`FIELD_MAP`/`_rows_for`/default parametra u `draft_aggregation_service.py`.

## Kontekst korišćen
`docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md` (cijeli — za razumijevanje
šireg konteksta alata prije nego što je konkretan bug prijavljen),
`gui/tabs/agent/agent_controller.py` (status bedž "bez tarife" logika,
da se potvrdi da broji `invoice_lines`, ne `items`), stvaran XML/kod
za `_filtriraj_stavke`/`_agregiraj_stavke`/`filtriraj`/`agregiraj` u
cijelosti pročitan prije izmjene.

## Šta je urađeno
1. `_resolve_target(draft, target)` u `draft_aggregation_service.py` —
   ako `target` nije eksplicitno naveden i `draft.items` je prazan dok
   `invoice_lines` nije, vraća `("invoice", napomena)`; inače vraća
   navedeni/postojeći default bez izmjene.
2. `agregiraj()`/`filtriraj()`: `target: str = "items"` → `target:
   Optional[str] = None`, pozivaju `_resolve_target()` na početku, dodaju
   `napomena` u rezultat kad postoji.
3. `_agregiraj_stavke()`/`_filtriraj_stavke()` (`chat_intent_handler.py`):
   ne kolabuju `args.get("target")` na `"items"` prije poziva servisa —
   prosljeđuju `None` ako LLM nije naveo target, čitaju stvaran `target`
   iz rezultata za labele, prikazuju `napomena` na vrhu odgovora.
4. `SYSTEM_PROMPT` (pravilo 6) i opisi `target` parametra u `TOOLS`
   definicijama — eksplicitno uputstvo LLM-u da IZOSTAVI target osim kad
   korisnik eksplicitno pomene "naimenovanja"/"Rb."
5. 4 nova testa (`test_draft_aggregation_service.py`, root+dist_client):
   tačna reprodukcija bug-a (19 vs 1), potvrda da eksplicitan
   `target="items"` ostaje nepromijenjen (bez fallback-a), potvrda da
   fallback NE aktivira kad items već postoje.

## Zašto je urađeno
Direktan, reprodukovan korisnikov bug — status bedž i agent chat davali
kontradiktorne brojeve za isto pitanje o istoj deklaraciji, što korisnik
opisao kao razlog zašto "cijeli ovaj način rada gotovo beskorisan". Ovo
nije bio problem LLM-ovog razumijevanja teksta (namjera "proizvodi bez
tarife" je ispravno prepoznata i ispravan alat pozvan) — bio je problem
u tome ŠTA alat pretražuje kad kontekst (workflow stage) nije eksplicitno
naveden.

## Kako je urađeno
Praćenje response formata unazad do izvornog koda (ne pretpostavka), zatim
provjera XML-a/koda status bedža da se potvrdi da postoji stvaran mismatch
u OBJEKTU koji se broji (invoice_lines vs items), ne u LOGICI filtriranja
same (`_primijeni_uslove`/`FIELD_MAP` su bili ispravni). Fallback dizajniran
da NIKAD ne aktivira kad je target eksplicitan (distinkcija `None` vs
`"items"` string vrijednosti u `args.get()`) — čuva postojeće ponašanje za
sve pozive koji već rade ispravno.

## Šta nije dirano
- `pretrazi_stavke` — drugačiji alat (tekstualna pretraga po `naziv_robe`),
  nije pogođen ovim bug-om (već koristi `target="all"` po defaultu).
- `_rows_for()`, `_primijeni_uslove()`, `FIELD_MAP` — logika filtriranja
  je bila ispravna, problem je bio isključivo u default target izboru.
- `target="all"` opcija — namjerno NIJE reintrodukovana (ranija odluka od
  2026-08-05, vidi `agent-agregacija-filtriranje-stavki` memoriju).

## Verifikacija
- `python -m py_compile` na svih 6 izmijenjenih `.py` fajlova — OK.
- `diff` root/dist_client za sva 3 izmijenjena koda-fajla — identično
  (exit 0) nakon izmjene.
- `pytest tests/unit/test_draft_aggregation_service.py -v` — 13/13 passed
  (9 postojećih + 4 nova), uključujući tačnu reprodukciju bug-a.
- `pytest tests/unit -q` (pun suite): 1557 passed (bilo 1553), 71 skipped,
  5 xfailed, 2 failed — isti pre-existing neuspjesi kao ranije danas,
  NE regresija.
- GitNexus `detect_changes(scope=unstaged)` prije commit-a: risk LOW,
  0 affected_processes, scope tačno odgovara planiranim fajlovima.

## Nezavisna provjera
- Checker korišćen: NE
- Obavezno razmotreno za HIGH (filtriraj) po AGENTS.md, ali nije sproveden
  kao poseban agent/model — umjesto toga: (a) korisnik upoznat sa punim
  HIGH nalazom prije izmjene kroz "Handoff visokog rizika" format u
  razgovoru, (b) izmjena je additivna/uska (novi helper + signature
  promjena default vrijednosti, bez izmjene postojeće filter/agregacija
  logike), (c) verifikovana regresionim testovima koji EKSPLICITNO
  pokrivaju i stari (eksplicitan target) i novi (fallback) put.
- Šta NIJE provjereno: ponašanje u produkcijskom chatu uživo (LLM stvarno
  bira da izostavi target za ovakva pitanja) — SYSTEM_PROMPT izmjena je
  heuristička (savjet LLM-u), deterministički fallback u kodu je stvarni
  garant ispravnosti bez obzira na LLM ponašanje.

## Pronađeni problemi
Nema novih van glavnog nalaza.

## Odbačene opcije
- Opcija: uvesti `target="all"` koji pretražuje i invoice i items i vraća
  oba broja odvojeno (uvijek tačno, eliminiše nagađanje potpuno).
- Zašto je razmatrana: potpuno robustno rješenje bez ikakve heuristike.
- Zašto je odbačena: raniji rad (2026-08-05) je eksplicitno uklonio
  `target="all"` opciju iz Crush-ovog predloga jer bi mogla navesti na
  miješanje invoice_lines/items u istom odgovoru (AGENTS.md zabrana).
  Auto-fallback postiže isti praktičan cilj (tačan odgovor za prijavljen
  scenario) bez tog rizika — bira TAČNO JEDAN target na osnovu stvarnog
  stanja drafta.
- Kada odluku ponovo otvoriti: ako se pokaže da fallback heuristika
  (items prazan → invoice) i dalje daje pogrešne odgovore u nekom drugom
  scenariju (npr. items ima par stavki ali korisnik ipak misli na
  invoice) — razmotriti eksplicitan "oba odvojeno" prikaz kao dodatnu
  opciju.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `1c0c1fe` | fix(agent): filtriraj_stavke/agregiraj_stavke ne pretpostavljaju "items" kad su naimenovanja prazna |

## Rizici / ograničenja
- Fallback se aktivira SAMO kad je `draft.items` TAČNO prazan (0 entries).
  Ako naimenovanja postoje ali ih je drastično manje od invoice_lines
  (npr. 2 naimenovanja kreirana ručno dok 17 fakturnih linija još čeka),
  fallback se NEĆE aktivirati i isti tip problema mogao bi se ponovo
  desiti u toj sivoj zoni — namjerno konzervativan prag (samo prazno)
  da se izbjegne nagađanje u nejasnim slučajevima.
- SYSTEM_PROMPT izmjena je savjet LLM-u, ne garancija — LLM i dalje MOŽE
  eksplicitno proslijediti `target="items"` kad ne treba; u tom slučaju
  fallback se neće aktivirati (po dizajnu, poštuje eksplicitan izbor) i
  odgovor će i dalje moći biti pogrešan za taj rijedak slučaj.

## Potreban follow-up
Pratiti da li se sličan "workflow stage mismatch" pojavljuje i u drugim
alatima (`prikazi`, `provjeri`) koji takođe imaju `items`/`invoice`
target — nije sistematski provjereno van `filtriraj_stavke`/`agregiraj_
stavke`.

## Potrebna korisnička potvrda
Ručna provjera u pokrenutoj aplikaciji: isto pitanje kao u bug reportu
("Pronađi mi sve proizvode bez tarifnog broja" dok su naimenovanja još
prazna) treba sad vratiti tačan broj (odgovarajući status bedžu) uz
napomenu da su pretražene fakturne linije.

## Addendum (isti dan) — prikazi="broj" primjer skidao listu iz odgovora

Odmah nakon gornjeg fix-a korisnik prijavio: "ne želim samo broj 19, nego
nazive proizvoda i redne brojeve u tabu faktura". Uzrok: SOPSTVENI
SYSTEM_PROMPT primjer napisan u fix-u iznad je eksplicitno predlagao
`prikazi="broj"` za upit istog oblika ("Koliko stavki nema X") — LLM je
taj primjer pratio doslovno, iako je podrazumijevani mod alata
(`prikazi="oboje"`, nedirano nikad) već ispravno vraćao i listu (naziv +
redni broj). Fix: primjeri u `SYSTEM_PROMPT`-u (`services/agent/chat/
tool_definitions.py` + dist_client) više ne navode `prikazi="broj"` za
opšte "koliko/pronađi" upite, dodato eksplicitno pravilo da odgovor MORA
sadržati naziv i redni broj svake stavke osim ako korisnik EKSPLICITNO
traži samo broj. Čista prompt-tekst izmjena, bez promjene koda/logike.
Pun test suite ponovo pokrenut: 1557 passed, isti 2 pre-existing neuspjeha.
Commit `8e0260f`.

**Pouka**: SYSTEM_PROMPT primjer koji eksplicitno navodi vrijednost za
parametar sa sigurnim defaultom efektivno mijenja to ponašanje za LLM —
provjeriti prije dodavanja primjera da li se time slučajno odstupa od
željenog defaulta.

## Addendum 2 (isti dan) — eksplicitan LLM target nije bio pouzdan signal

Korisnik restartovao aplikaciju (potvrdio da je prvobitni retest bio bez
restarta, dakle nevažeći) i ponovio identično pitanje — isti rezultat kao
prije prvog fix-a ("1 naimenovanje: Rb.1: —", bez napomene). Oborena
pretpostavka iz prvog dijela ovog izvještaja da "LLM eksplicitno navodi
target = stvarna namjera korisnika" — LLM (Groq) očigledno šalje
`target="items"` eksplicitno, bez obzira na SYSTEM_PROMPT uputstvo (dodato
u istom fix-u) da ga izostavi.

**Fix**: `_resolve_target()` prepravljen — prebacuje na skup koji STVARNO
ima podatke BEZ OBZIRA na to da li je LLM poslao target eksplicitno.
Izuzetak "eksplicitan target se poštuje" je UKINUT (bio pogrešna
pretpostavka). Fallback se aktivira i za `target="items"` eksplicitno
poslat kad je items prazan a invoice ima podatke; simetrično za obrnut
slučaj. Ne aktivira se JEDINO kad ni jedan skup nema podatke (nema
alternative). 3 nova/izmijenjena testa (root+dist_client), uključujući
tačnu reprodukciju drugog prijavljenog testa (eksplicitan `target="items"`
prazan → invoice, ranije je ovaj test tvrdio SUPROTNO ponašanje kao
namjerno — ta ranija tvrdnja je bila netačna pretpostavka, ne bug u testu).
Pun test suite: 1560 passed, isti 2 pre-existing neuspjeha. Commit
`bb6e07e`.

**Ključna pouka**: prompt-tekst uputstvo LLM-u NIJE dovoljno pouzdano kao
JEDINI mehanizam ispravnosti — potvrđeno dva puta istog dana (pogrešan
primjer naveo LLM na pogrešan mod; ispravno uputstvo ignorisano). Kod mora
biti deterministički ispravan nezavisno od toga šta LLM zaista pošalje;
prompt tekst samo smanjuje VJEROVATNOĆU da LLM uopšte zatraži pogrešnu
stvar, ne garantuje je.

## Ljudsko usvajanje rezultata
- Odgovorna osoba: <<< >>>
- Izvještaj pročitan u cijelosti: <<< DA/NE >>>
- Ključne odluke razumljive i prihvaćene: <<< DA/NE/PARCIJALNO >>>
- Ključne tvrdnje/rezultati provjereni (ne samo agentova tvrdnja da radi): <<< DA/NE/NIJE PRIMJENJIVO >>>
- Rezultat predstavlja stvarno prihvaćeno stanje: <<< DA/NE >>>
- Dijelovi koji još nisu ljudski potvrđeni: <<< >>>
- Dozvoljena naredna akcija: <<< >>>
