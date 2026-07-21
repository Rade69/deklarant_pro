# Faktura — završno poravnanje toolbara

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- Grana `codex/faktura-toolbar-razmaci`
- Worktree `.worktrees/codex-faktura-toolbar`
- `gui/tabs/faktura_view.py`

## GitNexus impact

Impact za `apply_display_profile` i `_populate_grid_sections` je LOW. Prva metoda
nema pronađenih upstream pozivalaca, a druga ima jednog direktnog pozivaoca, tri
povezana simbola, jedan modul i nijedan pogođeni izvršni proces. GitNexus MCP je
vezan za glavni worktree i zato staged diff posebnog worktree-a nije detektovao.

## Šta je urađeno

- Sadržaj svih toolbar grupa vertikalno je centriran.
- Akcijska dugmad imaju jedinstvenu visinu: 32 px u compact i 36 px u standard profilu.
- Display profil više ne prepisuje boju oznaka Bruto/Neto crnom bojom.
- Oznake Bruto/Neto ostaju desno poravnate uz brojčana polja.
- Donji rub zaglavlja ostaje ujednačen sa prethodno odabranom paletom.

## Zašto je urađeno

Različite prirodne visine dugmadi i panela masa davale su neujednačenu osnovnu liniju.
Display profil je dodatno poništavao dio prethodno uvedenog stila panela masa.

## Kako je urađeno

Izmjena je ograničena na postojeće layout i display-profile postavke. Nisu dodavani
widgeti niti mijenjane širine toolbar sekcija.

## Šta nije dirano

- Redoslijed, tekst i funkcija dugmadi.
- Širine toolbar grupa i glavni grid.
- Signali, poslovna logika, tabela i statusna traka.
- `dist_client`, frozen build i ostali tabovi.
- Četiri generisana `.ui.py` fajla označena zbog line-ending razlike u worktree-u.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py` — prolazi.
- Četiri ciljana Faktura test fajla — 37 passed.
- `git diff --check` — bez grešaka.
- Staged diff — samo `gui/tabs/faktura_view.py`, 5 dodatih i 3 izmijenjene linije.

## Pronađeni problemi

Checkout posebnog worktree-a označio je četiri generisana `.ui.py` fajla zbog CRLF/LF
razlike. Nisu staged niti uključeni u commit.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `9a5f232` | `style(faktura): ujednači razmake i visinu toolbar dugmadi` |

## Rizici / ograničenja

Grana je odvojena od `windows` i promjena još nije spojena u glavnu razvojnu granu.
Postojeći frozen build neće je prikazati bez merge-a i rebuilda.

## Potreban follow-up

Nakon korisničke vizuelne potvrde granu treba spojiti u `windows`.

## Potrebna korisnička potvrda

Potvrditi da su dugmad i panel masa sada vertikalno poravnati u stvarnom prozoru.
