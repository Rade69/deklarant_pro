# Faza 3 — Eliminacija UI blokada (threading plan)

**Datum:** 2026-08-05
**Status:** Analiza završena — ČEKA ODOBRENJE
**Opseg:** Svi `get_db_connection()` pozivi sa UI thread-a
**Metod:** Statička analiza 50+ fajlova, klasifikacija po riziku

---

## Nalaz: 5 HIGH, 25+ MEDIUM, ~30 LOW

Ukupno ~60 fajlova poziva `get_db_connection()`. Od toga:

| Klasa | Broj fajlova | Opis |
|-------|-------------|------|
| 🔴 HIGH | 5 | Direktno u `gui/tabs/` — blokira UI thread |
| 🟡 MEDIUM | 25+ | U `services/`, poziva se iz GUI-ja bez threada |
| 🟢 LOW | ~30 | QThread workeri, migracije, CLI skripte — OK |

---

## 1. HIGH — Zaglavlje tab (6 poziva)

**Fajl:** `gui/tabs/zaglavlje_view.py:82,101,115,133,157,667`

**Problem:** Svaki put kad se otvori Zaglavlje tab, View DIREKTNO poziva `get_db_connection()` za:
- Učitavanje carinskih ispostava (linija 82)
- Učitavanje deklaranata (linija 101)
- Učitavanje izvoznika (linija 115)
- Učitavanje uvoznika (linija 133)
- Učitavanje vrsta deklaracija (linija 157)
- Učitavanje priloga (linija 667)

UI zamrzava jer svaki poziv blokira dok čeka konekciju + izvršava upit. 6 uzastopnih DB poziva × 50-200ms = 0.3-1.2s zamrzavanja.

**Rješenje:** Kreirati `ZaglavljeDataWorker(QThread)` koji:
1. Otvori JEDNU konekciju
2. Izvrši SVIH 6 upita u nizu
3. Emituje `data_ready(dict)` signal sa svim rezultatima
4. View samo popuni polja iz signala

**Fajlovi za izmjenu:** `zaglavlje_view.py` (~40 linija promjene), novi `zaglavlje_data_worker.py` (~50 linija)

**Rizik:** 🟡 SREDNJI — refaktor 6 metoda u View-u. Signali moraju biti pravilno povezani.

---

## 2. HIGH — Session Manager (3 poziva)

**Fajl:** `gui/tabs/agent/session_manager.py:63,102,120`

**Problem:** Upravljanje agent sesijama (čitanje/pisanje u bazu) blokira UI pri pokretanju agent chata.

**Rješenje:** DB operacije izdvojiti u `SessionDBWorker(QThread)`. Alternativno — keširati podatke o sesijama u memoriji, pisati u bazu asinhrono.

**Fajlovi:** `session_manager.py` (~30 linija)

**Rizik:** 🟢 NIZAK — session manager je izolovan modul.

---

## 3. HIGH — Chat Intent Handler (1 poziv)

**Fajl:** `gui/tabs/agent/services/chat_intent_handler.py:703`

**Problem:** Jedan DB poziv unutar chat intent handler-a — vjerovatno čitanje konteksta ili podešavanja.

**Rješenje:** Provjeriti šta tačno radi poziv na liniji 703. Ako je read-only — keširati ili prebaciti u ChatWorker.

**Rizik:** 🟢 NIZAK — jedan poziv, lako izolovati.

---

## 4. HIGH — Admin Database Panel (2 poziva)

**Fajl:** `gui/tabs/admin/panels/database_panel.py:24,40`

**Problem:** Test konekcije i učitavanje statistike baze.

**Rješenje:** Već postoji `_TestConnThread` i `_LoadStatsThread` na linijama 18 i 33 — provjeriti da li se KORISTE. Ako da, ovo je već riješeno. Ako ne — ožičiti ih.

**Rizik:** 🟢 NIZAK — infrastruktura već postoji.

---

## 5. HIGH — Admin Analytics Panel (1 poziv)

**Fajl:** `gui/tabs/admin/panels/analytics_panel.py:53`

**Problem:** Učitavanje analitike blokira UI pri otvaranju Analytics taba.

**Rješenje:** Kreirati `AnalyticsWorker(QThread)` — isti obrazac kao Database Panel.

**Rizik:** 🟢 NIZAK — jednostavan worker.

---

## 6. MEDIUM — Sifarnici Service (51 poziv)

