# ASYCUDA parity profil 2024–2026

## 1. Cilj

Ovaj dokument definiše empirijski profil ASYCUDA World XML-a i prijedlog kako
Deklarant Pro približiti ASYCUDA ponašanju bez preuzimanja uloge carinskog
servera. Profil je izveden iz historijskih XML fajlova, a preporuke su
upoređene sa aktivnim izvoznim tokom u
`exporters/asycuda_xml_builder.py`.

Cilj nije bajt-po-bajt identičan XML. Cilj je:

- uvoz u ASYCUDA bez strukturnih grešaka;
- što manje automatskih korekcija i upozorenja;
- isti obračun vrijednosti prije ASYCUDA provjere;
- tačne dopunske jedinice i broj obrazaca;
- jasna granica između bezbjedne automatizacije i prijedloga deklarantu.

## 2. Scope i zaštita podataka

Izvor je `H:\New folder\NOVA ASIKUDA`.

Analiza je strogo ograničena na period od 2024. godine:

- interni ASYCUDA datum ima prednost kada postoji;
- ako je interni datum prazan, koristi se pouzdani datum izmjene fajla;
- fajlovi prije 2024. nisu korišćeni za pravila;
- originalni XML fajlovi nisu mijenjani, kopirani ni commitovani;
- u repozitorij se upisuju samo agregirani rezultati, bez partnera, brojeva
  faktura i drugih poslovnih identifikatora.

## 3. Referentni skup

| Efektivna godina | Deklaracije | Naimenovanja | Jedinstvene tarife |
| --- | ---: | ---: | ---: |
| 2024 | 429 | 1.164 | 572 |
| 2025 | 662 | 1.805 | 763 |
| 2026 | 539 | 1.724 | 593 |
| **Ukupno** | **1.630** | **4.693** | **1.211 ukupno** |

Svih 1.630 fajlova se uspješno XML parsira. Uočeno je 245 jedinstvenih XML
elemenata.

### 3.1. Nivoi pouzdanosti

Arhiva sadrži mješavinu registrovanih, obračunatih i predobračunskih XML-ova.
Zato se dokazi moraju rangirati:

1. važeća službena tarifa i šifrarnici za tekuću godinu;
2. registrovan/obračunat XML iz 2026;
3. obračunat XML iz 2024–2026 sa istim stabilnim ishodom;
4. neobračunat historijski XML kao pomoćni signal;
5. bez dokaza — ne automatizovati.

Popunjene ukupne dažbine ima 1.108 fajlova; 1.082 imaju iznos različit od nule
i predstavljaju najkorisniji operativni podskup za obračunska pravila.

## 4. Dominantni poslovni profil

### 4.1. Vrste deklaracija i postupci

| Kombinacija | Broj deklaracija |
| --- | ---: |
| `IM / H / 4000 / 000` | 1.582 |
| `EX / A / 1000 / 000` | 27 |
| `IM / J / 7100 / 000` | 9 |
| `IM / H / 4071 / 000` | 6 |
| `EX / D / 3171 / 000` | 2 |
| `IM / H / 4000 / 2CT` | 2 |
| `IM / H / 4200 / 48C` | 1 |

Profil je veoma jak za redovni uvoz `IM/H/4000/000`, ali preporuke za izvoz,
skladištenje i posebne postupke imaju mali uzorak i zahtijevaju ručnu potvrdu.

### 4.2. Ostali dominantni podaci

- Carinska ispostava `BA097012 / CI Bijeljina`: 1.624 deklaracije.
- Unutrašnji način transporta `30`: 1.624 deklaracije.
- Valute: EUR je dominantan; prisutni su i USD, BAM i TRY.
- Najzastupljenija porijekla stavki: RS, CN, TR, MK, IT i DE.
- Broj naimenovanja po deklaraciji: ukupno 4.693; 935 deklaracija imaju jedno
  naimenovanje.

Ove frekvencije nisu dozvola za hardkodovanje. One služe za prioritizaciju
testova i podrazumijevanih vrijednosti koje korisnik može promijeniti.

## 5. Potvrđena ASYCUDA pravila

## 5.1. Broj obrazaca

Referentni obrazac je:

