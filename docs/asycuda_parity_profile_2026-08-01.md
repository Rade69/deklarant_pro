# ASYCUDA parity profil — početni referentni skup

## Datum

2026-08-01

## Svrha

Ovaj profil bilježi šta je primijećeno poređenjem XML-a koji generiše
Deklarant Pro i XML-ova izvučenih iz ASYCUDA World aplikacije. Cilj nije
refaktor UI-a, nego precizno odvajanje:

- šta Deklarant Pro već radi dovoljno dobro;
- šta ASYCUDA sama normalizuje nakon uvoza;
- šta treba ciljano uskladiti u XML/export/DV1/PZT logici.

## Analizirani XML fajlovi

| Fajl | Izvor | Uloga u profilu |
| --- | --- | --- |
| `proba-refaktor.xml` | Deklarant Pro export | Probni XML nakon Faktura refaktora |
| `proba-refaktor-asycuda-provjera.xml` | ASYCUDA nakon provjere istog XML-a | Direktan par za semantičko poređenje |
| `BLAGIĆ-LOREN-17-7.xml` | ASYCUDA export | Referentni ASYCUDA primjer sa PE2/DUIM obrascem |
| `MEDIKO-20-7.xml` | ASYCUDA export | Referentni ASYCUDA primjer sa PE1, DUIM i kontrolnim dokumentima |

## Kratki zbir nalaza

| Tema | Nalaz |
| --- | --- |
| XML validnost | Svi pregledani XML fajlovi su well-formed |
| Tarifni brojevi | ASYCUDA XML koristi 8-cifrene tarifne brojeve; probni Deklarant Pro export je takođe bio 8-cifren |
| Broj stavki | Probni par ostaje 39/39; nema gubitka stavki |
| Mase | Bruto/neto zbir po stavkama se poklapa sa totalima u probnom paru |
| Rub.31 | Nema opisa preko 280 karaktera u analiziranom skupu |
| Dokumenti | ASYCUDA širi dio header dokumenata na item-level dokumente, posebno PE1/PE2/DUIM |
| CIF/troškovi | Probni par pokazuje razliku u `Total_CIF` i `Total_cost`; to je prioritet za poseban audit |
| Broj obrazaca | ASYCUDA koristi obrazac koji izgleda kao `1 + ceil(broj_stavki / 3)` |

## Direktno poređenje probnog para

| Polje | Deklarant Pro | ASYCUDA nakon provjere | Status |
| --- | ---: | ---: | --- |
| Stavki | 39 | 39 | OK |
| Ukupna faktura | 18,935.31 | 18,935.31 | OK |
| Bruto masa | 2,201.94 | 2,201.94 | OK |
| Neto zbir po stavkama | 2,103.98 | 2,103.98 | OK |
| Broj obrazaca | 13 | 14 | Razlika |
| `Total_cost` | 983.00 | 904.99 | Razlika |
| `Total_CIF` | 37,434.25 | 37,479.24 | Razlika |
| Prateći dokumenti | 11 | 29 | ASYCUDA širenje |

Razlika `Total_CIF` iznosi 44.99. Ovo ne izgleda kao posljedica Faktura
refaktora, ali može uticati na carinsku osnovicu i treba ga istražiti prije
daljeg približavanja ASYCUDA-i.

## Pravilo za broj obrazaca

Iz analiziranih ASYCUDA fajlova:

| Fajl | Stavki | ASYCUDA obrazaca | `1 + ceil(stavki / 3)` |
| --- | ---: | ---: | ---: |
| `proba-refaktor-asycuda-provjera.xml` | 39 | 14 | 14 |
| `BLAGIĆ-LOREN-17-7.xml` | 34 | 12 | 13? |
| `MEDIKO-20-7.xml` | 27 | 10 | 10 |

Napomena: dva od tri primjera direktno potvrđuju `1 + ceil(stavki / 3)`.
`BLAGIĆ-LOREN-17-7.xml` ima 34 stavke i 12 obrazaca, što sugeriše da ASYCUDA
može imati dodatno pravilo rasporeda ili da broj obrazaca ne zavisi isključivo
od ukupnog broja stavki. Ne uvoditi automatsku promjenu bez dodatne provjere
na većem referentnom skupu.

## Rub.31 / opis robe

ASYCUDA nakon provjere često zamijeni ili dopuni `Description_of_goods`
službenim tarifnim opisom. Primjeri iz referentnih XML-ova:

- `-- ostali`
- `brtve,podlošci i ostali proizvodi za brtvljenje`
- `uređaji za filtriranje ili pročišćavanje zraka`
- `- - - ostalo`

Zaključak: Deklarant Pro treba nastaviti da Rub.31 gradi iz tarifne baze, uz
odvojeno čuvanje trgovačkih naziva u `Commercial_Description`. Ne treba vraćati
logiku koja Rub.31 primarno gradi iz komercijalnih naziva fakture.

