# Ispravka naziva pakovanja "PP" — "Komadi" → "Komad" (ASYCUDA brisanje polja)

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `services/naimenovanja/create_naimenovanja_service.py`
- `dist_client/services/naimenovanja/create_naimenovanja_service.py`
- `exporters/asycuda_xml_builder.py`
- `dist_client/exporters/asycuda_xml_builder.py`
- `tests/unit/asycuda_item_limit_test.py`
- `tests/unit/test_asycuda_goods_description.py`

## GitNexus impact
Provjereno PRIJE izmjene:

- `_create_naimenovanje_from_line` — LOW risk, 1 direktan caller
  (`create_one_to_one`).
- `_create_naimenovanje_from_group` — **HIGH risk**: 7 pogođenih simbola,
  2 procesa (`continue_with_pending_declaration` u gui/ i dist_client/,
  `_on_create_naimenovanja`). Korisniku je prijavljen HIGH rizik prije
  izmjene — procjena: izmjena je samo string literal (default vrijednost
  `package_name`), ne mijenja signature/shape `NaimenovanjeDraft`, pa
  nijedan od pogođenih caller-a ne zavisi od konkretne vrijednosti osim
  2 testa (koja su ažurirana u istom commitu). Korisnik je potvrdio uzrok
  ("U pravu si u ASYCUDA aplikaciji je 'Komad'") i implicitno odobrio fix.

`gitnexus_detect_changes(scope="unstaged")` PRIJE commita: `risk_level:
"medium"`, 1 affected process (`create_one_to_one → _get_conn`, changed
step `_create_naimenovanje_from_line`, step 2). Detect_changes je takođe
prikazao NEPOVEZANE unstaged izmjene (AGENTS.md, CLAUDE.md,
gui/tabs/zaglavlje_view.py i dist_client mirroi) koje su PRETHODILE ovoj
sesiji — isključene iz commita (vidi "Šta nije dirano").

## Šta je urađeno
Svuda zamijenjeno `"Komadi"` (množina) → `"Komad"` (jednina) za naziv
pakovanja sa šifrom "PP":

1. `create_naimenovanja_service.py` (gui+dist_client): default
   `package_name='Komad'` u `_create_naimenovanje_from_line` (linija ~335)
   i `_create_naimenovanje_from_group` (linija ~403).
2. `asycuda_xml_builder.py` (gui+dist_client): fallback
   `item.package_name or "Komad"` (linija ~812).
3. `tests/unit/asycuda_item_limit_test.py`: test
   `test_created_naimenovanja_default_to_pp_komadi_packaging` →
   `test_created_naimenovanja_default_to_pp_komad_packaging`, asercija
   `{"Komadi"}` → `{"Komad"}`.
4. `tests/unit/test_asycuda_goods_description.py`: test
   `test_export_defaults_empty_package_type_to_pp_komadi` →
   `test_export_defaults_empty_package_type_to_pp_komad`, asercija
   `"Komadi"` → `"Komad"`.

## Zašto je urađeno
Korisnik je prijavio: ASYCUDA XML generisan u aplikaciji ima
`<Kind_of_packages_code>PP</Kind_of_packages_code>` /
`<Kind_of_packages_name>Komad(i)</Kind_of_packages_name>` po stavci, ali
nakon uvoza/provjere/snimanja u ASYCUDA World-u, ova dva polja se izbrišu
(postanu `<null/>`) za većinu stavki.

Root cause: šifarnik `catalogs.pakovanja` (356 šifara, sinhronizovan sa
ASYCUDA referencama) ima za šifru "PP" JEDINI ispravan opis "Komad"
(jednina) — naziv "Komadi" (množina) ne postoji ni za jednu šifru u tom
šifarniku. `create_naimenovanja_service.py` je za SVAKO novo naimenovanje
hardkodirano postavljao `package_code='PP', package_name='Komadi'`.