```text
broj_obrazaca = 1 + ceil((broj_naimenovanja - 1) / 3)
```

Primjeri iz arhive:

| Naimenovanja | Obrazaca |
| ---: | ---: |
| 1 | 1 |
| 2–4 | 2 |
| 5–7 | 3 |
| 8–10 | 4 |
| 51 | 18 |
| 53 | 19 |
| 63 | 22 |

Aktivni builder koristi `ceil(n_items / 3)`, što daje pogrešan rezultat za
više veličina deklaracije. To je direktno potvrđeno na BLAGIC-LOREN primjeru:
Deklarant Pro 18, ASYCUDA 19.

## 5.2. Ukupni troškovi

Potvrđena formula:

```text
Total_cost =
    external_freight
  + internal_freight
  + insurance
  + other_cost
  - deduction
```

Rezultat:

- poklapanje sa ASYCUDA: 1.626 od 1.629 testabilnih deklaracija;
- tri izuzetka imaju nekonzistentan `Total_cost`, ali CIF im i dalje slijedi
  potvrđeno pravilo; tretiraju se kao nacrti/ručne anomalije.

Aktivni builder odbitak sabira kao pozitivan trošak.

## 5.3. CIF vrijednost

Potvrđena formula:

```text
Total_CIF =
    invoice_amount_national
  + external_freight
  + insurance
  + other_cost
  - deduction
```

Unutrašnji prevoz ne ulazi u CIF.

Rezultat:

- poklapanje: 1.629 od 1.629 testabilnih deklaracija;
- sadašnja formula `invoice + external_freight` odstupa u 103 deklaracije.

BLAGIC-LOREN dokaz:

- Deklarant Pro CIF: 56.550,94;
- ASYCUDA CIF: 56.595,96;
- razlika: osiguranje `10` + ostalo `45` − odbitak `10` + korekcija vozarine
  `0,02`.

## 5.4. Raspodjela na stavke

U 1.547 od 1.630 deklaracija zbir `Total_CIF_itm` odgovara globalnom
`Total_CIF` unutar tolerancije za stavkovno zaokruživanje. Osamdeset dvije
deklaracije odstupaju i moraju se posebno analizirati prije promjene algoritma
raspodjele.

Siguran cilj:

- globalna formula mora biti identična ASYCUDA formuli;
- raspodjela se radi proporcionalno carinskoj/fakturnoj vrijednosti;
- posljednje naimenovanje dobija ostatak zaokruživanja, tako da zbir stavki
  tačno odgovara globalnoj vrijednosti;
- ne zaokruživati alfa koeficijent prije završnog obračuna.

## 5.5. Porezi

ASYCUDA je konačni autoritet za poreske stope, osnovice i iznose. U
referentnom skupu postoje šifre `001`, `090`, `020`, `050`, `036`, `034`,
`002`, `038` i druge stope.

Deklarant Pro ne treba popunjavati službene poreske linije kao konačnu istinu.
Treba:

- lokalno simulirati obračun za provjeru i upozorenje;
- ostaviti ASYCUDA da izvrši službeni obračun;
- porediti vraćeni ASYCUDA rezultat sa lokalnom procjenom.

## 6. Dopunske jedinice

Pronađeno je 18 ASYCUDA šifara dopunskih jedinica. Najčešće su:

- `KGD` — kilogram za obračun;
- `PCE` — broj komada;
- `KGM` — kilogram za statistiku;
- `MTK`, `LTD`, `LTR`, `NPR`, `MTQ` i druge specifične jedinice.

### 6.1. Stabilnost

Za 465 tarifa sa najmanje tri opažanja:

- 462 imaju najmanje 95% stabilan ishod;
- samo tri su ambivalentne;
- među 202 tarife prisutne u sve tri godine samo tri mijenjaju dominantnu
  jedinicu.

Dopunska jedinica je zato dobar kandidat za automatizaciju, ali uz godišnje
važenje.

### 6.2. Gap trenutne implementacije

Poređenje `get_supplementary_unit()` sa cijelim referentnim skupom:

- tačan dominantni ishod: 341 od 465 tarifa;
- pogrešan ishod: 124 tarife;
- pokrivena opažanja sa tačnim ishodom: 2.709 od 3.716.

