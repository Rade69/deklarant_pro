# Tehnički dug — pregled celog projekta

**Datum:** 2026-08-06
**Opseg:** Ceo Deklarant Pro repozitorijum
**Metodologija:** Statička analiza, grep, skeniranje foldera

---

## 1. Veliki nepotrebni fajlovi i folderi

| Stavka | Veličina | Problem | Akcija |
|--------|----------|---------|--------|
| `.worktrees/` (6 worktree-a) | **1.5 GB** | Stari paralelni branch-evi, više nisu potrebni | `git worktree remove` za svaki |
| `.aider.chat.history.md` | 465 KB | Istorija chata od aider alata | Obrisati ili dodati u `.gitignore` |
| `dist_client/.venv/` | ~500 MB | Duplikat virtuelnog okruženja | Obrisati, koristiti samo `.venv/` u korenu |
| `client.log.lck` | 0 B | Lock fajl, nepotreban | Obrisati, dodati u `.gitignore` |
| `__pycache__/` (94 foldera) | ~50 MB | Python keš | Obrisati, već u `.gitignore` |

**Ukupno za brisanje: ~2 GB**

---

## 2. Zaostali dokumenti u korenu

| Fajl | Problem | Akcija |
|------|---------|--------|
| `AGENT_CODE_DOC.md` | Stari dokument | Premestiti u `docs/` ili obrisati |
| `AGENT_IMPROVEMENT_PLAN.md` | Stari plan | Premestiti u `docs/archive/` |
| `QWEN.md` | Tuđi fajl (Qwen agent) | Obrisati |
| `2026-08-05_grill_startup_performance.md` | Grill artefakt | Premestiti u `agent_reports/` |
| `2026-08-06_grill_tarifne_kvote.md` | Grill artefakt | Premestiti u `agent_reports/` |
| `WINDOWS_SETUP.md` | Setup dokument | Već postoji u `docs/setup/`? Proveriti |

---

## 3. `dist_client/` problemi

| Problem | Detalji |
|---------|---------|
| **6754 fajla u `.venv/`** | `dist_client/` ne treba svoj venv |
| **94 fajla u `gui/` bez `dist_client/` kopije** | Runtime kopija zaostaje — neki fajlovi nisu sinhronizovani |
| **`dist_client/` sadrži `.venv/`** | Treba obrisati ili dodati u `.gitignore` |

---

## 4. `nul` fajl u korenu

Fajl `nul` (0 bajtova) u korenu projekta — Windows ekvivalent `/dev/null`. Verovatno nastao greškom pri redirekciji. **Obrisati.**

---

## 5. Već rešen tehnički dug (ova sesija)

| Modul | Šta je očišćeno | Linija |
|-------|----------------|--------|
| Admin | Mrtav kod, importi, CSS, BackupService | ~900 |
| Šifrarnici | Mrtav kod, importi | ~385 |
| Agent | ChatIntentHandler eliminisan, mixin-i | ~400 |
| Naimenovanja | Sugeriši tarifu fix, dijalog | ~50 |

---

## 6. Preostali strukturni problemi

| Problem | Lokacija | Preporuka |
|---------|----------|------------|
| `ChatIntentHandler` još uvek 2900+ linija | `gui/tabs/agent/services/` | Podeliti na manje fajlove |
| `sifarnici_view.py` 3670 linija | `gui/tabs/` | Izdvojiti logiku u controller/servis |
| `FakturaView` je monolit | `gui/tabs/` | Već u toku refactor (3-layer) |
| Dupliranje `services/` i `gui/tabs/agent/services/` | Oba foldera | Konsolidovati |
| Wildcard importi u nekim widgetima | `gui/tabs/agent/widgets/` | Zameniti eksplicitnim |

---

## 7. Preporuke po prioritetu

### Odmah (nisko rizično)
1. Obrisati `.worktrees/` (1.5 GB) — `git worktree remove <name>`
2. Obrisati `nul`, `client.log.lck`
3. Obrisati `dist_client/.venv/`
4. Premestiti grill artefakte u `agent_reports/`
5. Obrisati `QWEN.md`

### Kratkoročno
6. Sinhronizovati `dist_client/` sa `gui/` i `services/`
7. Premestiti zaostale .md fajlove iz korena u `docs/`
8. Obrisati `__pycache__` foldere (`find . -name __pycache__ -exec rm -rf {} +`)

### Srednjoročno
9. Podeliti `ChatIntentHandler` na više fajlova (već pripremljeno kroz region markere)
10. Nastaviti 3-layer refactor FakturaTab-a
11. Konsolidovati `gui/tabs/agent/services/` sa `services/agent/chat/`

---

*Reviziju izvršio: Crush (DeepSeek-v4)*
