# Faktura — meni za PDF izvještaje

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- Grana `codex/faktura-toolbar-razmaci`
- Worktree `.worktrees/codex-faktura-toolbar`
- `gui/tabs/faktura_view.py`

## GitNexus impact

Impact za `_populate_toolbar_section` je LOW: jedan direktni pozivalac, tri povezana
simbola, jedan modul i nijedan pogođeni izvršni proces.

## Šta je urađeno

Postojeće dugme `PDF` sada otvara meni sa dvije opcije:

- `Spisak naimenovanja` — postojeći PDF grupisan po naimenovanjima.
- `Pregled po fakturama` — kontrolni PDF grupisan po originalnim fakturama.

Uklonjena je konstrukcija zasebnog nevidljivog dugmeta `Pregled`.

## Zašto je urađeno

Funkcionalnost pregleda po fakturama postojala je i bila povezana sa skrivenim dugmetom,
ali dugme nikada nije dodano u layout. Dodavanje još jednog vidljivog dugmeta preopteretilo
bi već popunjenu sekciju `Izvezi`, pa su obje PDF funkcije objedinjene u jedan meni.

## Kako je urađeno

Na postojeći `btn_export_pdf` postavljen je `QMenu`. Dvije QAction stavke povezane su sa
postojećim handlerima `_on_export_pdf` i `_on_export_pregled_faktura`; export logika nije
mijenjana.

## Šta nije dirano

- Implementacija oba PDF eksportera.
- Excel export, kreiranje naimenovanja i panel masa.
- Širina, raspored i broj vidljivih toolbar dugmadi.
- `dist_client`, frozen build i ostali tabovi.
- Zatečene line-ending izmjene generisanih `.ui.py` fajlova.

## Verifikacija

- Offscreen Qt smoke test — meni sadrži tačno `Spisak naimenovanja` i
  `Pregled po fakturama`.
- `python -m py_compile gui/tabs/faktura_view.py` — prolazi.
- Četiri ciljana Faktura test fajla — 37 passed.
- `git diff --check` — bez grešaka.

## Pronađeni problemi

Potvrđeno je da prethodno `btn_pregled_faktura` nije bilo dodano u layout i zato nije
bilo dostupno korisniku.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `bc00a1a` | `feat(faktura): dodaj izbor PDF izvještaja u meni` |

## Rizici / ograničenja

Promjena je samo na posebnoj grani. Postojeći frozen build neće prikazati meni dok se
grana ne spoji i aplikacija ponovo ne izgradi.

## Potreban follow-up

Vizuelno potvrditi izgled padajućeg menija, zatim spojiti granu u `windows`.

## Potrebna korisnička potvrda

Potvrditi da su nazivi dvije PDF opcije dovoljno jasni u svakodnevnom radu.
