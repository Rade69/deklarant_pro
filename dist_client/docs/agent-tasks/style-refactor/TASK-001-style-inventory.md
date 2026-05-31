# TASK-001 - Inventar stilova i konflikt mapa

## Kontekst
Stilovi dolaze iz vise slojeva (`styles/*.qss`, tab-level stylesheet, inline `setStyleSheet`), sto uzrokuje konflikte.

## Scope
- Napraviti dokumentovani inventar svih aktivnih style izvora.
- Napraviti mapu konflikata za `QComboBox`, `QLineEdit`, dugmad i status label.

## Allowed Files
- `docs/architecture/STYLE_INVENTORY.md` (novi fajl)

## Zabranjeno
- Bez izmjena Python ili QSS fajlova.

## Implementacija
1. Enumerisati sve QSS fajlove koji se loaduju kroz `main_window.py`.
2. Enumerisati sve tabove/panele sa inline `setStyleSheet`.
3. Za svaku klasu widgeta navesti ko ima finalni prioritet.

## Acceptance kriteriji
- [ ] Dokument sadrzi listu izvora stilova.
- [ ] Dokument sadrzi konflikt mapu po widget tipu.
- [ ] Dokument navodi top 10 najrizičnijih inline stilova.

## Verifikacija
- `rg -n "setStyleSheet\\(" gui | wc -l`
- `rg -n "QComboBox::down-arrow|QLineEdit|QPushButton" styles/*.qss`
