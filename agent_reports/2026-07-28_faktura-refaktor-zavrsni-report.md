# Faktura 3-layer infrastruktura — završni report

## Datum

2026-07-29

## Agent

Pi, završni nezavisni pregled i dopuna: Codex

## Scope

Grana `refactor/faktura-3layer`, composition root, pasivni Controller ugovori,
karakterizacioni testovi i root/`dist_client` paritet. Kanonski plan je
`project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md`.

## Status izvora

- Kanonski detaljni plan: aktivan.
- Raniji naslov „Faze 0–8 završene“: zastario i netačan za produkcioni wiring.
- Postojeći View handleri na `windows`: aktivni autoritativni tok.
- Controller signali: aktivna migraciona infrastruktura, ali pasivni u
  produkcionom toku.

## GitNexus impact

Indeks formalno vraća `LOW`, ali je parcijalan i ne vidi poznate dinamičke
Agent/MainWindow pozivaoce. Ručni impact zato ostaje autoritativna dopuna:
Faktura tab je startup obavezan i koristi ga Puna automatizacija, import,
naimenovanja, mase, validacija i export. Dozvola: `no auto-merge`, obavezni
test gate i ručna Windows potvrda.

## Šta je urađeno

- Uveden je `FakturaController` sa dinamičkim getterom aktivnog drafta.
- Dodani su neutralni result modeli i čiste pomoćne funkcije.
- Dodani su View signali i povezani wrapper handleri.
- Signali nisu automatski emitovani iz starih View handlera, čime se izbjegava
  duplo izvršavanje.
- Validacioni handler poštuje `scope/rows` i koristi `blockSignals`.
- Ispravljeni su startup importi, servisni importi, logger i tarifna
  normalizacija bez nedozvoljenog `zfill`.
- Root i `dist_client` imaju sadržajno isti produkcioni Faktura kod.
- Uključen je najnoviji `windows` vrh sa zvučnim i tarifnim popravkama.

## Zašto je urađeno

Centralni Faktura View ima veliki blast radius. Pasivna infrastruktura omogućava
buduće vertikalne rezove bez promjene postojećeg ponašanja. Aktiviranje signala
na kraju starog View handlera bilo je odbačeno jer validaciju izvršava dvaput i
proizvodi `itemChanged` događaje.

## Kako je urađeno

Composition root kreira Controller, ali vlasništvo aktivnog toka ostaje u View-u
dok pojedinačni rez nema potpuni paritet test. `dist_client` test se izvršava iz
samog `dist_client` direktorija i importuje Controller i Tab kao standalone root.

## Šta nije dirano

- Nisu prespojeni import, auto-fill, mase, naimenovanja, brisanje, bulk tarifa
  niti export na Controller.
- Legacy View metode nisu brisane.
- Agent i MainWindow direktni adapteri nisu migrirani.
- Nisu mijenjani poslovni rezultati, grupiranje, povlastice ni XML format.

## Verifikacija

- Kombinovani ciljani testovi nakon spajanja `windows`: 63 prošla, 1 preskočen.
- Završna standalone/paritet i stvarni E2E import kapija: 26 prošlo.
- Puna svita: 1408 prošlo, 72 preskočena, 5 očekivano xfailed; 10 DB testova
  palo isključivo zato što PostgreSQL server nije bio dostupan.
- Stvarni povezani `FakturaTab` offscreen: 0 `itemChanged`, selektivno bojenje
  mijenja samo traženi red.
- Merge simulacija sa `windows`: bez konflikta.
- `git diff --check` i pre-commit `py_compile`: prolaze.

## Pronađeni problemi

Raniji test je provjeravao samo postojanje `dist_client` fajlova, a ne stvarni
standalone import. Raniji „aktivni“ validacioni signal bio je dodat na kraj
kompletnog View toka i time je validirao dvaput. Oba obrasca su uklonjena.

## Konflikti / kontradiktorni izvori

Commit poruke i stari report tvrdili su da su Faze 0–8 završene, dok sam kod i
plan potvrđuju da produkcioni signali nisu prespojeni. Kod i acceptance kriteriji
plana tretirani su kao važeći. Korisnička potvrda za tu interpretaciju nije
potrebna jer je funkcionalno stanje direktno dokazivo.

## Commitovi

| Hash | Poruka |
|---|---|
| `237915d` | `fix(test): koristi FakturaTab za blockSignals test, očisti trailing whitespace` |
| `05ac9c6` | `merge(windows): osvjezi faktura refaktor` |
| `e88b2de` | `test(faktura): ojacaj standalone i paritet kapije` |

Raniji fazni commitovi ostaju u historiji grane.

## Rizici / ograničenja

Ovo nije završen puni 3-layer refaktor. Kanonski plan procjenjuje kompletnu
migraciju na 53–83 sata i zahtijeva zaseban zeleni checkpoint za svaki
vertikalni rez. PostgreSQL-zavisni testovi moraju se ponoviti kada server bude
dostupan.

## Potreban follow-up

Migrirati redom validaciju, import, naimenovanja/auto-fill, mase, item edit i
export, svaki kao zaseban vertikalni rez. Stare View metode uklanjati tek kada
pretraga i testovi dokažu da nemaju pozivaoce.

## Potrebna korisnička potvrda

Prije mergea u `windows` korisnik treba ručno potvrditi startup i osnovni tok sa
stvarnom fakturom. Puni 3-layer refaktor zahtijeva novu eksplicitnu realizaciju
faza iz kanonskog plana, a ne samo uključivanje pripremljene infrastrukture.
