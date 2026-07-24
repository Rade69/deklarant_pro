# Master Frigo agent import fix — 2026-04-26

Arhivirano u `docs/archive/2026-04-26/` pri cišćenju `scripts/` foldera; aktivni
`# DOC:` linkovi u kodu i dalje pokazuju na ovaj zapis.

## Svrha

Popravlja agentski uvoz Master Frigo faktura kada uz PDF fakture postoji jedan
pomoćni Excel za porijeklo/tarife, npr. `Podela po poreklu.xlsx 18,12,2025.xlsx`.
Taj Excel nije faktura i ne smije popuniti kolonu `Faktura`; broj fakture mora
doći iz svake pojedinačne PDF fakture.

## Problem

Agent je obrađivao pomoćni Excel kao običan Excel import. Zbog toga su stavke iz
Excel-a ulazile u draft kao zasebna faktura, pa je kolona `Faktura` prikazivala
ime fajla `Podela po poreklu.xlsx ...`.

Dodatno, `_find_master_frigo_mapping_xlsx()` je tražio samo varijante `porekla`
i `porijekla`, ali stvarni decembarski fajl koristi oblik `poreklu`. Zbog toga
Master Frigo PDF parser nije dobijao mapping Excel za obogaćivanje tarifa i
zemalja porijekla.

## Rješenje

- `importers/smart_pdf_importer.py` sada prepoznaje mapping Excel nazive sa:
  `tarife`, `podela`, `porekla`, `poreklu`, `poreklo`, `porijekla`, `porijeklu`.
- `gui/tabs/agent/widgets/processing_worker.py` mapping Excel fajlove preskače
  u agentskom batch-u kada u istom folderu postoji PDF.
- PDF ostaje izvor broja fakture (`invoice_name`) i cijena/iznosa.
- Mapping Excel se upisuje u `consumed_paths`, tako da agent zna da ga ne treba
  obrađivati kao zasebnu fakturu.

## Provjera

Ručno provjereno na stvarnom fajlu:

```bash
python - <<'PY'
from importers.smart_pdf_importer import parse_smart_pdf
pdf = 'najavauvoza/R2503393 (16.12.2025.) (E)-MASTER FRIGO, BANJA LUKA  (AVANSNO)-23.503,15 EUR.pdf'
r = parse_smart_pdf(pdf)
print(r.invoice_name)
print([p.split('/')[-1] for p in r.consumed_paths])
for line in r.items:
    print(line.line_no, line.product_code, line.iznos, line.tarifni_broj, line.zemlja_porijekla)
PY
```

Očekivano:

- `invoice_name = 2503393`
- `consumed_paths` sadrži `Podela po poreklu.xlsx 18,12,2025.xlsx`
- `Iznos` iz PDF-a je popunjen, npr. `1400.0`, `10554.0`, `5346.0`, `6203.15`

## Testovi

```bash
pytest -q tests/unit/test_agent_processing_worker_sort.py \
  tests/unit/test_master_frigo_mapping_detection.py \
  tests/unit/test_master_frigo_invoice_number.py
```

Zadnji rezultat: `11 passed`.
