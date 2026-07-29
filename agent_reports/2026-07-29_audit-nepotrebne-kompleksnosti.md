# Audit nepotrebne kompleksnosti koda

## Datum

2026-07-29

## Agent

Codex

## Scope

Dubinska read-only analiza produkcionog Python koda Deklarant Pro aplikacije,
sa fokusom na nepotrebnu tehničku kompleksnost, paralelne tokove, dupliranje,
prevelike metode, široko hvatanje grešaka i cijenu održavanja `dist_client`
kopije. Testovi, dokumentacija, generisani UI fajlovi, build izlazi i worktree
kopije nisu uključeni u osnovne AST metrike.

## Status izvora

- `AGENTS.md`: aktivan, kanonski izvor projektnih pravila.
- `docs/CONTEXT.md`: aktivan, korišćen za poslovna i arhitekturna pravila.
- Aktivni kod na grani `windows`: autoritativan za trenutno ponašanje.
- `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md`: aktivan
  kao plan migracije, ali nije dokaz da su svi tokovi već migrirani.
- Raniji Faktura završni izvještaj sa tvrdnjom da su sve faze završene:
  zastario; produkcioni signali potvrđeno ostaju pasivni.
- GitNexus indeks je tokom audita osvježen na aktivni commit. FTS pretraga je
  i nakon osvježavanja prijavila degradaciju, pa su rezultati dopunjeni AST
  analizom, direktnim čitanjem koda i pretragom pozivalaca.

## GitNexus impact

Kod nije mijenjan, zato nije rađena pre-change izmjena pojedinačnih simbola.
GitNexus je korišćen za provjeru pozivalaca i strukture aktivnih tokova.
Za `FakturaView._on_import_finished_legacy()` potvrđen je aktivni pozivalac
`_on_import_finished()` i veliki broj izlaznih zavisnosti unutar Faktura toka.

Rizik budućeg pojednostavljenja zavisi od oblasti:

- Faktura import, XML export, naimenovanja i mase: HIGH po poslovnoj važnosti.
- Ujedinjavanje potpuno identičnih helper modula: MEDIUM, uz import-paritet.
- Uklanjanje neaktivnog scaffolding koda: MEDIUM dok se ne dokažu svi dinamički
  pozivaoci.
- Promjena root/`dist_client` modela distribucije: HIGH po build uticaju.

## Izvršni zaključak

Deklarant Pro ima opravdano složen poslovni domen, ali je tehnička složenost
veća nego što domen zahtijeva. Najveći uzrok nije složenost algoritama nego
obrazac u kojem se novi servis, Controller ili fallback put doda pored starog,
bez završetka migracije i uklanjanja zamijenjene implementacije.

Procjena je da je približno 25–35% sadašnje tehničke kompleksnosti moguće
smanjiti bez uklanjanja funkcionalnosti. To nije procenat linija koje treba
obrisati, nego procjena kognitivnog i održavačkog tereta koji stvaraju dupli
putevi, kopije modula, pasivna infrastruktura i nejasne greške.

## Mjerljivi nalazi

Analizirano je 434 produkciona Python fajla i 3.706 funkcija/metoda.

| Metrika | Rezultat |
|---|---:|
| Funkcije duže od 100 linija | 129 |
| Funkcije duže od 200 linija | 29 |
| Široki `except Exception`/bare `except` blokovi | približno 748 |
| Široki exception blokovi koji vraćaju, preskaču ili nastavljaju tok | 341 |
| Grupe potpuno identičnih funkcijskih tijela | 54 |
| Funkcije unutar tih grupa | 118 |
| Trivijalne wrapper metode | približno 470 |
| Root/`dist_client` upareni Python fajlovi | 610 |
| Sadržajno identični root/`dist_client` parovi | 574 |
| Root/`dist_client` parovi koji se razlikuju | 36 |

Ove brojke nisu automatski dokaz lošeg dizajna. Parser može opravdano biti dug,
a wrapper može biti namjerna API granica. Problem nastaje kada se više ovih
signala pojavi na istom aktivnom toku.

## Najveće klase

