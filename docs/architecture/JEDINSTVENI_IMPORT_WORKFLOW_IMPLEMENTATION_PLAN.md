# Jedinstveni radni tok uvoza faktura — implementacioni plan

## Status dokumenta

- Datum: 2026-07-24
- Status: odobren koncept, implementacija nije započeta
- Scope: ručni pojedinačni uvoz, ručni grupni uvoz i Agent uvoz u deklaraciju
- Cilj: isti ulazni fajlovi moraju proizvesti isti poslovni rezultat bez obzira na mjesto iz kojeg je uvoz pokrenut

## 1. Poslovni cilj

Trenutno ručni i Agent uvoz koriste različitu završnu obradu istih rezultata parsera. Razlike obuhvataju provjeru partnera, raspodjelu težina, dodjelu broja fakture, spajanje kombinovanih rezultata, primjenu zaglavlja i PE2/PE3/EUR1 odluke.

Cilj je uvesti jedan zajednički radni tok koji koriste:

1. ručni pojedinačni uvoz;
2. ručni grupni uvoz;
3. Agent režim „Uvezi u deklaraciju“;
4. aktivni Agent režim pune automatizacije kada završava uvoz u draft.

Poslovna obrada mora biti identična. Razlikovati se smiju samo prikaz napretka i kanal završne poruke.

## 2. Potvrđeno trenutno stanje

### Ručni uvoz trenutno ima

- provjeru konzistentnosti pošiljaoca i primaoca;
- normalizaciju tarifnih brojeva;
- raspodjelu ukupne bruto/neto mase na stavke;
- dodjelu identiteta fakture stavkama;
- `REPLACE/EXTEND` logiku za postojeći draft;
- akumulaciju ukupnih težina;
- PE2/PE3/EUR1 odluke;
- završnu historijsku tarifnu validaciju;
- modalnu završnu poruku.

### Agent uvoz trenutno ima

- normalizaciju tarifnih brojeva;
- zaštitu od dijela duplikata preko `is_combined` i `consumed_paths`;
- obradu više završenih fajlova;
- akumulaciju ukupne bruto/neto mase;
- PE2/PE3/EUR1 dijaloge po fakturi;
- prikaz toka i rezultata u Agent chatu;
- završnu historijsku validaciju.

### Potvrđene razlike

- Agent ne poziva istu provjeru konzistentnosti partnera.
- Agent ne raspoređuje ukupne težine na pojedinačne stavke.
- Broj fakture se ne dodjeljuje po istoj politici.
- Agent nema istu završnu `REPLACE/EXTEND` logiku.
- Agent privremeno čisti i ponovo sastavlja draft po fakturama.
- Pravila primjene zaglavlja i povlastica nisu objedinjena.
- Agent formira `combined_files` i `single_files`, ali ih završni tok ne koristi kao jedinstveni plan.

## 3. Autoritativne odluke i konflikti izvora

### `consumed_paths`

Svaki kombinovani importer mora vratiti `consumed_paths`. Zajednički završni tok koristi taj podatak da ukloni potrošeni prateći fajl i spriječi dupliranje stavki.

### Privatna `ImportService` instanca u workerima

`docs/CONTEXT.md` zahtijeva privatnu `ImportService()` instancu po workeru zbog race condition rizika. Stariji `docs/sections/import_pipeline.md` navodi singleton kao pretpostavku. Za novu implementaciju važi novija odluka iz `docs/CONTEXT.md`: worker ne koristi globalni singleton.

### Kombinovanje fajlova i primjena na draft nisu ista stvar

- `ImportService` kombinuje sadržaj povezanih fajlova u jedan `ImportResult`.
- `consumed_paths` uklanja fajl koji je već potrošen tim kombinovanjem.
- Zajednički završni servis odlučuje kako se rezultat primjenjuje na postojeći draft: dodavanje, zamjena ili preskakanje.

