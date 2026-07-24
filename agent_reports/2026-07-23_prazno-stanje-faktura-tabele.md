## Datum

2026-07-23

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`

## GitNexus impact

Impact za source `_InvoiceTableWidget` je MEDIUM: 17 zavisnosti, uglavnom testovi
i uvozi Faktura taba, bez pogođenih izvršnih procesa. Dist klasa je LOW bez
evidentiranih zavisnosti. Završni `detect_changes` prijavio je CRITICAL zbog
nepovezanih izmjena u glavnom checkoutu; commit je zato eksplicitno ograničen
na dva Faktura fajla.

## Šta je urađeno

U praznoj Faktura tabeli prikazuje se centrirana poruka:

`Nema učitanih stavki`

`Učitajte glavnu listu ili fakturu za početak rada.`

Poruka automatski nestaje čim tabela dobije red i vraća se nakon čišćenja.

## Zašto je urađeno

Prazna tabela ranije nije objašnjavala kako započeti rad. Rješenje koristi
postojeću praznu površinu i ne zauzima dodatni prostor u ograničenom layoutu.

## Kako je urađeno

`_InvoiceTableWidget.paintEvent()` nakon standardnog crtanja prikazuje poruku
samo kada je `rowCount() == 0`. Nisu dodavani novi widgeti niti layout elementi.

## Šta nije dirano

- Uvoz i čišćenje faktura.
- Model tabele, redovi, selekcija i signali.
- Toolbar, statusna traka i postojeći modali.
- Razlike koje su već postojale između source i `dist_client` Faktura fajlova.
- Nepovezane izmjene drugih agenata.

## Verifikacija

- `py_compile` za oba izmijenjena fajla: prošao.
- Qt offscreen render prazne tabele: poruka je vidljiva i centrirana.
- Qt offscreen render tabele sa redom: prazna poruka nije prikazana.
- `git diff --check`: prošao.
- Pre-commit `py_compile`: prošao.

## Pronađeni problemi

Offscreen Qt okruženje ne učitava projektni Windows font i na privremenim
snimcima prikazuje zamjenske kvadratiće. Aplikacioni font i tekst nisu mijenjani.

## Konflikti / kontradiktorni izvori

Source i `dist_client` Faktura fajlovi nisu bili identični prije zadatka. Umjesto
kopiranja, isti mali dodatak primijenjen je odvojeno na oba fajla. Korisnička
potvrda za taj pristup nije potrebna.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `a1eb2e7` | `feat(faktura): prikaži uputu u praznoj tabeli` |

## Rizici / ograničenja

Poruka je isključivo vizuelna i nema interaktivne elemente. Potrebna je ručna
provjera izgleda u stvarnom Windows runtime fontu i DPI skaliranju.

## Potreban follow-up

Nema obaveznog tehničkog follow-upa.

## Potrebna korisnička potvrda

Provjeriti veličinu i nijansu teksta u praznoj Faktura tabeli.