| Klasa | Približno metoda | Približno linija u metodama | Ocjena |
|---|---:|---:|---|
| `FakturaView` | 145 | 5.977 | kritičan kandidat |
| `SifarniciView` | 89 | 3.450 | visok kandidat |
| `NaimenovanjaView` | 112 | 2.873 | visok kandidat |
| `ZaglavljeView` | 47 | 2.147 | visok kandidat |
| `ZaglavljeService` | 23 | 1.867 | visok kandidat |
| `SifarniciService` | 72 | 1.204 | srednje-visok kandidat |
| `ZaglavljeController` | 27 | 1.117 | srednje-visok kandidat |
| `ChatWorker` | 22 | 1.100 | srednje-visok kandidat |
| `TariffMappingService` | 19 | 1.060 | visok poslovni rizik |
| `AsycudaXMLBuilder` | 27 | 950 | visok poslovni rizik |

## Najproblematičnije metode

| Metoda | Linije | Grananja | Glavni problem |
|---|---:|---:|---|
| `chat_intent_handler._handle_message_regex_fallback` | 335 | 94 | drugi skoro kompletan agent |
| `FakturaView._on_import_finished_legacy` | 331 | 36 | cijeli import use case u View-u |
| `ZaglavljeService.parse_naimenovanja_from_xml` | 324 | 52 | parsiranje, mapiranje i mutacije zajedno |
| `ZaglavljeService.validate` | 283 | 50 | mnogo nezavisnih pravila u jednoj metodi |
| `ZaglavljeService.load_from_draft` | 270 | 122 | veliki broj opcionih polja i grananja |
| `FakturaView._on_calculate_masses` | 243 | 40 | UI, poslovna odluka i raspodjela zajedno |
| `xml_workflow_service._primjeni_xml_template` | 225 | 58 | orkestracija i transformacije zajedno |
| `FakturaView._on_auto_fill` | 194 | 36 | više izvora i UI promjene u jednom toku |
| `import_pipeline_service._puna_auto_pipeline` | 187 | 24 | opravdana orkestracija, ali osjetljiva na rast |
| `FakturaView._on_create_naimenovanja` | 164 | 26 | View još upravlja poslovnim tokom |

## Nalaz 1 — Faktura ima dvije arhitekture, ali samo jednu aktivnu

`FakturaView` još sadrži aktivnu poslovnu logiku za import, validaciju, mase,
auto-popunu, kreiranje naimenovanja, bulk izmjene i dijaloge. Paralelno postoje
`FakturaController`, `FakturaTab` signal handleri i pripremljeni View signali.

Produkcioni kod ne emituje pripremljene signale:

- `import_requested`
- `validate_requested`
- `create_naimenovanja_requested`
- `calculate_masses_requested`

Emisije su pronađene samo u testovima. Dio `FakturaTab` handlera poziva
Controller, dok se drugi vraćaju u privatne metode View-a. To trenutno povećava
broj klasa, metoda, testova i mogućih mjesta za izmjenu, ali ne smanjuje
odgovornost starog View-a.

### Rizik

Controller logika može vremenom odstupiti od aktivne View logike. Na primjer,
Controller već ima vlastite verzije normalizacije tarifa, provjere partnera,
prepoznavanja iste fakture, kreiranja naimenovanja i bulk izmjene.

### Preporuka

Izabrati jednu od dvije opcije:

1. nastaviti vertikalnu migraciju, jedan kompletan tok po commitu, pa ukloniti
   odgovarajući stari View kod; ili
2. ukloniti pasivni scaffolding koji u doglednom periodu neće biti aktiviran.

Trajno zadržavanje trenutnog hibrida je najskuplja opcija.

## Nalaz 2 — Agent ima previše paralelnih puteva

Jedna korisnička poruka može proći kroz sigurnosnu provjeru, pending-action
obradu, lokalni router, LLM Tool Use, regex fallback, ChatWorker i dodatne
lokalne fallback servise. Arhitektura je nastajala inkrementalno, pa nije uvijek
jasno koji sloj je autoritativan za određenu namjeru.

`_handle_message_regex_fallback()` ima 335 linija i 94 grananja. To više nije
mali offline fallback nego drugi sistem namjera paralelan Tool Use sistemu.

### Posljedica

Upit može biti prepoznat kao tekstualna namjera, ali završiti u putu koji samo
prikaže podatke umjesto da izvrši poslovnu provjeru. Dodavanje još promptova ili
regex izraza ne rješava strukturni problem.

### Preporuka

Autoritativni tok treba biti:

