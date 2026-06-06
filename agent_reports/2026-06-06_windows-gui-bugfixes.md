# Agent Report: Windows GUI bugfixevi i funkcionalna poboljšanja
**Datum**: 2026-06-06  
**Grana**: windows  
**Sesija**: nastavak prethodne (context compaction)

---

## Šta je urađeno

### 1. Toolbar dugmad — visina smanjena na 24px
**Problem**: Donja ivica toolbar dugmadi nije bila vidljiva jer je visina bila prevelika.  
**Fix**: `btn.setFixedHeight(24)` u `zaglavlje_view.py` (obje lokacije: `gui/` i `dist_client/gui/`).  
**Commit**: `16d74f7`

### 2. Dokumenti tabela — ravnomjerna podjela kolona 50/50
**Problem**: "Naziv dokumenta" kolona zauzimala ~30%, "Referenca" premalo prostora.  
**Fix**: Obje kolone postavljene na `QHeaderView.ResizeMode.Stretch` — automatski dijele preostali prostor jednako. Prva (code) kolona ostaje fiksna 65px.  
**Commit**: `840a2df`

### 3. Autocomplete popup — bijeli tekst na bijeloj pozadini
**Problem**: Popup za unos šifri dokumenata nasljeđivao bijelu boju teksta od roditeljskog widgeta.  
**Fix**: Eksplicitni `color: #1e3820` u QSS za `QListView` i `QListView::item` unutar popup stylesheet-a.  
**Commit**: `aa02fb4`

### 4. Šifrarnici — tamno plavi alternativni redovi
**Problem**: `setAlternatingRowColors(True)` bez eksplicitnog `alternate-background-color` u QSS koristi Windows sistemsku paletu (tamno plava).  
**Fix**: Dodano `alternate-background-color: #f0f7f0` i `color: #1e3820` na `QTableWidget::item` u `sifarnici_view.py`.  
**Commit**: `d52339c`

### 5. Dijalozi — tamno plavi alternativni redovi (svi dialogi)
**Isti uzrok** kao tačka 4. Pogođeni dijalozi:
- `eur1_quick_dialog.py` → `alternate-background-color: #f0f4f8`
- `inspection_dialog.py` → `alternate-background-color: #f0f4f8`
- `tariff_search_dialog.py` → `alternate-background-color: #f7f9fc`
- `sifarnici/quota_panel.py` → `alternate-background-color: #f0f7f0`

**Commit**: `aa8aaf6`

### 6. Šumaprom — IR/IRSKA pogrešno čitano kao Iran
**Problem**: Šumaprom XLS koristi nestandardni "IR" za Irsku (ispravno ISO je "IE"). Regex izvlači "IR" koji je 2 slova → direktno prosljeđen kao zemlja porijekla.  
**Fix**: U `sumaprom_excel_parser.py`, kada je ISO kod "IR", provjeri puni naziv (iza "/") — ako sadrži "IRSKA" ili "IRELAND", prebaci na "IE".  
**Commit**: `e4e92af`

### 7. ProcessingWorker — TypeError pri sortiranju faktura
**Problem**: `_natural_invoice_parts()` vraćala tuple koji miješa `int` (za brojčane tokene) i `str` (za tekstualne). Python ne može uspoređivati `int < str` u sortiranju.  
**Poruka**: `TypeError: '<' not supported between instances of 'int' and 'str'`  
**Fix**: Sve dijelove konvertovati u `str`, a brojčane zero-paddovati na 10 znakova (`part.zfill(10)`) radi ispravnog prirodnog sortiranja.  
**Commit**: `5a32f21`

### 8. Toolbar neto override — bruto=neto bez koeficijenta
**Nova funkcionalnost**: Šumaprom XLS fajlovi često imaju samo bruto težinu (neto = 0 u fajlu). Korisnik ručno upiše neto u toolbar. Stari kod uvijek primjenjivao 0.95 koeficijent kada je neto=0 u bazi.  
**Fix**: U `faktura_view.py`, `_on_calculate_masses()`:
- Ako toolbar neto > 0 i sve sačuvane neto vrijednosti su 0
- Distribui toolbar neto proporcionalno po bruto težinama svake fakture
- Koeficijent `neto_bruto_ratio` tada postaje 1.0 (jer bruto=neto)  

**Commit**: `2d01d7a`

### 9. Tarifa — "unable to open database" greška na Windows klijentu
**Problem**: Kompajlirani `tariff.cp314-win_amd64.pyd` ima `__file__` koji pokazuje na `dist_client/services/tariff.cp314-win_amd64.pyd`. `DB_PATH` izgrađen sa `../../database/` → `dist_client/database/deklarant_sistem.db` koji ne postoji → SQLite OperationalError.  
**Fix (3-slojni)**:
1. `database/deklarant_sistem.db` kopiran u `dist_client/database/` (11MB, 13.556 tarifa) — trenutno rješenje
2. `services/tariff/tarifa_service.py`: `_resolve_db_path()` proba 3 kandidat lokacije — za sljedeću kompilaciju
3. `dist_client/services/tarifa_service.py`: Python patch koji ispravlja `DB_PATH` na importovanom modulu prije prvog poziva `_get_conn()` — radi odmah bez recompilacije

**Napomena**: `database/deklarant_sistem.db` nije u gitu (`.gitignore: *.db`). Kopija mora biti prisutna ručno na svakoj Windows instalaciji.  
**Commit**: `943dcde`

---

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `16d74f7` | fix | Toolbar dugmad visina 24px |
| `e9e568e` | fix | Sužen Naziv dok., proširen Referenca (prethodna verzija) |
| `840a2df` | fix | Dokumenti kolone 50/50 Stretch |
| `aa02fb4` | fix | Autocomplete popup bijeli tekst |
| `d52339c` | fix | Šifrarnici alternating rows |
| `aa8aaf6` | fix | Svi dijalozi alternating rows |
| `e4e92af` | fix | Šumaprom IR/IRSKA → IE |
| `5a32f21` | fix | ProcessingWorker TypeError sortiranje |
| `2d01d7a` | feat | Toolbar neto override (bruto=neto) |
| `943dcde` | fix | Tarifa SQLite DB_PATH fallback |

---

## Tehnički zaključci za buduće sesije

- **Windows alternating rows**: Uvijek dodavati `alternate-background-color` eksplicitno u QSS kada se koristi `setAlternatingRowColors(True)`. Windows sistemska paleta daje tamno plavu, Linux/Mac ignorišu.
- **Compiled .pyd i __file__**: Nuitka `.pyd` fajlovi imaju `__file__` koji pokazuje na `.pyd`, ne na Python source. Relativne putanje za DB/resurse moraju imati fallback logiku.
- **Natural sort miješani tipovi**: `tuple` za `key=` u `sort()` mora biti konzistentnog tipa. Koristiti `zfill()` za sve brojčane tokene.
- **Šumaprom XLS**: Koristi "IR" za Irsku (ne Iran). Format: `"IR / IRSKA"` — treba provjeriti puni naziv iza slash-a.
