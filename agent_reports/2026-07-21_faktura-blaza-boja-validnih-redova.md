# Faktura — blaža boja validnih redova

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- `gui/tabs/faktura_view.py`

## GitNexus impact

Pre-change impact za `FakturaView._validate_and_color_row` bio je MEDIUM:
8 direktnih pozivalaca, 28 ukupno povezanih simbola, 2 modula i 0 pogođenih
execution procesa. Staged `gitnexus_detect_changes` prijavio je LOW rizik i
0 pogođenih procesa za jednolinijsku izmjenu.

GitNexus je u staged rezultatu zbog dupliranog source/dist simbola prikazao i
`dist_client/gui/tabs/faktura_view.py`, iako git staged diff potvrđuje da je
izmijenjen isključivo source fajl.

## Šta je urađeno

Pozadina potpuno validnog reda na Faktura tabu promijenjena je iz intenzivne
zelene `#ccffcc` u diskretnu zeleno-sivu `#EAF4EE`.

## Zašto je urađeno

Korisnik je tražio jednu malu vizuelnu izmjenu kao primjer predloženog pravca.
Nova nijansa smanjuje zamor i vizuelnu dominaciju tabele, ali zadržava značenje
da je red validan.

## Kako je urađeno

Promijenjena je samo vrijednost `color_hex` u postojećoj `result.valid` grani
metode `_validate_and_color_row`. Redoslijed validacije, tooltip, delegate,
selekcija i ostala statusna stanja nisu mijenjani.

## Šta nije dirano

- Crvena, žuta, plava i neutralna validaciona stanja.
- Country/preference confidence boje.
- QSS, layout i toolbar Faktura taba.
- `dist_client` kopija i PyInstaller `.exe`.
- Business logika, draft, parseri, servisi i baza.
- Paralelne lokalne izmjene drugih autora.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py` — prolazi.
- `python -m pytest tests/unit/test_faktura_manual_import_sort.py -q` — 1 passed.
- `git diff --check` — bez grešaka.
- Staged GitNexus provjera — LOW, 0 pogođenih procesa.

Vizuelni smoke test nije urađen u trenutno pokrenutom `DeklarantPro.exe` jer je
to frozen artefakt koji ne učitava novu source izmjenu bez rebuilda.

## Pronađeni problemi

Nema funkcionalnih problema. Potvrđeno je da zelena boja sa snimka dolazi iz
programskog validacionog role podatka, a ne iz osnovnog QSS stila tabele.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `dfe4fa2` | `style(faktura): ublaži boju validnih redova` |

## Rizici / ograničenja

Izmjena će biti vidljiva pri pokretanju aplikacije iz source-a. Trenutno
pokrenuti frozen `.exe` neće je prikazati dok se ne napravi novi PyInstaller
build. Blaža boja ima manji kontrast od prethodne, ali tooltip i validaciona
logika ostaju nepromijenjeni.

## Potreban follow-up

Korisnik treba vizuelno potvrditi novu nijansu. Ako je pravac prihvatljiv,
sljedeća mala izmjena može neutralizovati zaglavlje ili osnovne toolbar zone.

## Potrebna korisnička potvrda

Potvrditi da li je `#EAF4EE` dovoljno uočljiva za validan red i prijatnija za
dugotrajan rad od prethodne `#ccffcc`.