Nova implementacija ne smije praviti drugi parser niti duplirati postojeću state machine logiku kombinovanja.

### Povlastice zahtijevaju potvrdu

PE1/PE2/PE3 i Rub.36 ne smiju se automatski upisivati samo na osnovu zemlje porijekla, istorije ili Agent procjene. I ručni i Agent tok moraju tražiti istu eksplicitnu potvrdu deklaranta.

### Težine su per-faktura

`invoice_weights` se čuva po logičkoj fakturi. Ukupna masa cijelog batcha nije zamjena za per-faktura raspodjelu.

## 4. Arhitekturni princip

Implementacija prati tri sloja:

```text
View
  prikazuje napredak, dijaloge i rezultat
        ↓ signali / odgovori korisnika
Controller
  pretvara ulaz u zajednički model i orkestrira odluke
        ↓
Service
  priprema plan, validira i atomski primjenjuje poslovne podatke
```

Servis ne otvara `QMessageBox`, ne upravlja tabovima i ne piše u Agent chat. View ne smije sadržavati poslovnu logiku raspodjele težina, deduplikacije ili spajanja drafta.

## 5. Ciljani zajednički tok

```text
Odabir fajlova
    ↓
Paralelno ili sekvencijalno parsiranje u workeru
    ↓
ImportResult / FileItem adapter
    ↓
Normalizovani ImportCandidate zapisi
    ↓
Deduplikacija i consumed_paths
    ↓
Identitet logičke fakture
    ↓
Provjera partnera, valute i zaglavlja
    ↓
Normalizacija tarifa i težina
    ↓
Plan ADD / REPLACE / SKIP
    ↓
PE2 / PE3 / EUR1 odluke korisnika
    ↓
Atomska primjena na draft
    ↓
Jedno osvježavanje UI-ja i jedna završna validacija
```

## 6. Zajednički modeli

### `ImportCandidate`

Neutralan zapis nezavisan od Qt widgeta:

- izvorna putanja;
- normalizovana apsolutna putanja;
- tip fajla;
- parser;
- `InvoiceLine` stavke;
- eksplicitni broj fakture;
- prikazni naziv fakture;
- bruto i neto masa fakture;
- pošiljalac;
- primalac;
- valuta;
- podaci relevantni za zaglavlje;
- `has_origin_statement`;
- `eur1_suggested`;
- `is_authorized_exporter`;
- `is_combined`;
- `consumed_paths`;
- upozorenja i greške parsera.

### `PreparedInvoice`

Jedna logička faktura nakon deduplikacije:

- stabilni interni ključ;
- poslovni broj fakture ako je pouzdano utvrđen;
- pripadajuće stavke;
- per-faktura težine;
- partneri i valuta;
- izvorni fajlovi;
- potrebna korisnička odobrenja;
- predložena draft operacija.

### `ImportPlan`

Kompletan plan prije izmjene drafta:

- prihvaćene fakture;
- preskočeni duplikati;
- neuspjeli fajlovi;
- konflikti partnera, valute i zaglavlja;
- PE2/PE3/EUR1 zahtjevi;
- `ADD`, `REPLACE` ili `SKIP` operacije;
- očekivani broj stavki i ukupne težine;
- upozorenja koja korisnik mora vidjeti.

### `ImportApplyResult`

Rezultat primjene:

- broj dodatih, zamijenjenih i preskočenih stavki;
- obrađene fakture;
- konačne težine;
- primijenjene odluke;
- upozorenja;
- greške;
- tekst pogodan i za modal i za Agent chat.

## 7. Politika identiteta fakture

Redoslijed izvora identiteta:

1. broj koji je parser eksplicitno pronašao;
2. broj potvrđen kombinovanim rezultatom;
3. normalizovani naziv fajla samo ako prolazi sigurnu validaciju obrasca;
4. interni privremeni ključ za grupisanje, bez upisivanja lažnog poslovnog broja.

