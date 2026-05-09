# Go-Live Checklist — Deklarant Pro

Datum: 2026-05-04  
Verzija/commit: 9d52aab  
Odgovorna osoba: Radovan (potvrditi)

## 1) Backup prije deploy-a

- [ ] PostgreSQL backup napravljen
- [ ] Backup licensing/config fajlova napravljen
- [ ] Test restore-a potvrđen na test okruženju
- Status: U TOKU
- Napomena: Nema evidencije da je backup/restore operativno izvršen u ovom ciklusu.

## 2) Konfiguracija okruženja

- [x] `config.ini` provjeren (bez hardkodovanih vrijednosti u kodu)
- [ ] Putanje za log/licensing dostupne za upis
- [ ] Produkcioni DB host/port kredencijali validni
- Status: PARCIJALNO
- Napomena: Kod je očvrsnut fallback-ima za read-only; produkcione dozvole i kredencijali još nisu potvrđeni.

## 3) Dependency i sistemski alati

- [ ] `uv sync` izvršen bez grešaka
- [x] PySide6 / ostale kritične biblioteke učitane
- [ ] OCR provjera (ako se koristi): `pytesseract` + sistemski `tesseract`
- Status: PARCIJALNO
- Napomena: Testovi i GUI moduli prolaze; nema zapisnika za svjež `uv sync` i produkcioni OCR check.

## 4) Schema i konekcija

- [ ] Potrebne tabele/kolone postoje
- [ ] Konekcija na PostgreSQL prolazi
- [ ] Brzi DB health-check prolazi
- Status: U TOKU
- Napomena: Potrebna eksplicitna provjera nad produkcionim DB okruženjem.

## 5) Smoke test kritičnih tokova

- [x] Uvoz PDF/XML radi
- [ ] Tarifiranje radi na realnom primjeru
- [x] Validacija zaglavlja/naimenovanja prolazi
- [x] Licensing panel učitava status i validaciju licence
- Status: PARCIJALNO
- Napomena: Pokriveno testovima i stabilizacionim popravkama; realni produkcioni primjer tarifiranja još nije formalno potvrđen.

## 6) Logovanje i nadzor

- [x] Aplikacija piše log bez rušenja
- [ ] Kritične greške su vidljive (log/alert kanal)
- [ ] Definisano ko reaguje na incident
- Status: PARCIJALNO
- Napomena: Dodan fallback kad log fajl nije upisiv; alert kanal i incident owner nisu dokumentovani.

## 7) Rollback plan

- [ ] Procedura rollback-a dokumentovana
- [x] Poznat poslednji stabilan commit/verzija
- [ ] Restore baze testiran
- Status: PARCIJALNO
- Napomena: Stabilni commit postoji (9d52aab), ali rollback dokument i restore proba nisu završeni.

## 8) Finalni release gate

- [x] `python -m pytest tests/ -q` zeleno na release buildu
- [x] Nema otvorenih blokera P0/P1
- [ ] Go/No-Go odluka potvrđena
- Status: PARCIJALNO
- Napomena: Test suite je zelen (218 passed, 6 skipped); potrebna formalna završna odluka.

---

## Go/No-Go odluka

- Odluka: NO-GO (dok se ne zatvore otvorene operativne stavke)
- Datum i vrijeme: 2026-05-04
- Potpis odgovorne osobe: __________
