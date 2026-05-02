# DEKLARANT LICENSE MANAGER — IMPLEMENTACIONI PROMPT

**Datum:** 2026-04-26
**Status:** Spremno za coding agenta
**Namjena:** Kompletan prompt za implementaciju Deklarant License Manager aplikacije
**Program:** Deklarant License Manager — zasebna standalone aplikacija

---

## 0. KONTEKST I VEZA SA DEKLARANT PRO

Deklarant License Manager je **zaseban Python/PySide6 projekat** — nije dio Deklarant Pro repozitorijuma.

Međutim, **direktno koristi kriptografsku logiku** iz Deklarant Pro:

```text
deklarant_pro/tools/licensing/generate_license.py   ← KOPIRATI ili reimplementirati
deklarant_pro/tools/licensing/keys/private_key.pem  ← DEFAULT putanja do private key-a
deklarant_pro/core/licensing/license_models.py      ← Format licence (referenca)
```

Agent **ne smije pisati novu signing logiku od nule**. Mora koristiti ili kopirati postojeću iz `generate_license.py`. Signing format mora biti identičan da bi licence bile kompatibilne sa Deklarant Pro validatorom.

---

## 1. TEHNOLOGIJA

- Python 3.10+
- PySide6
- SQLite (lokalna baza, bez servera)
- `cryptography>=42.0.0` (RSA 2048, PKCS1v15, SHA256)
- Bez internet konekcije
- Bez login sistema

---

## 2. ARHITEKTURA — OBAVEZNO: 3-LAYER PATTERN

**Ovo je najvažnija arhitekturna odluka u projektu. Svako odstupanje je greška.**

Svaki ekran mora biti implementiran u tri odvojena sloja:

```text
View       → GUI widget, PySide6, prikazuje podatke, emituje signale
Controller → Prima signale iz View-a, koordinira između View i Service
Service    → Sva business logika, DB pristup, generisanje licence
```

### Struktura projekta

```text
deklarant_license_manager/
├── main.py                          # Entry point
├── database/
│   └── db_manager.py                # SQLite konekcija i migracije
├── models/
│   ├── company.py                   # Company dataclass
│   └── license.py                   # License dataclass
├── services/
│   ├── company_service.py           # CRUD za firme
│   ├── license_service.py           # CRUD za licence + generisanje
│   └── settings_service.py          # Čitanje/pisanje podešavanja
├── gui/
│   ├── main_window.py               # QMainWindow, sidebar, stack
│   ├── sidebar.py                   # Sidebar widget
│   └── screens/
│       ├── dashboard/
│       │   ├── dashboard_view.py    # View
│       │   ├── dashboard_controller.py
│       │   └── dashboard_service.py # Statistike
│       ├── companies/
│       │   ├── companies_view.py
│       │   ├── companies_controller.py
│       │   └── company_form.py      # Dijalog za dodavanje/uređivanje
│       ├── licenses/
│       │   ├── licenses_view.py
│       │   └── licenses_controller.py
│       ├── generator/
│       │   ├── generator_view.py
│       │   └── generator_controller.py
│       └── settings/
│           ├── settings_view.py
│           └── settings_controller.py
├── licensing/
│   └── license_generator.py         # Kopija/adaptacija generate_license.py
├── docs/
│   ├── ARCHITECTURE.md              # Objašnjenje 3-layer odluke
│   ├── LICENSE_FORMAT.md            # Format license.dat fajla
│   └── DATABASE.md                  # SQLite shema i migracije
└── README.md
```

### Primjer ispravne implementacije

```python
# gui/screens/generator/generator_controller.py
# Arhitektura: docs/ARCHITECTURE.md
# Licensing logika: licensing/license_generator.py

class GeneratorController:
    def __init__(self, view: GeneratorView, license_service: LicenseService):
        self._view = view
        self._svc = license_service
        self._connect_signals()

    def _connect_signals(self):
        self._view.generate_clicked.connect(self._on_generate)

    def _on_generate(self, data: dict):
        result = self._svc.generate_license(data)
        if result.success:
            self._view.show_success(result.output_path)
        else:
            self._view.show_error(result.message)
```

**Zašto 3 sloja?**
View ne smije znati ništa o bazi ni o potpisivanju. Controller ne smije pisati SQL. Service ne smije znati ništa o PySide6 widgetima. Ovakva podjela omogućava testiranje servisa bez GUI-a i debagovanje po slojevima.

---

## 3. KONVENCIJE PISANJA KODA

### 3.1 Jezik

