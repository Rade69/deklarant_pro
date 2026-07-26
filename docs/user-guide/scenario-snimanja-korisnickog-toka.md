# Scenario snimanja korisničkog toka

## Cilj

Snimiti jedan kompletan i realan tok izrade deklaracije u aplikaciji Deklarant Pro.
Snimak će poslužiti za izradu korisničkog uputstva sa slikama ekrana, opisima
koraka, očekivanim rezultatima i rješenjima čestih problema.

## Priprema prije snimanja

- Koristiti testnu ili anonimizovanu fakturu.
- Pripremiti sve povezane PDF, Excel, XML i druge dokumente.
- Provjeriti da aplikacija ima vezu sa bazom podataka.
- Zatvoriti prozore koji mogu prikazati lozinke, API ključeve ili sadržaj `.env` fajlova.
- Po mogućnosti snimati cijeli prozor aplikacije u rezoluciji najmanje 1920 × 1080.
- Tokom rada kratko objasniti zašto se izvršava važnija radnja.

## Glavni scenario

| Korak | Radnja | Šta treba biti vidljivo na snimku |
| --- | --- | --- |
| 1 | Pokrenuti aplikaciju | Glavni prozor i uspješno učitane kartice |
| 2 | Otvoriti karticu **Faktura** | Početno stanje toolbara i prazne tabele |
| 3 | Uvesti fakturu | Izbor dokumenta, obrada i rezultat uvoza |
| 4 | Pregledati uvezene stavke | Broj stavki, nazivi, količine, iznosi, mase i zemlje |
| 5 | Ispraviti jednu stavku ako je potrebno | Izmjena polja i način potvrde izmjene |
| 6 | Pokrenuti **Auto-popuni** | Prijedlozi tarifa, izvor i pouzdanost prijedloga |
| 7 | Provjeriti porijeklo i povlastice | Zemlja porijekla, PE1/PE2/PE3 ili EUR.1 dijalog |
| 8 | Izračunati ili rasporediti mase | Unos ukupnog bruto/neto iznosa i rezultat raspodjele |
| 9 | Pokrenuti završnu provjeru fakture | Poruka validacije i eventualno označene greške |
| 10 | Kreirati naimenovanja | Broj kreiranih naimenovanja i prelazak na sljedeću karticu |
| 11 | Pregledati karticu **Naimenovanja** | Navigacija, Rub. 31, tarifa, mase i priložene isprave |
| 12 | Sačuvati nacrt ili poništiti izmjenu | Položaj i funkcija dugmadi za nacrt |
| 13 | Otvoriti karticu **Zaglavlje** | Pošiljalac, primalac, deklarant i podaci deklaracije |
| 14 | Dopuniti zaglavlje | Obavezna polja, dokumenti i završna provjera |
| 15 | Izvesti ASYCUDA XML | Izbor lokacije, rezultat izvoza i završna poruka |
| 16 | Po potrebi izvesti PDF ili Excel | Izbor vrste izvještaja i kreirani dokument |

## Dodatne situacije koje vrijedi snimiti

Ako se prirodno pojave tokom rada, zabilježiti i:

- stavku bez pronađenog tarifnog broja;
- upozorenje zbog nedostupne baze podataka;
- neusklađene bruto i neto mase;
- razliku između automatskog prijedloga i ručne odluke deklaranta;
- odustajanje od dijaloga bez primjene promjena;
- poništavanje i ponovno izvršavanje izmjene;
- poruku koja sprečava izvoz dok podaci nisu kompletni;
- uvoz više povezanih dokumenata za istu fakturu.

Nije potrebno namjerno izazivati greške koje bi mogle oštetiti postojeći nacrt.

## Slike koje obavezno treba izdvojiti

Iz snimka ili posebnim snimanjem ekrana sačuvati najmanje:

1. početni ekran kartice Faktura;
2. uspješno uvezenu fakturu;
3. dijalog tarifnih prijedloga;
4. rezultat validacije;
5. kreirana naimenovanja;
6. popunjeno Zaglavlje;
7. završnu provjeru;
8. uspješan XML izvoz.

## Pravila privatnosti

Na snimku i slikama ne prikazivati:

- lozinke, API ključeve i sadržaj `.env` fajlova;
- pune pristupne podatke baze;
- povjerljive podatke stvarnih klijenata ako nemamo dozvolu za njihovu upotrebu;
- druge aplikacije, poruke ili dokumente koji nisu dio scenarija.

Osjetljivi podaci na korisnim kadrovima mogu se naknadno zamagliti prije
objavljivanja uputstva.

## Predaja materijala

Snimak i slike smjestiti u privremeni folder, na primjer:

```text
docs/user-guide/source-material/
├── kompletan-tok.mp4
├── biljeske.md
└── screenshots/
```

U `biljeske.md` je dovoljno navesti:

- koja je faktura korišćena;
- koji tip deklaracije je napravljen;
- korake koji odstupaju od uobičajenog rada;
- mjesta na kojima je korisniku potrebno dodatno objašnjenje.

Izvorni materijal ne treba trajno commitovati ako sadrži stvarne poslovne podatke.