Pravila:

- proizvoljan naziv poput `scan_final_v2.pdf` ne postaje broj fakture;
- prikazni naziv može koristiti stem fajla, ali se ne mora upisati u `invoice_number`;
- sve stavke iste logičke fakture dobijaju isti pouzdani broj;
- `invoice_weights` koristi isti normalizovani ključ;
- ista imena fajlova iz različitih direktorijuma nisu automatski isti dokument;
- sličnost naziva je pomoćni signal, ne jedini dokaz;
- ponovni uvoz iste fakture mora proizvesti jasnu `REPLACE`, `SKIP` ili korisnički potvrđenu `ADD` odluku.

## 8. Deduplikacija i kombinovani fajlovi

Prioritet provjere:

1. `consumed_paths`;
2. normalizovana apsolutna putanja;
3. rezultat kombinovanog parsera;
4. pouzdan broj fakture;
5. sigurni fallback zasnovan na validiranom nazivu i tipu para.

Pravila:

- potrošeni fajl se ne obrađuje ponovo;
- kombinovani rezultat ima prednost nad njegovim pojedinačnim sastavnim fajlovima;
- deduplikacija ne smije ukloniti dvije različite fakture koje slučajno imaju sličan naziv;
- parser rezultat se ne kombinuje drugi put u završnom servisu;
- `REPLACE/EXTEND` uređuje postojeći draft, ne parser memoriju.

## 9. Politika partnera, valute i zaglavlja

### Partneri

- Prva prihvaćena faktura postavlja očekivanog pošiljaoca i primaoca ako ih draft nema.
- Kasnija faktura smije dopuniti prazno polje.
- Različit neprazan partner proizvodi konflikt prije izmjene drafta.
- Korisnik može odustati, preskočiti spornu fakturu ili eksplicitno nastaviti.
- Odluka i konačni rezultat moraju biti isti u ručnom i Agent toku.

### Valuta

- Prva pouzdana valuta postaje očekivana valuta batcha.
- Različite valute se ne smiju tiho sabirati kao isti iznos.
- Konflikt valute mora biti prikazan prije primjene.
- Ako je podržan nastavak sa više valuta, iznosi se ne objedinjuju bez eksplicitne konverzije i poznatog kursa.

### Ostala polja zaglavlja

Za svako polje treba definisati merge politiku:

- prvo pouzdano neprazno;
- dopuna samo praznog;
- posljednje potvrđeno;
- zbir;
- konflikt koji zahtijeva korisničku odluku.

Više rezultata ne smije nasumično prepisivati zaglavlje redoslijedom završetka workera.

## 10. Politika težina

Za svaku logičku fakturu:

1. Sačuvati postojeće pouzdane težine po stavkama.
2. Raspodjelu pokrenuti samo za nedostajuće ili nepotpune težine.
3. Koristiti `MassCalculator` i postojeće `weight_guards`.
4. Ne zaokruživati poslovne vrijednosti prije propisanog završnog prikaza.
5. Provjeriti:
   - masa nije negativna;
   - neto nije veće od bruto bez upozorenja;
   - zbir stavki odgovara ukupnoj masi fakture;
   - korekcija ostatka ne mijenja ukupan zbir;
   - težina jedne fakture ne prelazi na drugu.
6. Upisati `invoice_weights` za svaku prihvaćenu fakturu.
7. Tek nakon toga izračunati ukupne težine batcha.

Ako parser vrati samo bruto ili samo neto masu, rezultat mora sadržavati jasno upozorenje i ne smije izmišljati nedostajući podatak bez postojeće poslovne formule.

## 11. Politika povlastica i dokumenata porijekla

Za svaku logičku fakturu odrediti jedan tip odluke:

- PE2;
- PE3;
- EUR1/PE1;
- bez dijaloga.

Pravila:

- dijalog se prikazuje jednom po logičkoj fakturi, ne jednom po fizičkom fajlu;
- batch priprema sve zahtjeve prije izmjene drafta;
- potvrda korisnika je obavezna;
- Agent puna automatizacija ne smije zaobići potvrdu;
- odluke se primjenjuju samo na stavke pripadajuće fakture;
- odustajanje ne smije ostaviti djelimično primijenjene povlastice;
- odgođeni batch dijalozi ne smiju biti preskočeni.

## 12. Parcijalno uspješan batch

Parserska greška jednog fajla ne mora automatski odbaciti ispravne fakture, ali korisnik mora dobiti jasan izbor prije primjene:

- nastavi sa ispravnim fakturama;
- preskoči određenu fakturu;
- odustani od cijelog batcha.

Pravila:

- ako nema nijedne ispravne fakture, draft se ne mijenja;
- neuspjeli i preskočeni fajlovi ostaju u izvještaju;
- prihvaćeni dio se primjenjuje kao jedna atomska operacija;
- ručni i Agent tok moraju ponuditi iste poslovne izbore;
- Agent chat može prikazati detaljniji progres, ali odluka i rezultat ostaju isti.

## 13. Atomska primjena i Undo

Priprema plana ne mijenja draft.

Nakon svih odluka:

1. snimiti jednu Undo tačku;
2. sačuvati stanje potrebno za rollback;
3. primijeniti sve `ADD`, `REPLACE` i `SKIP` operacije;
4. primijeniti zaglavlje;
5. primijeniti težine i povlastice;
6. provjeriti invarijante;
7. potvrditi rezultat;
8. jednom osvježiti prikaz.

Ako dođe do neočekivane greške:

- vratiti draft na prethodno stanje;
- ne ostaviti djelimično izmijenjene `invoice_lines`;
- ne ostaviti djelimično izmijenjene `invoice_weights`;
- prikazati jasnu poruku na srpskom.

Ne miješati `draft.items` i `draft.invoice_lines`.

## 14. Thread i UI granice

- Parsiranje fajlova ostaje u worker threadu.
- Worker koristi privatnu `ImportService()` instancu.
- Worker ne otvara dijaloge.
- Qt widgeti i draft vezan za UI mijenjaju se isključivo u glavnom threadu.
- Redoslijed rezultata ne zavisi od redoslijeda završetka workera.
- Otkazivanje prije primjene ne mijenja draft.
- Zatvaranje aplikacije tokom obrade prati postojeću politiku sigurnog izlaza; ovaj projekat ne mijenja QThread lifecycle.
- Završno tabelarno osvježavanje koristi bulk update uz exception-safe vraćanje `blockSignals`, `updatesEnabled` i sorting stanja gdje je primjenjivo.

## 15. Performansna pravila

- Fajl se parsira samo jednom.
- Tarifna normalizacija se radi jednom po stavci.
- Težine se računaju jednom po fakturi.
- Tabela se ne učitava nakon svake pojedinačne fakture.
- Historijska validacija se pokreće jednom nakon uspješne primjene.
- Statusna traka se osvježava jednom završnim zbirnim podacima.
- Priprema većeg batcha ne smije blokirati UI ako sadrži teže kalkulacije.
- Logovi bilježe faze i trajanje bez ispisivanja osjetljivih podataka.

## 16. Višefazna implementacija

### Faza 0 — sigurnosna analiza

1. Pročitati `docs/CONTEXT.md`.
2. Provjeriti svježinu GitNexus indeksa.
3. Pokrenuti impact za:
   - `_on_import_finished`;
   - `_process_batch_records`;
   - `_on_all_completed`;
   - `_distribute_invoice_weights`;
   - `_check_partner_consistency`;
   - `_apply_import_result_to_header`;
   - `_is_same_combined_invoice`;
   - aktivni `_puna_auto_pipeline`.