- Sva objašnjenja u kodu, docstringovi i komentari: **srpski latinica**
- Nazivi varijabli, klasa i funkcija: **engleski** (Python standard)
- Log poruke: **srpski latinica** sa emoji prefiksom

### 3.2 Komentari — samo kad je WHY nejasan

```python
# DOBRO — objašnjava skriveno ograničenje
# SQLite ne podržava ALTER COLUMN — migracija briše i kreira tabelu iznova
# Detalji: docs/DATABASE.md#migracije

# LOŠE — objašnjava šta kod već jasno kaže
# Dohvati firmu po ID-u
company = company_service.get_by_id(company_id)
```

**Ne pisati:**
- Komentare koji opisuju šta kod radi (to rade nazivi)
- Multi-line blokove komentara
- "TODO" bez konkretnog plana
- Komentare vezane za trenutni zadatak ("dodano za generator ekran")

### 3.3 Logging i print poruke

```python
logger.info("✅ Licenca generisana: FIRMA_001_license.dat")
logger.warning("⚠️ Private key nije pronađen na default lokaciji")
logger.error("❌ Greška pri upisu u bazu: {e}")
logger.debug("🔍 Potpisivanje payload-a: {len(payload_bytes)} bajtova")
```

### 3.4 Docstringovi

Kratki, na srpskom, samo za javne metode servisa:

```python
def generate_license(self, data: dict) -> GenerateResult:
    """Generiše potpisani license.dat i upisuje u istoriju firme."""
```

Nije potrebno pisati parametre i return tip ako su jasni iz type hintova.

---

## 4. LINKOVI U KODU KA DOKUMENTACIJI

**Svaki modul mora imati na vrhu referencu na relevantni MD fajl.**

Format:

```python
# Arhitektura: docs/ARCHITECTURE.md
# Format licence: docs/LICENSE_FORMAT.md
# Baza podataka: docs/DATABASE.md
```

Gdje linkovi idu:

| Modul | Link |
|---|---|
| Svi service fajlovi | `docs/ARCHITECTURE.md` |
| `license_generator.py` | `docs/LICENSE_FORMAT.md` |
| `db_manager.py` | `docs/DATABASE.md` |
| `generator_controller.py` | `docs/LICENSE_FORMAT.md` |
| `settings_controller.py` | `docs/ARCHITECTURE.md` |

Svaka netrivijalna odluka u kodu mora imati kratki komentar ZA**ŠTO** + link na MD gdje je odluka dokumentovana:

```python
# Canonical JSON (sort_keys=True) jer redoslijed ključeva mora biti
# deterministički za RSA potpis — docs/LICENSE_FORMAT.md#potpisivanje
payload_bytes = json.dumps(payload, sort_keys=True, ...).encode("utf-8")
```

---

## 5. DOKUMENTACIJA — OBAVEZNI MD FAJLOVI

Agent mora kreirati sljedeće MD fajlove uz kod:

### `docs/ARCHITECTURE.md`

Mora sadržavati:
- Objašnjenje 3-layer odluke i zašto
- Dijagram toka podataka kroz slojeve
- Pravila: šta smije a šta ne smije svaki sloj
- Primjer ispravne i neispravne implementacije

### `docs/LICENSE_FORMAT.md`

Mora sadržavati:
- Kompletan JSON format `license.dat`
- Objašnjenje canonical JSON-a i zašto je bitan za potpis
- Kompatibilnost sa Deklarant Pro validatorom
- Primjer generisanja i verifikacije

### `docs/DATABASE.md`

Mora sadržavati:
- Kompletnu SQLite shemu sa objašnjenjima polja
- Strategiju migracija
- Putanju do baze fajla
- Primjere upita za česte operacije

---

## 6. VIZUELNI STIL

```text
Sidebar background:  #0B1F36
Sidebar active item: #1D64F2
Main background:     #F6F8FB
Card background:     #FFFFFF
Border:              #E5E7EB
Primary blue:        #1D64F2
Success green:       #16A34A
Warning orange:      #F59E0B
Danger red:          #DC2626
Text dark:           #1F2937
Text muted:          #6B7280
```

Vizuelni elementi:
- Tamni lijevi sidebar sa shield ikonom i nazivom
- Bijele kartice sa blagom sjenom
- Zaobljeni uglovi (border-radius: 8px)
- Status badge-ovi (zeleni/narandžasti/crveni)
- Plavi primary button za glavne akcije

---

## 7. LAYOUT APLIKACIJE

