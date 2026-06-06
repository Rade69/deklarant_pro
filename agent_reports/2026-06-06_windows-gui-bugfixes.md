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

---

## Nastavak sesije: Faktura status, historijska validacija i Zaglavlje fontovi

### 10. Faktura status bar — analiza sada prati stvarno stanje tabele

**Problem**: Status bar u tabu Faktura prikazivao je sažetak tipa `TW:51 | IN:32 | ... | 138 bez tarife`, ali brojevi nisu odgovarali stvarnom stanju u tabeli nakon popunjavanja tarifa, zemalja ili povlastica.

**Odluka**: Sažetak ne smije ostati "zamrznut" iz trenutka uvoza. Mora se ponovo računati iz vidljive tabele, jer korisnik nakon uvoza ručno ili automatski mijenja ćelije.

**Fix**:
- dodat je interni auto-flag za analysis summary;
- status se osvježava poslije validacije i poslije update-a status bara;
- brojanje se radi iz vidljivih kolona tabele:
  - tarifni broj,
  - zemlja porijekla,
  - povlastica,
  - EUR1 podatak kada je relevantan.

**Ključni razlog**: `draft` i tabela mogu kratko biti različiti tokom GUI rada. Za status bar korisnik gleda tabelu, pa status mora pratiti tabelu.

### 11. Historijska validacija tarifa — uklonjen "nepoznat izvoznik" kao izvor

**Problem**: Dijalog historijske validacije je znao prikazati prijedlog sa `Izvor: nepoznat izvoznik`. To nema smisla za korisnika jer aplikacija tada izgleda kao da preporučuje tarifu bez pouzdanog porijekla.

**Odluka**: Ako historijski prijedlog nema poznat izvor (`supplier` ili `source`), bolje ga je preskočiti nego prikazati nejasnu preporuku.

**Fix**:
- uveden je `source_display = supplier or source`;
- prijedlozi bez `source_display` se preskaču uz info log;
- prikazani prijedlozi sada moraju imati poznat izvor.

**Ključni razlog**: Kod carinskih tarifa pogrešan ili neobjašnjen prijedlog je rizičniji od izostanka prijedloga. Korisniku mora biti jasno odakle aplikacija "zna" preporuku.

### 12. Zaglavlje — Windows fontovi i GUI hijerarhija

**Problem**: Zaglavlje tab na Windowsu nije izgledao kao Linux referenca:
- fontovi su bili sitni i neujednačeni;
- nazivi rubrika su u jednoj iteraciji postali previše naglašeni;
- podaci u poljima nisu imali dovoljno vizuelnog prioriteta;
- lupa i plus dugmad u prvoj koloni su ranije bila odsječena ili nejasna.

**Poređenje sa dev granom**:
- razvojni Linux fajl je na `gui/tabs/zaglavlje_view.py`;
- Windows runtime koristi `dist_client/gui/tabs/zaglavlje_view.py`;
- zato se promjene moraju primarno raditi u `dist_client`, a po potrebi preslikati i u root kopiju da se smanji drift.

**Fix u Windows kopiji**:
- polja i combo boxovi u prvoj koloni pojačani su da podaci budu čitljiviji;
- nazivi rubrika su spušteni na mirniji `10pt / DemiBold`;
- podaci u poljima ostaju čitljiviji od labela;
- lupa i plus dugmad su dobila veće kontrole i ikone;
- srednja kolona je ujednačena sa istom logikom: labela je pomoćni tekst, podatak je primarni sadržaj.

**Ključna odluka**: Ne treba samo "povećati sve". GUI postane bučan ako su nazivi rubrika jednako agresivni kao podaci. Konačna smjernica je:

```text
naziv rubrike = 10pt, DemiBold, miran kontrast
podatak       = 11pt, regular, tamniji i čitljiviji
```

**Root kopija**:
- `gui/tabs/zaglavlje_view.py` je dotaknuta samo da se smanji razlika sa `dist_client`;
- usput je popravljena postojeća sintaksna greška u `setStyleSheet(...).replace(...)` bloku.

**Napomena za buduće sesije**:
Ako korisnik kaže da se promjena "ne vidi", prvo provjeriti koju kopiju aplikacija stvarno učitava:

```powershell
dist_client\.venv\Scripts\python.exe -c "import gui.tabs.zaglavlje_view as z; print(z.__file__)"
```

Na Windows instalaciji očekivano je da putanja bude pod `dist_client/gui/tabs/`.
