# TASK-002 - Dropdown strelice hardening

## Kontekst
Postoji fallback prikaz strelica (kvadrat/minus) zbog QSS konflikata i runtime override-a.

## Scope
- Stabilizovati prikaz strelica u `Zaglavlje` i `Naimenovanja`.
- Standardizovati jednu vizuelnu velicinu i poziciju.

## Allowed Files
- `gui/tabs/zaglavlje_view.py`
- `gui/tabs/naimenovanja_view.py`
- `styles/QSS_header_toolbar_sistem.qss`

## Zabranjeno
- Bez izmjena drugih tabova.
- Bez promjene poslovne logike.

## Implementacija
1. Potvrditi koji combo widgeti su kriticni.
2. Primijeniti runtime-safe strelicu (custom paint gdje treba).
3. Ostaviti QSS kao fallback i ukloniti konfliktne inline strelice.

## Acceptance kriteriji
- [ ] Nema kvadrat/minus indikatora u target combobox-ima.
- [ ] Strelica je konzistentna velicinom.
- [ ] Nema regresije u otvaranju popup liste.

## Verifikacija
- `python -m py_compile gui/tabs/zaglavlje_view.py gui/tabs/naimenovanja_view.py`
