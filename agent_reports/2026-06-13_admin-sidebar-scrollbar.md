# Admin Panel sidebar — uklanjanje nepotrebnog scrollbara

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `gui/tabs/admin/admin_view.py` — `AdminView._create_sidebar()`
- `dist_client/gui/tabs/admin/admin_view.py` — identičan mirror

## GitNexus impact
`mcp__gitnexus__impact` na `AdminView._create_sidebar` (disambiguirano preko
`target_uid="Method:gui/tabs/admin/admin_view.py:AdminView._create_sidebar#0"`):
- **Risk: LOW**
- `impactedCount: 2` (gui/ i dist_client/ varijante metode)
- `affected_processes: 0`

Nakon izmjene, `mcp__gitnexus__detect_changes(scope="staged")` na oba fajla:
`changed_count: 0`, `affected_count: 0`, `risk_level: low` — uklanjanje
jednog poziva (`addStretch()`) ne mijenja signaturu niti graf simbola.

## Šta je urađeno
U `_create_sidebar()` uklonjena linija `layout.addStretch()` koja je dolazila
odmah iza `layout.addWidget(self.nav_list)`, u oba fajla (gui/ i dist_client/).

## Zašto je urađeno
Korisnik je poslao screenshot Admin Panel sidebara sa 7 stavki navigacije
("Upravljanje Parserima", "Baza Podataka", "Analitika", "Logovi", "Sistemske
Informacije", "Licenca", "Učenje iz XML-ova") i vidljivim vertikalnim
scrollbarom, sa porukom: "Ovaj krol bar u admin tabu u side abru je
nepotreban jer ima dovoljno prostora da stanu sve stavke."

**Uzrok**: `QListWidget` (nav_list) ima default size policy
`Expanding/Expanding`. U `QVBoxLayout`-u, kad je iza Expanding widgeta (sa
stretch=0) dodat i `addStretch()` (stretch=0), Qt podijeli dodatni prostor
~50/50 između njih — nav_list je dobijao samo polovinu visine koju mu je
sidebar mogao ponuditi, pa je viewport (306px) bio manji od ukupne visine
7 stavki (350px) i prikazivao se scrollbar — premda je sidebar widget
(689px) imao dovoljno prostora za sve.

Referentni "ispravan" pattern već postoji u `gui/tabs/sifarnici_view.py`
`_create_sidebar()` (komentar u admin_view.py već kaže "stil usklađen sa
Šifrarnici tab") — taj kod dodaje `categories_list` (10 stavki) BEZ
`addStretch()` iza njega. admin_view.py je imao zaostali `addStretch()` koji
nije bio usklađen s tim patternom.

## Kako je urađeno
Jednostavno uklanjanje jedne linije (`layout.addStretch()`) u
`_create_sidebar()`, identično u `gui/tabs/admin/admin_view.py` i
`dist_client/gui/tabs/admin/admin_view.py`. Nema promjene signatura, importa
ni drugih metoda.

## Šta nije dirano
- `gui/main_window.py`, `dist_client/gui/main_window.py` — nepovezan WIP
  (DisplayProfile/window geometry), ostavljen netaknut.
- `gui/tabs/faktura_view.py`, `dist_client/gui/tabs/faktura_view.py` — nepovezan
  WIP (FlowLayout toolbar plan), ostavljen netaknut.
- `gui/utils/display_profile.py`, `dist_client/gui/utils/display_profile.py`,
  `styles/display_profiles.qss`, `dist_client/styles/display_profiles.qss`,
  `tests/unit/test_display_profile.py` — nepovezan WIP, netaknuto.
- `.env` / `dist_client/.env` (DB_HOST promjena iz prethodnog pod-zadatka) —
  gitignored, nije dio ovog commit-a.
- Sadržaj/redoslijed `items` liste (7 nav stavki), stilovi `QListWidget`,
  `_create_content_area`, paneli — nepromijenjeni.

## Verifikacija
Privremena offscreen skripta (`_tmp_admin_sidebar_test.py`, kreirana i
obrisana nakon provjere) — konstruisala `AdminView` sa `QT_QPA_PLATFORM=offscreen`,
resize na 1000x700, i mjerila `nav_list.height()`, `viewport().height()`,
`sizeHintForRow()` sumu i `verticalScrollBar().isVisible()/range`:

| Stanje | nav_list height | viewport height | total_items_h | scrollbar visible | scrollbar range |
|---|---|---|---|---|---|
| PRIJE (sa addStretch) | 322 | 306 | 350 | True | 0-1 |
| POSLIJE (bez addStretch) | 643 | 627 | 350 | False | 0-0 |

`sidebar widget height` = 689 u oba slučaja — potvrđuje korisnikovu tvrdnju
da je prostora bilo dovoljno od početka, samo ga layout nije dodjeljivao
nav_list-i.

`python -m py_compile gui/tabs/admin/admin_view.py dist_client/gui/tabs/admin/admin_view.py`
→ OK (oba fajla).

## Pronađeni problemi
Nema. Hipoteza potvrđena before/after mjerenjem, fix je minimalan i
jednoznačan.

## Commitovi
| Hash | Poruka |
|---|---|
| `c57595b` | `fix(gui): ukloni nepotreban scrollbar u Admin Panel sidebaru` |

## Rizici / ograničenja
Minimalan rizik — uklonjena je jedna linija koja je samo trošila prostor
spacer-om. `nav_list` sada zauzima cijelu preostalu visinu sidebara umjesto
~50%; vizuelno se stavke "rastežu" na cijelu visinu (veći razmak između
zadnje stavke i dna sidebara nema, nav_list ispunjava prostor). Ovo je
namjeravana posljedica (isti pattern kao Šifrarnici tab).

## Potreban follow-up
Nema poznatog follow-upa za ovu izmjenu.

## Potrebna korisnička potvrda
Vizuelna provjera u stvarno pokrenutoj aplikaciji: otvoriti Admin tab i
potvrditi da je scrollbar nestao i da sidebar izgleda kao Šifrarnici tab
(7 stavki popunjavaju visinu bez scrollbara).
