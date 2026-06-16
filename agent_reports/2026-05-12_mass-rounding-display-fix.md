# Fix: zaokruživanje masa po prikazu Faktura tabele — Agent Report

**Datum:** 2026-05-12  
**Commit:** 95b17a3

---

## Problem

Per-invoice raspodjela težina je interno čuvala zbir na 3 decimale, ali Faktura
tabela prikazuje mase na 2 decimale. Zbog toga je korisnik na fakturi `2601019`
vidio bruto stavke:

```text
1,33 + 1,33 + 1,33 + 2,00 + 1,33 + 10,00 + 2,67 = 19,99
```

iako je interna suma bila `20,000`.

---

## Fix

`services/faktura/mass_calculator.py` sada:

- zaokružuje izračunate mase na 2 decimale (`MASS_DECIMALS = 2`),
- poslije raspodjele računa mali ostatak zaokruživanja,
- ostatak dodaje/oduzima jednoj obračunatoj stavci,
- korekciju radi samo kada su sve stavke grupe bile predmet obračuna,
- ne dira djelimično popunjene težine.

Za fakturu `2601019` rezultat je sada:

```text
1,33 + 1,33 + 1,33 + 2,00 + 1,33 + 10,00 + 2,68 = 20,00
```

Neto ostaje:

```text
1,20 + 1,20 + 1,20 + 1,80 + 1,20 + 9,00 + 2,40 = 18,00
```

---

## Zašto nije popravljeno samo u toolbar-u

Toolbar bi mogao prikazati `20,00`, ali korisnik bi i dalje u tabeli vidio
stavke koje ručno sabiraju `19,99`. Zato je korekcija urađena u centralnom
`MassCalculator`, na istoj preciznosti koju prikazuje Faktura tabela.

---

## Provjera na realnim fajlovima

Putanja:

```text
/home/radovan/Desktop/deklarant_pro/najavauvoza/MASTER-12-5/najavauvoza
```

Rezultat poslije raspodjele:

| Faktura | Bruto faktura | Neto faktura | Bruto zbir stavki | Neto zbir stavki |
|---------|---------------|--------------|-------------------|------------------|
| 2601017 | 1994.00 | 1780.00 | 1994.00 | 1780.00 |
| 2601018 | 1048.00 | 936.00 | 1048.00 | 936.00 |
| 2601019 | 20.00 | 18.00 | 20.00 | 18.00 |
| **TOTAL** | **3062.00** | **2734.00** | **3062.00** | **2734.00** |

---

## Testovi

- `python -m pytest tests/unit/test_mass_calculator.py tests/unit/test_weight_guards.py -q`
  - 21 passed
- `python -m pytest tests -q -k "mass or weight or invoice"`
  - 37 passed, 1 skipped
- `python -m pytest tests/ -q`
  - 323 passed, 6 skipped

GitNexus:

- impact za `MassCalculator.calculate_masses`: MEDIUM prije izmjene
- `detect_changes`: low risk poslije izmjene

---

## Tabela commitova

| Hash | Opis |
|------|------|
| 95b17a3 | fix(weight): uskladi zaokruzenje masa sa prikazom u fakturi |
