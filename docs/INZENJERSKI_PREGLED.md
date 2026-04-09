# Inženjerski Pregled — ASYCUDA Pro

> Kompletna tehnička analiza arhitekture, tehnologija i inženjerskih praksi korištenih u razvoju desktop aplikacije za pripremu carinskih deklaracija.

---

## 1. 🐍 Jezik & Okruženje

| Komponenta | Detalj |
|---|---|
| **Python 3.13** | Stroga tipizacija (`typing`), `dataclasses`, f-string formatiranje |
| **`uv`** | Brz package manager i virtual environment tool (zamjena za `pip` + `venv`) |
| **`pyproject.toml`** | Centralizovana definicija projekta, zavisnosti, build sistema |
| **`hatchling`** | Moderni build backend (PEP 517/518 compliant) |
| **`python-dotenv`** | Izolacija konfiguracije (`.env`) od koda — nikad hardcoded credentials |
| **`pyright`** | Statička analiza tipova za otkrivanje grešaka prije runtime-a |

---

## 2. 🏗 Arhitekturni Obrasci

### 2.1 3-Layer Pattern (Per-Tab)
Svaki tab (Zaglavlje, Faktura, Naimenovanja, Agent) podijeljen je u tri jasno odvojena sloja:

```
View       → Čisto UI: widgeti, signali, prikaz podataka (NEMA business logike)
Controller → Orkestracija: prima signale, poziva servise, ažurira View
Service    → Business logika: validacije, kalkulacije, DB operacije (Qt-independent)
```

**Benefit:** Servise se mogu testirati izolovano, bez pokretanja GUI-a.

### 2.2 Strategy Pattern + Registry
Automatska detekcija formata fakture pri importu:
```
PDF → SmartPDFParser
  ├── Blagić-Attos
  ├── Master Frigo
  ├── ŠUMAPROM
  ├── IMAMOGLU
  └── Generic Fallback
```

Registry automatski bira odgovarajuću strategiju na osnovu heuristike (tekstualni markeri, layout, vendor imena).

### 2.3 Singleton Pattern
Kritični resursi se inicijalizuju samo jednom:
- `get_import_service()`
- `get_db_connection()`
- `LLMProvider()`

### 2.4 Dependency Injection
UI komponente ne kreiraju servise — one ih primaju kroz callback-e:
```python
service.on_activity = chat.add_activity
service.on_agent_message = chat.add_agent_message
```

### 2.5 State Management
- **`WorkflowState`**: Enum (`IDLE`, `ANALYZING`, `PROPOSAL_READY`, `WAITING_CONFIRMATION`, `COMPLETED`)
- **`AgentSessionState`**: Čuva stanje agent sesije (uploadovani fajlovi, chat kontekst, pending potvrde)
- **Token Budget**: Praćenje potrošnje tokena po sesiji

### 2.6 Service Layer (Qt-Independent)
Svi servisi (`TariffMappingService`, `MassCalculator`, `OriginStatementDetector`) ne znaju ništa o Qt-u. Mogu se koristiti u CLI, web API, ili testovima.

---

## 3. 🖥 GUI & Konkurencija

| Komponenta | Tehnologija |
|---|---|
| **Framework** | PySide6 (Qt6) — `QWidget` baziran UI |
| **Layout-i** | `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`, `QFormLayout`, `QSplitter` |
| **Tabele** | `QTableWidget` (fakture, šifarnici), `QTreeWidget` (hijerarhija tarifa) |
| **Dijalozi** | `QDialog` (PE2, EUR.1, validacija greške) |
| **Ikonice** | QtAwesome (Font Awesome 5 Solid) |
| **Styling** | Inline CSS (`setStyleSheet`) za custom teme (sage green, validacija boje) |
| **Streaming Chat** | HTML `QTextBrowser` sa dinamičkim token-appendChild |

### Konkurencija (Ne-Blokirajući UI)
- **`QThread`**: Pozadinski radnici za teške operacije
  - `ProcessingWorker` — parsiranje PDF/Excel fajlova
  - `ChatWorker` — LLM API pozivi
  - `TariffLLMWorker` — batch prijedlozi tarifnih brojeva
- **Signals & Slots**: Thread-safe komunikacija (`Signal.emit()` → `Slot.connect()`)
- **`QApplication.processEvents()`**: Forsira UI refresh između operacija
- **GC Management**: Čuvanje referenci na worker-e (`self._chat_workers`) da Python GC ne ubije aktivne thread-ove

---

## 4. 💾 Baze Podataka & Sigurnost

### PostgreSQL (Glavna)
- `psycopg2-binary` konekcija
- `catalogs` schema: šifrarnici, partneri, zemlje, carinske procedure
- `zvanicna_tarifa`: službeni tarifni brojevi 2026
- **Context Manager**:
  ```python
  with get_db_connection() as conn:
      with conn.cursor() as cur:
          cur.execute("SELECT ... WHERE kod = %s", (kod,))
  ```
