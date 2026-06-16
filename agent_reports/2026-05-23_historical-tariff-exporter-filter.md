# Agent Report: Filtriranje historijskih tarifarnih prijedloga po izvozniku

**Datum:** 2026-05-23  
**Commit:** a034fc7

---

## Problem

Sistem za historijsku validaciju tarifnih brojeva (`HistoricalTariffSearchService`) predlagao je tarifne brojeve iz deklaracija BILO KOJEG dobavljača iz baze znanja — ne samo od izvoznika sa trenutne fakture. To je dovodilo do pogrešnih prijedloga jer različite firme mogu imati istu ključnu riječ u opisu robe ali sasvim različite tarifne klasifikacije.

Korisnik: _"dešavalo da mi predlaže tarifne brojeve firmi koje ne uvoze ili koje ne proizvode ili prodaju te proizvode"_

## Uzrok

`_execute()` metoda koristila je `izvoznik` samo za `ORDER BY` boost (nije filtrisala WHERE clausom). Rezultat: prijedlozi su dolazili od svih firmi u bazi, sortirani po `usage_count DESC`.

```python
# Staro — izvoznik je samo ORDER BY hint, ne filter
sql = "... ORDER BY (supplier ILIKE %s) DESC, usage_count DESC"
```

## Rješenje

Kada je izvoznik fakture poznat, prijedlozi dolaze **ISKLJUČIVO** iz historije tog izvoznika:

1. **`_supplier_key(izvoznik)`** — extraktuje prvu značajnu riječ iz naziva (min 3 slova, preskače doo/ltd/gmbh/itd). Primjer: `"MEDICO PHARM SERVIS"` → `"MEDICO"`

2. **`_execute(..., supplier_key)`** — dodaje `AND supplier ILIKE %s` u WHERE kad je `supplier_key` poznat (hard filter, ne ORDER BY)

3. **Nema fallback na druge izvoznike** — ako nema rezultata za tog izvoznika, vraća praznu listu. Bolje bez prijedloga nego pogrešan prijedlog od druge firme.

4. **`_to_matches(..., supplier_matched)`** — propagira flag do `TariffHistoryMatch.supplier_match`

```python
# Novo — strogi filter samo na istog izvoznika
if supplier_key:
    extra_where = " AND supplier ILIKE %s"
    extra_params.append(f"%{supplier_key}%")
    # ORDER BY boost uklonjen — filter je u WHERE
```

## Dizajnerska odluka

Nepoznat izvoznik (prazan naziv) → staro ponašanje, pretraži sve. Poznat izvoznik → samo on. Nema "soft" prelaza između ova dva moda — jasna granica smanjuje kompleksnost.

## Fajlovi izmijenjeni

| Fajl | Promjena |
|------|----------|
| `services/agent/validation/historical_tariff_search_service.py` | `_supplier_key()` nova metoda, `_search_one()` stricter path, `_execute()` WHERE filter, `_to_matches()` supplier_matched param |

## Commitovi

| Hash | Opis |
|------|------|
| `a034fc7` | feat(validation): filtriraj historijske tarife isključivo po izvozniku |