## Prateći dokumenti

ASYCUDA u referentnim fajlovima radi širenje dokumenata:

- header dokumenti postoje jednom na deklaraciji;
- dio dokumenata se ponavlja po stavkama kao item-level dokument;
- `PE1`, `PE2` i `DUIM` su najčešći kandidati za ponavljanje.

Primjeri:

- `MEDIKO-20-7.xml`: 27 stavki, 36 dokumenata, od toga `PE1` 22 puta i `DUIM` 4 puta.
- `BLAGIĆ-LOREN-17-7.xml`: 34 stavke, 41 dokument, mnogo ponavljanja `PE2` i `DUIM`.
- Probni par: Deklarant Pro 11 dokumenata, ASYCUDA nakon provjere 29 dokumenata.

Zaključak: Deklarant Pro ne mora nužno unaprijed generisati identičan broj
item-level dokumenata ako ASYCUDA to sama proširuje. Ipak, treba osigurati da
svi header dokumenti koje ASYCUDA očekuje postoje i da su brojevi čisti.

## PE1 zapis sa navodnikom

U probnom Deklarant Pro exportu uočen je zapis:

```text
123456 | EUR1A9781904 | " | PE1EUR1A9781906 | PE1A9781905
```

Korisnik je potvrdio da je ovo najvjerovatnije greška pri unosu. Zato se ovaj
zapis ne tretira kao sistemska greška XML exporta. Ipak, ako se isti obrazac
ponovi na novom čistom unosu, otvoriti poseban bugfix za normalizaciju brojeva
PE1/PE2 dokumenata prije XML exporta.

## CIF i zavisni troškovi

Ovo je najvažniji otvoreni nalaz.

U direktnom probnom paru:

| Polje | Deklarant Pro | ASYCUDA |
| --- | ---: | ---: |
| `Total_cost` | 983.00 | 904.99 |
| `Total_CIF` | 37,434.25 | 37,479.24 |
| Zbir `Total_CIF_itm` | 37,434.24 | 37,479.22 |

Razlika nije samo formatiranje. Potreban je poseban audit formule i izvora:

- Rb.12 / ukupni troškovi;
- Rb.46 / vrijednost po stavci;
- Rb.47 / osnovice i dažbine;
- DV1/PZT troškovi;
- raspodjela zavisnih troškova po stavkama;
- kurs i eventualno zaokruživanje.

## Prioriteti za dalje

### P1 — CIF / zavisni troškovi audit

Napraviti ciljanu provjeru za jedan mali par XML-ova gdje imamo:

- Deklarant Pro export;
- ASYCUDA export nakon provjere;
- poznat unos PZT/DV1/troškova.

Cilj: tačno locirati gdje nastaje razlika u `Total_cost` i `Total_CIF`.

### P1 — Broj obrazaca

Na većem ASYCUDA referentnom skupu provjeriti formulu za
`Total_number_of_forms`. Trenutno imamo indikaciju da formula nije potpuno
trivijalna, jer 34 stavke daju 12 obrazaca u jednom referentnom primjeru.

### P2 — Dokumenti po stavkama

Mapirati kada ASYCUDA automatski širi `PE1`, `PE2`, `DUIM` i druge dokumente
na stavke. Ne popravljati naslijepo; prvo prikupiti pravila iz većeg skupa.

### P2 — Opisi robe

Uporediti Deklarant Pro tarifne opise sa ASYCUDA opisima za česte tarife.
Ako razlike dolaze iz lokalne tarifne baze, ažurirati bazu ili lookup strategiju,
ne UI.

### P3 — Validacioni izvještaj prije XML exporta

Dodati kasnije pre-export provjeru koja upozorava deklaranta na:

- sumnjive znakove u brojevima dokumenata;
- prazne ili preduge Rub.31 opise;
- tarifne brojeve koji nisu 8 cifara;
- CIF/trošak koji ne prati očekivani obrazac.

## Šta NE raditi sada

- Ne otvarati novi veliki Faktura UI refactor dok XML parity nalaz nije jasan.
- Ne mijenjati poslovnu logiku CIF-a bez dokaznog para i ručnog obračuna.
- Ne forsirati item-level dokumente da budu identični ASYCUDA-i prije nego se
utvrdi koja pravila ASYCUDA sama primjenjuje.
- Ne tretirati potvrđenu grešku ručnog unosa PE1 broja kao sistemski bug.

## Zaključak

Faktura refaktor je prošao praktičan XML/ASYCUDA smoke test: stavke, mase,
tarife, povlastice i ključna polja nisu pokazali očiglednu regresiju. Sljedeći
rad treba prebaciti sa UI refaktora na ASYCUDA parity oblast, prvenstveno
CIF/zavisne troškove i pravila dokumentacije po stavkama.