Na obračunatom podskupu:

- tačno: 229 od 306 tarifa;
- pogrešno: 77 tarifa.

Na obračunatom 2026 podskupu:

- tačno: 81 od 110 tarifa;
- pogrešno: 29 tarifa.

Najvažniji uzroci:

1. `NAR` nije ispravan opšti ASYCUDA kod za komad; referentni rezultat je često
   `PCE`.
2. Fallback „poglavlja 01–24 → KGM“ popunjava jedinicu i kada ASYCUDA ostavlja
   polje prazno.
3. Sibling lookup po šestocifrenom prefiksu bira većinsku jedinicu i za tarifu
   čiji tačan podbroj nema tu jedinicu.
4. Nedostaju specifične šifre `NPR`, `KNI`, `KNE`, `KVP` i druge.

Primjeri visokog povjerenja:

| Tarifa | ASYCUDA | Trenutno | Opažanja |
| --- | --- | --- | ---: |
| 90321080 | PCE | NAR | 49 |
| 44152020 | PCE | NAR | 31 |
| 84143081 | PCE | NAR | 20 |
| 21069098 | prazno | LTR | 85 |
| 39269097 | prazno | NAR | 80 |
| 23099096 | prazno | KGM | 38 |
| 64029998 | NPR | NAR | 9 |
| 31021015 | KNI | KGM | 8 |
| 20011000 | KNE | KGM | 11 |

## 7. Tarifni opisi i Rub.31

Za 465 dovoljno zastupljenih tarifa:

- 445 imaju najmanje 95% stabilan `Description_of_goods`;
- 20 imaju više varijanti;
- `Commercial_Description` je odvojeno polje i u BLAGIC-LOREN paru ostaje
  identično nakon ASYCUDA provjere.

Preporučeni model:

- `Description_of_goods`: važeći službeni tarifni opis iz tekuće tarife;
- `Commercial_Description`: trgovački nazivi + faktura/rb, po postojećem
  Rub.31 builderu;
- historijski opis je dokaz i fallback, nikada autoritet iznad tekuće tarife;
- tekst poput „koristiti samo za razduženje započetih procedura“ mora postati
  blokirajuće ili najmanje HIGH upozorenje prije izvoza.

Arhiva sadrži i 2026 XML-ove u kojima je `Description_of_goods` trgovački tekst.
To potvrđuje da historijska većina nije dovoljna bez klasifikacije
obračunatog/registrovanog stanja.

## 8. Priloženi dokumenti

Najčešće prisustvo po deklaraciji:

| Šifra | Deklaracije | Udio |
| --- | ---: | ---: |
| DIS | 1.626 | 99,8% |
| N380 | 1.599 | 98,1% |
| DV1 | 1.587 | 97,4% |
| OST | 1.491 | 91,5% |
| PZT | 1.278 | 78,4% |
| VOZ | 916 | 56,2% |
| N730 | 781 | 47,9% |
| N852 | 595 | 36,5% |
| FTAP | 592 | 36,3% |
| DUIM | 294 | 18,0% |

### 8.1. Dokument nije funkcija samo tarife

Za tarife sa najmanje tri opažanja:

- samo tarifa: 56 od 465 kombinacija ima najmanje 95% stabilan skup;
- tarifa + porijeklo: 76 od 474;
- tarifa + porijeklo + povlastica: 122 od 421;
- dodavanje postupka ne rješava problem: 120 od 419.

Dokumenti zavise i od stvarne robe, certifikata, partnera, vrijednosti,
transporta, inspekcijskih pravila i korisničkih isprava.

Zato:

- univerzalne dokumente graditi deterministički iz stvarnih podataka;
- tarifne dokumente prikazati kao prijedlog sa brojem historijskih dokaza;
- `DUIM` i slične dokumente ne upisivati automatski samo zato što su ranije
  viđeni uz tarifu;
- nikad ne izmišljati broj/reference dokumenta;
- XML readiness mora blokirati obavezni dokument bez reference.

## 9. Način plaćanja

Historijski prikaz:

- `PLAĆANJE` i ćirilična varijanta: 1.589 deklaracija;
- `GOTOVINA` i ćirilična varijanta: 41 deklaracija.

