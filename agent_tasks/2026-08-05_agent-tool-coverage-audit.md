# Agent Task — Audit pokrivenosti agent alata (SUSSINA-klasa bugova)

**Datum:** 2026-08-05
**Kreirao:** Claude Sonnet (nadzorni agent)
**Executor:** Crush / Pi agent
**Status:** ČEKA

---

> **IDE agent** (Crush, Pi, Qwen Code...): `AGENTS.md` već imaš u kontekstu — preskoči sekciju "Obavezno čitanje".
> **API/chat agent**: pročitaj `AGENTS.md` (root) prije početka.

---

## Obavezno čitanje prije početka

1. `AGENTS.md` (root) — projektni standardi, Korak 1-5 procedura
2. Fajlovi navedeni u sekciji "Fajlovi za čitanje"

---

## Kontekst

Korisnik je prijavio stvaran bug: pitanje agentu "Koliko ima proizvoda SUSSINA" dalo je
pogrešan, samoprotivrečan odgovor (agent je promašio jednu stavku i sam sebi protivrečio
u istom odgovoru — "3 proizvoda" pa "4 fakturne linije"). Root cause NIJE bio "LLM je
glup" — bila je konkretna rupa u alatima: `prikazi`/`provjeri` (jedina dva alata koja
pipaju stavke deklaracije) nemaju parametar za tekstualnu pretragu, pa je LLM morao RUČNO
brojati/skenirati iz snapshot teksta cijelog drafta — nepouzdano po definiciji, bez obzira
koliko je model dobar.

Popravka za taj konkretan slučaj je urađena (novi alat `pretrazi_stavke`, commit
`2c28ed5`, `agent_reports/2026-08-05_agent-pretraga-stavki-po-nazivu.md`), ali to je bio
samo JEDAN primjer. Sumnja je da postoje DRUGE slične rupe.

Ovo se nadovezuje na tvoj raniji `docs/agent/AGENT_TAB_CODE_AUDIT.md` (2026-08-04), koji je
već identifikovao da je `ChatIntentHandler` (3035 linija) monolit sa dupliranom logikom —
to arhitektonsko stanje čini ovu klasu buga vjerovatnijom (teško je znati koji alat već
postoji kad je logika razbacana/duplirana na više mjesta).

---

## Zadatak

**Ovo je AUDIT zadatak — NE implementirati ništa, samo istražiti i predati izvještaj.**

Pronaći druge moguće "SUSSINA-klase" rupe: upite koje korisnik realno može postaviti
agentu tokom rada na deklaraciji, a za koje trenutni set alata
(`services/agent/chat/tool_definitions.py:TOOLS`) nema odgovarajući deterministički alat —
pa LLM mora sam računati/brojati/porediti/agregirati iz teksta koji mu se vrati, umjesto da
dobije gotov, tačan odgovor od koda.

Za svaki alat u `TOOLS` provjeri:
1. Šta alat STVARNO vraća LLM-u (pun tekst snapshot-a? strukturiran sažetak? tačan
   izračunat broj?) — pogledaj implementaciju u `chat_intent_handler.py`, ne samo opis u
   `tool_definitions.py`.
2. Da li LLM mora dalje SAM obrađivati taj rezultat (brojati, porediti, sumirati,
   filtrirati, tražiti ekstrem) da bi tačno odgovorio korisniku.
3. Ako da — to je kandidat za istu klasu buga kao SUSSINA.

Primjeri upita za testiranje (razmisli i o drugim realnim upitima, ne samo ovima):
- "Koja je ukupna vrijednost svih stavki sa tarifom X?"
- "Koliko stavki nema popunjenu zemlju porijekla?"
- "Koje naimenovanje ima najveću bruto masu?"
- "Da li se neki tarifni broj ponavlja u više naimenovanja?"
- "Koliko fakturnih linija je iz fakture broj X?"
- "Koja stavka ima najveću vrijednost/najmanju maržu/itd.?"

---

## Fajlovi za čitanje (obavezno)

- `services/agent/chat/tool_definitions.py` — `TOOLS` lista, `SYSTEM_PROMPT` (šta LLM zna
  da treba pozvati i kada)
- `services/agent/chat/tool_policy.py` — `TOOL_EFFECTS` (svi registrovani alati, uključujući
  stara imena zadržana kao backward-compat)
- `gui/tabs/agent/services/chat_intent_handler.py` — `_dispatch_known_tool` (elif lanac) i
  sve `_pretrazi_*`/`_pregledaj_*`/`_provjeri_*`/`_dispatch_*` funkcije — šta svaki alat
  STVARNO vraća (puni tekst vs strukturiran/izračunat rezultat)
- `agent_reports/2026-08-05_agent-pretraga-stavki-po-nazivu.md` — puna analiza SUSSINA
  slučaja, koristi kao referentni template za "kako izgleda ova klasa buga"
- `core/draft/draft.py` — `InvoiceLine` / `NaimenovanjeDraft` / `DeclarationDraft` polja
  (da znaš šta je uopšte dostupno za agregaciju/računanje)

---

## Norme koje se primjenjuju

- Srpski field names (`tarifni_broj`, `naziv_robe`) — ne engleski, osim `NaimenovanjeDraft`
  koji je namjerno na engleskom (vidi AGENTS.md)
- **Ne implementirati ništa u ovom zadatku** — samo audit + preporuka, korisnik odlučuje
  šta se dalje radi
- Ne diraj `tests/test_origin_intent_routing.py` — poznato slomljen (nepovezan import bug),
  van scope-a
- Ne diraj stara imena alata (`prikazi_naimenovanja`, `provjeri_naimenovanja`,
  `provjeri_tarife`, `validuj_deklaraciju`) — namjerno uklonjena iz `TOOLS` tokom "Faza 1
  konsolidacije", zadržana samo kao backward-compat executor grane u
  `_dispatch_known_tool`/`TOOL_EFFECTS`. Ne predlaži njihovo vraćanje niti brisanje kao dio
  ovog audita — to je poseban nalaz, van ovog scope-a.
- GitNexus impact analiza nije potrebna za sâm audit (ne mijenja se kod) — ali za svaki
  predloženi novi/prošireni alat, navedi koje bi funkcije/fajlove trebalo dirati, da
  sledeći korak (implementacija) zna odakle da krene.

---

## Provjera (kako znamo da je završeno)

- [ ] Svaki alat u `TOOLS` je klasifikovan: "vraća tačan/strukturiran rezultat" ili "vraća
      sirov tekst koji LLM mora dalje obrađivati"
- [ ] Lista konkretnih korisničkih upita (minimum 8-10) za koje trenutno NE postoji
      pouzdan/deterministički put do tačnog odgovora
- [ ] Za svaki nalaz: koji alat bi trebalo dodati/proširiti, grubo koji podaci/funkcija bi
      mu trebali (bez pisanja koda)
- [ ] Nalazi rangirani po prioritetu (koji upiti su najvjerovatniji da se realno postave
      tokom rada na deklaraciji, ne egzotični rubni slučajevi)

---

## Output format (obavezan pri predaji)

Kreirati `docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md`, u istom stilu kao
`docs/agent/AGENT_TAB_CODE_AUDIT.md` (naslov, Datum revizije, Opseg, Metodologija,
numerisane sekcije, Zbirni pregled na kraju, "Reviziju izvršio: ...").

```
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: (očekivano: samo novi audit .md fajl, ništa drugo)
ŠTA JE URAĐENO: kratak opis
PITANJA: lista nejasnoća (ako postoje)
```
