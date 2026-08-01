# AGENTS.md — Deklarant Pro projektni standardi (KANONSKI FAJL)

Ovaj fajl je **jedini izvor istine** za sve agente koji rade na ovom projektu:
Claude Code, Codex, Cursor, GitHub Copilot, DeepSeek, GLM, Kimi, MiniMax, Qwen i drugi.
`CLAUDE.md` u korijenu samo importuje ovaj fajl i dodaje Claude-specifičnu memoriju —
**sva pravila se mijenjaju OVDJE**, ne u CLAUDE.md.

---

## Jezik — OBAVEZNO I PRIMARNO

- Svi odgovori korisniku: **srpski, latinica**
- Nikada ćirilica — nigdje, ni u komentarima ni u stringovima koji se prikazuju
- Nikada engleski (osim ako korisnik eksplicitno traži)
- Komentari u kodu: engleski (prati stil koji fajl već koristi)
- Commit poruke: srpski latinica, format `tip(scope): opis`

---

## Kontekst projekta — pročitaj prije kodiranja

**OBAVEZNO: Pročitaj `docs/CONTEXT.md` prije bilo kakvog kodiranja.**

Taj fajl sadrži ne-trivijalne odluke, zabranjene patterne i poznate bugove
koji nisu vidljivi iz samog koda. Dostupan je svim agentima jer je u git repozitoriju.

```text
docs/CONTEXT.md          ← evergreen pravila (sekcije 1-14) — pročitati cijeli, kratak je
docs/context/history.md  ← dated hronologija sesija — NE čitati cijeli, samo Grep po temi/datumu
```

> **Samo za Claude:** detaljna sesijska memorija je u
> `~/.claude/projects/<projekat>/memory/` (vidi CLAUDE.md).
> Za sve ostale agente `docs/CONTEXT.md` je autoritativni izvor.

---

## Token budget i context disciplina

Agent ne prenosi cijeli prethodni razgovor u novi zadatak — prenosi
prihvaćeni artefakt (`project_room` fajl, `agent_report`, ili konkretan
plan). Veliki fajlovi (stotine+ linija, npr. `docs/context/history.md`,
`faktura_view.py`) se prvo pretraže (Grep) po relevantnom pojmu; cijeli
fajl se čita samo kad je zadatak stvarno zahtijeva. Za HIGH/CRITICAL
odluke ili kad je potreban širi arhitektonski uvid, potpunost ima
prednost nad štednjom konteksta — ne štedjeti tokene na račun tačnosti.

---

## Paralelni agenti — izolacija working tree-a

Na ovom projektu stvarno rade više agenata paralelno u istom working
tree-u (Claude Code, Codex i drugi — potvrđeno, ne hipotetički: vidi
`agent_reports/2026-07-30_token-disciplina-context-split.md`, sekcija
"Pronađeni problemi", gdje je Codex-ov automatizovan commit pokupio
nekomitovane Claude-ove izmjene jer su oba agenta radila u istom working
tree-u u isto vrijeme).

Pravila:

- **Nikad `git add -A`/`git add .`** — uvijek navesti tačne fajlove koje
  je TAJ zadatak izmijenio.
- **Prije svakog `git add` i prije svakog `git commit`** provjeriti
  `git status --short` i `git log --oneline -1` (da vidiš da li se HEAD
  pomjerio od početka zadatka). Ako ima nepoznatih izmjena u working
  tree-u, prvo utvrditi čije su — mogu biti WIP drugog agenta.
- Ako se otkrije da je paralelan agent pokupio tvoje nekomitovane
  izmjene u svoj (nepovezan) commit — sadržaj nije izgubljen, ali
  numeracija/nazivi (npr. dated sekcije u `docs/context/history.md`)
  mogu se sudariti; provjeriti i poravnati prije nastavka, ne prepisivati
  tuđ rad bez provjere.
- Dugotrajni/automatizovani agent pipeline-ovi (npr. Codex faze koje rade
  u nizu commit-ova bez ljudskog pregleda svakog koraka) trebaju,
  gdje je moguće, raditi u zasebnom `git worktree` (`.worktrees/<tok>/`)
  umjesto direktno na `windows` working tree-u koji dijele interaktivne
  sesije — ovo nije uvijek pod kontrolom Claude sesije, ali je vrijedno
  predložiti korisniku kad se primijeti da se pattern ponavlja.

---

## Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš uraditi.
Čekaj potvrdu korisnika prije implementacije ako zadatak nije jednoznačan.

**Facts vs Decisions**: agent ne pita korisnika ono što može sam
provjeriti u kodu/repou (to je "fact", ne "decision"). Agent ne smije sam
odlučiti ono što je poslovna/UX/arhitektonska odluka samo zato što je
usput otkrio relevantnu tehničku činjenicu. Kad je pitanje stvarno za
korisnika, format:

```markdown
## Fact found
<<< tehnička činjenica koju si utvrdio (sa referencom) >>>

## Decision required
<<< konkretno pitanje koje samo korisnik može odlučiti >>>

## Recommendation
<<< tvoj predloženi odgovor i zašto >>>

## Consequence
<<< šta se dešava ako se ide suprotnim putem >>>
```

**Confirmation gate za veće/nejasne zadatke** (ne za svaku sitnicu):
prije implementacije, prikazati kratak "Shared Understanding Check" —
cilj, ključne odluke, otvorena pitanja, pretpostavke, predloženi sljedeći
korak — i sačekati potvrdu. Za mali, jednoznačan zadatak dovoljna je
gornja rečenica "šta sam razumio", bez posebnog gate-a.

---

## Reprodukcija i provjera prije rada (verify before brief)

**Bugfix**: bug se ne popravlja dok nije reprodukovan, osim kad je jasno
dokumentovano zašto reprodukcija nije moguća. Prihvatljivi dokazi: failing
test, minimalna reprodukcijska skripta, konkretan ulaz (faktura iz
`najavauvoza/`, XML, upit), log sa preciznim podacima i greškom,
screenshot/video stvarnog GUI ponašanja, precizno opisan ručni postupak,
ili stanje baze + upit koji izaziva problem.

Ako reprodukcija nije moguća, zapisati u `agent_report` (polje
"Reprodukcija prije izmjene"): šta je pokušano, zašto problem nije
reprodukovan, na kojoj pretpostavci se zasniva predložena izmjena, i koji
dodatni rizik zbog toga ostaje.

Ne mijenjati kod samo zato što pronađena implementacija izgleda sumnjivo
— "izgleda sumnjivo" nije isto što i "dokazano je uzrok problema". Ovo
dopunjuje "Provjeri hipotezu" korak u "Format zadatka za agenta" ispod —
tamo je pravilo za korisnikovu hipotezu, ovdje je zahtjev za KONKRETAN
dokaz prije izmjene koda.

**Feature/enhancement**: prije prihvatanja zadatka, potvrditi da
funkcionalnost već ne postoji (grep/pretraga postojećeg koda) i da
postoji stvarna korisnička potreba, ne samo pretpostavka da bi bilo
korisno.

**Eksterni/tuđi predlog koda** (patch od drugog agenta bez nezavisne
provjere, kod predložen van ove sesije): prije usvajanja — checkout,
pokrenuti testove, pregledati diff. Tek onda odluka o prihvatanju.

---

## PROBE — kad postoji stvarna nepoznanica

Za zadatke koji zahtijevaju istraživanje, ne implementaciju: nepoznato
ponašanje PySide6/Qt-a ili Windows štampača, neprovjerene performanse
(npr. koliko traje SMART_GROUP/`create_smart_group()` za 500+ stavki),
nepoznat format novog dobavljača prije pisanja parsera, dilema između
arhitektura. `PROBE` NE proizvodi produkcionu funkcionalnost — cilj mu je
da odgovori na JEDNO konkretno pitanje.

Rad na probe-u ide na throwaway granu/worktree (`probe/<pitanje>`) —
NIKAD se ne mergea u `windows`. Ako se pokaže vrijednim, prototip se ili
baci i implementira pravilno, ili se zadrži samo dokazani dio iza novog
interfejsa — nikad se ne "očvršćava" na licu mjesta u produkcioni kod.

Obavezan izlaz (u `agent_report` ili kratkom fajlu vezanom za probe):

```markdown
# Pitanje
# Pretpostavka
# Način provjere
# Rezultat
# Dokaz (test, screenshot, benchmark, primjer izlaza, log, mali prototip)
# Ograničenja rezultata
# Preporuka
# Odluka koju sada možemo donijeti
```

---

## Tech stack

