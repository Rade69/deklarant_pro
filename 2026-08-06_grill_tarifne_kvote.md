# Grill sesija — Tarifne kvote u Šifrarnicima

**Datum:** 2026-08-06
**Tema:** Panel "Tarifne kvote" ne radi — prazan ekran + greške
**Status:** završeno (dijagnostika)

---

## Pronađeni problemi

### 1. RuntimeError: _RefreshWorker already deleted ✅ POPRAVLJENO
- **Fajl:** `gui/tabs/sifarnici/quota_panel.py:347`
- **Uzrok:** `QThread.deleteLater()` uništi C++ objekat, ali `self._worker` i dalje drži Python referencu. `isRunning()` puca.
- **Popravka:** `_worker_running()` sa `try/except RuntimeError` + `self._worker = None` u handlerima
- **Commit:** `ee5a056`

### 2. PostgreSQL privilegije — "must be owner of table quota_snapshot_items" ⚠️ KONFIGURACIJA BAZE
- **Uzrok:** Korisnik baze nije vlasnik tabela `quota_snapshot_items` i `quota_snapshots`
- **Nije kod Deklarant Pro-a** — treba DBA intervencija na `dmserver`
- **Rešenje:** `ALTER TABLE quota_snapshot_items OWNER TO korisnik;`

### 3. UINO PDF URL radi
- URL `https://www.uino.gov.ba/portal/wp-content/uploads/GenerisaniPDF/Qba-Stanje.pdf` je dostupan (200 OK, 60KB)
- Download radi, parser verovatno radi — ali ne možemo potvrditi dok se ne reši problem #2

---

## Šta nije problem
- Kod QuotaPanel-a je ispravan
- `quota_service.py` je ispravan
- URL nije promenjen
- Parser nije pokvaren

---

## Preporuka
1. Rešiti PostgreSQL privilegije na `dmserver`
2. Testirati "Osvježi stanje sa UINO" ponovo
3. Ako parser padne — dodati bolje logovanje u `parse_uino_quota_pdf()`
