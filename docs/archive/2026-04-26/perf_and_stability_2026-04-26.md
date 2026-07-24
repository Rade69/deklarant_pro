# Optimizacije performansi i stabilnosti — 26. april 2026

## 1. Lazy tab loading

### Problem
Svi tabovi (Naimenovanja, Zaglavlje, Šifrarnici) inicijalizovani su pri pokretanju aplikacije,
čak i kad korisnik ne otvori te tabove. To je usporavalo startup za ~800ms.

### Rješenje — `gui/tabs/lazy_tab.py`
Kreiran `LazyTab(QWidget)` wrapper koji kreira pravi tab tek pri prvom `currentChanged` signalu.

- `ensure_initialized()` — kreira unutrašnji widget ako nije kreiran
- `sizeHint()` / `minimumSizeHint()` — vraća `800x600` dok je tab prazan,
  sprječava da QTabWidget skupi prozor pri prvom kliku
- `__getattr__` — proslijeđuje atribute na unutrašnji widget; vraća `_noop` dok nije kreiran

### Izmijenjeni fajlovi
- `gui/main_window.py` — Naimenovanja, Zaglavlje, Šifrarnici wrapped u LazyTab
- `gui/tabs/tab_factory.py` — svi importi premješteni unutar metoda (lazy module load)
- `gui/main_window.py` `_on_tab_changed` — `ensure_initialized()` pozvan u `currentChanged`
  da tab bude spreman PRIJE nego Qt mjeri veličinu sadržaja

### Rezultat
Startup ~800ms brži; tabovi se inicijalizuju tek kad korisnik klikne.

---

## 2. Thread-safe connection pool

### Problem
`SimpleConnectionPool` nije thread-safe. `ChatWorker` (QThread) i main thread
dijelili su isti pool → potencijalni crash ili corruption.

### Rješenje — `database/db.py`
`SimpleConnectionPool` → `ThreadedConnectionPool` (isti API, thread-safe implementacija).
`connect_timeout`: 10s → 3s (brže otkrivanje kad server nije dostupan).

---

## 3. N+1 query fix u get_tarifa_opis

### Problem
`get_tarifa_opis()` pozivala bazu u petlji za svaki fallback kod (do 6 upita po pozivu).

### Rješenje — `database/db.py`
Jedan upit sa `WHERE tarifni_kod = ANY(%s)` dohvata sve kandidate odjednom,
sortira po dužini koda (specifičniji = duži), vraća prvi rezultat.

---

## 4. N+1 fix u chat_worker partner pretrazi

### Problem
`_search_pg_partners` pravila 3 odvojena ILIKE upita za 3 ključne riječi.

### Rješenje — `gui/tabs/agent/widgets/chat_worker.py`
Jedan upit sa `WHERE name ILIKE %s OR name ILIKE %s OR name ILIKE %s`.

---

## 5. ProcessingWorker memory leak

### Problem
`ProcessingWorker` (QThread) kreiran na svakom importu, nikad Qt-brisano → memory leak.

### Rješenje — `gui/tabs/agent/agent_controller.py`
`self._worker.finished.connect(self._worker.deleteLater)`

---

## 6. Popravka skupljanja prozora pri tab klikovima

### Problem
Na KDE/Linux, klik na Zaglavlje ili Šifrarnici tab skupio bi prozor.

### Uzrok (dva sloja)

**Sloj 1** — `setMaximumWidth(1650)` u MainWindow konfliktor s maximizovanim prozorom.
KDE je forsirao max širinu pri layout update-u → resize prozora.

**Sloj 2** — `showEvent` u MainWindow imao `height() != 823` check koji je
forsirao resize svaki put kad se prozor fokusira (ne samo pri pokretanju).

### Rješenje — `gui/main_window.py`
- Uklonjen `setMaximumWidth(1650)`
- `showEvent` radi samo jednom (`_first_show_done` flag)
- `_on_tab_changed` poziva `ensure_initialized()` za sve LazyTab-ove odmah u `currentChanged`

---

## 7. Startup timer

### Rješenje — `run.py`
`time.perf_counter()` mjeri startup od pokretanja do `window.show()`.
Output: `⏱️ Startup: 466ms` u log-u.
