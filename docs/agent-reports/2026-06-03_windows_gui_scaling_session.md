# 2026-06-03 Windows GUI scaling session

## Kontekst

Radjeno je na Windows grani `windows`, u `dist_client`, sa ciljem da Windows GUI bude sto blizi Linux referenci. Glavni fokus je bio Naimenovanja tab, uz ranije manje izmjene na Faktura/Zaglavlje toolbarima i globalnim fontovima.

Terminal u Codex VS Code ekstenziji je tokom sesije prestao raditi sa greskom:

```text
Failed to create unified exec process: spawn setup refresh
```

Zbog toga nije bilo moguce pokretati `git`, `python`, testove, aplikaciju ili citati fajlove kroz shell. Rad je nastavljen preko GitNexus MCP-a, `apply_patch`, korisnickih screenshotova i rucnog pokretanja aplikacije od strane korisnika.

## Dosadasnje GUI izmjene

- `dist_client/run.py`
  - Windows globalni font smanjen na `Segoe UI` 9 pt, Linux ostaje 13 pt.
- `dist_client/gui/main_window.py`
  - Tab font smanjen na `Segoe UI` 9 pt.
- `dist_client/gui/tabs/faktura_view.py`
  - Faktura toolbar/header smanjen.
  - Dugme `Kreiraj Naimenovanja` skraceno u `Kreiraj Naim.`.
  - Bruto label smanjen.
- `dist_client/gui/tabs/zaglavlje_view.py`
  - Uklonjen prethodno dodani scroll area oko glavnog grida.
  - Toolbar visina i margine smanjene.
- `dist_client/gui/tabs/naimenovanja_view.py`
  - Windows scale factor spusten prema `1.00`.
  - Status bar eksplicitno pozicioniran ispod `main_grid_frame`.
  - Gornja navigacija smanjena: nav bar, margine, spacing, combo i dugmad.
  - Section heading smanjen.
  - `Sačuvaj` / `Poništi` dugmad smanjena.
  - Status bar visina i label font/padding smanjeni.
  - Rb.31 package combo dobio dodatni vizuelni trougao i pokusaj sakrivanja Windows kvadrata.

## Trenutno vizuelno stanje

Prema zadnjem screenshotu korisnika:

- Naimenovanja tab je vidno bolji nego na pocetku.
- Status bar se sada vidi.
- I dalje nije potpuno kao Linux.
- Preostale razlike:
  - status bar je jos kandidat za fino podesavanje,
  - Rb.31 dropdown indikator treba provjeriti nakon zadnje izmjene,
  - pozicija/sirina `Sačuvaj` / `Poništi` trake i dalje treba finije uskladjivanje,
  - glavni grid mozda treba jos minimalno sirinsko/visinsko podesavanje, ali oprezno jer sada nije slomljen.

## GitNexus provjere

Uradjene impact provjere su bile LOW za relevantne metode:

- `NaimenovanjaView._apply_ui_scaling`
- `NaimenovanjaView._add_status_bar`
- `NaimenovanjaView._add_navigation_controls`
- `NaimenovanjaView._add_section_heading`
- `NaimenovanjaView._create_icon_button`
- `NaimenovanjaView._setup_package_dropdown`
- `NaimenovanjaView._ArrowCombo`
- relevantne Faktura/Zaglavlje toolbar metode

`detect_changes(scope=all)` javlja `critical`, ali zato sto working tree vec sadrzi veliki broj ranijih lokalnih izmjena, ne zato sto je posljednja Naimenovanja GUI izmjena sama po sebi siroka.

## Sljedeci koraci

1. Napraviti commit trenutnog stanja prije nastavka.
2. Ako terminal u Codexu ostane blokiran, commit uraditi rucno iz VS Code terminala ili Source Control panela.
3. Nakon commita nastaviti samo Naimenovanja fino podesavanje prema Linux screenshotu.

Predlozena commit poruka:

```text
fix(windows): priblizi naimenovanja layout linux izgledu
```
