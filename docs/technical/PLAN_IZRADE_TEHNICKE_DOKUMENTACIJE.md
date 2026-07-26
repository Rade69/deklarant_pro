# Plan izrade tehničke dokumentacije

## 1. Cilj

Napraviti tačnu, održivu i modularnu tehničku dokumentaciju aplikacije
Deklarant Pro, izvedenu iz trenutnog koda, aktivnih poslovnih odluka i provjerenih
izvršnih tokova.

Dokumentacija treba da omogući novom programeru ili tehničkom administratoru da:

- razumije arhitekturu i granice modula;
- pronađe izvor poslovne logike;
- prati tok podataka od ulaznog dokumenta do ASYCUDA XML-a;
- bezbjedno proširi parser, servis, karticu ili bazu;
- pokrene, testira, izgradi i dijagnostikuje aplikaciju;
- razlikuje aktivnu implementaciju od tehničkog duga i planiranih promjena.

## 2. Granice dokumentacije

Ovaj plan obuhvata tehničku dokumentaciju za:

- desktop aplikaciju i PySide6 GUI;
- modele radnog nacrta;
- ručni i Agent import;
- PDF, Excel i XML parsere;
- Faktura, Naimenovanja, Zaglavlje, Šifrarnici, Agent i Admin kartice;
- tarifno mapiranje, istorijsku pretragu i Decision sloj;
- mase, validaciju, povlastice i inspekcijska pravila;
- ASYCUDA XML izvoz i ostale izvozne formate;
- PostgreSQL i SQLite baze;
- konfiguraciju, logovanje, threading i obradu grešaka;
- testiranje, izgradnju i `dist_client` distribuciju;
- održavanje, proširenje i poznata ograničenja.

Van ovog plana ostaju:

- detaljno korisničko uputstvo za svakodnevni rad;
- pravna tumačenja carinskih propisa;
- stvarni pristupni podaci, lozinke i API ključevi;
- kopiranje osjetljivih poslovnih podataka iz faktura;
- generisana API dokumentacija za svaku trivijalnu metodu.

Korisničko uputstvo se vodi odvojeno u `docs/user-guide/`.

## 3. Ciljna publika

Dokumentacija će razlikovati potrebe četiri grupe:

| Publika | Potrebne informacije |
| --- | --- |
| Novi programer | Arhitektura, struktura projekta, modeli, glavni tokovi i pravila izmjena |
| Održavalac parsera | Registry, detekcija formata, `ImportResult`, kombinovanje fajlova i testne fakture |
| Administrator | Konfiguracija, baze, licenca, logovi, instalacija, build i dijagnostika |
| Tehnički reviewer | Poslovni invarianti, granice slojeva, sigurnost, testovi i poznati rizici |

## 4. Izvori istine

Informacije se provjeravaju sljedećim redoslijedom:

1. trenutni izvršni kod na aktivnoj grani;
2. `AGENTS.md` i `docs/CONTEXT.md`;
3. testovi koji potvrđuju ponašanje;
4. aktuelni decision zapisi i agent izvještaji;
5. postojeća dokumentacija;
6. stari planovi i arhivirani dokumenti samo kao istorijski kontekst.

Ako se izvori razlikuju:

- trenutno ponašanje se potvrđuje kodom i testom;
- poslovna odluka se preuzima iz najnovijeg kanonskog zapisa;
- zastarjela tvrdnja se ne kopira u novu dokumentaciju;
- nerazriješen konflikt se označava kao otvoreno pitanje;
- planirano ponašanje se nikad ne predstavlja kao već implementirano.

## 5. Predložena struktura