Korisnik je dostavio stvarni round-trip XML (MASTER1812, 50 stavki) — fajl
nakon "provjeri + snimi" u ASYCUDA World-u. Tačno 2 od 50 stavki su
ZADRŽALE `Kind_of_packages_code=PP`/`Kind_of_packages_name=Komad`
(jednina); to su stavke kod kojih je korisnik RUČNO ponovo izabrao "PP" iz
padajuće liste u Naimenovanja tabu (čime se naziv auto-popuni iz baze =
"Komad"). Svih ostalih 48 stavki (default "PP"/"Komadi") imale su OBA
polja `<null/>` nakon round-trip-a.

Hipoteza: ASYCUDA pri provjeri/snimanju validira par (kod, naziv) pakovanja
protiv svog internog šifarnika. Par "PP/Komad" postoji → ostaje. Par
"PP/Komadi" ne postoji → ASYCUDA briše OBA polja za tu stavku. Korisnik je
potvrdio: "U pravu si u ASYCUDA aplikaciji je 'Komad'".

## Kako je urađeno
Mehanička zamjena string literala na 6 mjesta (4 izvorna fajla + 2 testa).
Nema promjene signature-a, tipova ni strukture `NaimenovanjeDraft` —
isključivo vrijednost default stringa za `package_name`.

## Šta nije dirano
- `package_code='PP'` — šifra ostaje ista, ona JE ispravna (DB potvrđuje
  `sifra='PP', opis='Komad'`).
- `catalogs.pakovanja` šifarnik — nije mijenjan, samo korišten kao dokaz.
- Nepovezane unstaged izmjene zatečene u radnom stablu prije ove sesije:
  `AGENTS.md`, `CLAUDE.md`, `gui/tabs/zaglavlje_view.py` i
  `dist_client/gui/tabs/zaglavlje_view.py` (IspravaDelegate) — NISU
  staged-ovane niti commit-ovane u ovom zadatku, ostaju kao WIP korisnika.
- `client.log.lck` i ostali untracked fajlovi iz git statusa — nepovezani.

## Verifikacija
- `python -m py_compile` na svih 6 izmijenjenih fajlova — OK.
- `pytest tests/unit/asycuda_item_limit_test.py
  tests/unit/test_asycuda_goods_description.py -q` → **38 passed**.

## Pronađeni problemi
Nema lažno pozitivnih nalaza. Grep za `Komadi` u cijelom repou nakon izmjene
→ 0 rezultata (sve referentne tačke su pokrivene).

## Commitovi
| Hash | Poruka |
|------|--------|
| `20c5085` | `fix(asycuda): ispravi naziv pakovanja PP - "Komadi" -> "Komad"` |

## Rizici / ograničenja
- Ovo mijenja DEFAULT vrijednost za SVA buduća naimenovanja (svi novi
  proizvodi će dobiti `package_name="Komad"` umjesto `"Komadi"`) —
  namjeravana posljedica fixa, ne nuspojava.
- ASYCUDA-ino ponašanje (brisanje `Kind_of_packages_*` za nepoznate
  parove kod/naziv) je pretpostavka izvedena iz jednog round-trip XML
  primjera (50 stavki, 2 sa "Komad" sačuvano, 48 sa "Komadi" izbrisano) —
  nije direktno testirano automatizovano (ASYCUDA je eksterna desktop
  aplikacija).

## Potreban follow-up
- Generisati NOVU deklaraciju (nakon ovog fixa) i provjeriti u ASYCUDA
  World-u (uvoz → provjeri → snimi) da SVE stavke sada zadržavaju
  "PP - Komad" (ne samo ručno dodirnute).

## Potrebna korisnička potvrda
1. Pri sljedećem uvozu nove deklaracije u ASYCUDA World, provjeriti da
   `Kind_of_packages_code`/`Kind_of_packages_name` ostaju "PP"/"Komad" za
   SVE stavke nakon "provjeri + snimi" (ne samo za ručno izmijenjene).
2. Ako neke stavke i dalje gube vrijednost — provjeriti da li te stavke
   imaju neku DRUGU šifru pakovanja (ne "PP") koja možda nije validna u
   ASYCUDA šifarniku.
