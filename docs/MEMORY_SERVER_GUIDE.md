# ASYCUDA Pro - Memory Configuration

Konfiguracija za pristup MCP Memory Serveru.

## Osnovna konfiguracija

```yaml
memory:
  # Server URL
  server_url: "http://localhost:8765"
  
  # Projekt identifikator
  project_id: "asycuda_pro"
  project_name: "ASYCUDA Pro - Carinska deklaracija"
  
  # Dozvoljeni tipovi memorije za čitanje
  allowed_read_types:
    - fact
    - decision
    - rule
    - exception
    - preference
    - session_summary
    - workflow
  
  # Dozvoljeni tipovi memorije za pisanje
  allowed_write_types:
    - session_summary
    - proposed_fact
    - proposed_decision
    - workflow
  
  # Pravila za pretragu
  retrieval_rules:
    default_scope: "project"
    require_status: "approved"
    cross_project_allowed: false
    max_results: 20
  
  # Pravila za pisanje
  write_rules:
    require_source_ref: true
    default_status: "proposed"
    auto_verify: false
    require_scope: true
  
  # Agent konfiguracija
  agents:
    default_agent_name: "claude_code"
    session_timeout_minutes: 60
```

## Kako koristiti

### 1. Prije rada - pročitaj kontekst
```python
# Python primer
import requests

config = {
    "server_url": "http://localhost:8765",
    "project_id": "asycuda_pro"
}

# Dobij projektni kontekst
response = requests.post(
    f"{config['server_url']}/project-context",
    json={
        "project_id": config["project_id"],
        "include_recent_decisions": True,
        "include_known_issues": True,
        "include_project_rules": True,
        "limit_per_category": 5
    }
)

context = response.json()
```

### 2. Tokom rada - pretraži memoriju
```python
# Pretraži memoriju
response = requests.post(
    f"{config['server_url']}/memory/search",
    json={
        "project_id": config["project_id"],
        "query": "tarifni broj format",  # opcionalno za semantic search
        "memory_type": "fact",  # opcionalno
        "topic": "tarifni broj",  # opcionalno
        "limit": 10
    }
)

results = response.json()
```

### 3. Nakon rada - sačuvaj sažetak
```python
# Sačuvaj session summary
response = requests.post(
    f"{config['server_url']}/memory/session-summary",
    json={
        "project_id": config["project_id"],
        "session_id": "session_123",
        "agent_name": "claude_code",
        "task_description": "Implementacija MCP memory servera",
        "findings": "Kreiran multi-tenant memory sistem",
        "unresolved_issues": "Treba dodati semantic search",
        "next_steps": "Integrisati sa postojećim agentima",
        "metadata": {
            "duration_minutes": 45,
            "files_modified": ["main.py", "models.py"]
        }
    }
)
```

### 4. Sačuvaj odluku
```python
# Sačuvaj odluku
response = requests.post(
    f"{config['server_url']}/memory/decision",
    json={
        "project_id": config["project_id"],
        "decision_topic": "tarifni broj format",
        "decision_text": "Koristiti 8-cifreni format bez tačaka interno",
        "rationale": "Konzistentnost sa ASYCUDA XML formatom",
        "alternatives_considered": "10-cifreni format, format sa tačkama",
        "impact": "Svi parseri moraju konvertovati u ovaj format",
        "scope_id": "core/draft",
        "source_ref": "AGENTS.md#4-tarifni-broj-format"
    }
)
```

## Projektna pravila (ručno uneti u memory server)

1. **Tarifni broj format**: Interno koristiti 8-cifreni format bez tačaka
2. **Field names**: Koristiti srpske nazive polja na InvoiceLine modelu
3. **Arhitektura**: 3-layer pattern (View-Controller-Service)
4. **Import/Export**: Svi importeri moraju vraćati ImportResult objekat

## Poznati problemi

1. **PDF parseri**: Neki PDF-ovi ne sadrže težine po liniji
2. **Tarifni lookup**: Konverzija 8→10 cifara za PostgreSQL lookup
3. **EUR.1 brojevi**: Validacija formata i jedinstvenost po zemlji

## Globalna pravila (system scope)

Pristupiti preko:
```python
response = requests.post(
    f"{config['server_url']}/memory/search",
    json={
        "project_id": "system_rules",  # ili "shared_knowledge"
        "scope_type": "system",
        "limit": 10
    }
)
```

## Testiranje konekcije

```bash
# Health check
curl http://localhost:8765/health

# Proveri da li projekt postoji
curl -X POST http://localhost:8765/project-context \
  -H "Content-Type: application/json" \
  -d '{"project_id": "asycuda_pro"}'
```

## Napomene

- Memory server mora biti pokrenut (`python main.py`)
- Prvo kreirati projekt u memory serveru ako ne postoji
- Svi upisi idu pod `project_id: "asycuda_pro"`
- Retrieval je po defaultu ograničen na ovaj projekt
- Cross-project search zahteva eksplicitnu dozvolu