```text
docs/technical/
├── README.md
├── PLAN_IZRADE_TEHNICKE_DOKUMENTACIJE.md
├── 01-pregled-sistema.md
├── 02-arhitektura-i-slojevi.md
├── 03-struktura-repozitorijuma.md
├── 04-model-podataka-i-draft.md
├── 05-pokretanje-i-zivotni-ciklus.md
├── 06-import-pipeline.md
├── 07-parseri-i-detekcija-formata.md
├── 08-faktura-radni-tok.md
├── 09-naimenovanja-i-grupisanje.md
├── 10-zaglavlje-i-prilozeni-dokumenti.md
├── 11-tarife-decision-i-ucenje.md
├── 12-agent-arhitektura.md
├── 13-sifrarnici-i-baze.md
├── 14-validacija-mase-povlastice-i-inspekcije.md
├── 15-asycuda-xml-i-izvozi.md
├── 16-konfiguracija-i-sigurnost.md
├── 17-threading-performanse-i-cache.md
├── 18-testiranje.md
├── 19-build-dist-client-i-instalacija.md
├── 20-logovanje-dijagnostika-i-incidenti.md
├── 21-vodic-za-prosirenje.md
├── 22-poznata-ogranicenja-i-tehnicki-dug.md
└── diagrams/
    ├── system-context.md
    ├── import-sequence.md
    ├── declaration-workflow.md
    ├── agent-import-sequence.md
    └── data-storage-map.md
```

## 6. Standard svakog dokumenta

Svaki dokument treba da sadrži samo primjenjive sekcije:

1. **Namjena** — zašto modul ili tok postoji.
2. **Odgovornosti** — šta pripada modulu, a šta ne.
3. **Glavni simboli i fajlovi** — klase, servisi i modeli.
4. **Ulazi i izlazi** — formati, signali i povratne vrijednosti.
5. **Tok izvršavanja** — redoslijed važnih koraka.
6. **Invarianti** — pravila koja se ne smiju prekršiti.
7. **Greške i oporavak** — očekivani neuspjesi i način obrade.
8. **Threading i performanse** — ako modul koristi workere, cache ili DB.
9. **Testna pokrivenost** — karakterizacioni i regresioni testovi.
10. **Poznata ograničenja** — samo potvrđeni aktivni problemi.
11. **Povezani dokumenti** — relativni linkovi prema drugim poglavljima.

Dokumenti neće prepisivati cijele funkcije niti praviti ručni API katalog za
trivijalne metode.

## 7. Faze izrade

### Faza 1 — Inventar i provjera izvora

Zadaci:

- evidentirati aktivne entry point fajlove;
- mapirati GUI kartice, controllere i servise;
- mapirati modele, baze i glavne adaptere;
- popisati aktivne importere i njihove testne fakture;
- označiti postojeće dokumente kao aktivne, djelimično zastarjele ili istorijske;
- evidentirati razlike između root koda i `dist_client`;
- prikupiti otvorene odluke iz `docs/CONTEXT.md` i najnovijih izvještaja.

Izlaz:

- matrica modula i vlasništva;
- matrica izvora istine;
- lista konflikata koji zahtijevaju provjeru.

### Faza 2 — Temelji sistema

Napisati:

- `README.md`;
- pregled sistema;
- arhitekturu i slojeve;
- strukturu repozitorijuma;
- model podataka i draft;
- pokretanje i životni ciklus aplikacije.

Posebno provjeriti:

- stvarne entry point putanje;
- `MainWindow`, tab factory i lifecycle tabova;
- komunikaciju signalima;
- granicu između `draft.invoice_lines` i `draft.items`;
- radni nacrt i njegov XML format.

### Faza 3 — Glavni poslovni tok

Napisati:

- import pipeline;
- parser arhitekturu;
- Faktura tok;
- Naimenovanja i grupisanje;
- Zaglavlje i priložene dokumente;
- ASYCUDA XML i druge izvoze.

Obavezno dokumentovati:

- `ImportResult`;
- `consumed_paths`;
- kombinovanje PDF/Excel i Invoice/Packing List parova;
- jedinstveni ručni i Agent import plan;
- raspodjelu težina;
- grupisanje po četiri ključa;
- Rub. 31 ograničenja;
- Rub. 36 potvrdu deklaranta;
- Rub. 44 dokumente;
- Rub. 48 zabranu istorijskog prepisivanja;
- ograničenje od 99 naimenovanja;
- split u više draftova.

### Faza 4 — Tarife, odluke i Agent

Napisati:

- tarifno mapiranje i učenje;
- Decision i Evidence sloj;
- istorijsku pretragu;
- Agent arhitekturu;
- LLM provider i fallback;
- tool-first tok;
- sigurnu granicu podataka prema LLM-u.

Obavezno razdvojiti:

- determinističke lokalne alate;
- istorijske prijedloge;
- fuzzy mapiranje;
- korisničku potvrdu;
- LLM objašnjenje;
- automatsku primjenu;
- podatke koji se ne smiju poslati cloud provideru.