```text
namjera → lokalni alat/servis → strukturirani rezultat → prikaz
```

Regex fallback zadržati samo za mali, eksplicitno definisan skup offline
naredbi. Svaka poslovna namjera treba imati jedan executor, bez obzira da li ju
je prepoznao lokalni router ili LLM.

## Nalaz 3 — Potpuno duplirani poslovni moduli

Potpuno identične implementacije postoje u parovima:

- `services/origin_statement_detector.py`
- `services/tariff/origin_statement_detector.py`
- `services/country_origin_validator.py`
- `services/tariff/country_origin_validator.py`

Pozivaoci koriste obje putanje. Buduća popravka u jednoj kopiji može ostaviti
drugu neispravljenu.

### Preporuka

Odrediti jednu kanonsku implementaciju. Stara putanja privremeno treba samo
re-exportovati kanonske simbole. Tek nakon migracije svih importa može se
ukloniti kompatibilni modul.

## Nalaz 4 — PE/Rub.44 poslovno pravilo je kopirano u tri sloja

Identična funkcija `_clear_secondary_pe_documents()` postoji u:

- `gui/tabs/faktura_view.py`
- `gui/tabs/naimenovanja_view.py`
- `gui/tabs/agent/services/import_pipeline_service.py`

To je poslovno pravilo, ne UI pomoćna funkcija. Različiti ulazni putevi mogu
proizvesti različit XML ako se samo jedna kopija naknadno promijeni.

### Preporuka

Premjestiti pravilo u jedan neutralan servis za PE/Rub.44 dokumente i zadržati
karakterizacione testove za sva tri postojeća pozivaoca.

## Nalaz 5 — Dva velika ASYCUDA XML buildera

Postoje dvije klase istog imena:

- `exporters/asycuda_xml_builder.py::AsycudaXMLBuilder`
- `exporters/deklarant_xml_builder.py::AsycudaXMLBuilder`

Veliki broj metoda je identičan, uključujući `_add_property`, `_add_traders`,
`_add_declarant`, `_add_transport`, `_add_financial` i `_add_transit`.

Aktivni GUI export, Agent export i XML readiness koriste
`asycuda_xml_builder.py`. Za `deklarant_xml_builder.py` nije pronađen vanjski
produkcioni import; modul sam instancira vlastitu klasu kroz vlastiti helper.

### Preporuka

Tretirati `deklarant_xml_builder.py` kao kandidata za zastarjeli paralelni
builder, ali ga ne brisati dok se ne provjere build skripte, dinamički importi,
pakovani EXE i eksterni pozivaoci. Ako je zaista neaktivan, uklanjanje cijelog
drugog buildera ima veću vrijednost od mikro-refaktora pojedinačnih metoda.

## Nalaz 6 — Velike View klase obavljaju poslovne use case-ove

`FakturaView`, `SifarniciView`, `NaimenovanjaView` i `ZaglavljeView` ne rade
samo prikaz. One na različitim mjestima:

- čitaju widgete;
- validiraju poslovna pravila;
- mijenjaju draft;
- pozivaju bazu i servise;
- upravljaju workerima;
- prikazuju modale;
- formatiraju rezultate;
- odlučuju o fallback putu.

Samo premještanje metode u Controller ili Service nije dovoljno ako stari View
tok ostane aktivan. Uspješna migracija mora smanjiti odgovornost i količinu
koda u View-u.

## Nalaz 7 — Zaglavlje je u pravom sloju, ali metode su još preširoke

`ZaglavljeService` je arhitektonski opravdan, ali nekoliko metoda spaja
parsiranje, normalizaciju, mapiranje XML-a, draft mutacije i validaciju.

Posebno:

- `load_from_draft()` — 270 linija i 122 grananja;
- `parse_naimenovanja_from_xml()` — 324 linije;
- `validate()` — 283 linije;
- `_parse_xml()` — 251 linija;
- `save_to_draft()` — 223 linije.

### Preporuka

Ne uvoditi dodatne klase samo radi manjeg broja linija. Prvo izdvojiti čiste
grupe pravila: partneri, transport, finansije, dokumenti i item mapiranje.
Javni `ZaglavljeService` može ostati facade sa stabilnim API-jem.

## Nalaz 8 — Široki exception blokovi brišu razliku između stanja