| Sloj | Tehnologija |
| --- | --- |
| GUI | PySide6 (Qt6) |
| Baza | PostgreSQL 16 (server `dmserver`, IP je DHCP — čitati iz `.env` preko `config/settings.py`, ne hardkodovati) + SQLite lokalno |
| Python | 3.11+, uv za pakete |
| Testovi | pytest, `tests/` folder |
| Parseri | pdfplumber, openpyxl, pytesseract (OCR) |

---

## Arhitektura

```text
deklarant_pro/
├── core/draft/          # Draft modeli: DeclarationDraft, InvoiceLine, NaimenovanjeDraft
├── gui/tabs/            # GUI tabovi (agent_tab, faktura_tab, naimenovanja_tab...)
│   └── agent/
│       ├── agent_controller.py      # Tanak controller — samo 1-liner wrapper metode
│       └── services/                # Sva logika izvučena ovdje
│           ├── xml_workflow_service.py
│           ├── import_pipeline_service.py
│           └── chat_intent_handler.py
├── importers/           # PDF/Excel parseri po dobavljaču
├── services/            # Business logika
│   └── agent/
│       ├── chat/        # intent_classifier, chat_memory, namjere
│       ├── tariff/      # hybrid_tariff_agent, rag, matching
│       ├── learning/    # historical_learning, exporter_xml_indexer
│       └── validation/  # declaration_validator, xml_template_service
├── database/            # SQLite: deklarant_sistem.db, zvanicna_tarifa.db
├── dist_client/         # Windows-runtime kopija (može zaostati za gui/ — uporedi pri vizuelnim bugovima)
└── ui/                  # Qt .ui fajlovi
```

**Pattern za services/agent/:** slobodne funkcije koje primaju `ctrl` kao prvi argument,
servisna klasa ih omotava kao public API. Controller metode su samo 1-liner pozivi servisa.

### 3-layer pattern za tabove (OBAVEZNO)

Svaki tab/modul je podijeljen na tri sloja — **ne miješati slojeve**:

```text
View       — samo UI, signali, prikaz podataka, NEMA business logike
Controller — orchestration, event handling, povezuje View ↔ Service
Service    — sva business logika, DB operacije, kalkulacije
```

Signali su jedini ispravni način komunikacije prema gore (View ne poziva
Controller metode direktno). Business logika ili DB konekcija u View-u je greška.

---

## Ključne konvencije

### Kod

- **Nema novih komentara** osim za neočigledne workarounds ili skrivene invarijante
- **Nema docstrings** na metodama koje slijede jasne naming konvencije
  (novi docstrings, gdje su stvarno potrebni, pišu se na srpskom latinici)
- **Ne miješati refactor i funkcionalnu izmjenu u istom zadatku/commit-u**
  — teško je dokazati šta je promijenilo ponašanje kad su izmiješani.
  Sitno čišćenje nastalo u istom koraku (očigledna duplikacija, ime
  varijable) je OK; veći refactor (pomjeranje granice modula, novi sloj)
  ide u poseban zadatak, čak i ako ga review otkrije usput
- Fuzzy matching threshold: `min_similarity = 0.92` (ne spuštati bez eksplicitnog razloga)
- SQL: isključivo parametrizovani upiti — nikad f-string u SQL-u
- Debug ispisi: emoji za vizualnu identifikaciju (🔍, ✅, ⚠️, 📝) — ali NIKAD direktno
  na stderr (cp1252 na Windowsu puca); koristiti logger
- Error handling: jasne poruke na srpskom

### Imenovanje polja — KRITIČNO

`InvoiceLine` i srodni modeli koriste **srpske nazive polja** — namjerno, ne mijenjati
na engleski (lomi sve importere): `tarifni_broj`, `naziv_robe`, `zemlja_porijekla`,
`povlastica`, `bruto_kg`, `neto_kg`, `iznos`, `kolicina`, `jm`, `eur1_number`.
Izuzetak: **NaimenovanjeDraft koristi engleski** (`tariff_code`, `goods_description`,
`origin_country_code`) — konzistentno s ASYCUDA XML formatom, takođe ne mijenjati.

### Tarifni broj format

- Interno **8 cifara bez tačaka**: `08052190`; PostgreSQL baza ima **10 cifara**: `0805219000`
- Konverzija pri PG lookup-u: dodati `'00'` na kraj
- Nikad ne čuvati format s tačkama (`0805.21.90`); normalizacija: `re.sub(r'\D', '', raw)[:10]`

### Formatiranje težina (bruto/neto kg)

