# Faktura — čitljivost glavne tabele

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- `gui/tabs/faktura_view.py`

## GitNexus impact

Impact za `_create_table` je LOW: jedan direktni pozivalac, dva povezana simbola,
jedan modul i nijedan pogođeni izvršni proces. Detect changes je takođe prijavio
LOW rizik i 0 pogođenih procesa.

## Šta je urađeno

- Pojačan kontrast zaglavlja kolona i donje linije zaglavlja.
- Mreža i vanjski okvir tabele učinjeni su jasnijim.
- Uključeno je diskretno alterniranje pozadine običnih redova.
- Selekcija reda je blago zatamnjena radi bolje uočljivosti.

## Zašto je urađeno

Velika tabela treba biti laka za horizontalno praćenje i brzo čitanje, a prethodno
zaglavlje i linije bili su suviše blagi.

## Kako je urađeno

Promijenjene su samo QSS boje u `_create_table` i uključen postojeći Qt mehanizam
`setAlternatingRowColors(True)`. Delegate validacione boje ostaju iznad osnovne
pozadine i nisu mijenjane.

## Šta nije dirano

- Visine redova, širine kolona i raspored tabele.
- Sadržaj ćelija, editovanje i signali.
- Validaciona pravila i njihove boje.
- Toolbar, statusna traka i poslovna logika.
- `dist_client`, frozen build i ostali tabovi.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py` — prolazi.
- Tri ciljana Faktura test fajla — 33 passed.
- `git diff --check` — bez grešaka.
- GitNexus detect changes — LOW, 0 pogođenih procesa.

## Pronađeni problemi

Nisu pronađene funkcionalne regresije.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `ca1f0e5` | `style(faktura): pojačaj čitljivost glavne tabele` |

## Rizici / ograničenja

Kod potpuno validiranih redova validaciona pozadina namjerno nadjačava alterniranje,
pa će pruganje biti vidljivije na običnim ili još nevalidiranim redovima.

## Potreban follow-up

Nema obaveznog tehničkog follow-upa.

## Potrebna korisnička potvrda

Potvrditi da su zaglavlje, mreža i selekcija dovoljno uočljivi na stvarnom monitoru.
