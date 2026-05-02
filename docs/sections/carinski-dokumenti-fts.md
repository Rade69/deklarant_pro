# Carinski dokumenti — FTS pretraga u agentu

## Šta je implementirano

Agent (chat asistent u Deklarant Pro) sada može odgovarati na pravna i proceduralna pitanja
koristeći stvarne BiH carinske propise — ne samo opće znanje LLM-a.

## Arhitektura

```
docs/Carinski dokumenti/*.pdf
        ↓
database/index_carinski_dokumenti.py   ← ekstrakcija teksta (pdfminer)
        ↓
catalogs.carinski_dokumenti (PostgreSQL)
  - naziv, filename, sadrzaj TEXT
  - fts_vektor tsvector GENERATED ALWAYS  ← automatski održavan
  - GIN indeks na fts_vektor
        ↓
services/carinski_dokumenti_service.py  ← pretraga (to_tsquery + ts_headline)
        ↓
chat_worker._search_knowledge_base()    ← ubacuje odlomke u agent kontekst
```

## Baza podataka

**Tabela:** `catalogs.carinski_dokumenti`

| Kolona | Tip | Opis |
|--------|-----|------|
| id | SERIAL | PK |
| naziv | TEXT | Čitljivo ime dokumenta |
| filename | TEXT UNIQUE | Originalni naziv PDF fajla |
| sadrzaj | TEXT | Cijeli ekstraktovani tekst |
| file_hash | TEXT | MD5 prvih 64KB — za inkrementalno ažuriranje |
| fts_vektor | tsvector GENERATED ALWAYS | PostgreSQL FTS vektor (simple rječnik) |
| datum_indeksa | TIMESTAMPTZ | Kada je indeksiran |

**Indeks:** `ix_carinski_dokumenti_fts` (GIN)

## Pretraga

Koristi `to_tsquery('simple', ...)` sa prefix matchingom (`word:*`) — radi bez stemovanja,
što je ispravno za bosanski/srpski jezik.

`ts_headline` vraća odlomak sa označenim riječima (max 2 fragmenta po 50 riječi).

### Primjer upita

```python
from services.carinski_dokumenti_service import pretrazi_i_formatiraj
print(pretrazi_i_formatiraj('privremeni uvoz'))
```

## Indeksirani dokumenti (29 PDF-ova)

- **B-serija** — UIO uputstva: carinska vrijednost, privremeni uvoz, spoljna obrada, carinska skladišta, provoz, osiguranje duga
- **H-serija** — Uputstva JCI, popunjavanje carinske prijave, kućno carinjenje, izvoz, AEO status, unutrašnja obrada, carinski prekršaji
- **Zakoni** — Zakon o carinskoj politici BiH, Zakon o carinskim prekršajima
- **Ostalo** — Harmonizovani sistem (HS konvencija), Objedinjeni spisak, Šifre

## Kada agent koristi dokumente

`chat_worker._is_regulatory_question()` provjerava da li pitanje sadrži ključne riječi:
`zakon`, `pravilnik`, `postupak`, `privremeni`, `uvoz`, `izvoz`, `povlastica`, `carinska vrijednost`, itd.

Ako da — `_search_knowledge_base()` pretražuje `carinski_dokumenti` i ubacuje
relevantne odlomke u sekciju `=== ZAKONSKA REGULATIVA ===` system prompta.

## Dodavanje novih dokumenata

1. Kopiraj PDF u `docs/Carinski dokumenti/`
2. Pokreni: `python3 database/index_carinski_dokumenti.py`

Skript automatski preskače nepromijenjene fajlove (po MD5 hashu).

## Kreiranje tabele (migracija)

```bash
python3 database/migrate_carinski_dokumenti.py
```

## Commits

- `d8fa080` — inicijalna implementacija (SQLite FTS5)
- `3c7f552` — prebačeno na PostgreSQL (tsvector + GIN)