### Faza 5 — Podaci i poprečne funkcije

Napisati:

- Šifrarnike i baze;
- validaciju, mase, povlastice i inspekcije;
- konfiguraciju i sigurnost;
- threading, performanse i cache;
- logovanje, dijagnostiku i incidentni tok.

Obavezno navesti:

- vlasništvo svake baze;
- PostgreSQL `catalogs` šemu;
- lokalne SQLite baze;
- aktivni `.env` prema načinu pokretanja;
- zabranu hardkodovanog IP-a;
- transakcione granice;
- QThread pravila;
- `blockSignals` pri bulk operacijama;
- timeout, fallback i korisničke poruke kod DB greške.

### Faza 6 — Razvoj, testiranje i distribucija

Napisati:

- testnu strategiju;
- vodič za proširenje;
- build, `dist_client` i instalaciju;
- poznata ograničenja i tehnički dug.

Vodič za proširenje treba da sadrži kontrolne liste za:

- novi importer;
- novu karticu;
- novi servis;
- novu DB migraciju;
- novi Agent alat;
- novo ASYCUDA XML polje;
- novu QSS temu ili widget;
- promjenu modela koji koristi `dist_client` kompajlirani modul.

### Faza 7 — Unakrsna provjera

Za svako poglavlje:

- provjeriti navedene putanje;
- potvrditi ključne simbole GitNexus kontekstom i izvornim kodom;
- povezati odgovarajuće testove;
- provjeriti Mermaid sintaksu;
- pokrenuti DOC Guard;
- provjeriti relativne linkove;
- ukloniti duplirane opise;
- označiti zastarjele stare dokumente bez njihovog brisanja;
- potvrditi da nema lozinki, IP adresa koje treba čitati iz `.env` ili stvarnih podataka klijenata.

### Faza 8 — Objavljivanje i održavanje

Završni koraci:

- dodati tehnički `README.md` kao navigacioni indeks;
- povezati tehničku dokumentaciju iz glavnog projektnog README-a ako postoji;
- napraviti agent izvještaj sa statusom izvora;
- commitovati dokumente po logičkim cjelinama;
- osvježiti GitNexus indeks;
- definisati vlasništvo i pravilo ažuriranja dokumentacije.

## 8. Plan dijagrama

Dijagrami se pišu u Mermaid formatu, bez zavisnosti od posebnih binarnih alata.

### Sistemski kontekst

Prikazuje:

- korisnika;
- desktop aplikaciju;
- PostgreSQL server;
- lokalne SQLite baze;
- lokalni fajl sistem;
- LLM providere;
- MCP server;
- ASYCUDA World kao odredišni sistem.

### Glavni radni tok deklaracije

```text
Ulazni dokumenti
    → detekcija i parser
    → ImportResult
    → import plan i odluke
    → DeclarationDraft
    → tarife i validacija
    → naimenovanja
    → zaglavlje i dokumenti
    → završna provjera
    → ASYCUDA XML
```

### Sekvenca importa

Prikazuje:

- GUI;
- worker;
- ImportService;
- parser registry;
- specijalizovani parser;
- import workflow;
- draft;
- dijaloge koji moraju ostati na glavnom threadu.

### Mapa skladištenja podataka

Prikazuje:

- podatke koji žive samo u memorijskom draftu;
- lokalne nacrte;
- lokalne SQLite baze;
- PostgreSQL kataloge;
- XML arhivu;
- logove;
- podatke koji ne smiju biti trajno sačuvani.

## 9. Matrica provjere

| Oblast | Kod | Testovi | Kontekst/odluka | Ručna provjera |
| --- | --- | --- | --- | --- |
| Pokretanje | Obavezno | Po mogućnosti | Obavezno | Da |
| Import | Obavezno | Obavezno | Obavezno | Prave fakture |
| Draft model | Obavezno | Obavezno | Obavezno | Ne |
| Tarife | Obavezno | DB-backed | Obavezno | Poznati proizvodi |
| Naimenovanja | Obavezno | Obavezno | Obavezno | XML rezultat |
| Zaglavlje | Obavezno | Obavezno | Obavezno | GUI |
| Agent | Obavezno | Offline + integracioni | Obavezno | Provider fallback |
| Baze | Obavezno | DB-backed | Obavezno | Aktivni server |
| Build/distribucija | Skripte/spec | Smoke test | Izvještaji | Windows klijent |

