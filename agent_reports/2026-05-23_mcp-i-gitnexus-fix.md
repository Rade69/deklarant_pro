# Agent Report: EUR1 dijalog fix za MEDICOPHARM batch uvoz

**Datum:** 2026-05-23  
**Commit:** be3d475

---

## Problem

Kod batch uvoza MEDICOPHARM faktura, EUR.1 dijalog se nikad nije prikazivao. Korisnik je vidio da "ne prijavljuje sve zemlje porijekla koje su na fakturi."

## Uzrok

Commit 6d502b7 odgodio je EUR.1 dijalog na kraj batch uvoza:

```python
# Stara logika (radilo):
self._show_eur1_dialog()  # odmah za svaku fakturu

# Nova logika (pokvarena):
logger.info("odgađam...")  # defer
# Na kraju:
if self._should_show_eur1_dialog(self.draft.invoice_lines):  # ← vraća False!
    self._show_eur1_dialog()
```

`_should_show_eur1_dialog` vraća `False` kad ijedan item ima `has_origin_statement=True`. MEDICOPHARM parser (`medicopharm-421.pdf`) postavlja `has_origin_statement=True` za sve stavke (nema specifičnih raspona u izjavi → `covered_items` je prazan → svi itemsi dobiju `True`). Rezultat: EUR.1 dijalog se nikad ne prikaže, niti jedna od 7 zemalja (AT, DE, FR, GB, IT, PL, PT) nije pokazana korisniku.

## Rješenje

Vraćena originalna logika u `_import_multiple_files`: kad `_origin_dialog_type` vrati `'eur1'`, dijalog se prikazuje odmah za tu fakturu — stavke su već privremeno u `self.draft.invoice_lines`:

```python
else:
    # EUR.1 — prikaži odmah za ovu fakturu (ne odgađaj)
    logger.info(f"📦 [{invoice_name_file}] → EUR.1 dialog")
    self._show_eur1_dialog()
```

Uz to povećan `maxHeight` tabele u EUR.1 dijalogu sa 300 na 480px — pri 7 zemalja i 48px/redu, 300px pokazuje samo ~5 redova, ostatak je bio van vidnog polja.

## Fajlovi izmijenjeni

| Fajl | Promjena |
|------|----------|
| `gui/tabs/faktura_view.py` | Uklonjen defer EUR.1, vraćen neposredni poziv `_show_eur1_dialog()` |
| `gui/dialogs/eur1_quick_dialog.py` | maxHeight tabele 300→480px |

## Commitovi

| Hash | Opis |
|------|------|
| `be3d475` | fix(eur1): prikaži EUR.1 dialog odmah pri batch uvozu sa izjavom o porijeklu |
