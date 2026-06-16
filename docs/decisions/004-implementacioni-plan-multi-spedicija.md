# 004 — Implementacioni plan za multi-špedicija prilagodbu

**Datum:** 2026-05-02  
**Status:** Plan implementacije  
**Veza na odluku:** `003-multi-spedicija-prilagodba.md`

---

## Cilj

Pripremiti aplikaciju da se nova špedicija uvodi bez izmjena koda, kroz:
- zasebnu PostgreSQL bazu po špediciji
- zaseban XML arhiv i SQLite indeks po špediciji
- konfiguraciju preko `.env`

---

## Scope (prva iteracija)

U prvoj iteraciji radimo samo ono što je neophodno za ponovljiv onboarding:
1. Uklanjanje hardkodovanih XML/SQLite putanja iz koda
2. Uvođenje `.env` varijabli i validacija konfiguracije
3. Operativni onboarding runbook (ručni koraci)
4. Minimalni setup skript za automatizaciju koraka 1-5 iz odluke 003
5. Verifikacija na testnoj "drugoj špediciji"

Nije u scope-u:
- multi-tenant (`tenant_id`) arhitektura
- velika refaktorizacija importera
- promjene MCP servera

---

## Faza 1 — Konfigurabilne putanje (kod)

### Zadaci
1. Uvesti varijable:
   - `XML_ARCHIVE_DIR`
   - `DECLARATION_INDEX_DB`
2. Zamijeniti hardkodovane konstante:
   - `services/agent/chat/declaration_search_service.py`
   - `services/agent/learning/exporter_xml_indexer.py`
3. Dodati fail-fast provjeru:
   - Ako varijabla nije postavljena ili putanja ne postoji, baciti jasnu grešku
4. Dodati fallback samo ako postoji eksplicitna potreba kompatibilnosti

### Kriterijum gotovosti
- Nema hardkodovanog `NOVA ASIKUDA` path-a u runtime kodu
- Aplikacija radi sa putanjama iz `.env`
- Greške konfiguracije su čitljive i odmah vidljive

---

## Faza 2 — Onboarding podataka za novu špediciju

### Zadaci
1. Kreirati novu praznu PostgreSQL bazu
2. Pokrenuti `setup_db.py` i migracije nad tom bazom
3. Postaviti XML folder nove špedicije
4. Pokrenuti reindeksiranje (`exporter_xml_indexer --reindex`)
5. Unijeti:
   - deklaranta
   - osnovne partnere (izvoznik/uvoznik/primalac)

### Kriterijum gotovosti
- Sistem se podiže na novoj bazi bez tuđih podataka
- Pretraga i historijsko učenje vide samo XML nove špedicije
- Može se završiti end-to-end testna deklaracija

---

## Faza 3 — Setup skript (minimalna automatizacija)

### Zadaci
1. Dodati `scripts/setup_new_spedition.sh` sa parametrima:
   - `<ime_spedicije>`
   - `<xml_folder>`
2. Skript radi:
   - kreiranje baze
   - setup šeme/migracije
   - generisanje `.env` vrijednosti za novu instancu
   - pokretanje XML reindeksa
3. Dodati safety provjere:
   - da baza već ne postoji
   - da XML folder postoji i nije prazan

### Kriterijum gotovosti
- Skript bez ručnih intervencija izvrši korake 1-5 iz odluke 003
- U slučaju greške daje jasnu poruku i prekida dalje korake

---

## Faza 4 — Verifikacija i test matrica

### Obavezne provjere
1. Smoke test pokretanja aplikacije na novoj bazi
2. Import najmanje 3 tipa fakture:
   - postojeći podržani format
   - format sa manjim odstupanjem
   - format koji pada (očekivana vidljiva greška)
3. Generisanje XML-a i validacija ključnih rubrika
4. Provjera da nema "curenja" podataka između baza

### Kriterijum gotovosti
- Testni zapisnik pokazuje da onboarding radi predvidivo
- Poznati gapovi su dokumentovani (npr. dobavljači bez importera)

---

## Predloženi redoslijed realizacije

1. Faza 1 (konfigurabilne putanje)
2. Faza 2 (ručni onboarding)
3. Faza 4 (verifikacija)
4. Faza 3 (automatizacija skriptom)

Razlog: prvo stabilizovati konfiguraciju i potvrditi proces ručno, pa tek onda automatizovati.

---

## Procjena trajanja

- Faza 1: 0.5-1 dan
- Faza 2: 0.5 dan
- Faza 4: 0.5-1 dan
- Faza 3: 0.5 dan

**Ukupno:** 2-3 dana za stabilan onboarding paket (bez novih importera).

---

## Rizici i mitigacije

1. Rizik: skrivena hardkodovana putanja ostane u pomoćnim modulima  
Mitigacija: `rg "NOVA ASIKUDA|declaration_index.db"` kroz repo nakon izmjena.

2. Rizik: nova špedicija ima nekompatibilne fakture  
Mitigacija: fallback na ručni unos + prioritetna izrada importera po frekvenciji dobavljača.

3. Rizik: "prljava" zajednička baza znanja utiče na preporuke  
Mitigacija: start sa praznim mapiranjima po novoj bazi, pa kontrolisano učenje.

---

## Definicija završetka (DoD)

Implementacija se smatra završenom kada:
1. Nema hardkodovanih tenant-specifičnih putanja u runtime kodu
2. Nova špedicija može biti podignuta samo kroz konfiguraciju i onboarding korake
3. Postoji jedan reproducibilan setup tok (runbook ili skript)
4. Postoji testni dokaz da podaci ostaju izolovani po bazi