Aktivni builder hardkoduje `PLAĆANJE`. BLAGIC-LOREN je ASYCUDA pretvorila u
`GOTOVINA`, ali arhiva pokazuje da `GOTOVINA` nije univerzalni default.

Preporuka:

- modelirati način plaćanja kao šifrirano polje u draftu;
- prikazni naziv generisati iz šifrarnika;
- ne zaključivati način plaćanja iz jednog XML para;
- template može predložiti prethodnu vrijednost istog uvoznika/postupka, uz
  obaveznu korisničku potvrdu kada dokaz nije jednoznačan.

## 10. Mase i broj pakovanja

- Zbir bruto masa stavki se poklapa sa globalnom bruto masom u 74 od 79
  testabilnih deklaracija.
- Globalna bruto masa je prazna u 1.551 XML-u, iako stavkovne mase postoje.
- Globalna neto masa je prazna u svih 1.630 XML-ova.
- Decimalne promjene poput `24.50 → 24.5` nisu poslovna razlika.

Deklarant Pro treba zadržati punu preciznost u modelu i generisati prihvatljiv
decimalni zapis. Ne treba namjerno brisati globalnu bruto masu samo da bi XML
ličio na ponovni ASYCUDA izvoz.

## 11. Arhitekturni gapovi u Deklarant Pro

Aktivni tok koristi:

```text
GUI/Agent
  → xml_readiness_service
  → exporters.asycuda_xml_builder.AsycudaXMLBuilder
  → XML
  → ASYCUDA World
```

`exporters/deklarant_xml_builder.py` je stara paralelna implementacija i nema
aktivne runtime pozivaoce. Njeno postojanje povećava rizik da buduća izmjena
završi u pogrešnom builderu.

Ključni gapovi:

1. pogrešna formula broja obrazaca;
2. odbitak se sabira u `Total_cost`;
3. CIF ne uključuje osiguranje, ostalo i odbitak;
4. strana vozarina se u dijelu header toka može konvertovati dvaput;
5. raspodjela troškova zaokružuje svaku stavku bez eksplicitnog remainder
   reconciliation koraka;
6. dopunske jedinice koriste agresivne i dokazano netačne fallbacke;
7. način plaćanja je hardkodovan;
8. historijski dokumenti nemaju dovoljno strogu podjelu na automatsko pravilo
   i informativni prijedlog;
9. dva buildera predstavljaju drift rizik;
10. parity testovi ne koriste agregirani 2024–2026 referentni profil.

## 12. Predloženi ciljni dizajn

## 12.1. `AsycudaParityService`

Novi servis treba biti čist business sloj bez Qt zavisnosti:

```text
services/asycuda_parity/
├── profile_models.py
├── valuation_rules.py
├── supplementary_unit_rules.py
├── document_evidence_service.py
├── parity_validator.py
└── reference_repository.py
```

Odgovornosti:

- računanje potvrđenih formula;
- provjera XML-a prije izvoza;
- evidence-based prijedlozi;
- verzionisanje pravila po godini;
- generisanje strukturisanih nalaza za GUI i agenta.

## 12.2. Lokalna agregirana baza

Ne indeksirati sirove XML sadržaje u aplikacijsku bazu. Čuvati samo agregate:

```text
asycuda_tariff_unit_evidence
  tariff_code, year, unit_code, observations, confidence, source_tier

asycuda_tariff_description_evidence
  tariff_code, year, normalized_description, observations, confidence

asycuda_document_evidence
  tariff_code, origin, preference, procedure, document_code,
  observations, confidence, auto_applicable

asycuda_parity_profile_version
  profile_id, min_year, max_year, generated_at, source_count, checksum
```

Sirovi brojevi faktura, partneri i reference dokumenata ne smiju biti dio
agregirane baze niti LLM konteksta.

## 12.3. Pravilo odlučivanja

```text
službeni šifrarnik tekuće godine
  > stabilan obračunati 2026 dokaz
  > stabilan višegodišnji dokaz
  > historijski prijedlog
  > bez automatske izmjene
```

Minimalni prag za automatsku dopunsku jedinicu:

- najmanje 3 obračunata opažanja;
- najmanje 95% isti ishod;
- nema konflikta sa službenom tarifom tekuće godine.

