# Faktura toolbar — prazan prostor iznad sekcija

## Datum

2026-06-14

## Agent

Claude Sonnet 4.6 (Claude Code)

## Scope

- `gui/tabs/faktura_view.py` + `dist_client/gui/tabs/faktura_view.py`
  (`FakturaView._setup_ui`)

## GitNexus impact

`gitnexus_impact(target="_setup_ui", direction="upstream",
target_uid="Method:gui/tabs/faktura_view.py:FakturaView._setup_ui#0")` →
**risk: LOW**, jedini poziv iz `FakturaView.__init__`, 0 pogođenih
procesa.

`gitnexus_detect_changes(scope="unstaged")` PRIJE commita: `risk_level:
"low"`, `affected_count: 0`, `affected_processes: []`.

## Šta je urađeno

Korisnik je poslao screenshot trake glavnih tabova + Faktura toolbar
sekcija i javio: "Ima osjećaj da ima previše prostora između tab dugmadi i
naziva blokova toolbara (Glavna lista, Uvezi ... itd)".

`gui/tabs/faktura_view.py` i `dist_client/gui/tabs/faktura_view.py`
(`_setup_ui`): glavni `QVBoxLayout`-ov `setContentsMargins(12, 12, 12,
12)` promijenjen u `setContentsMargins(12, 4, 12, 12)` — gornja margina
smanjena za 8px, lijeva/desna/donja nepromijenjene.

## Zašto je urađeno

**Provjera hipoteze**: razmak između trake tabova i `controlsContainer`
grida (header dugmići "Glavna lista"/"Uvezi"/"Uredi"/"Izvezi"/"Pametna
pomoć", grid margins/spacing = 0 → naslanjaju se direktno na vrh
containera) potiče ISKLJUČIVO od gornje margine glavnog `QVBoxLayout`-a
(`FakturaView._setup_ui`). `QTabWidget::pane` od `e5ca8bc`/`d84af78` nema
`border-top`, pa nema dodatne linije/border-a koji bi "apsorbovao" taj
razmak — sav prostor iznad header reda je čista margina iz koda.

Offscreen mjerenje (replika `controlsContainer`-a sa pravim kombinovanim
QSS-om iz `load_stylesheet()`, 11 fajlova, `displayProfile="compact"`,
1536x816) je potvrdilo **linearnu** vezu: top margin 12px → razmak 18px,
6px → 12px, 4px → 10px (apsolutne vrijednosti u offscreen aproksimaciji se
razlikuju od stvarnog Windows renderovanja, ali delta je 1:1 s promjenom
margine).

## Kako je urađeno

Jednolinijska izmjena u `_setup_ui` (gui/ linija 252, dist_client/ linija
250) — `setContentsMargins(12, 12, 12, 12)` → `setContentsMargins(12, 4,
12, 12)`. Lijeva/desna margina (12px, razmak od ivica prozora) i donja
margina (12px, razmak prema statusnoj traci/tabeli ispod) nepromijenjene
— dirana je samo gornja vrijednost.

## Šta nije dirano

- `controlsContainer` grid (`_create_controls_section`,
  `_populate_grid_sections`) — margins/spacing = 0, nepromijenjeno.
- `main_tabs.qss` / `QTabWidget::pane` — nepromijenjeno (fix iz
  `e5ca8bc`/`d84af78` ostaje).
- Razmak između toolbar sekcija i tabele ispod (`main_layout.setSpacing(12)`)
  — nepromijenjen.
- Ostali tabovi (Naimenovanja, Zaglavlje, Šifrarnici, Admin, Agent) — imaju
  svoje vlastite layout-e, nisu dirani (van scope-a, korisnikov screenshot
  je bio specifično za Faktura tab).

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py
  dist_client/gui/tabs/faktura_view.py` → OK.
- Offscreen render (privremeni `_tmp_diag5.py`/`_tmp_diag5b.py` +
  `_tmp_crop5*.png`, obrisani nakon provjere) — replika
  `controlsContainer`-a (5 sekcija: Glavna lista/Uvezi/Uredi/Izvezi/Pametna
  pomoć, iste boje i `border-bottom` kao u `_populate_grid_sections`) sa
  pravim kombinovanim QSS-om, poređenje top margina 12px / 6px / 4px —
  potvrđeno smanjenje razmaka pri manjoj margini, bez promjene rasporeda
  ili preklapanja sadržaja.

## Pronađeni problemi

- Offscreen render ne replicira potpuno Windows/Segoe UI geometriju
  `QTabWidget::pane`-a (vidi i prethodnu napomenu o "Š" fallback artefaktu
  u `2026-06-14_tabovi-donji-rub-izlaz-dugme.md`) — apsolutni razmak na
  stvarnom ekranu može se razlikovati od offscreen mjerenih 18px/10px, ali
  smjer i veličina promjene (−8px) su pouzdani.

## Commitovi

| Hash      | Poruka                                                                  |
|-----------|-------------------------------------------------------------------------|
| `759c4cf` | `fix(gui): smanji prazan prostor iznad toolbar sekcija na Faktura tabu` |

## Rizici / ograničenja

- Asimetrične margine (top=4px, left/right/bottom=12px) su namjeran,
  ciljani fix za ovaj specifični vizuelni problem — nije opšta promjena
  stila.

## Potreban follow-up

- Ako 4px i dalje izgleda kao previše ili premalo prostora na stvarnom
  ekranu, vrijednost je trivijalno podesiva (jedna linija, dva mjesta).

## Potrebna korisnička potvrda

- Pokrenuti aplikaciju na Faktura tabu i vizuelno potvrditi da je razmak
  između trake glavnih tabova i reda "Glavna lista / Uvezi / Uredi /
  Izvezi / Pametna pomoć" sada manji i da je raspored sekcija/dugmadi i
  dalje ispravan (nema preklapanja ili obrezivanja sadržaja).
