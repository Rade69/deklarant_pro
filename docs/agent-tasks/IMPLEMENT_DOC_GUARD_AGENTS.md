# Zadatak: Dodaj DOC Guard pravilo u sve agent konfiguracije

**Tip:** Dokumentaciona izmjena — nema izmjena Python ili QSS fajlova  
**Scope:** `USTAV_AGENTA.md`, `AGENTS.md`, `CLAUDE.md`, `QWEN.md`, `AGENT_CODE_DOC.md`

---

## Kontekst

Instaliran je DOC Guard sistem koji:
- Detektuje `# DOC:` linkove u Python kodu
- Hook injektuje reminder pri svakom `Write/Edit` na `.py` fajlu
- `scripts/doc_link_checker.sh` provjerava broken i stale linkove

Svi agenti moraju znati kako da reaguju na hook poruke i kako da pišu `# DOC:` komentare.

---

## Korak 1 — Provjeri lokacije fajlova

```bash
find ~ -name "USTAV_AGENTA.md" 2>/dev/null
ls -la AGENTS.md CLAUDE.md QWEN.md AGENT_CODE_DOC.md 2>/dev/null
```

Ispiši pronađene putanje. Ne nastavljaj dok ne potvrdiš sve lokacije.

---

## Korak 2 — Dodaj sekciju u USTAV_AGENTA.md

Pronađi `USTAV_AGENTA.md` (vjerovatno `~/.pi/agent/SYSTEM.md` ili slično).

Dodaj **novu sekciju 13** na kraj fajla, **prije** linije
`**Ovaj dokument zamjenjuje sve prethodne verzije...`

```markdown
## 13. DOC Guard — obavezna pravila

### 13.1 Šta je DOC Guard

Sistem koji osigurava da `# DOC:` linkovi u Python kodu ostanu validni i ažurni.
Kada agent završi `Write/Edit` na `.py` fajlu, hook injektuje poruku u kontekst.

### 13.2 Kada hook javi BROKEN

```
[DOC-GUARD] ... BROKEN (fajl ne postoji na disku):
  ✗ docs/sections/naziv.md
  → Kreiraj ovaj fajl odmah ili ispravi putanju u # DOC: komentaru.
```

**Obavezna akcija:** STOP. Prije nastavka bilo čega:
- Ako je putanja greška u kucanju — ispravi `# DOC:` komentar u kodu
- Ako fajl treba kreirati — kreiraj ga prema `.claude/DECISION_RECORD_TEMPLATE.md`
- Commitovati sa BROKEN linkom je zabranjeno (vidi sekciju 10)

### 13.3 Kada hook javi STALE

```
[DOC-GUARD] ... Postoje — provjeri da li su ažurni:
  ⚠ docs/sections/naziv.md
  → Ako si mijenjao logiku — ažuriraj linked MD.
```

**Procjena:**
- Mijenjao sam logiku, arhitekturu ili međuzavisnosti → ažuriraj MD prije commita
- Izmjena je bila kozmetička (rename, format, whitespace) → nastavi bez izmjene MD

### 13.4 Kako pisati # DOC: komentar

```python
# DOC: docs/decisions/001-naziv.md
def kompleksna_funkcija():
    ...
```

Pravila:
- Putanja je relativna na project root
- Jedan `# DOC:` po logičkoj cjelini (funkcija, klasa, modul)
- Samo za netrivijalne odluke — ne na svakoj liniji
- Nema specijalnih znakova u putanji (em-dash, +, razmaci)
- Linked fajl mora postojati u trenutku commita

### 13.5 Ručna provjera

```bash
bash scripts/doc_link_checker.sh .
```

Pokrenuti prije svakog commita kada su mijenjani `.py` fajlovi sa `# DOC:` komentarima.
```

---

## Korak 3 — Dodaj kratku referencu u AGENTS.md, CLAUDE.md, QWEN.md

U svaki od ova tri fajla dodaj sljedeći blok na kraj
(ili u postojeću sekciju o pravilima ako postoji):

```markdown
## DOC Guard

Kada hook injektuje `[DOC-GUARD]` poruku:
- **BROKEN** → zaustavi se, ispravi putanju ili kreiraj MD fajl prema
  `.claude/DECISION_RECORD_TEMPLATE.md` — ne commitaj sa broken linkom
- **STALE** → procijeni: logička izmjena = ažuriraj MD; kozmetička = nastavi
- Ručna provjera: `bash scripts/doc_link_checker.sh .`
```

---

## Korak 4 — Ažuriraj AGENT_CODE_DOC.md

U `AGENT_CODE_DOC.md` pronađi sekciju koja opisuje `# DOC:` komentare
(ili dodaj na kraj ako ne postoji).

Dodaj:

```markdown
### Pravila za # DOC: putanje

- Putanja relativna na project root: `docs/decisions/001-naziv.md`
- Nema specijalnih znakova: zabranjen em-dash (—), plus (+), razmaci
- Fajl mora postojati u trenutku commita
- Template za novi fajl: `.claude/DECISION_RECORD_TEMPLATE.md`
- Hook automatski detektuje broken i stale linkove pri svakom editu
```

---

## Korak 5 — Provjera i report

```bash
grep -n "DOC Guard" AGENTS.md CLAUDE.md QWEN.md AGENT_CODE_DOC.md
grep -n "DOC Guard" ~/.pi/agent/SYSTEM.md 2>/dev/null || \
grep -rn "DOC Guard" ~ --include="USTAV_AGENTA.md" 2>/dev/null
```

Kreiraj `agent_reports/2026-05-11_doc-guard-agent-config.md` sa:
- listom fajlova koji su izmijenjeni
- potvrdom da sekcija 13 postoji u USTAV_AGENTA.md
- potvrdom da DOC Guard blok postoji u AGENTS.md, CLAUDE.md, QWEN.md

---

## Šta NE radiš

- Ne mijenjaj postojeće sekcije u tim fajlovima — samo dodaješ
- Ne mijenjaš ni jedan Python fajl
- Ne pokrećeš `doc_link_checker.sh` ponovo — već je pokrenut
- Ne mijenjaj numeraciju postojećih sekcija u USTAV_AGENTA.md ako je sekcija 13 zauzeta —
  u tom slučaju javi mi broj i čekaj instrukciju

---

## Definicija gotovo

- `USTAV_AGENTA.md` sadrži sekciju 13 sa DOC Guard pravilima
- `AGENTS.md`, `CLAUDE.md`, `QWEN.md` sadrže DOC Guard blok
- `AGENT_CODE_DOC.md` sadrži pravila za `# DOC:` putanje
- `agent_reports/2026-05-11_doc-guard-agent-config.md` postoji
