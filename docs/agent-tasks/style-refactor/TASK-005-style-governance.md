# TASK-005 - Style governance i guardrails

## Kontekst
Bez jasnih pravila stilovi ce se ponovo razici kroz vrijeme.

## Scope
- Definisati style governance dokument.
- Dodati jednostavnu skriptu/pravila za detekciju anti-patterna.

## Allowed Files
- `docs/architecture/STYLE_GOVERNANCE.md` (novi fajl)
- `scripts/style_audit.sh` (novi fajl)

## Zabranjeno
- Bez izmjena GUI source fajlova.

## Implementacija
1. Definisati 3-layer model (global QSS, tab QSS, inline state-only).
2. Definisati naming konvencije (`objectName`, custom properties).
3. U skripti prijaviti:
   - duple `QComboBox::down-arrow` deklaracije
   - inline stilove bez komentara razloga
   - globalne nescopirane selektore visokog rizika

## Acceptance kriteriji
- [ ] Dokument postoji i primjenjiv je.
- [ ] Skripta radi i vraca listu potencijalnih konflikata.
- [ ] Skripta je read-only (bez automatskog mijenjanja fajlova).

## Verifikacija
- `bash scripts/style_audit.sh`