```text
┌─────────────────────────────────────────┐
│ Deklarant License Manager               │
├──────────────┬──────────────────────────┤
│ Sidebar      │ Content Area             │
│              │                          │
│ Dashboard    │                          │
│ Firme        │                          │
│ Licence      │                          │
│ Generator    │                          │
│ Podešavanja  │                          │
├──────────────┤                          │
│ Licencirani  │                          │
│ za: DEKL.PRO │                          │
│ Verzija 1.0.0│                          │
│ ● Lokalno    │                          │
└──────────────┴──────────────────────────┘
```

---

## 8. DASHBOARD EKRAN

4 stat kartice:

```text
Ukupno firmi | Aktivne licence | Ističu za 30 dana | Istekle licence
```

Tabela "Pregled licenci":

| Firma | Kontakt osoba | Machine ID | Važi do | Status | Akcija |
|---|---|---|---|---|---|

Status badge: Aktivna (zeleno) / Ističe uskoro (narandžasto) / Istekla (crveno)

Akcije po redu: pregled, eksport `.dat`, obnova

---

## 9. FIRME EKRAN

Dva panela:

**Lijevo:** Lista sa search poljem i `+` dugmetom. Svaka firma prikazuje naziv i grad.

**Desno:** Detalji izabrane firme:
- Naziv, JIB/PIB, Adresa, Grad
- Kontakt osoba, Telefon, Email
- Status saradnje, Napomena
- Broj aktivnih licenci
- Istorija licenci (lista)
- Dugme "Uredi"

---

## 10. LICENCE EKRAN

Gornji toolbar: search input + "Nova licenca" + filter dropdown (Sve/Aktivne/Ističu/Istekle)

Tabela: Firma | Machine ID | Važi od | Važi do | Paket | Status | Akcija

Donji toolbar: Pregled licence | Eksportuj license.dat | Obnovi licencu | Blokiraj licencu

---

## 11. GENERATOR EKRAN

Najvažniji operativni ekran. Layout: forma lijevo, pregled desno.

**Lijeva forma:**
- Firma: dropdown (iz baze)
- Machine ID: text input + "Kopiraj" dugme
- Važi od: date picker (default: danas)
- Važi do: date picker (default: danas + 12 mj)
- Trajanje: automatski izračunato i prikazano
- Paket: dropdown (Basic / Full)
- Features checkboxevi:
  - XML Export
  - Reports
  - AI Agent / Automation
  - Admin Tools
  - Custom Integrations

Dugme: **"Generiši license.dat"** (primary, plavo, istaknuto)

**Desni panel (preview):**
- Firma, Machine ID, Važi od, Važi do, Paket
- Features count (npr. "4 od 5")
- Info box: "Licenca će biti generisana sa digitalnim potpisom."
- Izlazna putanja (cross-platform, Path objekat)

---

## 12. PODEŠAVANJA EKRAN

```text
Putanja do private_key.pem    [input]  [Izaberi...]
Default output folder          [input]  [Izaberi...]
Default trajanje: 12 mj        [spinbox]
Naziv aplikacije: Deklarant Pro [input]
License prefix: DKP            [input]
Grace period: 7 dana           [spinbox]
```

**Default vrijednosti pri prvom pokretanju:**

```python
# Putanja do ključa — default lokacija iz Deklarant Pro projekta
# Korisnik može promijeniti u podešavanjima
DEFAULT_PRIVATE_KEY = Path.home() / "Desktop" / "deklarant_pro" / \
                      "tools" / "licensing" / "keys" / "private_key.pem"

DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "Licence"
```

**Napomena u UI:**
> ⚠️ Private key nikada ne smije biti kopiran ni dijeljen. Čuvajte ga samo lokalno.

---

## 13. SQLITE BAZA

**Lokacija baze:**

```python
# Cross-platform, nikada hardkodirati apsolutnu putanju
# docs/DATABASE.md#lokacija
DB_PATH = Path.home() / ".config" / "deklarant_license_manager" / "licenses.db"
```

**Shema:**

```sql
CREATE TABLE companies (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    jib_pib          TEXT,
    address          TEXT,
    city             TEXT,
    contact_person   TEXT,
    phone            TEXT,
    email            TEXT,
    cooperation_status TEXT DEFAULT 'Aktivna',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE licenses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id       INTEGER NOT NULL REFERENCES companies(id),
    machine_id       TEXT NOT NULL,
    valid_from       TEXT NOT NULL,
    valid_to         TEXT NOT NULL,
    package          TEXT NOT NULL DEFAULT 'Full',
    features_json    TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL DEFAULT 'active',
    license_file_path TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
```

---

## 14. LICENSE GENERATION LOGIKA