- Puna preciznost (ne zaokruživati na 2 decimale)
- Separator za hiljade (zarez): `1,234.567`
- Referenca: `_format_weight()` u faktura_tab_v2.py

### Parseri (importers/)

- Svaki importer mora imati `exporter` i `importer` polja u `ImportResult`
- XML lookup se radi po paru `(exporter, tariff_code)` — ne samo po tariff_code
- CBBH kurs se čita iz baze, ne hardkoduje
- **Auto-detekcija formata**: svaki importer ima `detect_*` funkciju
- **Blagić Loren**: jedinica mjere može biti bilo koja riječ (regex: `[a-zA-Z]{1,10}`)
- **IMAMOGLU**: dvofazno parsiranje (kodovi/opisi na str. 1-2, cijene na str. 4-5)
- **Težine**: uvijek ekstraktovati gross/net weight iz PDF-a
- **Rezultat**: uvijek vraća `ImportResult` sa items, bruto_kg, neto_kg
- **OBAVEZNO — `consumed_paths`** za kombinirane importere (puno pravilo + primjeri
  dobavljača: `docs/CONTEXT.md` §1) — bez toga agent procesira oba fajla zasebno →
  duplikati stavki u deklaraciji
- **OBAVEZNO — `incoterm_code`**: svaki importer koji ekstraktuje puni tekst fakture
  (PDF, ili Excel+PDF kombinacija) MORA pozvati `detect_incoterm(full_text)` iz
  `importers/incoterm_utils.py` i proslijediti rezultat kao `incoterm_code=...` u
  `ImportResult` — popunjava Rb.20 "Uslovi isporuke" u Zaglavlju. Paritet je pravno
  obavezan podatak u carinjenju, pa je detekcija namjerno konzervativna (samo uz
  poznatu oznaku: "Incoterms", "Paritet isporuke", "Uslovi isporuke", "Delivery terms");
  ako izostane poziv ili paritet nije prepoznat, Rb.20 jednostavno ostaje prazan za
  ručni unos (nije greška, samo propuštena auto-popuna). Excel-only importeri bez
  slobodnog teksta (nema PDF-a) mogu ovo preskočiti.

### GUI konvencije

- **QTextEdit** za multi-line prikaze (ne QLineEdit)
- **Read-only polja** za auto-popunjene vrijednosti
- **Word wrap** omogućiti gdje je potrebno

### XML template (xml_template_service.py)

- Rb.48/`TEMPLATE_FIELDS` pravila (šifra odgođenog plaćanja se ne prepisuje iz
  historijskog XML-a, mijenjati samo whitelist) — puno pravilo: `docs/CONTEXT.md` §3

### Naimenovanja

- Rb.31 auto-opis se generiše po tarifi, ne prepisuje iz fakture
- **Trgovački naziv (`le_r31_trg_naziv`)**: prikazuje sve nazive proizvoda iz fakture koji
  pripadaju tom naimenovanju (comma-separated / multi-line, QTextEdit)
- ASYCUDA XML Rub.31 max 280 znakova/3 linije — puno pravilo: `docs/CONTEXT.md` §3
- **Grupiranje po 4 ključa** (svi moraju biti identični): `tarifni_broj`, `zemlja_porijekla`,
  `povlastica`, `eur1_number` — koristiti `CreateNaimenovanjaService.create_smart_group()`,
  ne pisati vlastitu logiku grupiranja

### Auto-popunjavanje tarifnih brojeva

- **TariffMappingService**: mapiranje product_code/naziv_robe → tarifni_broj
- Matching prioritet: 1) tačan match po `product_code`, 2) fuzzy match po nazivu (>85%)
- Auto-učenje: sistem pamti mapiranja pri kreiranju naimenovanja
- Database: tabela `product_tariff_mapping` u deklarant_sistem.db
- ⚠️ Poznati obrazac buga: jedna ručna greška postane "naučen" trajni bug jer exact-match
  nadjača fuzzy logiku (3x viđeno: GREJAC SPIRALA, Plamenik 540101...)

### LLM / Agent integracija

- Primarni provider: Groq; fallback: Gemini (samo free modeli — DeepSeek isključen)
- Koristiti `LLMProvider` klasu (`gui/tabs/agent/widgets/llm_provider.py`) —
  **ne pozivati providere direktno** (zaobilazi fallback logiku)
- Streaming kroz `provider.stream_chat()`, batch kroz `provider.complete()`
- QThread workeri za sve LLM pozive — nikad blokirati UI thread

