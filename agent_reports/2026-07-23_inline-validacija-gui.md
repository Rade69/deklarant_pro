## Datum

2026-07-23

## Agent

OpenAI Codex

## Scope

Faktura, Naimenovanja, Zaglavlje i Šifrarnici GUI validacija u root i `dist_client` runtime kopiji.

## Status izvora

`docs/CONTEXT.md` i aktivni kod tretirani su kao autoritativni. Necommitovane izmjene u `AGENTS.md`, `CLAUDE.md` i generisanim UI fajlovima pripadaju drugom radu i nisu uključene.

## GitNexus impact

`FakturaView._validate_and_color_row`: HIGH, 28 zavisnih simbola i 8 direktnih pozivalaca. `_validate_all_items`, `ZaglavljeController._on_validate` i `SifarniciView._on_snimi`: LOW. Završni `detect_changes` je prijavio CRITICAL za cijeli prljavi worktree i naveo nepovezane/stale simbole; stvarni staged scope ručno je ograničen na 15 eksplicitnih fajlova.

## Šta je urađeno

- Faktura označava samo tarifnu ili zemlja ćeliju kada je problem vezan za to polje.
- Status Naimenovanja je klikabilan, prelazi na prvo neispravno naimenovanje i fokusira/ističe polje.
- Stavke validacije Zaglavlja imaju akciju „Prikaži polje“ koja zatvara modal i fokusira odgovarajući widget.
- Šifrarnici prije postojećeg upozorenja fokusiraju prvo prazno obavezno polje.
- Dodano pet regresionih testova.

## Zašto je urađeno

Korisniku je mjesto greške ranije bilo vidljivo samo kroz cijeli obojeni red, zbirnu statusnu poruku ili modal. Poboljšanje skraćuje put do ispravke bez uklanjanja modalnih provjera i bez zauzimanja dodatnog prostora u gustim obrascima.

## Kako je urađeno

Postojeće validacione rezultate dopunjavaju isključivo View/Controller navigacija, fokus, tooltip i privremeni QSS rub. Poslovna pravila i draft modeli nisu mijenjani.

## Šta nije dirano

Validaciona pravila, baze, import/export, draft modeli, generisani UI fajlovi, geometrija tabova i tuđe necommitovane izmjene.

## Verifikacija

- `py_compile` za 12 izmijenjenih runtime Python fajlova: prošao.
- `pytest tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_view_provjeri_selekcija.py -q`: 9/9 prošlo.
- `git diff --check`: prošao.
- Encoding skeniranje ciljnih fajlova: bez novih mojibake znakova.
- Širi `tests/unit` paket: 55 testova prošlo, zatim zaustavljen postojećim nedostatkom SQLite tabele `tarifa_2026` u `test_export_replaces_known_invalid_tariff_code`.

## Pronađeni problemi

GitNexus indeks miješa stvarni worktree diff sa zastarjelim simbolima i nepovezanim fajlovima. Širi test paket u ovom okruženju nema pripremljenu `tarifa_2026` tabelu.

## Konflikti / kontradiktorni izvori

GitNexus završni CRITICAL rezultat nije odgovarao stvarnom staged scope-u. Važećim je tretiran `git diff --cached --name-only`, koji je prije commita pokazao samo fajlove ovog zadatka. Korisnička potvrda nije potrebna.

## Commitovi

| Hash | Poruka |
|---|---|
| `4f3bc4d` | `feat(gui): poveži validaciju sa problematičnim poljima` |

## Rizici / ograničenja

Zaglavlje direktno mapira poznate nazive validacionih polja na widgete. Nova polja koja validator kasnije uvede dobiće jasnu poruku da direktan fokus nije dostupan dok se mapa ne dopuni.

## Potreban follow-up

Vizuelno provjeriti sve četiri kartice u stvarnom Windows prozoru i eventualno fino podesiti nijansu/rub bez promjene funkcionalnosti.

## Potrebna korisnička potvrda

Provjeriti da klik na status Naimenovanja i „Prikaži polje“ u modalu Zaglavlja vode na očekivano polje pri realnoj deklaraciji.