Pronađeno je približno 748 širokih exception blokova; 341 mijenja tok tako što
vrati podrazumijevanu vrijednost, preskoči element ili nastavi na fallback.

Najveća koncentracija:

| Fajl | Široki blokovi ili tihi izlazi |
|---|---:|
| `gui/tabs/sifarnici_view.py` | 63 široka bloka |
| `services/sifarnici_service.py` | 52 tiha/flow-change izlaza |
| `gui/tabs/faktura_view.py` | 28 širokih blokova |
| `chat_intent_handler.py` | 20 |
| `gui/tabs/naimenovanja_view.py` | 19 |
| `gui/tabs/zaglavlje_controller.py` | 14 |

Best-effort zvuk, cache ili tooltip opravdano ne smiju oboriti proces. Poslovne
kapije, tarifa, XML i baza moraju razlikovati:

- nema podataka;
- provjera nije izvršena;
- provjera je izvršena i nije našla problem;
- došlo je do greške.

Jedan `False`, prazna lista ili `None` često ne mogu izraziti sva četiri stanja.

## Nalaz 9 — `dist_client` skoro udvostručava površinu održavanja

Od 610 uparenih Python fajlova, 574 su sadržajno identična, a 36 se razlikuje.
To znači da skoro svaka izmjena traži:

- root izmjenu;
- `dist_client` izmjenu;
- paritet provjeru;
- provjeru `.py` naspram ranije kompajliranog `.pyd`;
- provjeru standalone importa i builda.

### Preporuka

Dugoročni cilj treba biti jedan izvor produkcionog Python koda. `dist_client`
bi trebalo da sadrži konfiguraciju, klijentske resurse i build artefakte, a ne
ručnu kopiju skoro cijele aplikacije. Ovo je visokorizična distribuciona
promjena i ne treba je kombinovati sa funkcionalnim refaktorom tabova.

## Nalaz 10 — Wrapperi imaju vrijednost samo uz jasan ugovor

Pronađeno je približno 470 trivijalnih wrapper metoda. Najviše ih je u:

- `AgentController`;
- `chat_intent_handler`;
- `NaimenovanjaView`;
- admin servisima;
- `FakturaView`.

Wrapper nije automatski višak. U Agent arhitekturi je čak propisan tanak
Controller. Problematičan je kada:

- samo prosljeđuje poziv bez stabilnog javnog ugovora;
- postoji zajedno sa direktnim pozivima istog servisa;
- nema dodatnu autorizaciju, transakciju, signal ili normalizaciju;
- ostaje nakon što su svi pozivaoci već migrirani.

Takvi wrapperi povećavaju dubinu stack trace-a i otežavaju pronalazak stvarnog
vlasnika poslovnog pravila.

## Nalaz 11 — Produkcioni kod sadrži tragove faza umjesto trajnih ugovora

Faktura Controller i Tab sadrže oznake poput „Faza 1–7B“, komentare da View još
ne emituje signale i privremene migracione handlere. To je korisno tokom kratke
migracije, ali nije stabilna arhitektura.

Kada fazni kod ostane duže vrijeme:

- budući agent pretpostavi da je faza završena;
- testira postojanje infrastrukture umjesto aktivnog ponašanja;
- dodaje novi sloj na nedovršeni sloj;
- privremena odluka postaje trajna bez eksplicitne odluke.

Svaki migracioni scaffold treba imati vlasnika, kriterij završetka i odluku:
aktivirati do određenog checkpointa ili ukloniti.

## Nalaz 12 — Dupliranje u parserima je djelimično opravdano

Potpuno ili skoro identični helperi postoje za:

- `_detect_exporter`;
- `_detect_origin_statement`;
- `_detect_all_origin_statements`;
- `get_float`;
- `_parse_number`.

Ove male funkcije su kandidati za zajedničke utility module. Međutim, velike
vendor parser metode ne treba automatski pretvarati u generički framework.
Različiti PDF rasporedi, OCR, tabele i packing-list fallbacki predstavljaju
stvarnu poslovnu složenost.

Pravilo treba biti: izdvojiti samo dokazano identične, stabilne operacije, bez
apstrakcije vendor-specifičnih razlika.

## Nalaz 13 — Testovi ponekad potvrđuju infrastrukturu, ne ponašanje

Tokom Faktura refaktora pronađeni su testovi koji su provjeravali samo da
`dist_client` fajl postoji ili da signal može biti ručno emitovan. Takav test
ne dokazuje:

