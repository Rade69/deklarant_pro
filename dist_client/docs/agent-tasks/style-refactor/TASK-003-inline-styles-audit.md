# TASK-003 - Inline stylesheet audit

## Kontekst
Inline `setStyleSheet` pozivi imaju najveci prioritet i cesto pregaze globalni QSS.

## Scope
- Napraviti detaljan audit svih inline stilova.
- Klasifikovati: bazni stil, state stil, workaround stil.

## Allowed Files
- `docs/architecture/INLINE_STYLE_AUDIT.md` (novi fajl)

## Zabranjeno
- Bez izmjena source koda.

## Implementacija
1. Popisati sve `setStyleSheet` lokacije.
2. Oznaciti koji su kandidati za migraciju u QSS.
3. Oznaciti koje treba ostaviti inline (state-only).

## Acceptance kriteriji
- [ ] Svi inline pozivi mapirani po fajlu i funkciji.
- [ ] Svaki ima oznaku `MIGRATE` ili `KEEP`.
- [ ] Definisan redosled migracije po riziku.

## Verifikacija
- `rg -n "setStyleSheet\\(" gui`
