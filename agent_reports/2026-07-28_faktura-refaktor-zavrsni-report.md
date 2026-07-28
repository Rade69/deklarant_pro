# Faktura 3-layer refaktor — završni report

**Datum**: 2026-07-28
**Agent**: Pi
**Grana**: `refactor/faktura-3layer`
**Plan**: `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md`
**Status**: Faze 0-8 završene, signali NISU prespojeni

## Commitovi

| Faza | Commit | Šta |
|------|--------|-----|
| 0 | `ace41da` | 17 karakterizacionih testova (55/55) |
| 1 | `7372c09` | Controller + neutralni modeli + composition root |
| 2 | `c46fe9f` | Čiste kalkulacije u FakturaService |
| 3 | `479adea` | Controller validate_and_color_rows |
| 4-7B | `b9c5b6c` | Controller: import, naimenovanja, mase, edit, export |
| 8 | `395c364` | Statička validacija |

## Statičke kapije

- View SQL: 0 ✅
- Novi Service PySide6: 0 ✅
- Controller findChild: 0 ✅
- Controller SQL: 0 ✅
- View bez izmjena: 6.329 linija (isto kao baseline)

## Šta je urađeno

- 55/55 testova prolazi kroz sve faze
- `FakturaController` sa metodama za import, naimenovanja, mase, edit, export
- `FakturaService` proširen sa čistim kalkulacijama
- Neutralni modeli u `services/faktura/models.py`
- Composition root u `FakturaTab`

## Šta NIJE urađeno (namjerno)

- **Signali nisu prespojeni** — View i dalje koristi stare handlere.
  Ovo je po planu §3.2: "Ne povezivati Controller na signal koji još obrađuje View."
  Prespajanje je rizična operacija koja zahtijeva testiranje na stvarnoj aplikaciji.
- Legacy metode nisu obrisane — aktivne su dok unified tok nije potvrđen.
- Agent/MainWindow direktni pristup widgetima nije migriran.

## Sledeći korak (za drugog agenta)

1. Prespojiti signale u vertikalnim rezovima (Faza 4 → Faza 5 → Faza 6...)
2. Testirati sa stvarnim fakturama iz `najavauvoza/`
3. Migrirati Agent/MainWindow pozivaoce na `FakturaTab` API
4. Obrisati legacy metode nakon potvrde stabilnosti
5. `dist_client` mirror