4. Dopuniti ručnom pretragom jer je GitNexus indeks ranije bio degradiran.
5. Za HIGH/CRITICAL rezultat napraviti obavezni `project_rooms` zapis i prijaviti rizik korisniku.
6. Snimiti početno stanje testova i `git status`.

Izlaz: potvrđen blast radius, scope lock i lista aktivnih pozivalaca.

### Faza 1 — karakterizacioni i regresioni testovi

Prije promjene ponašanja napraviti testove koji dokumentuju trenutno i željeno stanje:

- pojedinačni PDF;
- pojedinačni Excel;
- kombinovani Excel+PDF;
- invoice+packing list;
- obrnuti redoslijed fajlova;
- više faktura;
- ponovljena ista faktura;
- različiti partneri;
- različite valute;
- broj fakture postoji/ne postoji;
- ukupne težine postoje, a težine stavki ne postoje;
- djelimične težine po stavkama;
- PE2/PE3/EUR1;
- parcijalno neuspješan batch;
- korisnik odustaje;
- Undo i rollback.

Izlaz: testovi koji mogu dokazati paritet ručnog i Agent toka.

### Faza 2 — neutralni adapteri

1. Uvesti `ImportCandidate`.
2. Napraviti adapter `ImportResult → ImportCandidate`.
3. Napraviti adapter Agent `FileItem → ImportCandidate`.
4. Ne mijenjati parser API.
5. Ne uvoditi zavisnost zajedničkog servisa prema Agent widgetima.

Izlaz: oba ulaza proizvode isti neutralni model.

### Faza 3 — servis pripreme

1. Deduplikacija i `consumed_paths`.
2. Stabilno sortiranje.
3. Identitet fakture.
4. Grupisanje fizičkih fajlova u logičke fakture.
5. Partner/valuta/header konflikti.
6. Normalizacija tarifa.
7. Priprema težina.
8. Priprema PE2/PE3/EUR1 zahtjeva.
9. Plan `ADD/REPLACE/SKIP`.

Izlaz: determinističan `ImportPlan` bez izmjene drafta.

### Faza 4 — korisničke odluke

1. Controller dobija potrebne odluke iz plana.
2. View prikazuje postojeće dijaloge.
3. Odgovori se vraćaju kontroleru.
4. Servis validira da su sve obavezne odluke prisutne.
5. Odustajanje završava bez izmjene drafta.

Izlaz: jedna poslovna politika uz dva dozvoljena kanala prikaza.

### Faza 5 — atomska primjena

1. Uvesti primjenu `ImportPlan` na draft.
2. Implementirati rollback.
3. Uvesti jednu Undo tačku.
4. Primijeniti težine, zaglavlje i povlastice.
5. Provjeriti invarijante nakon primjene.

Izlaz: jedan testabilan servisni ulaz za konačnu izmjenu drafta.

### Faza 6 — migracija ručnog pojedinačnog uvoza

`_on_import_finished()` postaje tanak orkestrator:

1. adapter;
2. priprema plana;
3. korisničke odluke;
4. primjena;
5. prikaz rezultata.

Postojeće metode mogu privremeno ostati kao kompatibilni wrapperi dok se svi pozivaoci ne prebace.

Izlaz: ručni pojedinačni uvoz koristi zajednički tok.

### Faza 7 — migracija ručnog grupnog uvoza

`_process_batch_records()` koristi isti servis. Parser worker i njegov thread model ostaju netaknuti.

Izlaz: pojedinačni i grupni ručni uvoz daju isti rezultat za isti skup faktura.

### Faza 8 — migracija Agent uvoza

Aktivni Agent tok:

1. pretvara završene `FileItem` zapise u kandidate;
2. poziva zajedničku pripremu;
3. prikazuje iste obavezne odluke;
4. primjenjuje isti plan;
5. ispisuje napredak i završni rezultat u chat.

Agent više ne čisti draft za svaku fakturu i ne sastavlja sopstveni paralelni završni tok.

Izlaz: Agent i ručni uvoz proizvode isti draft.

