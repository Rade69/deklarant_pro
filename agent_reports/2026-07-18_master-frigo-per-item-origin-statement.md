# Agent Report — 2026-07-18: Master Frigo per-item has_origin_statement

## Datum
2026-07-18

## Agent
Claude Sonnet 4.6

## Scope
- `importers/vendors/master_frigo/master_frigo_importer.py` + dist_client mirror

---

## GitNexus impact
`detect_changes` rizik: **LOW**, nula pogođenih procesa. Sve promjene su unutar privatnih funkcija jednog importera.

---

## Šta je urađeno

1. **`ImportedLine` dataclass** — dodano `has_origin_statement: bool = False` polje (između `preferential` i `serials`)
2. **`_apply_origin_from_text`** — refaktorisan da po svakoj stavci odredi `pref` iz raspona NEOVISNO od toga da li stavka ima origin iz Excel mappinga. Postavlja `item.has_origin_statement = pref` za sve stavke.
3. **`convert_to_invoice_lines`** — dodano `has_origin_statement=item.has_origin_statement` u `InvoiceLine(...)` konstruktor.
4. **`import_master_frigo`** — dodan fallback: ako nema `zemlja_porekla_data` (per-item parsing nije uspio) ali globalni `has_origin_statement=True`, sve stavke dobivaju `True`.

---

## Zašto je urađeno

Master Frigo fakture imaju tekst poput:
> "Zemlja porekla Srbija, osim stavke broj 43-46 Zemlja porekla Srbija bez pref. porekla i stavke broj 47 - Zemlja porekla Francuska bez pref. porekla."

`_parse_zemlja_porekla_text()` je već ispravno parsirala ove raspone (`pref=False` za 43-47). Međutim, `_apply_origin_from_text` nije postavljala `has_origin_statement` per-item — sve stavke dobivale su isti globalni `header["has_origin_statement"]=True`. Posljedica: PE2/EUR.1 dijalogu prikazivao stavke 43-47 sa povlasticom, iako su eksplicitno "bez pref".

Isti pattern fiksiran ranije za Medicopharm (commit `859083e`) — PE2/EUR.1 dijalozi poštuju per-item flag ako je ikoja stavka `True`.

---

## Kako je urađeno

`_apply_origin_from_text` refaktorisan u dvije faze po stavci:
1. Određi `pref` iz raspona (za SVE stavke, uključujući one s Excel mapping originom)
2. Ako nema Excel mapping origina: dodijeli origin iz teksta
3. Postavi `item.has_origin_statement = pref`

Ovo je backward-compatible: stavke bez `zemlja_porekla_data` imaju `has_origin_statement=False` (default) i globalni fallback u `import_master_frigo` ih pokriva.

---

## Šta nije dirano

- `_parse_zemlja_porekla_text` — logika parsiranja raspona je ispravna, nije mijenjana
- `_detect_all_origin_statements` — globalna detekcija nepromjenjena
- `PE2QuickDialog` / `EUR1QuickDialog` — downstream logika filtriranja već ispravna (commit `859083e`)
- Blagić Loren parser — već ima per-item tracking (`_extract_statement_item_numbers`), nije trebao izmjenu

---

## Verifikacija

- `py_compile` provjera oba fajla: OK
- GitNexus `detect_changes`: LOW rizik, 0 pogođenih procesa
- Logička verifikacija: za stavke 43-46 `pref=False` → `has_origin_statement=False` → PE2/EUR.1 dijalozi ih filtriraju van

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `c9f4125` | feat(import): Master Frigo per-item has_origin_statement iz zemlja_porekla_data |

---

## Rizici / ograničenja

- Stavke s Excel mapping originom koje padaju u "bez pref" raspon sada dobivaju `has_origin_statement=False`. Ovo je ispravno ponašanje — ali ako mapping i tekst nisu konzistentni, može doći do false negative. Vjerovatnoća: niska (mapping i tekst obično opisuju iste raspone).
- Ako `zemlja_porekla_data` ima prazan `ranges` (samo `default_origin`): sve stavke dobivaju `pref=True` → `has_origin_statement=True`. Ispravno.

---

## Potrebna korisnička potvrda

- Uvesti Master Frigo fakturu s "bez pref" stavkama i u PE2 dijalogu provjeriti da te stavke ne dobivaju povlasticu
