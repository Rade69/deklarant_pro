# Modul tarifnih kvota (UINO) — 26. april 2026

## Opis

Modul omogućava pregled informativnog stanja tarifnih kvota prema javno objavljenom
UINO PDF izvještaju. Dostupno u: **Šifrarnici → Tarifne kvote**.

## Napomena o podacima

Podaci su **informativni** — presjek stanja u trenutku kad je UINO generisao PDF.
Ne prikazuju real-time stanje. Naziv u aplikaciji:
> "Zadnje objavljeno stanje kvote prema UINO PDF izvještaju"

## Arhitektura

```
services/quota_service.py          — parser + DB operacije + entry point
gui/tabs/sifarnici/quota_panel.py  — GUI panel
gui/tabs/sifarnici_view.py         — integracija u Šifrarnici sidebar
```

## PDF parser — `services/quota_service.py`

### URL
`https://www.uino.gov.ba/portal/wp-content/uploads/GenerisaniPDF/Qba-Stanje.pdf`

### Struktura PDF-a (koordinatni pragovi)
PDF koristi fiksirane X kolone:

| Kolona | X0 raspon |
|---|---|
| Tarifni kod (4 grupe) | x0 < 110 |
| Opis | 100 ≤ x0 < 545 |
| JM | 545 < x0 < 600 |
| Odobreno | 600 < x0 < 670 |
| Iskorišteno | 670 < x0 < 745 |
| Preostalo | x0 > 745 |

### Kritična napomena — sub-piksel razlika
pdfplumber vraća blago različite `top` vrijednosti za lijevu i desnu stranu iste
vizuelne linije (npr. `163.013` vs `162.981`). Grupisanje po `round(top/2)*2` ih
razdvaja u različite redove. Ispravno grupiranje: `round(top)` (1px tolerancija).

### Deduplikacija
SHA-256 hash PDF fajla sprječava duplikate. Ako isti PDF već postoji u bazi,
vraća se `"duplicate"` status bez ponovnog upisivanja.

## PostgreSQL tabele (catalogs schema)

```sql
CREATE TABLE IF NOT EXISTS catalogs.quota_snapshots (
    id SERIAL PRIMARY KEY,
    source_url TEXT NOT NULL,
    report_datetime TIMESTAMP,
    downloaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    pdf_hash TEXT UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalogs.quota_snapshot_items (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER NOT NULL
        REFERENCES catalogs.quota_snapshots(id) ON DELETE CASCADE,
    tariff_code TEXT NOT NULL,
    description TEXT,
    approved_qty NUMERIC,
    used_qty NUMERIC,
    remaining_qty NUMERIC,
    unit TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Tabele se kreiraju automatski pri prvom otvaranju panela (`ensure_tables()`).

## GUI panel — `gui/tabs/sifarnici/quota_panel.py`

### Status indikator (QIcon — obojeni krug)

| Preostalo | Boja | Tekst |
|---|---|---|
| > 50% | 🟢 zelena (#22c55e) | Nizak rizik |
| 10–50% | 🟡 žuta (#eab308) | Srednji rizik |
| < 10% | 🟠 narandžasta (#f97316) | Visok rizik |
| 0% | 🔴 crvena (#ef4444) | Potrošeno |

Ikone su kreirane programatski sa `QPixmap` + `QPainter` (ne emoji — emoji ne
prikazuju se pouzdano u Qt tabelama na Linuxu).

### Osvježavanje podataka
`_RefreshWorker(QThread)` — preuzima PDF u background threadu, ne blokira UI.
Po završetku emituje `success(snapshot_id, status)` ili `error(msg)`.

## Integracija u Šifrarnici

`sifarnici_view.py` koristi `QStackedWidget` za prebacivanje između standardnog
sadržaja i `QuotaPanel`. Lazy init — QuotaPanel se kreira tek pri prvom kliku
na "Tarifne kvote" kategoriju.