### Faza 9 — uklanjanje duplikovane logike

Tek nakon migracije svih aktivnih pozivalaca:

- ukloniti mrtvu ili dupliranu završnu obradu;
- ukloniti neiskorištene `combined_files`/`single_files` grane ako ih zajednički servis zamijeni;
- zadržati kompatibilne wrappere samo gdje ih aktivan pozivalac zahtijeva;
- ne dirati mrtve Agent metode samo zato što postoje, osim ako impact potvrdi da su bez pozivalaca i scope to dozvoli.

Izlaz: jedan izvor istine bez paralelne poslovne logike.

### Faza 10 — `dist_client`

1. Uporediti root i runtime kopiju.
2. Utvrditi da li se pogođeni fajl generiše, kopira ili kompajlira u `.pyd`.
3. Prenijeti samo potvrđene promjene.
4. Ne prepisivati namjerne frozen-path i `.pyd` razlike.
5. Ponoviti ciljane testove u runtime okruženju.

Izlaz: shipped Windows ponašanje jednako root ponašanju.

### Faza 11 — završna verifikacija

1. Pokrenuti ciljane testove.
2. Pokrenuti kompletan `pytest`.
3. Pokrenuti `py_compile`.
4. Pokrenuti offscreen Qt provjere.
5. Testirati pravim fakturama iz `najavauvoza/`.
6. Uvesti isti skup ručno i preko Agenta.
7. Serijalizovati i uporediti konačne draftove.
8. Pokrenuti `gitnexus_detect_changes()`.
9. Provjeriti da promjene ne prelaze dogovoreni scope.

Izlaz: dokaz funkcionalnog pariteta.

### Faza 12 — dokumentacija i commitovi

1. Ažurirati `docs/CONTEXT.md` samo konačnim ne-očiglednim odlukama.
2. Napisati agent report.
3. Grupisati commitove po logičkim cjelinama:
   - karakterizacioni testovi;
   - zajednički servis;
   - ručni pozivaoci;
   - Agent pozivalac;
   - runtime mirror i dokumentacija.
4. Ne koristiti `--no-verify`.
5. Osvježiti GitNexus indeks ako je zastario.

## 17. Testna matrica

| Slučaj | Očekivani rezultat |
| --- | --- |
| Jedan PDF | Iste stavke, zaglavlje i težine u oba toka |
| Jedan Excel | Isti draft i ista upozorenja |
| Excel+PDF par | Jedna logička faktura, bez duplikata |
| Invoice+packing list | Cijene i težine spojene u jednu fakturu |
| Obrnuti redoslijed para | Isti rezultat kao normalni redoslijed |
| Više faktura istog partnera | Sve prihvaćene i pravilno sabrane |
| Različit pošiljalac | Ista potvrda prije izmjene |
| Različit primalac | Ista potvrda prije izmjene |
| Različita valuta | Nema tihog sabiranja |
| Broj iz parsera | Broj ima prednost nad nazivom fajla |
| Siguran broj iz naziva | Kontrolisani fallback |
| Proizvoljan naziv fajla | Ne postaje poslovni broj |
| Ponovni uvoz | Jasna `REPLACE/SKIP/ADD` odluka |
| Težine samo na fakturi | Raspodijeljene na stavke |
| Težine već na stavkama | Sačuvane, bez nepotrebnog preračuna |
| Samo bruto ili samo neto | Upozorenje, bez izmišljanja podatka |
| PE2/PE3/EUR1 | Jedan dijalog po logičkoj fakturi |
| Parcijalno neuspješan batch | Korisnik bira nastavak ili odustajanje |
| Otkazivanje | Draft ostaje identičan |
| Greška tokom primjene | Potpun rollback |
| Undo | Jednim korakom vraća cijeli import |
| Agent puna automatizacija | Ne zaobilazi obavezne potvrde |
| Assembly/master lista | Postojeći podržani tok ostaje funkcionalan |
| Multi-draft podjela | Fakture i težine ostaju pravilno povezane |

