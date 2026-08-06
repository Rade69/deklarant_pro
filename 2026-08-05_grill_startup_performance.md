# Grill sesija — Ubrzanje pokretanja Deklarant Pro

**Datum:** 2026-08-05/06
**Tema:** Optimizacija startup vremena aplikacije
**Status:** završeno (prva faza)

---

## Izmerene vrednosti

| Merenje | Pre | Posle |
|---------|-----|-------|
| Ukupni startup | 1329ms | 1114ms |
| MainWindow init | 952ms | 910ms |
| Show | 184ms | 92ms |
| FakturaTab | 657ms | 901ms* |
| AgentTab | 277ms | 1ms ✅ |
| Styles | 11ms | 7ms |

\* Varijacija sistema, FakturaTab nije menjan.

---

## Donete odluke

### 1. AgentTab → lazy loading ✅
- **Odluka:** AgentTab se kreira tek pri prvom kliku (LazyTab)
- **Ušteda:** ~277ms
- **Rizik:** Nizak — signal veza koristi `ensure_initialized()` lambda
- **Commit:** `acb279b`

### 2. FakturaTab ostaje eager
- **Odluka:** FakturaTab se ne odlaže — prvi je tab, mora biti spreman
- **Rizik odlaganja:** Korisnik čeka pri prvom kliku, lošiji UX

### 3. AdminTab je već lazy
- **Status:** Već implementirano ranije (`326c7ad`)

### 4. Naimenovanja, Zaglavlje, Šifrarnici — već lazy
- **Status:** Već implementirano

---

## Preostale nepoznanice (evidence_needed)

### FakturaTab — šta unutar njega troši 900ms?
- **Potrebno:** Dodati markere u `FakturaView.__init__` i `FakturaController.__init__`
- **Hipoteza:** View (UI kreiranje, tabele, toolbar) ili Controller (servisi, importi)
- **Očekivana ušteda:** 200-400ms ako se delovi odlože

### Da li se može odložiti kreiranje FakturaView tabele?
- **Potrebno:** Analiza zavisnosti — da li MainWindow koristi `faktura_tab.view.table` pre prvog prikaza?
- **Hipoteza:** Tabela se može kreirati u `showEvent` umesto u `__init__`

---

## Preporuke za sledeći korak

1. **Očistiti merne markere** iz `run.py` i `main_window.py`
2. **Izmeriti FakturaTab interno** (View.__init__ vs Controller.__init__)
3. Na osnovu brojki, odlučiti da li odlagati delove View-a

---

## Scope granice

**Šta je VAN ovog grilla:**
- Optimizacija importa (već urađeno kroz lazy importe)
- Promena PySide6 → drugačiji GUI framework
- Kompajliranje u exe (PyInstaller)
- Optimizacija DB konekcije (već se radi asinhrono)
