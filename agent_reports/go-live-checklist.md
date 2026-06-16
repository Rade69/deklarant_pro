# Go-Live Checklist — Deklarant Pro

Datum ažuriranja: 2026-05-12  
Prethodni status (2026-05-04): NO-GO  
Trenutni commit: d72393d  
Odgovorna osoba: Radovan

---

## 1) Backup prije deploy-a

- [ ] PostgreSQL backup napravljen (`pg_dump deklarant_sistem > backup_YYYY-MM-DD.sql`)
- [ ] Backup sačuvan na lokaciji van servera (external drive ili cloud)
- [ ] Test restore potvrđen: `psql deklarant_test < backup_YYYY-MM-DD.sql`

**Akcija:** Radovan izvršava ručno na Ubuntu serveru.  
**Status:** ⬜ OTVORENO

---

## 2) Lozinka u git historiji — KRITIČNO

- [ ] Rotirati lozinku za PostgreSQL korisnika koji je bio u kodu
- [ ] Potvrditi da nova lozinka radi na oba terminala
- [ ] Opciono: `git filter-repo` za čišćenje historije (samo ako repo nije shared)

**Akcija:** Radovan mijenja lozinku na serveru + u `config.ini` na oba terminala.  
**Status:** ⬜ OTVORENO — ne idi u produkciju dok ovo nije zatvoreno!

---

## 3) Konfiguracija okruženja

- [ ] `config.ini` na Terminal 1 — provjeren (DB host, port, user, password)
- [ ] `config.ini` na Terminal 2 — provjeren (isti server, isti credentials)
- [ ] Putanje za log fajlove dostupne za upis na oba terminala
- [ ] Putanje za `najavauvoza/` folder konfigurisane (lokalne, ne shared)
- [x] Nema hardkodovanih vrijednosti u kodu (zatvoreno refaktorom)

**Akcija:** Radovan provjerava oba računara.  
**Status:** ⬜ PARCIJALNO

---

## 4) Dependency i sistemski alati

- [ ] `uv sync` izvršen bez grešaka na Terminal 1
- [ ] `uv sync` izvršen bez grešaka na Terminal 2
- [ ] PySide6 radi na oba terminala (pokrenuti aplikaciju jednom)
- [ ] `tesseract` instaliran ako se koristi OCR (`tesseract --version`)

**Akcija:** Pokrenuti terminal i izvršiti komande na svakom računaru.  
**Status:** ⬜ OTVORENO

---

## 5) Konekcija na produkcioni PostgreSQL

- [ ] Terminal 1 → server: konekcija prolazi (pokrenuti aplikaciju, provjeriti log)
- [ ] Terminal 2 → server: konekcija prolazi
- [ ] Sve potrebne tabele/šeme postoje (`catalogs.*`, `public.*`)
- [ ] Connection pool ne odbacuje konekcije pri simultanom korištenju oba terminala

**Akcija:** Pokrenuti aplikaciju na oba terminala istovremeno i provjeriti log.  
**Status:** ⬜ OTVORENO

---

## 6) Smoke test kritičnih tokova

- [ ] Uvoz PDF fakture (Blagić, Leburic ili Šumaprom) — radi na Terminal 1
- [ ] Uvoz PDF fakture — radi na Terminal 2
- [ ] Kreiranje naimenovanja iz uvezene fakture
- [ ] Auto-popuni tarifnih brojeva
- [ ] XML export (Asycuda format) — fajl se kreira bez greške
- [ ] Zaglavlje: čuvanje i učitavanje drafta
- [x] Validacija zaglavlja/naimenovanja prolazi (potvrđeno testovima)
- [x] Licensing panel učitava status licence

**Akcija:** Radovan prođe kroz jedan kompletan ciklus deklaracije na svakom terminalu.  
**Status:** ⬜ PARCIJALNO

---

## 7) Logovanje i nadzor

- [x] Aplikacija piše log bez rušenja (zatvoreno — dodan fallback za read-only log)
- [ ] Log fajl lokacija poznata na oba terminala (dokumentovati gdje se nalazi)
- [ ] Dogovoreno ko reaguje na incident (Radovan ili drugi admin)
- [ ] Procedura: šta korisnik radi kad aplikacija pukne (restart? javljanje Radovanu?)

**Akcija:** Napisati 5 rečenica procedure za korisnika.  
**Status:** ⬜ PARCIJALNO

---

## 8) Rollback plan

- [x] Poznat posljednji stabilan commit: `d72393d` (2026-05-12)
- [ ] Procedura rollback-a dokumentovana:
  ```
  1. git checkout <prethodni-commit>
  2. uv sync
  3. Pokrenuti aplikaciju
  4. Ako DB schema promijenjena — restore iz backupa
  ```
- [ ] Backup baze testiran (veza sa stavkom 1)

**Akcija:** Radovan dokumentuje u internom wiki/notesu.  
**Status:** ⬜ PARCIJALNO

---

## 9) Što je riješeno od 4. maja (kod)

| Datum | Šta | Commit |
|-------|-----|--------|
| 2026-05-09 | SQL injection fix (4 mjesta, f-string → psycopg2.sql) | `sql_fix` |
| 2026-05-09 | Security: pool timeout, shutdown, upozorenje za lozinku | `sec_fix` |
| 2026-05-09 | Rub.36/Rub.44 fix + Blagić PDF footer fix | `rub_fix` |
| 2026-05-11 | MCP server fix + memorija migracija | `mcp_fix` |
| 2026-05-12 | /simplify: -707 linija mrtavog koda, O(n²) fix | `d72393d` |
| 2026-05-12 | Bug fix: `_PRESERVE_REFS` NameError u zaglavlje_view | `de30b96` |

---

## 10) Konkretan plan za produkciju

### Faza 1 — Sigurnost (danas ili sutra)
1. Rotirati PostgreSQL lozinku
2. Ažurirati `config.ini` na oba terminala
3. Napraviti PostgreSQL backup

### Faza 2 — Deploy (1-2 dana)
4. `uv sync` na oba terminala
5. Pokrenuti aplikaciju — provjeriti konekciju i log
6. Smoke test: jedan kompletan ciklus deklaracije na svakom terminalu

### Faza 3 — Go-Live (dan 3)
7. Oba korisnika prisutna — testiranje simultanog rada
8. Napisati kratku proceduru za incident
9. Potpisati Go/No-Go odluku

---

## Go/No-Go odluka

- **Prethodni status:** NO-GO (2026-05-04)
- **Trenutni status:** PENDING — kod je spreman, operativne stavke otvorene
- **Procjena:** 10-15 sati operativnog rada do Go-Live
- **Odluka:** __________
- **Datum i potpis:** __________