## 18. Kriterijumi identičnog rezultata

Za isti početni draft, iste fajlove i iste korisničke odluke moraju biti identični:

- broj i redoslijed stavki;
- `invoice_number`;
- `tarifni_broj`;
- `naziv_robe`;
- količina i jedinica mjere;
- vrijednost i valuta;
- zemlja porijekla;
- povlastica i EUR1 broj;
- bruto/neto masa svake stavke;
- per-faktura `invoice_weights`;
- ukupne težine;
- pošiljalac i primalac;
- relevantna polja zaglavlja;
- upozorenja i status validacije;
- Undo rezultat.

Dozvoljene razlike:

- tekst i učestalost progress poruka;
- završna poruka u modalu ili Agent chatu;
- vizuelna prezentacija istog upozorenja.

## 19. Scope lock — šta se ne mijenja

- Specijalizovani parseri i njihove detekcije.
- Redoslijed ImportService parser pipeline-a.
- Format `InvoiceLine` polja.
- Pravila grupisanja naimenovanja.
- Tarifni fuzzy threshold.
- Historijsko tarifno učenje.
- XML builder.
- Vizuelni stil dijaloga.
- Agent LLM provider i fallback.
- QThread lifecycle politika.
- Baza podataka i migracije, osim ako test dokaže da je nova šema neophodna.
- Paralelizacija parsera kao zasebna performansna tema.

## 20. Rizici i zaštite

| Rizik | Zaštita |
| --- | --- |
| Dupliranje kombinovanih fajlova | `consumed_paths` + testovi oba redoslijeda |
| Pogrešna zamjena postojeće fakture | Pouzdan identitet + eksplicitna odluka |
| Miješanje partnera | Konflikt prije primjene |
| Miješanje valuta | Posebna validacija valute |
| Gubitak težina po stavkama | Čuvanje postojećih vrijednosti i per-faktura testovi |
| Djelimično izmijenjen draft | Dvostepena priprema i rollback |
| UI zamrzavanje | Worker za parsiranje i jedno bulk osvježavanje |
| Različit root i Windows runtime | Kontrolisani `dist_client` mirror |
| Regresija Agent pune automatizacije | Test aktivnog `_puna_auto_pipeline` toka |
| Zaobilaženje povlastice | Obavezna eksplicitna potvrda |
| Skriveni pozivaoci starih helpera | GitNexus + ručna pretraga |

## 21. Redoslijed commitova

Predložene logičke cjeline:

1. `test(import): pokrij paritet ručnog i agent uvoza`
2. `refactor(import): uvedi zajednički model i pripremu uvoza`
3. `refactor(import): uvedi atomsku primjenu plana na draft`
4. `refactor(faktura): prebaci ručni uvoz na zajednički tok`
5. `refactor(agent): prebaci agent uvoz na zajednički tok`
6. `chore(runtime): uskladi dist_client import tok`
7. `docs(import): dokumentuj jedinstveni radni tok`

Svaki commit mora imati ciljane testove i `Co-Authored-By` liniju.

## 22. Definicija završetka

Zadatak je završen tek kada:

- sva tri ulaza koriste isti servisni tok;
- nema paralelne poslovne obrade u View-u ili Agent kontroleru;
- isti dokumenti daju isti konačni draft;
- partneri, valuta, težine i povlastice koriste iste odluke;
- kombinovani fajlovi se ne dupliraju;
- ponovni uvoz ima determinističko ponašanje;
- Undo i rollback rade;
- root i `dist_client` ponašanje je usklađeno;
- ciljani i kompletni testovi prolaze;
- GitNexus detect changes potvrdi očekivani scope;
- konačne odluke budu upisane u `docs/CONTEXT.md`;
- agent report sadrži verifikaciju pravim fakturama.