- **Connection Pooling**: Max 10 istovremenih konekcija

### SQLite (Lokalna)
- `asycuda_sistem.db` — mapping znanja (tariff mappings), lokalne konfiguracije, sesije
- `zvanicna_tarifa.db` — read-only snapshot carinske tarife za offline pretragu

### Sigurnosne Prakse
- ✅ **Parameterizovani upiti** (`%s`) — zaštita od SQL injection
- ✅ **Credentials u `.env`** — nikad u kodu
- ✅ **Read-only pristup** lokalnoj tarifi
- ✅ **Auto commit/rollback** kroz context manager

---

## 5. 🤖 AI/LLM Sloj

### Provider Redoslijed (Chain-of-Fallback)
```
1. DeepSeek (deepseek-chat)  ← primarni, OpenAI-kompatibilan API
2. Groq (llama-3.3-70b)      ← fallback na 429 rate limit
3. Gemini (gemini-2.5-flash-lite) ← zadnji fallback
```

### Arhitektura
- **`LLMProvider`**: Apstrakcija nad svim providerima — isti interfejs za sve
- **Streaming API**: Token-po-token ispis u chatu (`yield delta`)
- **Batch Mode**: Jednokratni pozivi za obradu više stavki odjednom
- **Context Engineering**:
  - Dinamički prompt sa trenutnim stanjem draft-a
  - Hijerarhijski prikaz tarifa (drvo → 2→4→6→8→10 cifara)
  - RAG-like fallback iz lokalne baze znanja
- **Chat Memory**: `ChatMemoryService` čuva posljednjih N poruka za kontekst
- **System Prompts**: Domen-specifična pravila (carinsko grupisanje, rubrike, povlastice)

---

## 6. 📦 Import & Parsiranje

### Parseri po Vendoru
| Vendor | Format | Tehnologija |
|---|---|---|
| Blagić-Attos | PDF + Packing List | `pdfplumber` + regex |
| Master Frigo | PDF + Excel mapping | `pdfplumber` + `openpyxl` |
| ŠUMAPROM | Excel + PDF | `openpyxl` + `pdfplumber` |
| Generic | Bilo koji PDF | Table extraction + fuzzy match |

### Tehnike Parsiranja
- **Regex Engine**: Napredni patterni za:
  - Detekciju stavki (`Rbr Šifra Naziv JM Količina Cena Iznos`)
  - Jedinice mjere (`k o m` → `kom`, `k g` → `kg`)
  - Cijene i iznose (`1.250,00`, `150,00`)
  - Izjave o porijeklu (multi-language detection)
- **Fuzzy Matching**: `difflib.SequenceMatcher` za mapiranje naziva robe na bazu znanja
- **Auto-Combine**: Detekcija parova Faktura + Packing List po broju fakture, automatsko spajanje težina i zemalja

### Validacija
- `_validiraj_prije_uvoza()`: Provjera duplikata, postojanja partnera, formata tarifnih brojeva
- `TariffMappingService.min_similarity`: Prag 0.70 za prihvatanje match-a

---

## 7. 🧪 Testiranje & Kvalitet

| Alat | Namjena |
|---|---|
| **`pytest`** | Unit i integration testovi (300+ testova) |
| **`pytest-qt`** | Testiranje Qt widgeta i interakcija |
| **`py_compile`** | Sintaksna validacija prije commita |
| **`pyright`** | Statička analiza tipova |
| **Git** | Verzionisanje, atomični commiti, backup branch-ovi |

### Logging
Strukturirani logovi po modulu:
```
asycuda_pro.import.blagic_attos
asycuda_pro.tariff_mapping
asycuda_pro.agent.controller
asycuda_pro.country_origin_validator
```

### Code Quality
- **Konvencije**: `snake_case` za funkcije, `PascalCase` za klase, `UPPER_SNAKE` za konstante
- **Docstringovi**: Svaka javna metoda ima opis, args, return
- **Error Handling**: `try/except` sa specifičnim exception tipovima, ne goli `except:`
- **No Hardcoded**: Putanje, API ključevi, DB credentials — sve kroz konfiguraciju

---

## 8. 📊 Metrike Projekta (Stanje: April 2026)

| Metrika | Vrijednost |
|---|---|
| **Fajlova** | ~150 Python fajlova |
| **Linija koda** | ~18,000+ |
| **Testova** | 300+ (svi prolaze) |
| **Servisa** | 20+ (tariff, mass, origin, import, agent, xml, ...) |
| **Vendor Parsera** | 6+ specijalizovana + generic |
| **LLM Providera** | 3 (DeepSeek, Groq, Gemini) |
| **Git Commita** | 100+ |
| **Branch-ova** | 2 (main, dev) |

---

*Ovaj dokument je generiran na osnovu kompletnog pregleda koda, git historije i arhitektonskih odluka donesenih tokom razvoja ASYCUDA Pro aplikacije.*
