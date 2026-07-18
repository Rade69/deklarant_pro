# Checklist: priprema PRIJE početka rada na novoj aplikaciji

> Zasnovano na radnom toku deklarant_pro projekta (multiagentski rad:
> Claude Code + Codex kao vodeći, DeepSeek/GLM/Kimi/MiniMax za pomoćne
> zadatke) i lekcijama naučenim na njemu. Redoslijed faza je namjeran —
> ne preskakati Fazu 0 i 1.

---

## Faza 0 — Definicija projekta (papir prije koda)

Prije ijedne linije koda napisati kratak dokument (može i samo sekcija u
budućem `docs/CONTEXT.md`) koji odgovara na:

- [ ] **Šta aplikacija radi** — jedna rečenica; ako ne stane u jednu, scope je premutan
- [ ] **Ko je koristi** — koliko korisnika, na kojim mašinama (OS!), lokalno ili mreža
- [ ] **Šta je dobar ishod v1** — vidljiv/testabilan rezultat (isti princip kao
      "Šta je dobar ishod" u formatu zadatka za agente)
- [ ] **Šta v1 NE radi** — eksplicitna lista van scope-a (scope lock od prvog dana)
- [ ] **Tech stack odluka** — jezik, GUI framework, baza; zapisati i ZAŠTO
      (alternativa i razlog odbacivanja — kasnije niko ne pamti)

**Lekcija iz deklarant_pro:** odluke koje nisu zapisane postaju "kontradiktorni
izvori" poslije 2 mjeseca — stari report kaže jedno, kod drugo, niko ne zna šta važi.

---

## Faza 1 — Git repozitorij i higijena (prije prvog commita)

- [ ] `git init` + odmah odrediti grane: `main` (stabilno) i radna grana
- [ ] **`.gitignore`** prije prvog commita: `__pycache__/`, `.env`, `*.db` (ako je
      baza lokalna), `dist/`, `*.log`, `*.lck`, IDE folderi
- [ ] **`.gitattributes`** prije prvog commita — na Windows/Linux mješovitom okruženju
      ovo je obavezno, ne opcionalno:

  ```text
  * text=auto
  *.py text eol=lf
  *.md text eol=lf
  *.bat text eol=crlf
  *.ps1 text eol=crlf
  scripts/git-hooks/* text eol=lf
  *.db binary
  *.pdf binary
  *.xlsx binary
  ```

- [ ] **Pre-commit hook od prvog dana** — kopirati `scripts/git-hooks/pre-commit`
      iz deklarant_pro (py_compile na staged .py + podsjetnici), pa:

  ```bash
  git config core.hooksPath scripts/git-hooks
  ```

  Ponoviti na SVAKOJ mašini koja klonira repo (lokalna konfiguracija!).
- [ ] Prvi commit = samo skelet (README, .gitignore, .gitattributes, hook) — čist temelj

**Lekcije:** CRLF u sh skripti lomi hook na Linuxu; lozinka jednom commitovana
u git ostaje u historiji zauvijek (deklarant_pro je morao rotirati DB lozinku) —
`.env` u `.gitignore` PRIJE nego što `.env` uopšte nastane.

---

## Faza 2 — Harness za agente (najvažnija faza za multiagentski rad)

Jedan kanonski fajl pravila, deterministička pravila kao hookovi, zajednička memorija.

- [ ] **`AGENTS.md` u korijenu — KANONSKI fajl** za sve agente.
      Uzeti `templates/agent-md/AGENTS.md` iz deklarant_pro i popuniti placeholdere.
      Minimalno mora imati: jezik komunikacije, tech stack, arhitekturu,
      ključne konvencije, zabrane sa razlozima, format outputa, proceduru
      nakon zadatka (Korak 1-5)
- [ ] **`CLAUDE.md` tanak** — samo `@AGENTS.md` import + Claude-specifična memorija.
      NIKAD ne duplirati sadržaj između ta dva fajla (drift je garantovan)