### Baza podataka

- `deklarant_sistem.db` (SQLite) — mappinzi, šifrarnici, lokalni podaci
- `zvanicna_tarifa.db` (SQLite) — samo čitanje, carinska tarifa
- PostgreSQL — `catalogs` schema; context manager (`with conn:`) za transakcije
- `blockSignals(True/False)` pri bulk operacijama na Qt tabelama (vidi CONTEXT.md §5)

---

## Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
| --- | --- |
| Direktni `import` iz `gui/tabs/agent/agent_controller.py` u servis | Kružni import |
| Mijenjati `TEMPLATE_FIELDS` van `xml_template_service.py` | Single source of truth |
| Hardkodovati IP adresu servera u kodu | Mora biti u aktivnom `.env` fajlu (`root` ili `dist_client`, zavisno od pokretača) |
| Dodavati UI logiku u servisne klase | Narušava razdvajanje slojeva |
| Brisati stub fajlove u `services/agent/` bez provjere importa | Backward compat |
| f-string za QSS blokove | CSS `{}` puca u f-stringu — koristiti `.replace("PLACEHOLDER", ...)` |
| `return None` u `tab_factory`/`create_tab()` except bloku | Skriva greške — uvijek `raise` |
| Pozivati Groq/Gemini direktno bez `LLMProvider` | Nema fallback logike |
| Logika grupiranja naimenovanja van `CreateNaimenovanjaService` | Duplikacija, greške |
| Mijenjati srpske field names na modelima | Lomi sve importere |
| `mock` za SQLite/PostgreSQL u testovima | Maskira realne greške |
| Zaokruživati težine na 2 decimale | Gubi se preciznost pri carinskom obračunu |
| Miješati `draft.items` s `draft.invoice_lines` | Potpuno različiti koncepti |

---

## Format zadatka za agenta (preporučeno)

Za netrivijalne i debug zadatke, korisnik formuliše zadatak po ovom obrascu.
Agent ga prepoznaje i direktno mapira na sekcije agent reporta (Korak 3):

- **Zadatak** — šta treba popraviti/promijeniti
- **Moja radna pretpostavka** — korisnikova hipoteza o uzroku/rješenju
- **Provjeri hipotezu** — agent PRIJE izmjene potvrđuje ili odbacuje
  hipotezu dokazima (baza, kod, logovi) → puni "Zašto je urađeno" i
  "Verifikacija" u izvještaju
- **Granice** — šta agent NE smije dirati (van scope-a) → puni "Šta nije dirano"
- **Šta je dobar ishod** — opis vidljivog/testabilnog rezultata
- **Obavezno** — agent prikazuje impact/rizik i ostavlja agent_report
  → puni "GitNexus impact" i "Rizici / ograničenja"

Ovaj format je preporuka, ne zamjena za Korak 1-5: za sitne, jednolinijske
ispravke (npr. jedan red u bazi, jedna konstanta) format je nepotreban overhead.

---

## Definition of Done po tipu promjene

Promjena nije završena samo zato što se aplikacija pokrenula ili je jedan
test prošao. Obavezan dokaz zavisi od tipa promjene:

- **GUI (PySide6)** — screenshot prije/poslije za vizuelne izmjene;
  provjera realnog korisničkog toka (fokus, tab redoslijed, skrol);
  offscreen render NIJE dovoljan dokaz za nešto što zavisi od stvarnog
  prikaza (monitor, skaliranje, fontovi na Windows-u) — za takve slučajeve
  eksplicitno navesti da je potrebna ručna provjera na stvarnom računaru.
- **Parseri/import** (`importers/`) — fixture/realne fakture iz
  `najavauvoza/`, edge case-ovi (bez kodova, multi-line opisi, različite
  jedinice — vidi "Testiranje" ispod), provjera `consumed_paths`/
  `incoterm_code` gdje su primjenjivi, dokaz da postojeći/stari izvori
  nisu pokvareni (ponovni test na poznatom dobavljaču).
- **XML export / generisani dokumenti** (ASYCUDA, PZT, CMR, DV1) —
  poređenje ključnih polja sa referentnim/ranije ispravnim XML-om;
  provjera specifičnih pravila (Rb.31 max 280 znakova/3 linije, Rb.48 se
  ne prepisuje iz istorijskog XML-a); otvaranje generisanog fajla i
  potvrda da nije korumpiran.
