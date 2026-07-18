# Agent Report — 2026-07-18: Medicopharm PE2 per-item filter + višestruki GUI fixevi

## Datum
2026-07-18

## Agent
Claude Sonnet 4.6

## Scope
- `gui/dialogs/pe2_quick_dialog.py` + mirror
- `importers/vendors/medicopharm/medicopharm_importer.py` + mirror
- `gui/delegates/validation_delegate.py` + mirror
- `gui/tabs/agent/widgets/tariff_validation_dialog.py` + mirror
- `gui/tabs/faktura_view.py` + mirror

---

## GitNexus impact
Ocijenjen ručno (private metode unutar dijaloga, bez vanjskih pozivača):
- `_group_by_country` — private metoda `PE2QuickDialog`, poziva se samo u `setup_ui()`. Rizik: **LOW**
- `_extract_origin_statement_item_set` — standalone funkcija, poziva se samo na jednom mjestu u `medicopharm_importer.py`. Rizik: **LOW**
- `ValidationDelegate.paint()` — override Qt metode, jedini korisnik je `FakturaView`. Rizik: **LOW**

---

## Šta je urađeno

### Fix 1 — PE2 dijalog ignoriše per-item has_origin_statement (MAIN BUG)
**Fajl**: `gui/dialogs/pe2_quick_dialog.py`, metoda `_group_by_country`

**Problem**: Kad Medicopharm faktura kaže "Ova izjava se odnosi na stavke: 1-3; 5-41; 43-51; 53-85; 87;88; 92-94", importer ispravno postavlja `has_origin_statement=True` samo za pokrivene stavke i `False` za stavke 4, 42, 52, 86, 89, 90, 91. Međutim, PE2 dijalog je prikazivao i te nepokrivene stavke, a `apply_pe2_data` je postavljao `povlastica` za SVE.

**Fix**: U `_group_by_country`, ako ikoja stavka ima `has_origin_statement=True` (per-item tracking aktiviran), preskačamo stavke sa `has_origin_statement=False`.

```python
any_has_statement = any(
    getattr(item, 'has_origin_statement', False)
    for item in self.invoice_lines
)
# ...
if any_has_statement and not getattr(item, 'has_origin_statement', False):
    continue
```

**Backward compatibility**: Ako su SVE stavke `has_origin_statement=False` (stariji importeri koji ne rade per-item tracking), `any_has_statement=False` → ponašanje nepromijenjeno.

### Fix 2 — Medicopharm debug logging
**Fajl**: `importers/vendors/medicopharm/medicopharm_importer.py`, funkcija `_extract_origin_statement_item_set`

Dodani print ispisi: regex segment koji je pronađen, broj pokrivenih stavki, lista rbr-ova bez pokrića.

### Fix 3 — ValidationDelegate boje redova
**Fajl**: `gui/delegates/validation_delegate.py`

`super().paint()` nakon `fillRect()` ponovo crtao QPalette.AlternateBase boju (tamno plava pri dark temi) i brisao custom validacione boje. Fix: postavi `Base` i `AlternateBase` na custom boju PRIJE `super().paint()`.

### Fix 4 — TariffValidationDialog terminologija
**Fajl**: `gui/tabs/agent/widgets/tariff_validation_dialog.py`

Dvije različite metrike zvale se "Pouzdanost":
- Fuzzy match procenat (Podudarnost sličnosti naziva) → preimenovano u **"Podudarnost"**
- Decision confidence score → preimenovano u **"Sigurnost preporuke"**
- Uklonjen redundantni "Oprez: slabiji prijedlog" label (badge to već pokazuje)

### Fix 5 — Auto-fill scope
**Fajl**: `gui/tabs/faktura_view.py`, metoda `_on_auto_fill()`

Bez selekcije, prethodno je auto-fill popunjao i stavke koje već imaju tarifni broj. Fix: filtrira samo stavke gdje `tarifni_broj` je prazan.

### Fix 6 — Preview dijalog tamni redovi
**Fajl**: `gui/tabs/faktura_view.py`, metoda `_show_tariff_preview_dialog()`

