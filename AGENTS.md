# AGENTS.md — Deklarant Pro projektni standardi

Ovaj fajl čitaju svi agenti koji rade na ovom projektu: Qwen Code, GitHub Copilot, Cursor,
MiniMax, CLI agenti i drugi. Dopunjuje globalni `~/.claude/AGENTS.md` — ne zamjenjuje ga.

---

## Kontekst projekta — pročitaj prije kodiranja

Memorija projekta (ne-trivijalni fakti, odluke, historija) nalazi se u:
```
~/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/
```
Indeks svih zapisa: `MEMORY.md` u tom folderu.

**Ako si IDE agent (Copilot, Cursor, Qwen Code):** memory fajlove možeš čitati direktno.
**Ako si CLI/API agent (MiniMax, prompt bez IDE konteksta):** task fajl koji dobiješ
sadrži sve potrebne informacije — ne moraš ručno tražiti memoriju.

Klauza `CLAUDE.md` u korijenu projekta sadrži formatske konvencije i projektne standarde
koje prati Claude. Pročitaj je ako radiš šire izmjene.

---

## Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš uraditi.
Čekaj potvrdu korisnika prije implementacije ako zadatak nije jednoznačan.

---

## Jezik

- Svi odgovori korisniku: **srpski, latinica**
- Komentari u kodu: engleski (prati stil koji fajl već koristi)
- Nikada ćirilica — nigdje, ni u komentarima ni u stringovima koji se prikazuju
- Commit poruke: srpski latinica, format `tip(scope): opis`

---

## Tech stack

| Sloj | Tehnologija |
|------|------------|
| GUI | PySide6 (Qt6) |
| Baza | PostgreSQL 16 (server 192.168.0.69) + SQLite lokalno |
| Python | 3.11+, uv za pakete |
| Testovi | pytest, `tests/` folder |
| Parseri | pdfplumber, openpyxl, pytesseract (OCR) |

---

## Arhitektura

```
deklarant_pro/
├── core/draft/          # Draft modeli: DeclarationDraft, InvoiceLine, NaimenovanjeDraft
├── gui/tabs/            # GUI tabovi (agent_tab, faktura_tab, naimenovanja_tab...)
│   └── agent/
│       ├── agent_controller.py      # Tanak controller — samo 1-liner wrapper metode
│       └── services/                # Sva logika izvučena ovdje
│           ├── xml_workflow_service.py
│           ├── import_pipeline_service.py
│           └── chat_intent_handler.py
├── importers/           # PDF/Excel parseri po dobavljaču
├── services/            # Business logika
│   └── agent/
│       ├── chat/        # intent_classifier, chat_memory, namjere
│       ├── tariff/      # hybrid_tariff_agent, rag, matching
│       ├── learning/    # historical_learning, exporter_xml_indexer
│       └── validation/  # declaration_validator, xml_template_service
├── database/            # SQLite: deklarant_sistem.db, zvanicna_tarifa.db
└── ui/                  # Qt .ui fajlovi
```

**Pattern za services/agent/:** slobodne funkcije koje primaju `ctrl` kao prvi argument,
servisna klasa ih omotava kao public API. Controller metode su samo 1-liner pozivi servisa.

---

## Ključne konvencije

### Kod
- **Nema novih komentara** osim za neočigledne workarounds ili skrivene invarijante
- **Nema docstrings** na metodama koje slijede jasne naming konvencije
- Fuzzy matching threshold: `min_similarity = 0.92` (ne spuštati bez eksplicitnog razloga)
- SQL: isključivo parametrizovani upiti — nikad f-string u SQL-u

### Parseri (importers/)
- Svaki importer mora imati `exporter` i `importer` polja u `ImportResult`
- XML lookup se radi po paru `(exporter, tariff_code)` — ne samo po tariff_code
- CBBH kurs se čita iz baze, ne hardkoduje

### XML template (xml_template_service.py)
- Rb.48 (`odgodjeno_placanje`) se **ne prepisuje** iz historijskog XML-a — šifra se mijenja godišnje
- Mijenjati samo `TEMPLATE_FIELDS` whitelist — ne pisati ad-hoc logiku po polju

### Naimenovanja
- Rb.31 auto-opis se generiše po tarifi, ne prepisuje iz fakture
- `le_r31_trg_naziv` prikazuje sve comercijalne nazive, max 550 znakova, skraćuje sa "..."

---

## Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
|---------|--------|
| Direktni `import` iz `gui/tabs/agent/agent_controller.py` u servis | Kružni import |
| Mijenjati `TEMPLATE_FIELDS` van `xml_template_service.py` | Single source of truth |
| Hardkodovati IP adresu servera u kodu | Mora biti u `config.ini` |
| Dodavati UI logiku u servisne klase | Narušava razdvajanje slojeva |
| Brisati stub fajlove u `services/agent/` bez provjere importa | Backward compat |

---

## Format outputa

```
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratko
ŠTA NIJE URAĐENO: (ako PARCIJALNO/BLOKIRANO)
PITANJA: (ako postoje)
```

---

## Provjera prije predaje

- [ ] Nisam mijenjao kod van scope-a zadatka
- [ ] Nisam dodao nepotrebne komentare ili docstrings
- [ ] Nisam ostavio zakomentiran kod
- [ ] Nisam koristio string interpolaciju u SQL-u
- [ ] Testovi prolaze: `cd /home/radovan/Desktop/deklarant_pro && python -m pytest tests/ -q`
- [ ] Output format je popunjen (STATUS, IZMIJENJENI FAJLOVI, itd.)