- **Baza i migracije** (PostgreSQL/SQLite) — test na izolovanoj test
  bazi/šemi, backup prije bilo koje migracije na `dmserver`, broj redova
  prije/poslije, transakcija gdje je moguća; NIKAD prvi put testirati na
  produkcionim podacima.
- **Tarifno matching/performanse** — ako se dira `TariffMappingService`/
  `HybridMatchingService` ili slično, mjerenje broja SQL upita ili
  vremena prije/poslije za reprezentativan skup stavki; provjera da
  `min_similarity = 0.92` nije tiho promijenjen bez eksplicitnog razloga.
- **Sigurnost/osjetljivi podaci** — carinski dokumenti sadrže poslovne i
  lične podatke (JIB, imena, adrese, brojevi faktura); ti podaci ne
  završavaju u `agent_report`-u, logovima van postojećeg logger stila,
  niti u promptu preko onoga što je zadatak stvarno zahtijevao.

**Hijerarhija dokaza** (od najjačeg prema najslabijem — koristiti
najjači koji je razumno dostupan):

```text
1. deterministički test
2. integration test
3. reproducibilan benchmark
4. build/package rezultat
5. golden file (semantičko poređenje)
6. screenshot ili video
7. ručna QA kontrolna lista
8. agentovo objašnjenje ("radi jer sam tako napisao")
```

Agentova tvrdnja da nešto radi je NAJSLABIJI mogući dokaz — prihvatljiva
samo kad ništa jače nije razumno dostupno, i tada eksplicitno navesti
zašto.

---

## Podjela odgovornosti

| Ko | Šta |
| --- | --- |
| **Agent radi samostalno** | pretraga koda, pronalaženje pozivalaca, sažimanje postojećeg ponašanja, priprema failing testa, mala lokalna izmjena, pokretanje testova, `agent_report` |
| **Agent samo predlaže** (korisnik odlučuje) | arhitektonska promjena, promjena domenskog modela (`InvoiceLine`/`NaimenovanjeDraft` polja), promjena centralne poslovne logike (tarifno mapiranje, grupiranje naimenovanja, XML template), bazna migracija, širi refactor, promjena javnog interfejsa |
| **Nezavisan checker potvrđuje** (vidi "Nezavisna provjera" ispod) | da diff odgovara scope-u, da testovi provjeravaju pravi problem, da nisu promijenjena sporedna ponašanja, da nema očigledne regresije |
| **Korisnik odlučuje** | da li poslovna logika ima smisla, da li je UX prihvatljiv, da li se prihvata HIGH/CRITICAL rizik, da li se pušta migracija/mijenja produkcijsko stanje na `dmserver` |

---

## Nezavisna provjera (checker)

Nezavisan pregled — neko OSIM onoga ko je pisao izmjenu (druga agent
sesija, drugi model, ili korisnik) — je obavezan ili snažno preporučen
kada promjena: ima HIGH/CRITICAL GitNexus impact; dira bazu/migracije na
`dmserver`; dira tarifno mapiranje, grupiranje naimenovanja, ili XML
export logiku; nije bila pouzdano reprodukovana; ima kontradiktorne
izvore (vidi "Konflikti" polja); ima veliku cijenu greške (carinski
dokument koji ide u ASYCUDA).

Konkretni mehanizmi na ovom projektu: `/code-review` skill (za pregled
trenutnog diff-a), `/security-review` skill (za sigurnosno osjetljive
izmjene), ili druga paralelna agent sesija (Codex, druga Claude sesija —
vidi "Paralelni agenti" iznad za bezbjedan rad u dijeljenom working
tree-u dok se to radi).

Checker nezavisno: pregleda diff, potvrdi scope, provjeri pozivaoce i
zavisnosti, pokrene relevantne testove, POKUŠA OBORITI hipotezu prvog
agenta (ne samo potvrditi je), provjeri edge case-ove, i jasno navede šta
NIJE provjerio. `agent_report` (radni agent) tvrdi da je zadatak završen;
polje "Nezavisna provjera" u istom izvještaju tvrdi da je to i DOKAZANO —
ne miješati te dvije tvrdnje.

**Dvije odvojene ose pregleda** (kod može biti lijepo napisan a rješavati
pogrešan problem, ili tačno riješiti problem a biti arhitekturno loše —
jedan opšti pregled često pomiješa ova dva kriterija):