- [ ] **`docs/CONTEXT.md`** — prazan skelet zajedničke memorije za sve agente:
      sekcije "Kritična pravila", "Poznati bugovi", "Kako ažurirati ovaj fajl".
      Svi agenti ga čitaju, u repou je
- [ ] **`agent_reports/`** folder — prazan, sa jednim README redom šta ide unutra
- [ ] **`project_rooms/`** folder — za planove HIGH/CRITICAL izmjena
- [ ] **`.claude/settings.json`** — hooks (npr. doc-guard), permissions
- [ ] **Pravilo od prvog dana:** sve što MORA da se desi svaki put ide u hook
      (git ili Claude Code), ne u prompt tekst — slabiji modeli tekst zaborave

**Lekcija:** deklarant_pro je 2 mjeseca imao duplirana pravila u CLAUDE.md i
AGENTS.md koja su driftovala; spajanje je kasnije koštalo cijelu sesiju. Nova
aplikacija kreće ispravno od nule — to je besplatno sada, skupo kasnije.

---

## Faza 3 — Struktura projekta i arhitektura

- [ ] Definisati folder strukturu PRIJE koda (po uzoru na deklarant_pro):

  ```text
  nova_app/
  ├── core/            # modeli podataka (dataclasses)
  ├── gui/             # samo UI (ako je GUI app)
  ├── services/        # SVA business logika
  ├── database/        # konekcije, migracije
  ├── tests/           # pytest od prvog dana
  ├── docs/            # CONTEXT.md i ostalo
  ├── scripts/         # git-hooks/, pomoćne skripte
  ├── agent_reports/
  └── project_rooms/
  ```

- [ ] **3-layer pattern odmah**: View (samo UI, signali) / Controller (orchestration,
      1-liner pozivi) / Service (logika, DB). U AGENTS.md kao OBAVEZNO
- [ ] **Konvencija imenovanja polja** odlučiti odmah (srpski ili engleski) i zapisati
      u AGENTS.md — naknadna promjena lomi sve
- [ ] Zabraniti od prvog dana: SQL f-string (samo parametrizovani upiti),
      hardkodovane IP adrese (sve u `config.ini`/`.env`), UI logiku u servisima

---

## Faza 4 — Python okruženje i tooling

- [ ] **venv, ne PyInstaller** za interne Windows klijente
      (`setup_windows_venv.bat` + `start_silent.vbs` pattern iz deklarant_pro) —
      PyInstaller mijenja `sys.executable`/`__file__`/stderr i puca na svakom od njih
- [ ] `requirements.txt` ili `pyproject.toml` (uv) od prvog dana — verzije pinovane
- [ ] **`.env` + `.env.example`**: `.env` u .gitignore, `.env.example` u repou;
      u kodu `load_dotenv(env_file, override=True)` (default override=False
      ignoriše .env ako sistem već ima varijablu!)
- [ ] **Encoding pravila** (Windows lekcije — sve su se stvarno desile):
  - `.env` čuvati BEZ BOM-a (BOM lomi parsiranje)
  - emoji NIKAD direktno na stderr (cp1252 → UnicodeEncodeError pri startu);
    uvijek logger
  - bulk izmjene teksta NE raditi PowerShell Get/Set-Content (mojibake);
    byte-preserving Python alat ili eksplicitno `-Encoding utf8`
  - QSS blokovi NIKAD f-string (CSS `{}` = SyntaxError); `.replace("PLACEHOLDER", ...)`
- [ ] **pytest skelet + 1 smoke test odmah** — makar samo "app se importuje bez greške".
      Bez ovoga verifikacija ostaje 100% ručna zauvijek
- [ ] Zabraniti `mock` za SQLite/PostgreSQL u testovima (maskira realne greške)

---

## Faza 5 — GitNexus / code intelligence (čim postoji kod)

- [ ] Poslije prvih par modula: `npx gitnexus analyze`
- [ ] U AGENTS.md pravila: `gitnexus_impact` prije izmjene simbola,
      `gitnexus_detect_changes` prije commita, upozorenje na HIGH/CRITICAL