- da produkcioni View emituje signal;
- da se novi Controller tok zaista koristi;
- da stari tok više nije aktivan;
- da se proces ne izvršava dvaput.

### Preporuka

Za svaki migrirani tok test mora početi od istog događaja koji korisnik izaziva
u GUI-ju i potvrditi konačnu promjenu drafta. Broj poziva starog handlera treba
biti nula kada se tok proglasi migriranim.

## Šta nije nepotrebna kompleksnost

Ne treba automatski pojednostavljivati:

- ASYCUDA poslovna pravila;
- ograničenja Rub.31;
- grupiranje naimenovanja po četiri ključa;
- eksplicitne EUR.1/PE potvrde;
- per-invoice raspodjelu težina;
- konservativnu Incoterm detekciju;
- vendor-specifične parser fallbacke;
- fail-closed XML readiness kapije;
- `blockSignals` zaštitu kod bulk Qt izmjena.

Ovo su složena ili sigurnosno važna pravila. Njih treba centralizovati i dobro
testirati, ne uklanjati radi manjeg broja linija.

## Preporučeni redoslijed realizacije

### P0 — zaustaviti rast

1. Novi sloj ne uvoditi bez plana uklanjanja starog.
2. Svaki refaktor mora navesti koji stari kod na kraju nestaje.
3. Test postojanja klase ili signala ne računati kao završenu migraciju.
4. Ne spajati više velikih arhitektonskih refaktora u jednu granu.
5. Za svaki privremeni kompatibilni sloj evidentirati kriterij uklanjanja.

### P1 — mali rizik, velika korist

1. Ujediniti duple origin-statement module.
2. Ujediniti duple country-origin validatore.
3. Centralizovati PE/Rub.44 čišćenje.
4. Dokazati status starog XML buildera i ukloniti ga ako nema pozivalaca.
5. Klasifikovati 36 root/`dist_client` razlika na opravdane i drift.
6. Ukloniti neaktivne migracione komentare tek nakon odluke o Faktura smjeru.

### P2 — završiti ili povući Faktura hibrid

Migrirati zasebno:

1. validaciju;
2. import;
3. kreiranje naimenovanja;
4. mase;
5. auto-popunu;
6. bulk izmjene;
7. export.

Za svaki rez:

- karakterizacioni test starog ponašanja;
- signal iz stvarnog GUI događaja;
- Controller/Service izvršenje;
- root i `dist_client` paritet;
- ručni test sa stvarnom fakturom;
- uklanjanje zamijenjene View logike.

### P3 — pojednostaviti Agent routing

1. Napraviti jedinstven katalog namjera i executora.
2. Tool Use i lokalni router smiju birati namjeru, ali ne smiju imati zasebnu
   poslovnu implementaciju.
3. Regex fallback svesti na eksplicitne offline naredbe.
4. Svaka provjera vraća strukturirani status, nalaze i dokaz izvršenja.
5. LLM samo formatira autoritativni rezultat kada poslovni alat postoji.

### P4 — velike View klase

Redoslijed:

1. izdvojiti use case bez promjene javnog GUI API-ja;
2. dodati karakterizacione i E2E testove;
3. prespojiti signal;
4. ukloniti staru View logiku;
5. tek zatim preći na sljedeći use case.

Ne raditi mehaničko cijepanje po broju linija.

### P5 — distribucija

Planirati zaseban projekat za jedan izvor Python koda i tanji `dist_client`.
Ne kombinovati ga sa poslovnim refaktorom jer build, Nuitka/PyInstaller i
klijentske konfiguracije imaju drugačiji rizik.

## Kriteriji uspjeha

Pojednostavljenje je uspješno samo ako:

- poslovni rezultat ostane isti;
- jedan korisnički događaj ima jedan aktivni izvršni put;
- novi sloj zamijeni, a ne samo obavije stari;
- broj produkcionih implementacija istog pravila se smanji;
- root/`dist_client` drift ne poraste;
- greška se ne pretvara u „nema nalaza“;
- svi ciljani i E2E testovi prolaze;
- stvarna faktura daje isti rezultat prije i poslije;
- uklonjeni kod nema statičke ni dinamičke pozivaoce.

## Šta je urađeno

