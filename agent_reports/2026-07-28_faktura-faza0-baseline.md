# Faktura 3-layer refaktor — Faza 0 report

**Datum**: 2026-07-28
**Agent**: Pi
**Grana**: `refactor/faktura-3layer`
**Plan**: `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md`

## Šta je urađeno

- Kreiran worktree `.worktrees/faktura-3layer` sa grane `windows` (commit `e8aa6f2`)
- Snimljen baseline: 6.329 linija, 154 metode, merge-base = e8aa6f2
- Napisano 17 karakterizacionih testova (0 produkcionih izmjena):
  - `test_faktura_table_roundtrip.py` (6): rowCount, lines preserved, empty values, QTableWidget, column count, signal
  - `test_faktura_characterization.py` (11): import, validation, signal, weight, auto-fill, public contracts, dist standalone
- 55/55 testova prolazi (17 novih + 38 postojećih)

## Gate status

- [x] Nema produkcionih izmjena
- [x] Novi karakterizacioni testovi prolaze na starom kodu
- [x] Puna suite nije lošija od baseline-a
- [x] Merge-base potvrđen: `e8aa6f2`

## Sledeći korak

Faza 1 — Controller + neutralni modeli + composition root. Dodati `FakturaController` sa praznim signal wiringom. Ne prespajati signale dok karakterizacioni testovi ne potvrde paritet.
