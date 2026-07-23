## Datum

2026-07-23

## Agent

OpenAI Codex

## Scope

Glavne kartice, Faktura, Naimenovanja, Zaglavlje i Šifrarnici u root i `dist_client` GUI sloju.

## Status izvora

Aktivni kod i `docs/CONTEXT.md` tretirani su kao važeći. Necommitovane izmjene u projektnim instrukcijama i generisanim UI fajlovima nisu dio zadatka.

## GitNexus impact

Impact za `MainWindow.__init__`, `NaimenovanjaView.keyPressEvent`, `_setup_shortcuts` i `_setup_tab_order` je LOW, sa najviše jednim direktnim pozivaocem. Završni `detect_changes` je zbog cijelog prljavog worktreeja prijavio nepovezan CRITICAL rezultat; staged scope je ručno potvrđen na 12 fajlova zadatka.

## Šta je urađeno

- Dodani `Ctrl+1`–`Ctrl+6` za direktno otvaranje svih glavnih kartica.
- Faktura, Naimenovanja i Šifrarnici koriste `Alt+Left/Right` i `Alt+A/D` za prethodni/sljedeći zapis.
- Faktura dobija `Ctrl+N`; postojeći undo/redo ostaje netaknut.
- Naimenovanja koriste stvarne `QShortcut` objekte za postojeće CRUD kombinacije i navigaciju.
- Zaglavlje dobija eksplicitan Tab fokusni lanac, `Ctrl+N` i `Ctrl+S`.
- Tooltipovi prikazuju dostupne kombinacije.

## Zašto je urađeno

Kartice su imale različite, djelimično skrivene prečice. Standardizacija smanjuje potrebu za mišem, ali namjerno ne presreće obične strelice ni `W/A/S/D`, jer su potrebni za tekst, tabele i combo polja.

## Kako je urađeno

Korišteni su lokalni Qt `QShortcut` objekti vezani za odgovarajući tab i centralni shortcuti samo za izbor glavne kartice. Zaglavlje gradi fokusni lanac iz postojećeg `field_widgets` registra.

## Šta nije dirano

Poslovna logika, podaci, validacija, baze, modalno ponašanje, layout, generisani UI fajlovi i postojeće tuđe izmjene.

## Verifikacija

- `py_compile` za 10 izmijenjenih runtime Python fajlova: prošao.
- `pytest` za tastaturnu navigaciju, inline validaciju i Faktura selekciju: 12/12 prošlo.
- `git diff --check`: prošao.
- Testovi potvrđuju šest direktnih tab prečica, ograničeno kretanje redovima Fakture i redoslijed fokusa Zaglavlja.

## Pronađeni problemi

GitNexus `detect_changes` i dalje uključuje nepovezane simbole iz prljavog worktreeja i nije pouzdan za završni scope bez staged git provjere.

## Konflikti / kontradiktorni izvori

GitNexus CRITICAL nije odgovarao stvarnom staged diffu. `git diff --cached --name-only` tretiran je kao važeći izvor scope-a. Korisnička potvrda nije potrebna.

## Commitovi

| Hash | Poruka |
|---|---|
| `cc49ba4` | `feat(gui): standardizuj tastaturnu navigaciju` |

## Rizici / ograničenja

`Alt+A/D` radi samo na karticama koje imaju stvarni prethodni/sljedeći zapis. Na Zaglavlju, Adminu i Agentu nema izmišljenog pojma zapisa; tamo ostaju globalne kartične i standardne Tab prečice.

## Potreban follow-up

Ručno provjeriti kombinacije u stvarnom Windows prozoru i utvrditi da li korisnik želi mali ekran sa spiskom svih prečica.

## Potrebna korisnička potvrda

Provjeriti da `Alt+A/D` ne ulazi u unos teksta i da Tab redoslijed Zaglavlja prati očekivani radni tok.