- **Standards review** — da li je kod u skladu sa konvencijama i
  arhitekturom (naming, stil, 3-layer razdvajanje, error handling,
  zavisnosti, testna praksa, sigurnost, performanse).
- **Spec review** — da li kod zaista rješava zadati problem (acceptance
  kriteriji, izostavljeni slučajevi, scope creep, kontradikcije sa
  zadatkom, van-opsežne promjene).

---

## Plan prije izmjene — HIGH/CRITICAL GitNexus impact

Ako `gitnexus_impact` za simbol koji se mijenja vrati **HIGH** ili **CRITICAL**,
agent PRIJE izmjene napravi JEDAN kratki fajl (ne cijeli "project room"):

```text
project_rooms/YYYY-MM-DD_kratak-naziv-zadatka.md
```

Kopirati `templates/agent-md/project_room_template.md` kao polaznu
tačku — puna šema sa objašnjenjem svakog polja živi TAMO. Sekcije:
Cilj, Pogođeno (simboli/procesi iz `gitnexus_impact`), Plan, Šta NE
dirati (scope lock — vidi "Handoff visokog rizika" ispod), Plan
verifikacije (vidi "Definition of Done" iznad), Rollback/oporavak,
Nezavisni checker (vidi "Nezavisna provjera" iznad), Odbačene opcije,
Konflikti (kontradiktorni izvori — koji se tretira kao važeći i zašto,
da li treba korisnička potvrda).

Fajl se na kraju može spojiti u `agent_report` (Korak 3) ili obrisati — nije trajna
dokumentacija. Za MEDIUM ili niži impact ovaj korak se preskače.

**Kad praviti `project_room` i ISPOD HIGH/CRITICAL praga**: tri pitanja —
da li je odluku teško vratiti, da li je iznenađujuća bez konteksta (neko
bi je mogao "popraviti" natrag jer izgleda kao greška), da li je rezultat
stvarnog kompromisa (razmotrene alternative, ne očigledan izbor). Ako je
odgovor DA na bilo koje — vrijedi kratak zapis čak i za MEDIUM impact
(npr. netrivijalna odluka u tarifnom mapiranju ili grupiranju
naimenovanja koja tehnički ne dira mnogo simbola, ali je lako da je neko
kasnije "ispravi" nazad).

---

## Handoff visokog rizika (HIGH/CRITICAL GitNexus impact)

Kada `gitnexus_impact()` vrati `HIGH` ili `CRITICAL` rizik za simbol koji mijenjaš,
prijavi korisniku rizik u ovom formatu PRIJE izmjene (ne nakon):

> "GitNexus impact za `<simbol>` je `<risk>`: zavise od njega `<broj>` simbola/procesa
> (`<koji>`). Promjena je mala/velika po obimu ali `<visoka/niska>` po sistemskoj
> važnosti jer `<razlog>`. Scope ostaje ograničen na: `<šta NE diraš>`.
> Obavezni izlaz: `<šta MORA postojati — npr. ciljane izmjene + test pokrivenost>`."

Za svaku planiranu izmjenu odredi i navedi:

| Polje | Pitanje na koje odgovara |
| --- | --- |
| **Tip promjene** | bugfix / behavior adjustment / mapping correction / safety patch / refactor? |
| **Prihvatljiv ishod (scope lock)** | šta MORA ostati identično (npr. "validacija ostaje ista osim novog izvora dokaza") |
| **Nivo dozvole** | draft change only / no auto-merge / mandatory review / test gate required |

---

## ⚠️ OBAVEZNA PROCEDURA: nakon završenog zadatka (Korak 1-5)

Svaki agent MORA slijediti ovaj redosljed nakon što završi zadatak.
Git pre-commit hook (`scripts/git-hooks/pre-commit`) automatski sprovodi
py_compile provjeru i ispisuje podsjetnike — NE zaobilaziti ga sa `--no-verify`.

### Korak 1 — Git commit
- Staged promjene grupisati po logičkim cjelinama (ne sve u jedan commit)
- Format poruke: `tip(oblast): kratki opis` (`fix`, `feat`, `refactor`, `docs`, `chore`)
- Uvijek dodati `Co-Authored-By:` liniju sa imenom modela koji je radio
  (npr. `Co-Authored-By: Claude <noreply@anthropic.com>`)
- **Nikad `git add -A`/`git add .`** — vidi "Paralelni agenti — izolacija
  working tree-a" iznad; provjeriti `git status --short` prije staging-a