**Fajl:** `services/sifarnici_service.py` (51 `get_db_connection()` poziv)

**Problem:** Već smo optimizovali pretragu (FTS indeks, LIMIT), ali servis i dalje blokira pozivajući UI thread dok čeka DB. 51 poziv znači da svaki metod otvara svoju konekciju.

**Rješenje:**
- **Ne treba refaktor svih 51 poziva** — većina su brzi upiti (<50ms)
- Dodati connection pooling na nivou servisa (jedna konekcija po requestu)
- Ili: koristiti `@lru_cache` za read-only podatke koji se rijetko mijenjaju (carinarnice, deklaranti)

**Rizik:** 🟡 SREDNJI — veliki broj poziva, ali većina nije kritična.

---

## 7. MEDIUM — Tariff Mapping Service (10 poziva)

**Fajl:** `services/tariff/tariff_mapping_service.py` (10 poziva)

**Problem:** Slično kao sifarnici — svaki metod otvara novu konekciju.

**Rješenje:** Connection pooling na nivou servisa. Već smo dodali `get_tarifa_opis_batch()` što smanjuje broj poziva.

**Rizik:** 🟢 NIZAK — već djelimično optimizovano.

---

## 8. MEDIUM — Ostali servisi (15+ fajlova)

**Fajlovi:** `zaglavlje_service.py`, `naimenovanja_service.py`, `tariff_facade.py`, agent servisi...

**Problem:** Svi pozivaju `get_db_connection()` direktno, što znači da svaki poziv otvara novu konekciju iz pool-a.

**Rješenje:** NE dirati pojedinačno — ovo je normalno ponašanje za servise. Connection pool (`database/db.py`) već upravlja konekcijama. Problem je samo kad se pozivaju sa UI thread-a.

**Fokus:** Samo servisi koje direktno poziva UI thread bez QThread worker-a.

---

## 9. Root cause — `time.sleep(0.1)` u `db.py`

**Fajl:** `database/db.py:168`

**Problem:** `get_db_connection()` koristi `time.sleep(0.1)` u wait petlji za connection pool. Ako se pozove sa UI thread-a dok je pool zauzet, aplikacija zamrzava.

**Rješenje (dugoročno):**
- Povećati `_POOL_MAX` sa trenutne vrijednosti na 20
- Dodati `_POOL_TIMEOUT` kao konfigurabilnu vrijednost
- Dodati warning log kad se konekcija čeka duže od 500ms

**Ovo NIJE dio Faze 3** — zahtijeva testiranje pod opterećenjem.

---

## Plan implementacije

### Korak 1 — Zaglavlje tab (prioritet 1, najveći efekat)
- Novi fajl: `gui/tabs/zaglavlje_data_worker.py` — QThread worker
- Izmjena: `gui/tabs/zaglavlje_view.py` — prebaciti 6 DB poziva na worker
- Vrijeme: ~1h

### Korak 2 — Admin paneli (prioritet 2, lako)
- Provjeriti `database_panel.py` — da li postojeći workeri rade
- Dodati `AnalyticsWorker` za `analytics_panel.py`
- Vrijeme: ~30 min

### Korak 3 — Session Manager + Chat Intent (prioritet 3)
- `session_manager.py` — asinhrono čitanje/pisanje sesija
- `chat_intent_handler.py:703` — provjeriti i izmjestiti
- Vrijeme: ~45 min

### Korak 4 — Connection pool tuning (poseban zadatak)
- Povećati pool size
- Dodati monitoring/warning za spore konekcije
- Vrijeme: ~30 min + testiranje pod opterećenjem

---

## Šta NE DIRATI u Fazi 3

- `sifarnici_service.py` — 51 poziv, ali već optimizovani. Nisu bottleneck.
- `tariff_mapping_service.py` — već poboljšan batch-om.
- Svi `services/agent/` servisi — pozivaju se iz `ChatWorker(QThread)` — već u background-u.
- `database/db.py` — connection pool infrastruktura, ne dirati bez testiranja.
- `importers/` — ne koriste `get_db_connection()`.

---

## Očekivani rezultat

Nakon Faze 3:
- Zaglavlje tab se otvara **trenutno** (bez 0.3-1.2s zamrzavanja)
- Admin paneli se učitavaju u pozadini
- Agent sesije ne blokiraju UI pri pokretanju
- Aplikacija **nikad ne "zastane"** zbog čekanja na bazu

Ukupno vrijeme implementacije: **2-3 sata**
