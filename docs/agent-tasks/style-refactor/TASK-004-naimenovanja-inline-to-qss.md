# TASK-004 - Naimenovanja: migracija baznih inline stilova u QSS

## Kontekst
Naimenovanja tab ima veliki broj inline stilova koji otežavaju kontrolu hijerarhije.

## Scope
- Migrirati samo bazne (static) inline stilove u `styles/naimenovanja_components.qss`.
- Ostaviti inline samo dinamičke state stilove (error/flash/focus workaround).

## Allowed Files
- `gui/tabs/naimenovanja_view.py`
- `styles/naimenovanja_components.qss`

## Zabranjeno
- Bez promjene layout geometrije.
- Bez izmjena poslovne logike.

## Implementacija
1. Uvesti `objectName`/`property` selektore gdje fali.
2. Premjestiti static stilove iz inline u QSS.
3. Očistiti duplikate i konfliktne strelica/dropdown deklaracije.

## Acceptance kriteriji
- [ ] Broj inline `setStyleSheet` poziva u `naimenovanja_view.py` smanjen najmanje 30%.
- [ ] Vizuelno bez regresije u Rubrika 40 i nav baru.
- [ ] `py_compile` prolazi.

## Verifikacija
- `python -m py_compile gui/tabs/naimenovanja_view.py`
- `rg -n "setStyleSheet\\(" gui/tabs/naimenovanja_view.py`
