# Agent Report — Git Windows Grana
**Datum:** 2026-05-31  
**Cilj:** Postaviti git repozitorij na Windows mašini i kreirati `windows` granu na GitHub-u

---

## Šta je urađeno

### 1. Git inicijalizacija na Windows mašini
- `git init` u `C:\Users\38765\Desktop\deklarant_pro`
- `git remote add origin https://github.com/Rade69/deklarant_pro.git`
- Kreirana `windows` grana (neovisno od `main`/`dev` — bez zajedničkog ancestora)
- Konfigurisano: `user.email = radovan1969@gmail.com`, `user.name = Radovan`

### 2. .gitignore i .gitattributes
- `.gitignore`: uklonjen `dist_client/` (koji je bio na kraju fajla), dodana specifična pravila za `dist_client/.venv/`, `*.pyd`, `.env`
- `.gitattributes`: kreiran za pravilno upravljanje line endings (`.bat`/`.vbs` CRLF, `.py` LF)

### 3. Inicijalni commit (0149de9)
- 1021 fajlova u prvom commitu
- Uključuje: sav izvorni kod, `dist_client/`, `agent_reports/`, skripte

### 4. Sinhronizacija sa dev granom (d18cb79)
- Preuzeto 27 fajlova koji su se razlikovali između `windows` i `origin/dev`
- Re-aplicirane Windows-specifične zakrpe na vrh dev koda:
  - `run.py` — `SetCurrentProcessExplicitAppUserModelID`, 11pt font
  - `zaglavlje_view.py` — chevron-down SVG, sys.stderr → logger (5 mjesta)
  - `naimenovanja_view.py` — sys.stderr → logger (4 mjesta)
  - `faktura_view.py` — sys.stderr → logger (qtawesome)
  - `zaglavlje_service.py` — FAK/CMR blokada, XML auto-format detekcija
  - `zaglavlje_controller.py` — FAK/CMR filter, PE dedup po šifri
  - `naimenovanja_view.py` + `faktura_view.py` — PE dedup po šifri

---

## Stanje git grana

| Grana | Commitovi | Opis |
|-------|-----------|------|
| `origin/main` | ? | Stabilna Fedora verzija |
| `origin/dev` | 576 | Aktivni razvoj na Fedori |
| `windows` | 2 | Windows deploy + Windows zakrpe |

**Važno:** `windows` i `dev` NEMAJU zajednički ancestor. Windows grana je kreirana `git init` (ne `git checkout -b windows origin/dev`). Ovo znači:
- `git merge origin/dev` nije moguć bez `--allow-unrelated-histories`
- Sinhronizacija se radi ručno: `git checkout origin/dev -- <fajlovi>`

---

## Preporučeni tok rada unaprijed

**Kad na Fedori napravite novi commit na `dev`:**
```bash
# Na Windows mašini:
git fetch origin
# Uzmi samo promijenjene fajlove:
git checkout origin/dev -- <fajl1> <fajl2>
# Re-apliciraj Windows zakrpe ako su ti fajlovi dirani
# Commit:
git add <fajlovi>
git commit -m "sync: preuzeto sa dev grane YYYY-MM-DD"
git push origin windows
```

**Alternativa — ispravna historija (uraditi na Fedori):**
```bash
git checkout dev
git checkout -b windows-proper
# Appliciraj Windows zakrpe
git push origin windows-proper
# Na Windows: git fetch, git checkout windows-proper
```

---

## CRLF upozorenja
Git je ispisao ~288 CRLF upozorenja pri `git add` — to je normalno pri prvom commitovanju na Windows (`.gitattributes` ispravlja ovo unaprijed za buduće commitove).
