# Agent Report: Usklađivanje Bruto/Neto labela u toolbar-u Faktura taba

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je poslao screenshot toolbar-a Faktura taba na kojem se vidi da labela
"Bruto:" ima vidno manji font i drugačiji raspored od labele "Neto:" — tekst i
polja se ne poravnavaju.

## Kako je urađeno

Poređenjem `dist_client/gui/tabs/faktura_view.py` (Windows runtime, koji aplikacija
stvarno učitava) sa referentnom `gui/tabs/faktura_view.py` (dev/Linux verzija)
pronađena je razlika u inline stilizaciji unutar `_populate_toolbar_section`:

| Labela | dist_client (prije) | gui/ (referenca) |
|--------|---------------------|------------------|
| `bruto_label` | `setFixedWidth(42)`, `font-size: 12px` | `setFixedWidth(50)`, `font-size: 14px` |
| `neto_label` | `setFixedWidth(50)`, `font-size: 14px` | `setFixedWidth(50)`, `font-size: 14px` |

`bruto_label` u `dist_client` je ostao na starim vrijednostima (vjerovatno iz ranije
verzije prije nego što je `gui/` ažuriran), dok je `neto_label` već uskladjen — otud
vizuelna asimetrija.

Izmijenjen je samo `dist_client/gui/tabs/faktura_view.py` (linije ~488-491), uskladivši
`bruto_label` sa `neto_label` i sa `gui/` referencom: `setFixedWidth(50)`,
`"color: #222; font-size: 14px; font-weight: bold;"`.

`gitnexus_detect_changes()` potvrdio je da su pogođeni samo `FakturaView` i
`_populate_toolbar_section` (uz nepovezane, već postojeće izmjene u `xml_importer.py`
i dokumentacionim fajlovima) — rizik **LOW**, 0 zahvaćenih procesa.

## Zašto

`dist_client/` je odvojena runtime kopija koja se ručno portuje iz `gui/` (dev/Linux)
verzije — pri ranijem portovanju `bruto_label` nije dobio isto ažuriranje stila kao
`neto_label`, pa su dvije labele u istom redu ostale vizuelno neusklađene. Popravka
sinhronizuje vrijednosti tako da toolbar izgleda konzistentno, kako je i dizajnirano
u `gui/` verziji.

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `e64dfa4` | fix | Uskladi font i širinu Bruto labele sa Neto u toolbar-u Faktura taba |

---

## Napomena za buduće sesije

Vizuelni problemi prijavljeni za Windows klijenta često su posljedica drift-a između
`gui/` (dev/Linux izvor) i `dist_client/` (Windows runtime kopija) — vidi
[[feedback-windows-patterns]] za opšti pattern provjere.
