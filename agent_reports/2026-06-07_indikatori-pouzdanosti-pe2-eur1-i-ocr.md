# Agent Report: Indikatori pouzdanosti porijekla (PE2/EUR.1), Auto-popuni UX i Tesseract OCR

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

1. **Popravljen bug nedosljednih indikatora pouzdanosti porijekla** — stavke
   sa rucno potvrdjenom povlasticom (kroz PE2/PE3 izjavu ili EUR.1 sertifikat)
   su prikazivale nedosljedne ✅/bez-kvacice oznake za sustinski iste slucajeve.
2. **Citljiviji prikaz rezultata "Auto-popuni tarifne"** — umjesto sirovih
   sifri proizvoda (npr. "609ER004 → 40091100") sad se prikazuje naziv robe.
3. **Scroll-ujuci dijalog umjesto QMessageBox** — sprijecava da prozor postane
   veci od ekrana i sakrije OK dugme.
4. **Nova kolona-indikator za Povlasticu** — vizuelno odvaja pouzdanost
   povlastice od pouzdanosti zemlje porijekla.
5. **Ispravljeno lazno upozorenje "Tesseract nije instaliran"** pri startu
   aplikacije iako je Tesseract instaliran na Windows-u.

## Kako je urađeno

### 1. Stale country_source/confidence pri PE2/EUR.1 potvrdi
- `gui/dialogs/pe2_quick_dialog.py::PE2QuickDialog.apply_pe2_data` (i
  `dist_client` mirror): nakon postavljanja `povlastica`/`eur1_number`/
  `has_origin_statement`/`is_authorized_exporter`, dodato osvjezavanje
  `country_source = "PDF_IZJAVA"`, `country_confidence = "HIGH"`,
  `country_conflict_details = ""`.
- `gui/dialogs/eur1_quick_dialog.py::Eur1QuickDialog.apply_eur1_data` (i
  `dist_client` mirror): isto, ali sa NOVIM source-om
  `country_source = "EUR1_POTVRDA"` — namjerno razlicitim od `"PDF_IZJAVA"`
  jer EUR.1 je zaseban zvanicni sertifikat, a ne izjava na fakturi
  (`has_origin_statement` ostaje `False`).
- `gui/tabs/faktura_view.py::_apply_country_confidence_color` (i mirror):
  dodat tooltip case za `"EUR1_POTVRDA"` ("✅ Porijeklo potvrđeno EUR.1
  sertifikatom").

### 2. Auto-popuni — citljiv prikaz + scroll dijalog
- `_show_tariff_mapping_result`: izgradjen `naziv_by_line` mapping
  (`line_no → naziv_robe`) iz `self.draft.invoice_lines`, prikaz koristi
  naziv umjesto sirove sifre iz `result.matched_details`.
- Nova `_show_scrollable_info_dialog(title, text)`: `QDialog` + read-only
  `QTextEdit` (scroll) + `QDialogButtonBox`, velicina ogranicena na
  `min(560/620, dostupna_velicina_ekrana - 100)`.

### 3. Indikator pouzdanosti Povlastice
- Nova `_apply_preference_confidence_color(row, item)`: boji kolonu
  Povlastica (kolona 10) — žuto (`⚠️`) kad je `country_source == "PDF_OZNAKA"`
  i nema povlastice (treba rucna provjera), zeleno (`✅`) kad povlastica
  postoji i `country_source` je `"PDF_IZJAVA"` ili `"MATCH"`.
- Pozvana iz `_add_item_to_table` odmah nakon `_apply_country_confidence_color`.

### 4. Tesseract OCR lazno upozorenje
- `run.py` / `dist_client/run.py::_check_ocr_availability`: dodat import
  `importers.pdf.ocr_utils` PRIJE poziva `pytesseract.get_tesseract_version()`
  — taj modul pri ucitavanju auto-detektuje Tesseract na uobicajenim Windows
  putanjama i postavlja `pytesseract.tesseract_cmd`. Bez tog importa,
  provjera se oslanjala samo na PATH.
- Verifikovano direktnim testom kroz `dist_client\.venv\Scripts\python.exe`:
  `tesseract_cmd = C:\Program Files\Tesseract-OCR\tesseract.exe`,
  `verzija = 5.4.0.20240606`.

## Zašto

**Indikatori pouzdanosti** — korisnik je prijavio da identicne, rucno
potvrdjene stavke (npr. roba iz Srbije sa PE2 izjavom i CEFTAR povlasticom)
nekad imaju zelenu kvacicu pored zemlje porijekla, a nekad ne, sto ga
zbunjuje ("ne razumije šta mu aplikacija poručuje"). Uzrok: `apply_pe2_data`
i `apply_eur1_data` su azurirali `povlastica` ali NIKAD nisu dirali
`country_source`/`country_confidence` — te oznake su ostajale zaglavljene na
vrijednostima iz trenutka UVOZA fakture (npr. `"PDF_OZNAKA"`, postavljeno
PRIJE nego sto je korisnik rucno potvrdio porijeklo). Ovo je isti obrazac
"zaglavljene naucene/uvozne vrijednosti" kao u
[[2026-06-07_pogresna-tarifa-grejac-spirala]] — popravka mora osvjeziti SVE
povezane derivate polja, ne samo glavno polje koje korisnik vidi da se mijenja.

**Auto-popuni prikaz** — korisnik je rekao da sirove sifre proizvoda
(npr. "609ER004") "ne znace nista" obicnom korisniku, dok naziv robe odmah
otkriva eventualnu gresku (vidi prethodni slucaj GREJAC SPIRALA gdje je
pogresna tarifa bila skrivena iza nepoznate sifre).

**Scroll dijalog** — `QMessageBox.information` se nekontrolisano siri sa
duzinom teksta; kod vise od ~10 stavki prozor postaje veci od ekrana i OK
dugme ispada van vidljivog podrucja — korisnik nije mogao zatvoriti dijalog
("NE MOGU DA KLIKNEM DA PRIHVATIM").

**Tesseract** — `_check_ocr_availability` je provjeravao dostupnost OCR-a
prije nego sto je modul koji auto-detektuje instalaciju uopste ucitan,
pa je javljao laznu poruku iako je alat ispravno instaliran.

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `e53b3b4` | fix | Osvježi indikatore pouzdanosti porijekla pri PE2/EUR.1 potvrdi + UX poboljšanja Auto-popuni dijaloga |
| `b748d08` | fix | Ispravi lažno upozorenje "Tesseract nije instaliran" |

---

## Napomena za buduće sesije

Novi `country_source` kod `"EUR1_POTVRDA"` treba dodati u dokumentaciju /
nabrajanja gdje god se `country_source` enumerise (npr. ako postoje
validacije ili izvještaji koji provjeravaju dozvoljene vrijednosti tog polja).
Provjereno da `merge_country_origin` i `_apply_country_confidence_color`
ispravno rukuju nepoznatim/novim source vrijednostima (fallback na generican
tekst), pa nema rizika od regresije za postojece slucajeve.