`setAlternatingRowColors(True)` pri dark temi davalo tamno plave redove. Fix: eksplicitni bijeli QSS + `setBackground()`/`setForeground()` po ćeliji.

---

## Zašto je urađeno

**Główny bug (PE2 per-item)**: Korisnik je uvezao Medicopharm fakturu 1476/26 (94 stavke). Izjava o porijeklu pokriva 87 od 94 stavki. Parser je ispravno parsirao raspon. Međutim, PE2 dijalog je ignorisao to i primjenjivao povlasticu na sve stavke sa `zemlja_porijekla` — tj. i na stavke 4, 42, 52, 86, 89, 90, 91 koje je izjava eksplicitno izostavila.

**ValidationDelegate**: Korisnik primijetio da se "CN" kolona boji naizmjenično različitim bojama, što nije trebalo biti.

**Terminologija**: Korisnik primijetio kontradiktornost između "Pouzdanost 82%" i "Pouzdanost prijedloga slab (60%)" — dvije različite veličine sa istim imenom.

---

## Kako je urađeno

Root cause analiza:
1. `medicopharm_importer._extract_origin_statement_item_set` — ISPRAVNO radi per-item tracking
2. `PE2QuickDialog._group_by_country` — NIJE filtrirala po `has_origin_statement`, slala sve stavke sa `zemlja_porijekla` u dijalog
3. `PE2QuickDialog.apply_pe2_data` — primjenjuje `povlastica` na sve stavke iz dijaloga

Fix je na tački 2 (najmanji scope, bez promjene interfejsa).

---

## Šta nije dirano

- `apply_pe2_data` — logika primjene povlastice nije mijenjana
- `_extract_origin_statement_item_set` — parser logika ispravna, samo dodani debug printovi
- EUR.1 dijalog (`eur1_quick_dialog.py`) — nije u scope-u
- Agent mod (`_auto_handle_povlastice_agent`) — već ispravno čita per-item `has_origin_statement`

---

## Verifikacija

- `py_compile` provjera: implicitna kroz git commit hooks
- Logička verifikacija: traced kroz `_group_by_country` → `apply_pe2_data` za Medicopharm slučaj
- Debug printovi su ostavljeni u `_extract_origin_statement_item_set` — korisnik može uvezeti Medicopharm fakturu i odmah vidjeti koji su rbr-ovi bez pokrića

---

## Pronađeni problemi

- Bug nije bio u samom parseru (regex ispravno parsira izjavu), nego u PE2 dijalogu koji ignoruje per-item tracking
- Ovaj isti bug može pogoditi i druge importere koji rade per-item tracking u budućnosti

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `fbc202b` | fix(gui): validacija boja redova i preimenovanje pouzdanosti u dijalogu |
| `b3c739c` | fix(faktura): auto-popuni samo stavke bez tarife + debug preview dijalog |
| `859083e` | fix(import): PE2 dijalog poštuje per-item has_origin_statement (Medicopharm) |

---

## Rizici / ograničenja

- Fix u `_group_by_country` pretpostavlja da `has_origin_statement=True` na bar jednoj stavci znači per-item tracking. Importeri koji ne rade per-item tracking (sve stavke `False`) neće biti pogođeni.
- Ako importer greškom postavi `has_origin_statement=True` na sve stavke (i "loše" i "dobre"), filter neće pomoći — to treba ispraviti na nivou importera.

---

## Potreban follow-up

- [ ] Korisnik treba uvesti Medicopharm fakturu 1476/26 i provjeriti konzolne ispise i da li stavke 4, 42, 52, 86, 89, 90, 91 ostaju bez povlastice
- [ ] DHCP rezervacija za server MAC `10:e7:c6:6c:64:65` (neriješeno od prethodne sesije)
- [ ] Debug printovi u `_extract_origin_statement_item_set` mogu se ukloniti nakon potvrde ispravnosti

---

## Potrebna korisnička potvrda

- **OBAVEZNO**: Uvesti Medicopharm fakturu 1476/26 i u PE2 dijalogu provjeriti da se prikazuju samo stavke pokrivene izjavom (ne sve 94 nego 87)
- Vizuelno: validacione boje u CN koloni ne smiju više naizmjenično mijenjati nijanse