## 10. Pravila pisanja

- Jezik je srpski, latinica.
- Nazivi klasa, metoda, polja i fajlova ostaju onakvi kakvi su u kodu.
- Prvi put kada se koristi stručni pojam daje se kratko objašnjenje.
- Poslovni invariant se piše kao jasno pravilo, ne kao usputna napomena.
- Primjeri ne sadrže stvarne lozinke, API ključeve ni identifikacione podatke.
- SQL primjeri su parametrizovani.
- Putanje su relativne prema korijenu projekta.
- Dokument navodi aktivni tok; legacy tok se opisuje samo ako je i dalje izvršiv.
- Tehnički dug se vodi u posebnom poglavlju i linkuje iz relevantnog modula.
- Datumi se koriste samo za istorijske odluke, ne u nazivima trajnih poglavlja.

## 11. Kriterijumi završetka

Dokumentacija se smatra završenom kada:

- sva planirana poglavlja postoje i povezana su iz indeksa;
- glavni tok dokumenta do XML izvoza ima najmanje jedan sekvencijski dijagram;
- svaki važan modul ima jasno vlasništvo i granicu odgovornosti;
- poslovni invarianti iz `AGENTS.md` i `docs/CONTEXT.md` su zastupljeni;
- nema kontradikcije između ručnog i Agent import opisa;
- root i `dist_client` odnos je jasno objašnjen;
- svaki vodič za proširenje ima testnu kontrolnu listu;
- svi relativni linkovi i DOC Guard provjera prolaze;
- pregled ne otkriva pristupne ili poslovno osjetljive podatke;
- najmanje jedna osoba koja nije pisala dokumentaciju može pratiti arhitekturu bez usmenog objašnjenja.

## 12. Rizici

### Zastarjela postojeća dokumentacija

Postoji više analiza, planova i izvještaja iz različitih faza razvoja. Nova
dokumentacija ne smije ih nekritički objediniti. Svaka bitna tvrdnja mora biti
potvrđena trenutnim kodom ili aktivnom poslovnom odlukom.

### Veliki i mješoviti View moduli

Neki GUI moduli trenutno sadrže i orchestration ili poslovnu logiku. Dokumentacija
treba opisati stvarno stanje, ali istovremeno jasno navesti propisanu ciljnu
View–Controller–Service granicu.

### Root i `dist_client` razlike

`dist_client` može sadržati kompajlirane ili starije kopije modula. Dokumentacija
ne smije pretpostaviti da je ručno kopiranje pouzdan build proces.

### Promjenjiva DB adresa

Server koristi DHCP. Dokumentacija opisuje konfiguracioni ključ i način provjere,
nikad trenutnu IP adresu kao trajnu činjenicu.

### Dokumentacija bez održavanja

Najveći dugoročni rizik je da dokumentacija ponovo zastari. Zato svaka značajna
arhitekturna ili poslovna promjena treba da ažurira odgovarajuće poglavlje u istom
commitu ili da dobije eksplicitnu DOC Guard procjenu.

## 13. Predloženi redoslijed commitova

1. plan i tehnički indeks;
2. pregled sistema, arhitektura, struktura i modeli;
3. import, parseri i Faktura;
4. Naimenovanja, Zaglavlje i izvozi;
5. tarife, Decision i Agent;
6. baze, konfiguracija, threading i sigurnost;
7. testiranje, build, dijagnostika i proširenje;
8. dijagrami, tehnički dug i završna unakrsna provjera;
9. završni agent izvještaj.

Svaki commit mora biti dovoljno mali da se može zasebno pregledati, ali ne smije
razdvajati dokument od dijagrama i linkova koji su potrebni da bude razumljiv.

## 14. Odluka prije početka izrade

Prije pisanja prve faze treba potvrditi:

- da je predložena struktura prihvatljiva;
- da li tehnička dokumentacija treba kasnije imati i PDF/HTML izdanje;
- da li se postojeći stari dokumenti samo označavaju kao zastarjeli ili se kasnije arhiviraju;
- ko će biti primarni održavalac dokumentacije nakon završetka.

Ove odluke ne blokiraju pregled koda, ali utiču na završno pakovanje i način
dugoročnog održavanja.
