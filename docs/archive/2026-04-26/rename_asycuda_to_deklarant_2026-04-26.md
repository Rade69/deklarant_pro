# Preimenovanje ASYCUDA Pro → Deklarant Pro

**Datum:** 2026-04-26  
**Commit:** `3354c90` (main) → fast-forward merge u `dev`  
**Broj fajlova:** 160 promijenjenih, 161 u merge-u

---

## Šta je urađeno

### 1. Oporavljeni obrisani fajlovi
Tokom renaming-a greškom su obrisana 3 fajla koji se aktivno importuju:
- `exporters/asycuda_xml_builder.py` — importuje se u `zaglavlje_controller.py` i `xml_workflow_service.py`
- `styles/asycuda_modern_material.qss` — učitava se u `gui/main_window.py`
- `styles/asycuda_pro_ui.qss` — dodatni UI stilovi

Vraćeni komandom: `git checkout HEAD -- <fajl>`

### 2. Zamjena naziva kroz codebase (160 fajlova)
| Staro | Novo |
|---|---|
| Naslov prozora `"ASYCUDA Pro"` | `"Deklarant Pro"` |
| `app.setApplicationName("ASYCUDA Pro")` | `"Deklarant Pro"` |
| Logger namespace `asycuda_pro.*` | `deklarant_pro.*` |
| PostgreSQL DB name `asycuda_pro` | `deklarant_pro` |
| SQLite referenca `asycuda_sistem.db` | `deklarant_sistem.db` |
| Default DB user `asycuda_app` | *(nije promijenjeno — vidjeti TODO)* |

### 3. Novi fajlovi kreirani
- `exporters/deklarant_xml_builder.py` — nova kopija XML buildera
- `styles/deklarant_modern_material.qss` — novi stil
- `styles/deklarant_pro_ui.qss` — novi UI stil
- `assets/deklarant-pro.svg` — nova SVG ikonica

### 4. Preimenovani fajlovi (git rename)
- `assets/asycuda-pro.svg` → `assets/deklarant-pro.svg`
- `agent_tasks/analiza_poredjenja_asycuda_xml.md` → `...deklarant_xml.md`
- `agent_tasks/kako_primijeniti_12_claude_code_principa_na_asycuda_pro.md` → `...deklarant_pro.md`
- `agent_tasks/three_layer_outcome_agent_asycuda_pro.md` → `...deklarant_pro.md`

### 5. Git operacije
```bash
git add -A
git commit -m "refactor: preimenovanje aplikacije ASYCUDA Pro → Deklarant Pro"
git checkout dev
git merge main --no-edit   # fast-forward, bez konflikta
```

---

## Šta je NAMJERNO zadržano sa starim imenom

Ovi fajlovi/reference su zadržani jer se i dalje koriste pod starim imenom:

| Fajl | Razlog |
|---|---|
| `exporters/asycuda_xml_builder.py` | Importuje se na 2 mjesta — mijenjati zajedno |
| `styles/asycuda_modern_material.qss` | Referencira se u `main_window.py` |
| `services/admin/analytics_service.py` | Traži `asycuda.db` u `~/.deklarant_pro/` |
| `services/admin/backup_service.py` | Traži `asycuda.db`, kreira `asycuda_backup_*.db` |
| `services/admin/log_service.py` | Kreira log fajl `asycuda.log` |
| `run.py:18` | Log fajl `asycuda_launch.log` |
| `gui/dialogs/db_setup_dialog.py:217` | Default korisnik `asycuda_app` |

---

## TODO — Server migracija (kada bude prilike)

- [ ] Preimenovati PostgreSQL bazu: `asycuda_pro` → `deklarant_pro` na serveru
- [ ] Ažurirati analytics/backup servise da koriste `deklarant.db`
- [ ] Ažurirati log fajl nazive
- [ ] Ažurirati default DB korisnika u db_setup_dialog
- [ ] Zamijeniti `exporters/asycuda_xml_builder.py` sa `deklarant_xml_builder.py`
- [ ] Zamijeniti `styles/asycuda_modern_material.qss` sa `deklarant_modern_material.qss`