**VAŽNO:** Signing logika mora biti identična Deklarant Pro implementaciji.
Referenca: `deklarant_pro/tools/licensing/generate_license.py`

Format `license.dat`:

```json
{
  "payload": {
    "customer_name": "ABC Import Export d.o.o.",
    "customer_id": "COMPANY_001",
    "machine_id": "DKP-A7F2-91KD-8821-FF09",
    "valid_from": "2026-04-26",
    "valid_to": "2027-04-26",
    "features": ["xml_export", "reports", "ai_agent", "admin_tools"],
    "issued_at": "2026-04-26"
  },
  "signature": "BASE64_SIGNATURE"
}
```

Signing algoritam:
- RSA 2048, PKCS1v15, SHA256
- Potpisuje se **samo payload** kao canonical JSON (`sort_keys=True, separators=(",",":")`)
- Nikad ne potpisivati cijeli fajl sa `signature` poljem

Output putanja (cross-platform):

```python
# Nikad ne hardkodirati Windows putanje
# docs/LICENSE_FORMAT.md#output
output_path = settings.output_dir / company_id / f"license_{date.today().strftime('%Y%m%d')}.dat"
output_path.parent.mkdir(parents=True, exist_ok=True)
```

---

## 15. FUNKCIONALNI ZAHTJEVI

Implementirati:

- Dodavanje i uređivanje firme
- Pretraga firmi (real-time filter)
- Prikaz detalja firme sa istorijom licenci
- Prikaz svih licenci sa filtriranjem po statusu
- Generisanje licence (potpisani `license.dat`)
- Upis generirane licence u istoriju firme
- Eksport `license.dat` na disk
- Obnova licence (nova licenca za istu firmu/machine_id)
- Blokiranje licence (status = 'blocked')
- Podešavanje private key putanje
- Podešavanje output foldera
- Automatski izračun statusa (active/expiring/expired) na osnovu datuma

---

## 16. UX PRAVILA

- Aplikacija ne smije izgledati kao obična forma bez strukture
- Korisnik uvijek mora znati šta je izabrano (highlight u listi)
- Status licence mora biti vizuelno jasan (badge, ne samo tekst)
- Dugme "Generiši license.dat" mora biti primarna akcija — istaknuto
- Greške prikazivati inline, ne samo u terminal
- Uspješno generisanje: poruka + putanja do fajla + klik za otvaranje foldera
- Tehnički detalji (private key, putanje, grace period) idu u Podešavanja

---

## 17. MOCK DATA

**Ne dodavati mock firme.** Aplikacija počinje sa praznom bazom.

Jedino što se inicijalizuje su default `settings`:

```python
DEFAULT_SETTINGS = {
    "private_key_path": str(DEFAULT_PRIVATE_KEY),
    "output_dir": str(DEFAULT_OUTPUT_DIR),
    "default_duration_months": "12",
    "app_name": "Deklarant Pro",
    "license_prefix": "DKP",
    "grace_period_days": "7",
}
```

---

## 18. DELIVERABLES

Na kraju implementacije:

1. Kompletna PySide6 aplikacija sa 3-layer arhitekturom
2. SQLite migraciona skripta ili `db_manager.py` sa auto-kreiranjem
3. `licensing/license_generator.py` kompatibilan sa Deklarant Pro
4. `docs/ARCHITECTURE.md` — 3-layer objašnjenje
5. `docs/LICENSE_FORMAT.md` — format i signing
6. `docs/DATABASE.md` — shema i migracije
7. `README.md` sa uputama za pokretanje

---

## 19. OGRANIČENJA

Ne implementirati:
- Server ili API
- Online aktivaciju
- Login sistem
- Cloud sync
- Permission sistem

Ovo je **lokalni interni alat** koji koristi isključivo vlasnik Deklarant Pro aplikacije.

---

## 20. KRITERIJ USPJEHA

Aplikacija je uspješna ako se može uraditi ovaj tok:

```text
1. Dodam firmu (naziv, JIB, kontakt)
2. Unesem Machine ID koji mi je klijent poslao
3. Izaberem datum važenja
4. Kliknem "Generiši license.dat"
5. Fajl se snimi u output folder
6. Licenca se pojavi u istoriji firme
7. Kasnije mogu obnoviti licencu za istu firmu
```

I ovaj debug tok:

```text
1. Otvorim bilo koji .py fajl
2. Na vrhu vidim link ka relevantnom MD fajlu
3. Otvorim MD fajl i razumijem ZAŠTO je nešto implementirano tako
4. Mogu pratiti tok podataka kroz View → Controller → Service
```
