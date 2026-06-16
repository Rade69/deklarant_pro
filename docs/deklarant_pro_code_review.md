# Deklarant Pro — Kompletan Code Review

> Grana: `dev` | Datum: 2026-05-05  
> Analizirani fajlovi: file tree, README, CLAUDE.md, app/run.py, .env.example,  
> config/settings.py, database/db.py, database/repository.py, core/draft/draft.py,  
> chat_worker.py, docs/sections/*, agent_reports/legacy-sections/*

---

## Sadržaj

1. [Arhitekturalni pregled](#1-arhitekturalni-pregled)
2. [Sigurnosni problemi](#2-sigurnosni-problemi)
3. [database/db.py](#3-databasedbpy)
4. [database/repository.py](#4-databaserepositorypy)
5. [core/draft/draft.py](#5-coredraftdraftpy)
6. [config/settings.py](#6-configsettingspy)
7. [app/run.py](#7-apprunpy)
8. [gui/tabs/agent/widgets/chat_worker.py](#8-guitabsagentwidgetschat_workerpy)
9. [Repozitorij i dokumentacija](#9-repozitorij-i-dokumentacija)
10. [Pozitivni nalazi — što radi dobro](#10-pozitivni-nalazi--što-radi-dobro)
11. [Konsolidovana prioritetna lista](#11-konsolidovana-prioritetna-lista)

---

## 1. Arhitekturalni pregled

### Potvrđena arhitektura

```
Windows klijenti (PySide6)
    │
    ├── direktni SQL (tranzicionalno) ──→ PostgreSQL (Ubuntu server)
    │                                         ↑
    └── MCP alati (ciljano) ──→ MCP server (Ubuntu, isti server)
    
Lokalno na svakom klijentu:
    └── SQLite (deklarant_pro.db) — lokalni draft-ovi (work in progress)
```

**Tri sloja podataka:**

| Sloj | Tehnologija | Lokacija | Sadržaj |
|------|-------------|----------|---------|
| Lokalni drafts | SQLite (`repository.py`) | Svaki klijent | Deklaracije u radu |
| Referentni podaci | PostgreSQL (`db.py`) | Ubuntu server | Tarife, partneri, inspekcije, XML arhiv |
| MCP alati | JSON-RPC subprocess | Ubuntu server (ciljano) | Stabilan API sloj za PostgreSQL |

**Ovo je ispravna arhitektura** — SQLite za lokalni scratch pad, PostgreSQL za dijeljene podatke, MCP kao sigurnosni sloj. Migracija od direktnog SQL-a prema MCP-u je u toku i eksplicitno dokumentovana.

### Poznate nedovršene implementacije

Sljedeće su namjerno nedovršene (dokumentovano u agent reports):

- **ŠUMAPROM kombinovani importer** — `combine_sumaprom_excel_and_pdf()` baca `ImportError`, očekivano ponašanje
- **MCP write alati** — server je trenutno read-only; svi writeovi idu direktnim SQL-om
- **Klijenti drže DB kredencijale** — tranzicionalno, dok MCP write alati nisu gotovi

---

## 2. Sigurnosni problemi

### 2.1 🔴 JIB se šalje LLM-u — kontradikcija s komentarom

**Fajl:** `gui/tabs/agent/widgets/chat_worker.py` → `_search_declarations_context()`

Komentar u `_build_session_zone` kaže *"JIB se nikad ne šalje LLM-u"*, ali:

```python
# BUG — JIB odlazi direktno u LLM kontekst
f"  JIB: {r.get('consignee_jib','?')}"
```

Nema `SEND_SENSITIVE_DATA` provjere. Carinski JIB broj odlazi na Groq/Gemini/OpenRouter.

**Rješenje:**
```python
send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"
jib_display = r.get('consignee_jib', '?') if send_sensitive else "[JIB skriven]"
ctx.append(
    f"  Izvoznik: {r.get('exporter_name','?')[:50]} | "
    f"Primalac: {r.get('consignee_name','?')[:40]} | "
    f"JIB: {jib_display}"
)
```

---

### 2.2 🔴 `_search_pg_partners` ignorira `SEND_SENSITIVE_DATA`

**Fajl:** `chat_worker.py` → `_search_pg_partners()`

Puna imena firmi iz PostgreSQL-a idu u LLM kontekst bez obzira na postavku:

```python
# BUG — nema provjere SEND_SENSITIVE_DATA
f"  [{row['type']}] {row['name']} (kod: {row['code']})"
```

**Rješenje:**
```python
def _search_pg_partners(self, query: str) -> list:
    send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"
    # ...
    name_display = row['name'] if send_sensitive else "[ime skriveno]"
    results.append(f"  [{row['type']}] {name_display} (kod: {row['code']})")
```

---

### 2.3 🔴 PostgreSQL konekcija bez SSL-a

**Fajl:** `database/db.py` → `get_connection_pool()`

Pool se kreira s individualnim parametrima, ne s `connection_string`. Čak i ako se doda `sslmode` u `DatabaseSettings.connection_string`, ovdje neće imati efekta:

```python
# TRENUTNO — sslmode nikad nije proslijeđen
_connection_pool = ThreadedConnectionPool(
    minconn=1, maxconn=10,
    host=settings.host, port=settings.port,
    # sslmode nedostaje!
)
```

**Rješenje:**
```python
_connection_pool = ThreadedConnectionPool(
    minconn=1, maxconn=10,
    host=settings.host,
    port=settings.port,
    database=settings.database,
    user=settings.user,
    password=settings.password,
    sslmode=settings.sslmode,        # DODATI
    cursor_factory=RealDictCursor,
    connect_timeout=3,
)
```

Dodati u `DatabaseSettings`:
```python
sslmode: str = Field(default="require", alias="DB_SSLMODE")
```

Dodati u `.env.example`:
```
DB_SSLMODE=require
# Za lokalni razvoj bez SSL: DB_SSLMODE=disable
```

---

### 2.4 🟠 Nema provjere da li je provider lokalan kad je `SEND_SENSITIVE_DATA=true`

**Fajl:** `chat_worker.py` → `_build_session_zone()`

`.env.example` kaže `true` je dozvoljeno *"SAMO za lokalni Ollama"*, ali kod ne provjerava:

```python
# RJEŠENJE — prisilno maskiranje ako je cloud provider
if send_sensitive:
    from .llm_provider import LLMProvider
    if LLMProvider().active_provider() not in ("ollama", "local", "none"):
        import logging
        logging.getLogger(__name__).warning(
            "SEND_SENSITIVE_DATA=true sa cloud providerom! Prisilno maskiranje."
        )
        send_sensitive = False
```

---

### 2.5 🟠 `SEND_SENSITIVE_DATA` čita se van centralnog settings sistema

**Fajl:** `chat_worker.py` (i potencijalno drugi)

```python
# TRENUTNO — zaobilazi Pydantic settings
import os
send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"
```

Dodati `AISettings` klasu u `config/settings.py` (detalji u sekciji 6).

---

## 3. database/db.py

### 3.1 🟡 `get_connection_pool()` nije thread-safe

```python
def get_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ThreadedConnectionPool(...)  # race condition
```

UI thread i MCP thread mogu istovremeno kreirati dva pool-a.

**Rješenje:**
```python
import threading
_pool_lock = threading.Lock()

def get_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:  # double-checked locking
                _connection_pool = ThreadedConnectionPool(...)
    return _connection_pool
```

---

### 3.2 🟡 Nema health check-a za mrtve konekcije

`ThreadedConnectionPool` ne testira konekcije automatski. Idle konekcija koju server dropi vraća `InterfaceError: connection already closed` na sljedećem upitu.

**Rješenje — dodati reconnect logiku:**
```python
@contextmanager
def get_db_connection():
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        if conn.closed:
            pool.putconn(conn, close=True)
            conn = pool.getconn()
        yield conn
        conn.commit()
    except psycopg2.OperationalError:
        conn.rollback()
        pool.putconn(conn, close=True)
        conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
```

---

### 3.3 🟡 Nekonzistentna duljina tarifnog koda između modula

`normalize_tarifni_kod` u `db.py` generiše **11 cifara**:
```python
if len(digits) == 8:
    return digits + "000"  # → 11 cifara
```

`_fetch_pg_tariff_descriptions` u `chat_worker.py` generiše **10 cifara**:
```python
if len(d) == 8:
    lookup[d + '00'] = code  # → 10 cifara
```

Jedan od ova dva modula radi lookup s pogrešnom duljinom. Treba provjeriti šta `catalogs.zvanicna_tarifa` stvarno čuva i standardizovati na jednu funkciju u `db.py`.

---

### 3.4 🟡 Tri paralelne tabele za partnere

U jednom fajlu postoje funkcije za tri različite tabele s istom svrhom:

| Tabela | Funkcije |
|--------|----------|
| `catalogs.partneri` | `get_partner_by_jib`, `search_partnere` |
| `catalogs.izvoznici` + `catalogs.uvoznici` | `get_izvoznik_by_jib`, `search_izvoznike`, itd. |
| `public.traders` | `get_trader_by_code`, `search_traders`, itd. |

Rezultat višestrukih iteracija migracija bez konsolidacije. Treba odrediti jednu kanonsku tabelu.

---

### 3.5 🟢 `get_connection()` — kandidat za misuse

```python
def get_connection():
    pool = get_connection_pool()
    return pool.getconn()  # konekcija može procuriti
```

Dokument `db-pool-fix.md` potvrđuje da je ovaj pattern već uzrokovao `pool exhausted` bug.
Funkcija treba biti uklonjena ili označena kao deprecated.

**Napomena:** Agent report `db-pool-fix.md` potvrđuje da je pool exhaustion bug već
popravljen migracijom na `get_db_connection()`. `get_connection()` je ostatak koji treba ukloniti.

---

## 4. database/repository.py

### 4.1 🟠 Draft podaci su lokalni — arhitekturalna odluka nije dokumentovana

`DraftRepository` koristi SQLite, ne PostgreSQL. Posljedice:

- Svaki klijent ima vlastitu bazu draft-ova
- Dva deklaranta ne mogu vidjeti međusobne draft-ove
- Reinstalacija Windows-a = gubitak svih draft-ova
- Nema server-side backupa draft podataka

Ovo može biti namjerna odluka (drafts = lokalni scratch pad), ali nije dokumentovana nigdje.
Treba dodati komentar u `repository.py` koji objašnjava zašto je SQLite, a ne PostgreSQL.

---

### 4.2 🟠 Hardcoded relativna putanja SQLite fajla

```python
def __init__(self, db_path: str = "deklarant_pro.db"):
```

Relativna putanja = baza u CWD pri pokretanju. Može biti na različitim mjestima zavisno od načina pokretanja.

**Rješenje:**
```python
from config.settings import get_path_settings

def __init__(self, db_path: str = None):
    if db_path is None:
        db_path = str(get_path_settings().project_root / "deklarant_pro.db")
    self.db_path = db_path
```

---

### 4.3 🟡 `AttachmentRepository` ne inicijalizuje tabele

`DraftRepository._init_db()` kreira obje tabele (`drafts` + `attachments`), ali `AttachmentRepository.__init__` ne poziva `_init_db()`. Ako se `AttachmentRepository` instancira prije `DraftRepository`, tabela ne postoji.

---

### 4.4 🟡 Duplirana `_get_connection()` u obje klase

Identičan kod u `DraftRepository` i `AttachmentRepository`. Treba biti module-level funkcija ili base klasa, s dodavanjem `PRAGMA journal_mode=WAL`:

```python
@contextmanager
def _sqlite_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # bolje za desktop app
    try:
        yield conn
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"SQLite error: {e}")
        raise
    finally:
        conn.close()
```

---

### 4.5 🟢 `get_all()` bez paginacije

```python
cursor.execute("SELECT * FROM drafts ORDER BY updated_at DESC")  # nema LIMIT
```

Za sada OK, ali s godinama rada akumuliraju se stotine zapisa.

---

## 5. core/draft/draft.py

### 5.1 🔴 Kritičan bug — `InvoiceLine.key()` ne uključuje EUR1 broj

Agent report `asycuda-99-item-limit.md` eksplicitno kaže:
> *"grupisanje zasniva na carinskom ključu: tarifni broj, zemlja porijekla, povlastica i EUR.1 broj"*

Ali `InvoiceLine.key()` koristi samo 3 elementa:

```python
def key(self) -> Tuple[str, str, str]:
    return (_s(self.tarifni_broj), _s(self.zemlja_porijekla), _s(self.povlastica))
    # eur1_number NEDOSTAJE
```

Posljedica: linije s istom tarifom/zemljom/povlasticom ali **različitim EUR1 brojevima** grupišu se u jedno naimenovanje — direktna greška u carinskoj deklaraciji.

**Treba provjeriti** da li `CreateNaimenovanjaService` koristi `InvoiceLine.key()` ili ima vlastitu implementaciju ključa. Ako koristi `key()` — bug je aktivan u produkciji.

**Rješenje:**
```python
def key(self) -> Tuple[str, str, str, str]:
    return (
        _s(self.tarifni_broj),
        _s(self.zemlja_porijekla),
        _s(self.povlastica),
        _s(self.eur1_number),  # DODATI
    )
```

---

### 5.2 🟡 Callback iteracija bez kopije liste

```python
def _notify_data_change(self) -> None:
    for callback in self._data_change_callbacks:  # direktna iteracija
        callback()
```

Ako `callback()` pozove `unregister_data_change_callback()` → `RuntimeError: list changed size during iteration`.

**Rješenje:**
```python
for callback in list(self._data_change_callbacks):  # kopija liste
```

---

### 5.3 🟡 Nema `remove_item()` metode

Postoji `add_item()` koji poziva `mark_dirty()`, ali nema `remove_item()`. Brisanje se vjerovatno radi direktno s `self.draft.items.pop(i)` — zaobilazeći `mark_dirty()` i callbacks.

**Rješenje:**
```python
def remove_item(self, item_id: str) -> bool:
    before = len(self.items)
    self.items = [it for it in self.items if it.item_id != item_id]
    if len(self.items) < before:
        self._renumber_items()
        self.mark_dirty()
        return True
    return False

def _renumber_items(self) -> None:
    for i, it in enumerate(self.items, 1):
        it.ordinal_no = i
```

---

### 5.4 🟡 `apply_to_all()` koristi `setattr` — nije type-safe

```python
def apply_to_all(self, field_name: str, value: Any) -> None:
    for it in self.items:
        setattr(it, field_name, value)
    # mark_dirty() nedostaje!
```

Nema provjere polja i nema `mark_dirty()` poziva.

**Rješenje:**
```python
def apply_to_all(self, field_name: str, value: Any) -> None:
    if not self.items:
        return
    if not hasattr(self.items[0], field_name):
        raise AttributeError(f"NaimenovanjeDraft nema polje '{field_name}'")
    for it in self.items:
        object.__setattr__(it, field_name, value)
    self.mark_dirty()
```

---

### 5.5 🟢 `DeclarationDraft` bez `slots=True`

Sve prateće klase (`Party`, `InvoiceLine`, `NaimenovanjeDraft`) imaju `slots=True`, ali `DeclarationDraft` sa 60+ polja nema. Minor nedosljednost, nema funkcionalnog uticaja.

---

### 5.6 🟢 `header: Dict[str, Any]` — nedovršena migracija

`DeclarationDraft` ima i typed polja i generički `header: Dict[str, Any]`. Nije jasno koje polje je autoritativno za koji podatak. Oznaka nedovršene migracije od dict-a prema typed modelu.

---

## 6. config/settings.py

### 6.1 🟠 `AISettings` klasa nedostaje

`.env.example` definiše `GROQ_API_KEY`, `GEMINI_API_KEY`, `SEND_SENSITIVE_DATA`, `CLIENT_NAME`, `SESSION_TOKEN_BUDGET` ali nema `AISettings` klase. Te varijable se čitaju direktnim `os.getenv()` pozivima, van Pydantic validacije.

**Rješenje — dodati u `config/settings.py`:**
```python
from pydantic import field_validator

class AISettings(BaseSettings):
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    send_sensitive_data: bool = Field(default=False, alias="SEND_SENSITIVE_DATA")
    session_token_budget: int = Field(default=50000, alias="SESSION_TOKEN_BUDGET")
    client_name: str = Field(default="klijent1", alias="CLIENT_NAME")
    sslmode: str = Field(default="require", alias="DB_SSLMODE")

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, v: str) -> str:
        if v.strip().lower() == "klijent1":
            import warnings
            warnings.warn(
                "CLIENT_NAME je defaultna vrijednost 'klijent1'. "
                "Promijeni u .env za ispravno logovanje.",
                UserWarning, stacklevel=2,
            )
        return v

    model_config = SettingsConfigDict(
        case_sensitive=False, extra="ignore", populate_by_name=True,
    )

_ai_settings: Optional[AISettings] = None

def get_ai_settings() -> AISettings:
    global _ai_settings
    if _ai_settings is None:
        _ai_settings = AISettings()
    return _ai_settings
```

---

### 6.2 🟡 Singleton getteri nisu thread-safe

```python
def get_db_settings():
    global _db_settings
    if _db_settings is None:
        _db_settings = DatabaseSettings()  # race condition
```

MCP thread i UI thread mogu istovremeno kreirati dvije instance.

**Rješenje (primijeniti za sve tri getter funkcije):**
```python
import threading
_settings_lock = threading.Lock()

def get_db_settings() -> DatabaseSettings:
    global _db_settings
    if _db_settings is None:
        with _settings_lock:
            if _db_settings is None:
                _db_settings = DatabaseSettings()
    return _db_settings
```

---

### 6.3 🟡 `PathSettings.model_post_init` radi I/O

Settings klasa treba biti čista konfiguracija — kreiranje direktorijuma je side effect koji pravi probleme u testovima.

**Rješenje — premjestiti u `app/run.py`:**
```python
def _init_directories() -> None:
    paths = get_path_settings()
    for d in [paths.temp_dir, paths.logs_dir]:
        d.mkdir(parents=True, exist_ok=True)
```

---

### 6.4 🟡 `DB_HOST=localhost` — tiha zamka za produkciju

Ako klijent ne postavi `DB_HOST`, aplikacija se pokušava konektovati na localhost.

**Rješenje:**
```python
@field_validator("host")
@classmethod
def warn_localhost(cls, v: str) -> str:
    if v in ("localhost", "127.0.0.1"):
        import logging
        logging.getLogger(__name__).warning(
            "DB_HOST je 'localhost' — za produkciju postavi IP servera u .env"
        )
    return v
```

---

### 6.5 🟢 Nema `APP_ENV` varijable

`DEBUG=False` nije isti kao razlikovanje dev/staging/prod.

```python
# Dodati u AppSettings
app_env: str = Field(default="production", alias="APP_ENV")

@property
def is_development(self) -> bool:
    return self.app_env.lower() == "development"
```

---

## 7. app/run.py

### 7.1 🟡 Globalni `_mcp_client` — anti-pattern

```python
_mcp_client = None  # module-level global

def _start_mcp_server(app):
    global _mcp_client  # anti-pattern
```

**Rješenje — enkapsulirati ili proslijediti kao argument:**
```python
# Opcija A: proslijediti MainWindow-u
win = MainWindow(mcp_client=_mcp_client)

# Opcija B: AppState klasa
class AppState:
    mcp_client = None
```

---

### 7.2 🟢 `_init_directories()` nedostaje

Direktorijumi se trenutno kreiraju u `PathSettings.model_post_init` (side effect).
Nakon refaktora, trebaju biti eksplicitno inicirani ovdje.

---

## 8. gui/tabs/agent/widgets/chat_worker.py

### 8.1 🟡 `_sync_pe_docs_to_header` dupliciran na 3 mjesta

Agent report `pe-rub44-4.md` potvrđuje da je identična logika kopirana u:
- `gui/tabs/naimenovanja_view.py`
- `gui/tabs/faktura_view.py`
- `gui/tabs/agent/services/import_pipeline_service.py`

Treba biti jedna funkcija u zajedničkom servisu (npr. `services/pe_docs_service.py`).

---

### 8.2 🟡 `_build_context()` je god method — 250+ linija

Jedan metod čita draft, gradi 6 kontekst zona, poziva 4 servisa, formatira tablice.

**Prijedlog:**
```python
class ContextBuilder:
    def __init__(self, draft, message: str, memory_service=None): ...
    def build(self) -> str: ...
    def _zone_status(self) -> list: ...
    def _zone_session(self) -> list: ...
    def _zone_items(self) -> list: ...
    def _zone_knowledge(self) -> list: ...
    def _zone_regulatory(self) -> list: ...
    def _zone_declarations(self) -> list: ...
```

---

### 8.3 🟢 `import os` unutar metode

```python
def _build_session_zone(self, lines: list) -> list:
    import os  # treba biti na vrhu fajla
```

---

## 9. Repozitorij i dokumentacija

### 9.1 🟠 Veliki data fajlovi u gitu

| Fajl | Veličina |
|------|----------|
| `database/traders.json` | 552 KB |
| `database/exporters.json` | 366 KB |
| `docs/Galvni-fajlovi/inspection_tariff_rules_master.json` | 675 KB |
| `docs/Galvni-fajlovi/inspection_master_view_by_tariff.json` | 534 KB |
| `docs/Galvni-fajlovi/inspection_legal_context_master.json` | 188 KB |

```bash
# Dodati u .gitignore
database/traders.json
database/exporters.json
docs/Galvni-fajlovi/*.json

# Ukloniti iz trackinga
git rm --cached database/traders.json database/exporters.json
git rm --cached "docs/Galvni-fajlovi/*.json"
```

---

### 9.2 🟠 Migracijski konflikt — dva fajla s brojem 001

```
database/migrations/001_add_declaration_tables.sql
database/migrations/001_declarations_history.sql
```

```bash
git mv database/migrations/001_declarations_history.sql \
       database/migrations/002_declarations_history.sql
```

---

### 9.3 🟡 GitNexus auto-injektuje u CLAUDE.md

`npx gitnexus analyze` može mijenjati agent-instrukcijska pravila u `CLAUDE.md`. Vendor lock-in u primarni instrukcijski fajl. Razmotriti premještanje GitNexus bloka u zasebni skills fajl.

---

### 9.4 🟢 README sadrži hardcoded razvojnu putanju

```
cd /home/radovan/Desktop/PythonProjects/deklarant_pro
```

Zamijeniti s generičkom putanjom.

---

### 9.5 🟢 `test_app.py` pomenut u README ali nije u repozitoriju

Dodati fajl ili ukloniti sekciju iz README-a.

---

## 10. Pozitivni nalazi — što radi dobro

Namjerno evidentirano da agent koji radi popravke ne dirne ove dijelove:

| Oblast | Što je dobro |
|--------|-------------|
| Import pipeline | 4-koračni fiksni redosljed, dokumentovan. Stateful singleton za Excel+PDF pairing je ispravno rješenje. |
| Kombinovani importeri | `consumed_paths` sprječava duplikat-import pri Excel+PDF paru. |
| Fuzzy pairing | 80% prefix matching za `_similar_invoice_number` — tolerantan na " PL" / "-packing" sufikse vendora. |
| ASYCUDA 99-item limit | `MAX_ASYCUDA_ITEMS=99` + split na dva draft toka. `pending_next_declaration` ne dira tabove. |
| Prompt injection zaštita | 9 regex pattern-a pokrivaju osnovne vektore. `_MAX_MESSAGE_LEN=2000` na korisničku poruku. |
| Token budget | `check_budget()` prije API poziva. `SESSION_TOKEN_BUDGET` konfigurabilno. |
| Kontekst zone | Selektivno uključivanje knowledge/regulatory/declaration zona po tipu upita štedi tokene. |
| Carinski FTS | `catalogs.carinski_dokumenti` s PostgreSQL `tsvector` + GIN indeksom. Ispravno koristi `simple` rječnik za B/S/H. |
| Inspection rules | Prefix matching s `tariff_len` kolom — clean SQL, nema hardkodiranog loopa u Pythonu. |
| PE/OST sinhronizacija | `_sync_pe_docs_to_header` automatski ažurira zaglavlje. Add-only merge pri XML uvozu. |
| Attached docs guard | `clear_refs_on_import` flag + `save_to_draft()` prije reload-a sprječava gubitak korisničkih podataka. |
| Window geometry | `SafeMessageBox` i `exec_dialog_preserving_geometry` centralizuju modal parent problem. |
| Rb.23 auto-kurs | `editingFinished` umjesto `textChanged` — ne okida API na svaki karakter. EUR=1.95583 fiksno, ostalo CBBH API. |
| MCP arhitektura | Čist stdio JSON-RPC ugovor. Lokalni subprocess → Ubuntu server bez promjene tool ugovora. |
| `InvoiceLine.from_any()` | Normalizuje 10+ varijanti naziva polja od različitih importera. |
| `SEND_SENSITIVE_DATA=false` | Privacy-by-default ispravno implementiran u `_build_session_zone`. |
| `draft.dirty` + callbacks | Koherentan mehanizam za praćenje promjena i reaktivni refresh tabova. |

---

## 11. Konsolidovana prioritetna lista

| # | Problem | Fajl | Prioritet |
|---|---------|------|-----------|
| 1 | EUR1 nedostaje u `InvoiceLine.key()` | `core/draft/draft.py` | 🔴 Kritično |
| 2 | JIB leak u `_search_declarations_context` | `chat_worker.py` | 🔴 Hitno |
| 3 | `_search_pg_partners` ignorira `SEND_SENSITIVE_DATA` | `chat_worker.py` | 🔴 Hitno |
| 4 | PostgreSQL konekcija bez SSL | `database/db.py` + `settings.py` | 🔴 Hitno |
| 5 | `SEND_SENSITIVE_DATA=true` bez provjere providera | `chat_worker.py` | 🟠 Visoko |
| 6 | `AISettings` klasa nedostaje — `os.getenv()` razbacano | `config/settings.py` | 🟠 Visoko |
| 7 | Veliki data fajlovi u gitu | `database/`, `docs/` | 🟠 Visoko |
| 8 | Migracijski konflikt `001_*` | `database/migrations/` | 🟠 Visoko |
| 9 | SQLite baza — relativna putanja | `database/repository.py` | 🟠 Visoko |
| 10 | `_sync_pe_docs_to_header` dupliciran na 3 mjesta | `naim_view`, `faktura_view`, `import_pipeline_service` | 🟠 Visoko |
| 11 | Pool nije thread-safe | `database/db.py` | 🟡 Srednje |
| 12 | Nema health check-a za mrtve konekcije | `database/db.py` | 🟡 Srednje |
| 13 | Nekonzistentna duljina tarifnog koda (10 vs 11) | `db.py` vs `chat_worker.py` | 🟡 Srednje |
| 14 | Tri paralelne tabele za partnere | `database/db.py` | 🟡 Srednje |
| 15 | `get_connection()` bez lifecycle — ostaviti kao deprecated | `database/db.py` | 🟡 Srednje |
| 16 | `AttachmentRepository` ne inicijalizuje tabele | `database/repository.py` | 🟡 Srednje |
| 17 | `get_all()` bez paginacije | `database/repository.py` | 🟡 Srednje |
| 18 | Callback iteracija bez kopije liste | `core/draft/draft.py` | 🟡 Srednje |
| 19 | Nema `remove_item()` | `core/draft/draft.py` | 🟡 Srednje |
| 20 | `apply_to_all()` bez `mark_dirty()` i bez validacije | `core/draft/draft.py` | 🟡 Srednje |
| 21 | Settings singleton nije thread-safe | `config/settings.py` | 🟡 Srednje |
| 22 | `PathSettings` radi I/O | `config/settings.py` | 🟡 Srednje |
| 23 | `CLIENT_NAME` validacija | `config/settings.py` | 🟡 Srednje |
| 24 | `DB_HOST=localhost` warning | `config/settings.py` | 🟡 Srednje |
| 25 | `_build_context()` god method | `chat_worker.py` | 🟡 Srednje |
| 26 | Globalni `_mcp_client` | `app/run.py` | 🟡 Srednje |
| 27 | GitNexus u CLAUDE.md | `CLAUDE.md` | 🟡 Srednje |
| 28 | `APP_ENV` varijabla nedostaje | `.env.example` | 🟢 Nisko |
| 29 | README hardcoded putanja | `README.md` | 🟢 Nisko |
| 30 | `test_app.py` nedostaje | `README.md` | 🟢 Nisko |
| 31 | `import os` unutar metode | `chat_worker.py` | 🟢 Nisko |
| 32 | `DeclarationDraft` bez `slots=True` | `core/draft/draft.py` | 🟢 Nisko |
| 33 | `header: Dict` — nedovršena migracija | `core/draft/draft.py` | 🟢 Nisko |

---

*Dokument generisan statičkom analizom koda i agent execution reports. Aplikacija nije pokretana.*  
*Broj 1 (EUR1 u grouping ključu) treba hitnu provjeru — ako `CreateNaimenovanjaService` koristi `InvoiceLine.key()`, bug je aktivan u produkciji.*