Dokumenti ostaju prijedlog osim univerzalnih i eksplicitno kodiranih službenih
pravila.

## 13. Plan realizacije

### P0 — obračunska i strukturna tačnost

1. Ispraviti broj obrazaca.
2. Ispraviti znak odbitka u `Total_cost`.
3. Ispraviti globalni i stavkovni CIF.
4. Ukloniti mogućnost dvostruke konverzije strane vozarine.
5. Dodati remainder reconciliation za raspodjelu troškova.
6. Dodati regresioni test BLAGIC-LOREN prije/poslije ASYCUDA.

Prihvatni kriterij:

- formule prolaze na svih 1.629 testabilnih referentnih deklaracija, osim
  dokumentovana tri anomalna `Total_cost` fajla;
- zbir stavkovnog CIF-a jednak je globalnom CIF-u;
- broj obrazaca odgovara referentnoj formuli za 1–99 stavki.

### P1 — dopunske jedinice

1. Ukinuti opšti fallback poglavlja 01–24 → KGM.
2. Zamijeniti NAR/PCE mapiranje prema ASYCUDA šifrarniku.
3. Tačan tarifni podbroj mora imati prednost nad sibling većinom.
4. Dodati nedostajuće jedinice i njihove količinske izvore.
5. Uvesti verzionisanu evidence tabelu.

Prihvatni kriterij:

- najmanje 95% ponderisane tačnosti na obračunatom 2026 referentnom podskupu;
- ambivalentne tarife ostaju prazne i prikazuju upozorenje.

### P2 — tarifni opisi i zastarjele tarife

1. Tekuća tarifa ostaje primarni izvor.
2. ASYCUDA historijski opis služi za parity provjeru.
3. Uvesti status važeća/ograničena/ukinuta tarifa.
4. Blokirati tarifu koja je samo za razduženje ranije procedure.

### P3 — dokumenti

1. Razdvojiti univerzalne, službeno uslovne i historijski viđene dokumente.
2. Prikazati dokaz: broj opažanja, godine i kontekst.
3. Automatski upis dozvoliti samo službenom pravilu.
4. Reference ostaju korisnički ili dokumentom potvrđene.

### P4 — način plaćanja i ostali šifrarnici

1. Ukloniti hardkodovani prikaz.
2. Uvesti šifrirano draft polje i šifrarnik.
3. Dodati template prijedlog uz potvrdu.

### P5 — kontinuirani parity testovi

1. Svaki novi par Deklarant Pro/ASYCUDA dodati u privatni read-only corpus.
2. Regresioni testovi koriste anonimizovane agregate i posebno odobrene
   fixture fajlove.
3. Mjeriti:
   - strukturnu prihvatljivost;
   - broj ASYCUDA korekcija;
   - CIF i troškovni delta;
   - tačnost dopunskih jedinica;
   - broj upozorenja o dokumentima;
   - broj ručnih izmjena poslije importa.

## 14. Šta ne treba pokušavati

- Ne klonirati ASYCUDA poreski engine kao službeni autoritet.
- Ne automatski dodavati dokument samo zato što je čest uz tarifu.
- Ne učiti reference dokumenata, partnere ili brojeve faktura.
- Ne koristiti stariji XML iznad tekuće službene tarife.
- Ne optimizovati bajt-po-bajt formatiranje kada su vrijednosti semantički
  jednake.
- Ne popunjavati nepoznatu dopunsku jedinicu agresivnim fallbackom.

## 15. Preporučeni cilj

Realističan visoki nivo usklađenosti:

- 100% strukturno prihvatljiv XML;
- 100% poklapanje potvrđene globalne CIF formule;
- tačan broj obrazaca;
- najmanje 95% tačnost automatskih dopunskih jedinica uz fail-safe prazno
  polje za nejasne slučajeve;
- službeni opis i upozorenje za nevažeću tarifu;
- dokumenti kao dokazani prijedlozi, ne nekontrolisana automatika;
- ASYCUDA ostaje konačni autoritet za poreze i registraciju.

To Deklarant Pro približava ASYCUDA ponašanju bez stvaranja lažne sigurnosti da
desktop aplikacija može zamijeniti službeni carinski sistem.