### Korak 2 — Zajednička memorija
- Sve **ne-očigledno** i korisno za buduće sesije upisati u `docs/context/history.md`
  (dated stavka na kraj fajla) — samo trajna, cross-cutting pravila idu u
  `docs/CONTEXT.md` sekcije 1-14 (vidi CONTEXT.md §13). Claude dodatno u svoju
  sesijsku memoriju (vidi CLAUDE.md)
- **Šta upisivati**: poslovne odluke, pravila koja nisu u kodu, bug uzroci, fiksevi koji se ponavljaju
- **Šta NE upisivati**: šta kod radi (vidi se iz koda), git historija, privremeno stanje

### Korak 3 — Agent report
- Kreirati izvještaj u `agent_reports/YYYY-MM-DD_naziv-zadatka.md` —
  kopirati `templates/agent-md/agent_report_template.md` kao polaznu
  tačku (puna šema sa objašnjenjem svakog polja živi TAMO, ne ovdje)
- Obavezna polja (`##` sekcije): Datum, Agent, Scope, Status izvora
  (samo kompleksni/rizični zadaci), GitNexus impact, Reprodukcija prije
  izmjene (bugfix — vidi "Reprodukcija i provjera prije rada" iznad),
  Šta je urađeno, Zašto je urađeno, Kako je urađeno, Šta nije dirano,
  Verifikacija (mora odgovarati "Definition of Done" iznad), Nezavisna
  provjera (obavezno za HIGH/CRITICAL), Pronađeni problemi, Odbačene
  opcije, Konflikti/kontradiktorni izvori, Commitovi, Kontekst korišćen
  (samo kompleksni zadaci), Rizici/ograničenja, Potreban follow-up,
  Potrebna korisnička potvrda
- Commitovati izvještaj odmah nakon pisanja

### Korak 4 — Link u kodu (opcionalno, za kompleksne odluke)
- Kada je odluka netrivijalna, dodati komentar koji referiše na izvještaj:
  ```python
  # Vidi agent_reports/2026-05-09_naziv.md — objašnjenje odluke
  ```
- Samo gdje je stvarno potrebno, ne na svakoj promjeni

### Korak 5 — GitNexus ažuriranje
- Nakon commita provjeriti je li GitNexus index zastario
- Ako jeste: `npx gitnexus analyze`

---

## Testiranje

- Uvijek testirati sa pravim fakturama iz `najavauvoza/` foldera
- Debug ispisi moraju biti informativni i pregledni
- Provjeriti edge case-ove (bez kodova, multi-line opisi, različite jedinice)

---

## Format outputa

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratko
ŠTA NIJE URAĐENO: (ako PARCIJALNO/BLOKIRANO)
PITANJA: (ako postoje)
```

---

## Provjera prije predaje

- [ ] Bug je reprodukovan prije popravke (ili je zapisano zašto nije mogao biti)
- [ ] Nisam mijenjao kod van scope-a zadatka
- [ ] Nisam dodao nepotrebne komentare ili docstrings
- [ ] Nisam ostavio zakomentiran kod
- [ ] Nisam koristio string interpolaciju u SQL-u
- [ ] Testovi prolaze: `python -m pytest tests/ -q` (iz korijena projekta)
- [ ] Dokaz odgovara "Definition of Done" za tip promjene (GUI/parser/XML/baza/...)
- [ ] Za HIGH/CRITICAL: nezavisna provjera je urađena i navedena u `agent_report`
- [ ] Provjerio sam `git status --short` prije staging-a (nema tuđeg WIP-a)
- [ ] Output format je popunjen (STATUS, IZMIJENJENI FAJLOVI, itd.)

## DOC Guard

Kada hook injektuje `[DOC-GUARD]` poruku:

- **BROKEN** → zaustavi se, ispravi putanju ili kreiraj MD fajl prema
  `.claude/DECISION_RECORD_TEMPLATE.md` — ne commitaj sa broken linkom
- **STALE** → procijeni: logička izmjena = ažuriraj MD; kozmetička = nastavi
- Ručna provjera: `bash scripts/doc_link_checker.sh .`

---

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **deklarant_pro** (54384 symbols, 81481 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/deklarant_pro/context` | Codebase overview, check index freshness |
| `gitnexus://repo/deklarant_pro/clusters` | All functional areas |
| `gitnexus://repo/deklarant_pro/processes` | All execution flows |
| `gitnexus://repo/deklarant_pro/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
