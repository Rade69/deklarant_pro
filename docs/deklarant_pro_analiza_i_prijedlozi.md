# Deklarant Pro — Analiza i prijedlozi za poboljšanja

> Grana: `dev` | Datum analize: 2026-05-05  
> Analizirani fajlovi: file tree, README.md, CLAUDE.md, app/run.py, .env.example, config/settings.py, gui/tabs/agent/widgets/chat_worker.py

---

## Sadržaj

1. [Sigurnosni problemi](#1-sigurnosni-problemi)
2. [Konfiguracijski problemi](#2-konfiguracijski-problemi)
3. [Arhitekturalni problemi](#3-arhitekturalni-problemi)
4. [Problemi u repozitoriju](#4-problemi-u-repozitoriju)
5. [Manji problemi](#5-manji-problemi)
6. [Prioritetna lista](#6-prioritetna-lista)

---

## 1. Sigurnosni problemi

### 1.1 JIB se šalje LLM-u — kontradikcija s komentarom

**Fajl:** `gui/tabs/agent/widgets/chat_worker.py` → metoda `_search_declarations_context()`

**Problem:**  
U `_build_session_zone` stoji komentar *"JIB se nikad ne šalje LLM-u"*, ali u `_search_declarations_context` JIB odlazi direktno u kontekst bez ikakve provjere:

```python
# TRENUTNI KOD — BUG
f"  JIB: {r.get('consignee_jib','?')}"
```

**Rješenje:**

```python
# ISPRAVKA — maskirati ili izostaviti JIB
send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"

if send_sensitive:
    jib_display = r.get('consignee_jib', '?')
else:
    jib_display = "[JIB skriven]"

ctx.append(
    f"  Izvoznik: {r.get('exporter_name','?')[:50]} | "
    f"Primalac: {r.get('consignee_name','?')[:40]} | "
    f"JIB: {jib_display}"
)
```

---

### 1.2 `_search_pg_partners` ignorira `SEND_SENSITIVE_DATA`

**Fajl:** `gui/tabs/agent/widgets/chat_worker.py` → metoda `_search_pg_partners()`

**Problem:**  
Puna imena firmi iz PostgreSQL baze idu u LLM kontekst bez ikakvog maskiranja, bez obzira na postavku `SEND_SENSITIVE_DATA`:

```python
# TRENUTNI KOD — BUG
f"  [{row['type']}] {row['name']} (kod: {row['code']})"
```

**Rješenje:**

```python
def _search_pg_partners(self, query: str) -> list:
    send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"
    try:
        from database.db import get_db_connection
        words = [w for w in re.split(r'\s+', query) if len(w) >= 3]
        if not words:
            return []
        patterns = [f"%{w}%" for w in words[:3]]
        or_clause = " OR ".join(["name ILIKE %s"] * len(patterns))
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT code, name, type FROM public.traders "
                    f"WHERE {or_clause} LIMIT 15",
                    patterns,
                )
                results = []
                for row in cur.fetchall():
                    if send_sensitive:
                        name_display = row['name']
                    else:
                        name_display = "[ime skriveno — SEND_SENSITIVE_DATA=false]"
                    results.append(
                        f"  [{row['type']}] {name_display} (kod: {row['code']})"
                    )
        return list(dict.fromkeys(results))
    except Exception:
        return []
```

---

### 1.3 Nema provjere da li je provider lokalan kada je `SEND_SENSITIVE_DATA=true`

**Fajl:** `gui/tabs/agent/widgets/chat_worker.py` → metoda `_build_session_zone()`

**Problem:**  
`.env.example` eksplicitno kaže `SEND_SENSITIVE_DATA=true` je dozvoljeno *"SAMO za lokalni Ollama"*, ali kod ne provjerava ovo. Ako korisnik postavi `SEND_SENSITIVE_DATA=true` s aktivnim `GROQ_API_KEY`, puna poslovna imena idu na cloud.

**Rješenje — dodati provjeru u `LLMProvider` ili u `_build_session_zone`:**

```python
def _build_session_zone(self, lines: list) -> list:
    import os
    send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"

    # Sigurnosna provjera: SEND_SENSITIVE_DATA=true dozvoljen samo za lokalne providere
    if send_sensitive:
        from .llm_provider import LLMProvider
        provider = LLMProvider()
        if provider.active_provider() not in ("ollama", "local", "none"):
            import logging
            logging.getLogger(__name__).warning(
                "SEND_SENSITIVE_DATA=true detektovan sa cloud providerom '%s'. "
                "Prisilno maskiranje podataka.",
                provider.active_provider()
            )
            send_sensitive = False  # Prisilno maskiranje
    # ... ostatak metode ostaje isti
```

---

### 1.4 PostgreSQL konekcija bez SSL-a

**Fajl:** `config/settings.py` → klasa `DatabaseSettings`

**Problem:**  
`connection_string` generiše URL bez SSL parametra. Sav SQL promet između Windows klijenata i Ubuntu servera ide unencrypted po mreži:

```python
# TRENUTNI KOD
return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
```

**Rješenje:**

```python
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=5432, alias="DB_PORT")
    database: str = Field(default="deklarant_pro", alias="DB_NAME")
    user: str = Field(default="postgres", alias="DB_USER")
    password: str = Field(..., alias="DB_PASSWORD")
    sslmode: str = Field(default="require", alias="DB_SSLMODE")  # NOVO

    @property
    def connection_string(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?sslmode={self.sslmode}"  # NOVO
        )
```

Dodati u `.env.example`:
```
DB_SSLMODE=require
# Za development/lokalni server gdje SSL nije konfigurisan:
# DB_SSLMODE=disable
```

---

## 2. Konfiguracijski problemi

### 2.1 `SEND_SENSITIVE_DATA` se čita van centralnog settings sistema

**Fajlovi:** `chat_worker.py` (i potencijalno drugi)

**Problem:**  
`config/settings.py` postoji upravo za centralizovanu konfiguraciju s Pydantic validacijom. Direktan `os.getenv()` zaobilazi ovu centralizaciju:

```python
# TRENUTNI KOD — razbacano po fajlovima
import os
send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"
```

**Rješenje — dodati `AISettings` klasu u `config/settings.py`:**

```python
class AISettings(BaseSettings):
    """Konfiguracija za AI/LLM integraciju."""

    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")

    send_sensitive_data: bool = Field(default=False, alias="SEND_SENSITIVE_DATA")
    session_token_budget: int = Field(default=50000, alias="SESSION_TOKEN_BUDGET")
    client_name: str = Field(default="klijent1", alias="CLIENT_NAME")

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, v: str) -> str:
        if v.strip().lower() == "klijent1":
            import warnings
            warnings.warn(
                "CLIENT_NAME je još uvijek defaultna vrijednost 'klijent1'. "
                "Promijeni u .env fajlu za ispravno logovanje.",
                UserWarning,
                stacklevel=2,
            )
        return v


_ai_settings: Optional[AISettings] = None

def get_ai_settings() -> AISettings:
    global _ai_settings
    if _ai_settings is None:
        _ai_settings = AISettings()
    return _ai_settings
```

Upotreba u `chat_worker.py`:
```python
from config.settings import get_ai_settings
send_sensitive = get_ai_settings().send_sensitive_data
```

---

### 2.2 `CLIENT_NAME=klijent1` — niko neće promijeniti default

**Fajl:** `.env.example`, `config/settings.py`

**Problem:**  
Svaki klijent koji instalira aplikaciju vjerovatno neće promijeniti `CLIENT_NAME=klijent1`, što čini audit log u PostgreSQL beskorisnim.

**Rješenje:**  
- Dodati `@field_validator` (vidi sekciju 2.1 gore)
- Prikazati upozorenje pri startu aplikacije ako je `CLIENT_NAME` defaultna vrijednost

```python
# app/run.py — u main() funkciji, nakon db provjere
from config.settings import get_ai_settings
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    ai_cfg = get_ai_settings()
    if w:
        # Prikaži QMessageBox upozorenje korisniku
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "Konfiguracija", str(w[0].message))
```

---

### 2.3 `DB_HOST` default je `localhost` — tiha zamka

**Fajl:** `config/settings.py`

**Problem:**  
Ako klijent ne postavi `DB_HOST` u `.env`, aplikacija se pokušava konektovati na `localhost:5432`, javlja kriptičnu grešku, a korisnik ne zna zašto.

**Rješenje:**

```python
from pydantic import Field, field_validator

class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost", alias="DB_HOST")

    @field_validator("host")
    @classmethod
    def warn_localhost(cls, v: str) -> str:
        if v == "localhost" or v == "127.0.0.1":
            import logging
            logging.getLogger(__name__).warning(
                "DB_HOST je 'localhost' — za produkciju postavi IP adresu servera u .env"
            )
        return v
```

---

### 2.4 Nema `APP_ENV` varijable

**Fajl:** `.env.example`, `config/settings.py`

**Problem:**  
`DEBUG=False` nije ekvivalent razlikovanju dev/staging/prod okruženja.

**Rješenje — dodati u `AppSettings`:**

```python
class AppSettings(BaseSettings):
    app_env: str = Field(default="production", alias="APP_ENV")
    # ...

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"
```

Dodati u `.env.example`:
```
# Okruženje: development | staging | production
APP_ENV=production
```

---

## 3. Arhitekturalni problemi

### 3.1 Singleton pattern nije thread-safe

**Fajl:** `config/settings.py`

**Problem:**  
MCP server se pokreće u zasebnoj niti (`app/run.py`). Ako ta nit i UI thread pozovu `get_db_settings()` istovremeno dok je `_db_settings is None`, mogu kreirati dvije instance (race condition):

```python
# TRENUTNI KOD — nije thread-safe
def get_db_settings():
    global _db_settings
    if _db_settings is None:
        _db_settings = DatabaseSettings()  # race condition ovdje
    return _db_settings
```

**Rješenje:**

```python
import threading

_db_settings: Optional[DatabaseSettings] = None
_settings_lock = threading.Lock()

def get_db_settings() -> DatabaseSettings:
    global _db_settings
    if _db_settings is None:
        with _settings_lock:
            if _db_settings is None:  # double-checked locking
                _db_settings = DatabaseSettings()
    return _db_settings
```

Primijeniti isti pattern za `get_path_settings()` i `get_app_settings()`.

---

### 3.2 `PathSettings.model_post_init` radi I/O

**Fajl:** `config/settings.py`

**Problem:**  
Settings klasa treba biti čista konfiguracija. Kreiranje direktorijuma u `model_post_init` znači da svaki import koji dirne settings može imati fajlsistem side effect — neočekivano ponašanje u testovima.

**Rješenje — premjestiti inicijalizaciju direktorijuma u `app/run.py`:**

```python
# config/settings.py — ukloniti model_post_init

# app/run.py — dodati eksplicitno
def _init_directories() -> None:
    """Kreira potrebne direktorijume pri pokretanju aplikacije."""
    paths = get_path_settings()
    for d in [paths.temp_dir, paths.logs_dir]:
        d.mkdir(parents=True, exist_ok=True)

def main():
    # ...
    _init_directories()
    # ...
```

---

### 3.3 `_build_context()` je god method (250+ linija)

**Fajl:** `gui/tabs/agent/widgets/chat_worker.py`

**Problem:**  
Jedan metod čita draft, gradi 6 kontekst zona, poziva 4 servisa, formatira tablice i parsira korisnički upit. Nije testabilan niti lako održiv.

**Prijedlog refaktorisanja:**

```python
class ContextBuilder:
    """Gradi LLM kontekst iz drafta — svaka zona je zasebna metoda."""

    def __init__(self, draft, message: str, memory_service=None):
        self.draft = draft
        self.message = message
        self.memory_service = memory_service
        self._zones = ChatWorker._determine_context_zones(message.lower())

    def build(self) -> str:
        parts = []
        parts.extend(self._zone_status())       # uvijek
        parts.extend(self._zone_session())      # uvijek
        parts.extend(self._zone_items())        # uvijek
        if 'knowledge' in self._zones:
            parts.extend(self._zone_knowledge())
        if 'regulatory' in self._zones:
            parts.extend(self._zone_regulatory())
        if 'declarations' in self._zones:
            parts.extend(self._zone_declarations())
        return "\n".join(parts)
```

Ovako svaka zona može biti zasebno testirana. `_build_context()` postaje:
```python
def _build_context(self) -> str:
    return ContextBuilder(self.draft, self.message, self.memory_service).build()
```

---

### 3.4 Globalni `_mcp_client` u `app/run.py`

**Fajl:** `app/run.py`

**Problem:**  
Globalni mutabilni state s `global` keyword-om u funkcijama je anti-pattern koji otežava testiranje i praćenje lifecycle-a:

```python
_mcp_client = None  # module-level global

def _start_mcp_server(app):
    global _mcp_client  # anti-pattern
```

**Rješenje — enkapsulirati u klasu:**

```python
class AppState:
    """Centralni holder za global application state."""
    mcp_client = None

    @classmethod
    def get_mcp_client(cls):
        return cls.mcp_client

    @classmethod
    def set_mcp_client(cls, client):
        cls.mcp_client = client

# Ili jednostavnije — proslijediti mcp_client kao argument MainWindow-u
win = MainWindow(mcp_client=_mcp_client)
```

---

## 4. Problemi u repozitoriju

### 4.1 Veliki data fajlovi u gitu

**Problem:**  
Sljedeći fajlovi bloataju git historiju i svaki commit koji ih dotakne duplira ih u `.git/objects`:

| Fajl | Veličina |
|------|----------|
| `database/traders.json` | 552 KB |
| `database/exporters.json` | 366 KB |
| `docs/Galvni-fajlovi/inspection_tariff_rules_master.json` | 675 KB |
| `docs/Galvni-fajlovi/inspection_legal_context_master.json` | 188 KB |
| `docs/Galvni-fajlovi/inspection_master_view_by_tariff.json` | 534 KB |

**Rješenje:**

```bash
# Dodati u .gitignore
database/traders.json
database/exporters.json
docs/Galvni-fajlovi/*.json

# Ukloniti iz git trackinga (ne briše fajlove lokalno)
git rm --cached database/traders.json
git rm --cached database/exporters.json
git rm --cached "docs/Galvni-fajlovi/*.json"
git commit -m "chore: uklanjanje velikih data fajlova iz git trackinga"
```

Alternativno: koristiti `git-lfs` ako fajlovi moraju ostati u repozitoriju.

---

### 4.2 Migracijski konflikt — dva fajla s brojem 001

**Problem:**  
```
database/migrations/001_add_declaration_tables.sql
database/migrations/001_declarations_history.sql
```

Oba fajla imaju broj `001`. Svaki alat koji sortira migracije po broju (uključujući ručne skripte) će ih tretirati konfliktno.

**Rješenje:**

```bash
# Pregledati sadržaj i odrediti koji je stariji/noviji
# Preimenovati jedan od njih
git mv database/migrations/001_declarations_history.sql \
       database/migrations/002_declarations_history.sql
git commit -m "fix: ispravka konflikta u numeraciji migracija"
```

---

### 4.3 GitNexus auto-injektuje u CLAUDE.md

**Problem:**  
Na dnu `CLAUDE.md` postoji auto-injektovan blok:
```
<!-- gitnexus:start -->
NEVER edit a function without first running gitnexus_impact...
<!-- gitnexus:end -->
```

Alatka `npx gitnexus analyze` može mijenjati tvoja pravila za agente. Ovo je vendor lock-in u primarni agent-instrukcijski fajl.

**Prijedlog:**  
- Razmotriti da li GitNexus aktivno koristiš i da li donosi vrijednost
- Ako da — prebaciti ove instrukcije u zasebni fajl (npr. `.claude/skills/gitnexus/`) umjesto u root `CLAUDE.md`
- Ako ne — ukloniti GitNexus integraciju

---

### 4.4 `agent_reports/` i `agent_tasks/` u root-u

**Problem:**  
Za 6 mjeseci ovo će biti 100+ fajlova direktno u root-u projekta. Struktura već postoji u `docs/` folderu.

**Prijedlog:**

```bash
git mv agent_reports docs/agent_reports
git mv agent_tasks docs/agent_tasks
git commit -m "chore: premještanje agent reporta u docs/"
```

---

## 5. Manji problemi

### 5.1 README sadrži hardcoded razvojnu putanju

**Fajl:** `README.md`

```markdown
# TRENUTNO — treba ukloniti
cd /home/radovan/Desktop/PythonProjects/deklarant_pro
```

Zamijeniti sa:
```markdown
cd /putanja/do/deklarant_pro
```

---

### 5.2 `test_app.py` pomenut u README ali nije u repozitoriju

**Fajl:** `README.md`

README dokumentuje pokretanje `python3 test_app.py` ali fajl nije pronađen u stablu grane `dev`. Ili dodati fajl ili ukloniti sekciju iz README-a.

---

### 5.3 `import os` unutar metode

**Fajl:** `chat_worker.py` → `_build_session_zone()`

```python
# TRENUTNO — minor code smell
def _build_session_zone(self, lines: list) -> list:
    import os
    send_sensitive = ...
```

Premjestiti na vrh fajla zajedno s ostalim importima.

---

## 6. Prioritetna lista

| # | Problem | Fajl | Prioritet |
|---|---------|------|-----------|
| 1 | JIB leak u `_search_declarations_context` | `chat_worker.py` | 🔴 Hitno |
| 2 | `_search_pg_partners` ignorira `SEND_SENSITIVE_DATA` | `chat_worker.py` | 🔴 Hitno |
| 3 | PostgreSQL konekcija bez SSL | `config/settings.py` | 🔴 Hitno |
| 4 | `SEND_SENSITIVE_DATA=true` bez provjere providera | `chat_worker.py` | 🟠 Visoko |
| 5 | `SEND_SENSITIVE_DATA` van centralnog settings sistema | `chat_worker.py` | 🟠 Visoko |
| 6 | Veliki data fajlovi u gitu | `database/`, `docs/` | 🟠 Visoko |
| 7 | Migracijski konflikt `001_*` | `database/migrations/` | 🟠 Visoko |
| 8 | `CLIENT_NAME` validacija | `config/settings.py` | 🟡 Srednje |
| 9 | `DB_HOST=localhost` warning | `config/settings.py` | 🟡 Srednje |
| 10 | Singleton nije thread-safe | `config/settings.py` | 🟡 Srednje |
| 11 | `PathSettings` radi I/O | `config/settings.py` | 🟡 Srednje |
| 12 | `AISettings` klasa nedostaje | `config/settings.py` | 🟡 Srednje |
| 13 | `_build_context()` god method | `chat_worker.py` | 🟡 Srednje |
| 14 | Globalni `_mcp_client` | `app/run.py` | 🟡 Srednje |
| 15 | GitNexus u CLAUDE.md | `CLAUDE.md` | 🟡 Srednje |
| 16 | `agent_reports/` u root-u | repo root | 🟢 Nisko |
| 17 | README hardcoded putanja | `README.md` | 🟢 Nisko |
| 18 | `test_app.py` nedostaje | `README.md` | 🟢 Nisko |
| 19 | `import os` unutar metode | `chat_worker.py` | 🟢 Nisko |
| 20 | `APP_ENV` varijabla nedostaje | `.env.example` | 🟢 Nisko |

---

*Dokument generisan na osnovu statičke analize koda — nije pokretana aplikacija niti izvršavani testovi.*