- Osvježen je GitNexus indeks.
- Izračunate su AST metrike produkcionog koda.
- Identifikovane su velike metode i klase.
- Pronađene su potpuno identične funkcije i moduli.
- Provjereni su pozivaoci Faktura legacy importa, pasivnih signala, duplih
  origin validatora i XML buildera.
- Izmjeren je root/`dist_client` paritet.
- Napravljen je prioritizovan plan pojednostavljenja.

## Zašto je urađeno

Cilj nije smanjiti kod radi estetike, nego spriječiti da AI-generisani slojevi,
fallbacki i wrapperi povećavaju broj mogućih izvršnih puteva. U carinskoj
aplikaciji pogrešno pojednostavljenje može biti rizičnije od duplog koda, zato
su preporuke razdvojene po poslovnom riziku i zahtijevaju karakterizacione
testove prije uklanjanja.

## Kako je urađeno

Korišćeni su:

- GitNexus indeks i provjera pozivalaca;
- Python AST analiza dužine, grananja, poziva i exception blokova;
- poređenje funkcijskih tijela bez oslanjanja na nazive;
- poređenje root i `dist_client` fajlova uz normalizaciju line endinga;
- direktna pretraga importa, signala, legacy i fallback puteva;
- ručno čitanje ključnih Faktura, Agent, Zaglavlje i XML modula.

## Šta nije dirano

- Nije mijenjan aplikacioni kod.
- Nisu uklanjani dupli moduli.
- Nisu aktivirani Faktura signali.
- Nije mijenjan Agent routing.
- Nije mijenjan XML export.
- Nisu dirani postojeći necommitovani korisnički fajlovi.
- Nije izvršen merge niti push.

## Verifikacija

- GitNexus indeks je nakon audita prijavio stanje `up-to-date`.
- AST analiza je izvršena samo nad produkcionim Python kodom uz navedene
  izuzetke.
- Direktna pretraga je potvrdila da se pripremljeni Faktura signali emituju
  samo u testovima.
- Direktna pretraga je potvrdila miješane importe duplih origin modula.
- Direktna pretraga je potvrdila da aktivni GUI, Agent i readiness koriste
  `asycuda_xml_builder.py`.
- Audit nije proizveo izmjene aplikacionog koda.

## Pronađeni problemi

- GitNexus FTS pretraga ostala je degradirana i nakon uspješnog osvježavanja
  indeksa; zato nije korišćena kao jedini izvor.
- Statička pretraga ne može potpuno dokazati odsustvo dinamičkog importa.
- Broj širokih exception blokova je signal za pregled, ne tvrdnja da je svaki
  blok pogrešan.
- Broj linija je signal koncentracije odgovornosti, ne automatski dokaz da
  metodu treba podijeliti.

## Konflikti / kontradiktorni izvori

Ranije fazne poruke i izvještaji sugerisali su da je Faktura 3-layer refaktor
završen. Aktivni kod pokazuje da View ne emituje pripremljene signale i da su
stari handleri i dalje autoritativni. Kod i izvršni wiring tretirani su kao
važeći izvor. Korisnička potvrda za ovaj tehnički zaključak nije potrebna.

## Commitovi

Ovaj audit ne mijenja aplikacioni kod. Commit koji dodaje izvještaj treba
posmatrati kao dokumentacioni commit.

## Rizici / ograničenja

- Procjena 25–35% odnosi se na tehnički teret, ne na tačan broj linija.
- Uklanjanje navodno mrtvog koda zahtijeva provjeru builda i dinamičkih importa.
- Refaktor Faktura, XML i distribucije ima visok blast radius.
- Pojednostavljenje bez karakterizacionih testova može promijeniti carinski
  rezultat i nije prihvatljivo.

## Potreban follow-up

Najrazumniji prvi implementacioni paket je P1: dupli origin moduli, zajedničko
PE/Rub.44 pravilo i dokaz statusa drugog XML buildera. Nakon toga treba donijeti
eksplicitnu odluku da li se Faktura Controller migracija nastavlja ili se
pasivni scaffold privremeno povlači.

## Potrebna korisnička potvrda

Prije implementacije treba potvrditi samo redoslijed prioriteta. Preporučeni
početak je P1, bez promjene vidljivog ponašanja aplikacije i bez spajanja velikih
Faktura ili `dist_client` zahvata u isti paket.
