# Produkcijska spremnost — checklist

**Datum:** 2026-08-06
**Stanje:** 80% spremno — potrebno testiranje + par popravki

---

## ⚠️ Blokirajuće (mora pre produkcije)

- [ ] **Testirati sve import parsere** u exe-u (PDF i Excel)
  - Blagić Attos, Blagić Loren, IMAMOGLU, Leburić, Medicopharm
  - Univerzalni PDF parser, Excel importer
  - Proveriti: `pip_food`, `master_frigo`, `leburic_pekabesko`
- [ ] **Agent ne radi u exe-u** — Google Gemini SDK (`google-generativeai`) nije u build-u
  - Dodati u `.spec` hidden imports: `google.genai`, `google.generativeai`
  - ILI dodati u `setup.iss` [Run] sekciju: `pip install google-generativeai`
- [ ] **`importers.vendors.blagic.blagic_importer` not found** — greška u build log-u
  - Proveriti da li fajl postoji: `importers/vendors/blagic/blagic_importer.py`
  - Ako ne postoji — ukloniti iz `.spec` hidden imports
- [ ] **PostgreSQL permisije za nove korisnike**
  - `permission denied for database deklarant_pro`
  - `must be owner of table quota_snapshot_items`
  - Rešenje: dodati `GRANT` skriptu u instalaciju ili `README`

---

## 🔧 Preporučeno (srednji prioritet)

- [ ] **Testirati XML export** (ASYCUDA format)
- [ ] **Testirati kreiranje naimenovanja** iz fakture
- [ ] **Testirati "Provjeri" i "Sugeriši tarifu"** u exe-u
- [ ] **Testirati Admin → Učenje iz XML-ova** (reindeksiranje)
- [ ] **Testirati Admin → Tarifne kvote** (UINO download)
- [ ] **Dodati `.env` čarobnjak pri prvom pokretanju**
  - Ako `.env` ne postoji, prikazati dijalog za unos DB kredencijala
  - Ili bar prikazati uputstvo gde da se kreira `.env`
- [ ] **Ukloniti debug logove** — `_on_suggest_tariff: dugme kliknuto`
  - Fajl: `gui/tabs/naimenovanja_view.py`
- [ ] **Dodati srpski jezik u Inno Setup**
  - Skinuti `SerbianLatin.isl` sa neta
  - Ili ostaviti engleski (prihvatljivo)

---

## 💡 Opciono (niski prioritet)

- [ ] **Smanjiti veličinu instalacije** (~800 MB zbog torch-a i transformers-a)
  - Ako se ne koristi ML/AI van agenta — dodati `torch` i `transformers` u excludes
  - Ili koristiti `--onedir` umesto `--onefile`
- [ ] **Code signing** — digitalni potpis za exe (Windows SmartScreen)
- [ ] **Auto-updater** — mehanizam za proveru novih verzija
- [ ] **Verzija u exe metapodacima** — `build_hooks/version_info.txt`
- [ ] **Ikona u instalacionom exe-u** — dodati `SetupIconFile` u `setup.iss`
- [ ] **`.gitignore` ažurirati** — dodati `dist/`, `build/`, `*.exe`
- [ ] **Obrisati `.worktrees/`** (1.5 GB) — više nisu potrebni

---

## 📦 Finalni deliverables

- [ ] `dist/DeklarantPro_Setup_2.0.0.exe` — instalacioni program
- [ ] `README.md` sa uputstvom za instalaciju i `.env` konfiguraciju
- [ ] `CHANGELOG.md` sa spiskom izmena
- [ ] Backup produkcijske baze pre prvog puštanja
