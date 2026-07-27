# Ispravka prikaza automatizacije i arhitekture

## Datum

2026-07-27

## Agent

Codex

## Scope

- `gui/tabs/agent/widgets/upload_area.py`
- `services/admin/admin_service.py`
- odgovarajuće `dist_client` kopije
- ciljani regresioni testovi

## GitNexus impact

- `ModeCard.set_selected`: LOW, 2 pogođena simbola, 0 procesa.
- `AdminService.get_system_info`: LOW, 0 pronađenih upstream zavisnosti i
  0 procesa.
- Završni `detect_changes(all)`: LOW, 0 pogođenih procesa. Izlaz uključuje i
  ranije nepovezane izmjene drugih agenata; one nisu uključene u ovaj commit.

## Šta je urađeno

- Selektovana kartica više ne dodaje znak `✓` u naslov.
- Status izbora i dalje je jasno vidljiv kroz postojeći plavi okvir i pozadinu.
- Sirovi Windows naziv `AMD64` normalizovan je u korisnički razumljiv
  `64-bit (x86-64)`.
- Kada Windows pouzdano prijavi proizvođača, prikazuje se i `Intel` ili `AMD`.
- Dodana su četiri regresiona testa.

## Zašto je urađeno

Dodavanje znaka `✓` povećavalo je širinu naslova „Puna automatizacija“,
mijenjalo prelamanje i dovodilo do vertikalnog rezanja teksta u kartici.

`AMD64` je tehnički ispravan naziv x86-64 arhitekture koji Windows/Python
vraća i na Intel procesorima, ali korisniku izgleda kao pogrešno prepoznat
proizvođač. Prikaz je zato odvojen na arhitekturu i detektovanog proizvođača.

## Kako je urađeno

- `ModeCard.set_selected()` uvijek zadržava originalni naslov.
- `format_architecture()` normalizuje x86, x86-64 i ARM nazive i koristi
  `platform.processor()`/`PROCESSOR_IDENTIFIER` samo za vendor oznaku.
- `AdminService.get_system_info()` koristi normalizovanu vrijednost.
- Root i `dist_client` implementacije su identično izmijenjene.

## Šta nije dirano

- Logika pokretanja pune automatizacije.
- Tekst opisa kartice i dimenzije drugih kartica.
- Hardverski fingerprint licenciranja.
- Postojeće izmjene u `docs/CONTEXT.md`, `admin_view.py` i generisanim
  `ui/` fajlovima.

## Verifikacija

- Nova četiri testa: prolaze.
- `tests/unit/test_puna_auto_pipeline.py`: 10 testova prolazi.
- `tests/admin/test_admin_e2e.py`: 16 testova prolazi kada se pokrene odvojeno.
- Puni suite: `1300 passed, 72 skipped, 5 xfailed`.
- Stvarni rezultat na korisnikovom računaru:
  `64-bit (x86-64, Intel)`.

## Pronađeni problemi

Zajedničko pokretanje novog Qt testa i starog admin E2E fajla u jednom
ciljanom pytest procesu izaziva fixture konflikt: stari E2E fixture pokušava
kreirati drugi `QApplication` singleton. Odvojeno pokretanje admin fajla i
puni standardni suite prolaze; nije pronađen aplikacijski kvar.

## Konflikti / kontradiktorni izvori

Nema konflikta u kodu. Korisnička pretpostavka da `AMD64` znači AMD procesor
nije tehnički tačna, ali je UI oznaka opravdano zbunjujuća i zato je
normalizovana.

## Commitovi

Popunjava se Git historijom ovog zadatka.

## Rizici / ograničenja

Na sistemima koji ne prijave pouzdan vendor prikazaće se samo neutralno
`64-bit (x86-64)`, što je namjerno preciznije od nagađanja.

## Potreban follow-up

Nakon sljedećeg Windows builda vizuelno potvrditi karticu na stvarnom DPI
skaliranju korisničkog računara.

## Potrebna korisnička potvrda

Potvrditi da naslov nakon novog builda više nije odrezan i da Sistemske
informacije prikazuju `64-bit (x86-64, Intel)`.