- [ ] Znati ograničenje: na zastarjelom indeksu detect_changes prijavljuje i
      nedirnute fajlove — uvijek ukrstiti sa `git status`

---

## Faza 6 — Multiagentski radni tok (pravila igre)

- [ ] **Podjela uloga** zapisati u AGENTS.md:
  - Claude Code / Codex — arhitektura, plan, netrivijalne izmjene, integracija
  - DeepSeek / GLM / Kimi / MiniMax — mehanički poslovi: testovi, docstrings,
    šablonske migracije, prva runda review-a
- [ ] **Jedan agent = jedan git worktree** za paralelni rad — nikad dva agenta
      istovremeno u istom radnom stablu (lekcija: paralelna sesija u istom stablu
      = kolizije koje se vide tek kad je kasno)

  ```bash
  git worktree add ../nova_app-agent2 -b feature/xyz
  ```

- [ ] **Cross-review**: kod koji piše jedan model pregleda DRUGI vendor —
      obavezno za HIGH/CRITICAL impact izmjene
- [ ] **Format zadatka** (iz AGENTS.md) koristiti za sve netrivijalno:
      Zadatak / Radna pretpostavka / Provjeri hipotezu / Granice / Dobar ishod
- [ ] **Procedura nakon zadatka (Korak 1-5)**: commit po logičkim cjelinama →
      memorija/CONTEXT.md → agent_report → (link u kodu) → reindeks
- [ ] Oprez sa `git reset` / `--skip-worktree`: reset briše skrivene flagove
      (lekcija iz deklarant_pro — 4 fajla se iznenada "pojavila" kao izmijenjena)

---

## Faza 7 — Baza i infrastruktura

- [ ] Konekcioni podaci u `config.ini`/`.env` — NIKAD u kodu; server na DHCP-u
      mijenja IP (dmserver lekcija), pa hardkodovana IP znači tihi pad
- [ ] Odlučiti odmah: šta je u centralnoj bazi (PostgreSQL), šta lokalno (SQLite),
      šta je read-only
- [ ] Migracije/šema u repou od prve tabele (ne "sredićemo kasnije")
- [ ] Backup plan za bazu prije prvog pravog podatka
- [ ] Ako ima SSH automatizacije sa Windowsa: Python + paramiko (OpenSSH/sshpass
      nepouzdani za neinteraktivnu lozinku), stdout `reconfigure(encoding="utf-8")`

---

## Faza 8 — Definicija verifikacije (prije prvog feature-a)

- [ ] Odrediti **skup pravih test podataka** (ekvivalent `najavauvoza/` foldera) —
      verifikacija na izmišljenim podacima je lažna verifikacija
- [ ] Pravilo: agent koji je pisao kod NIJE arbitar da li radi — arbitar su
      testovi ili drugi agent; vizuelne stvari potvrđuje korisnik na stvarnom
      hardveru (lekcija: 3 varijante toolbar skaliranja izgledale dobro "na papiru",
      sve odbijene na stvarnom ekranu)
- [ ] U AGENTS.md sekcija "Provjera prije predaje" — checkbox lista koju svaki
      agent popunjava prije nego kaže "gotovo"

---

## Brza finalna lista (dan 0, redom)

1. `git init` → `.gitignore` → `.gitattributes` → hook + `core.hooksPath`
2. `AGENTS.md` (kanonski, iz template-a) + tanak `CLAUDE.md` + `docs/CONTEXT.md` skelet
3. Folder struktura + prazni `tests/`, `agent_reports/`, `project_rooms/`
4. venv + requirements + `.env.example` + smoke test
5. Prvi commit skeleta, pa tek onda prvi feature
6. Čim ima koda: `npx gitnexus analyze`

**Procjena:** kompletna priprema je 1-2 sata rada. Svaka preskočena stavka
na deklarant_pro projektu se kasnije naplatila višestruko (mojibake sesija,
spajanje dupliranih pravila, rotacija lozinke, skip-worktree zamka).
