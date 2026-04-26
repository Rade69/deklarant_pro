# Plan integracije PageIndex u postojeći Agent tab (`deklarant_pro`)

## 1. Cilj

Cilj nije da se postojeći RAG izbaci i zamijeni PageIndex-om, nego da se u postojeću arhitekturu doda **specijalizovani retrieval engine** za strukturisane dokumente.

U tvojoj aplikaciji to znači:

- postojeći agent ostaje
- konekcija na bazu ostaje
- postojeći RAG ostaje
- PageIndex se dodaje kao **drugi način pretrage i navigacije kroz dokumente**

Najzdraviji model za `deklarant_pro` je:

- **DB / klasični RAG** za pitanja nad bazom, istorijom i manje strukturisanim izvorima
- **PageIndex** za pravilnike, zakone, uputstva, višestranične PDF priloge i druge dokumente sa jasnom hijerarhijom
- **Hybrid mode** za slučajeve gdje treba spojiti dokument + bazu + aktivni kontekst deklaracije

---

## 2. Zašto ne rušiti postojeći RAG

Potpuna zamjena postojećeg RAG-a bila bi loša ideja iz tri razloga:

1. Već imaš implementiranu logiku i vezu sa bazom.
2. Veliki dio upita u ovoj aplikaciji nije dokument-first nego data-first.
3. PageIndex je najjači za strukturisane dokumente, ali nije univerzalno najbolji retrieval za sve vrste pitanja.

Zato je ispravan smjer:

**PageIndex kao dodatni engine, ne kao zamjena kompletnog sistema.**

---

## 3. Predloženi retrieval model

Uvesti `retrieval_router` koji će za svaki upit birati odgovarajući retrieval režim.

### 3.1 Režimi

#### A. `database`
Koristi se kada je pitanje primarno vezano za postojeće podatke u aplikaciji.

Primjeri:
- Koja je zadnja deklaracija za ovog klijenta?
- Koliko puta smo koristili ovu šifru?
- Prikaži prethodne naimenovane stavke.
- Na osnovu istorije predloži tarifni broj.

#### B. `vector_rag`
Koristi se za:
- opšta pitanja
- manje strukturisane dokumente
- pretragu kroz više raznih izvora
- brze odgovore iz baze znanja

#### C. `pageindex`
Koristi se za:
- zakone
- pravilnike
- uputstva
- tehničke priručnike
- višestranične fakture i priloge sa jasnom strukturom
- dokumente kod kojih je važan odnos poglavlje → član → stav → tačka → tabela

Primjeri:
- Gdje u pravilniku piše uslov za ovu proceduru?
- Šta kaže član X za ovu rubriku?
- Na kojoj strani fakture je Incoterms?
- Da li ovaj prilog sadrži zemlju porijekla?

#### D. `hybrid`
Koristi se kada treba spojiti više izvora.

Primjeri:
- Za ovu robu, šta kaže propis i šta smo ranije koristili?
- Na osnovu ovog PDF-a i naših ranijih unosa predloži šta ide u rubriku 44.
- Uporedi dokument sa istorijskim unosima i označi odstupanja.

---

## 4. Gdje se PageIndex uklapa u postojeći UI

Na osnovu postojećeg Agent taba, PageIndex se prirodno uklapa u već postojeći tok rada.

### 4.1 Upload panel
Nakon učitavanja dokumenta sistem može interno dodijeliti retrieval režim:

- `vector`
- `pageindex`
- `hybrid`

To može biti automatski, na osnovu tipa dokumenta.

Primjer:
- PDF pravilnik / zakon / uputstvo → `pageindex`
- veliki strukturisani PDF sa sekcijama i tabelama → `hybrid`
- kratki nestrukturisani dokument → `vector`
- Excel / XML → postojeći parser pipeline

### 4.2 Chat panel desno
Kada korisnik postavi pitanje o aktivnom dokumentu, agent može vratiti:

- odgovor
- referencu na poglavlje / član / sekciju
- broj strane
- eventualno nivo pouzdanosti

To povećava povjerenje jer korisnik vidi **na osnovu čega** je odgovor dobijen.

### 4.3 Režimi obrade
Postojeća tri moda mogu se zadržati i unaprijediti:

#### Analiza
Najbolji prvi korak za PageIndex.

- agent čita dokument
- navigira strukturu dokumenta
- izdvaja bitne informacije
- daje objašnjenja i reference
- ništa ne upisuje automatski

#### Uvezi u deklaraciju
- PageIndex pomaže da se pronađu relevantne vrijednosti
- vraćaju se kandidati za unos
- servis i korisnik potvrđuju finalni unos

#### Puna automatizacija
- PageIndex može pomoći retrieval dijelu
- ali konačne odluke moraju ići kroz validatore i poslovna pravila

---

## 5. Predložena tehnička arhitektura

Ne treba miješati svu logiku direktno u postojeći agent kod. Bolje je napraviti odvojene servise.

### 5.1 `retrieval_router`
Odlučuje koji retrieval ide na koji upit.

**Ulaz:**
- korisničko pitanje
- tip dokumenta
- aktivni tab / ekran
- aktivna deklaracija
- dostupni izvori

**Izlaz:**
- `database`
- `vector_rag`
- `pageindex`
- `hybrid`

### 5.2 `pageindex_service`
Zadužen za:
- obradu strukturisanih PDF-ova
- gradnju stabla dokumenta
- navigaciju kroz sekcije
- pretragu po hijerarhiji
- vraćanje relevantnih dijelova dokumenta

### 5.3 `document_structure_service`
Ako ne koristiš puni eksterni PageIndex odmah, ovaj servis može praviti internu, lakšu verziju:

- poglavlja
- podpoglavlja
- članove
- stavove
- tabele
- napomene
- reference na strane

### 5.4 `answer_composer`
Spaja sve izvore u jedan odgovor:

- baza podataka
- vector RAG
- PageIndex rezultat
- aktivni kontekst deklaracije
- korisničko pitanje

Vraća:
- finalni odgovor
- reference
- confidence
- eventualno strukturisani prijedlog za naredni korak

### 5.5 `extraction_service`
Za dokumente iz kojih želiš izvući konkretna polja:

- broj fakture
- datum
- valuta
- Incoterms
- bruto / neto masa
- zemlja porijekla
- opis robe

Vraća:
- vrijednost
- izvorni segment
- broj strane
- nivo pouzdanosti

---

## 6. Glavni use caseovi za `deklarant_pro`

### 6.1 Tumačenje propisa i pravilnika
Najbolji fit za PageIndex.

Tok:
1. Učitaju se pravilnici, zakoni i interna uputstva.
2. Za svaki dokument se gradi hijerarhijsko stablo.
3. Korisnik pita pitanje kroz desni panel.
4. Agent navigira kroz strukturu dokumenta.
5. Odgovor vraća uz referencu na član, stav, tačku i stranu.

Primjeri pitanja:
- Šta ide u ovu rubriku?
- Kada je obavezna ova šifra postupka?
- Koji dokument je potreban za ovaj slučaj?

### 6.2 Pomoć pri popunjavanju rubrika
PageIndex ne treba sam upisivati podatke, ali može pomoći korisniku.

Primjer:
- korisnik klikne rubriku 44
- pita šta ide tu u ovom slučaju
- sistem pronalazi relevantna pravila i interne upute
- vraća objašnjenje, uslove, izuzetke i referencu

### 6.3 Analiza priloženih PDF dokumenata
Idealno za:
- fakture
- packing liste
- transportne dokumente
- certifikate
- dozvole

Primjeri pitanja:
- Nađi broj fakture.
- Na kojoj strani je Incoterms?
- Da li dokument sadrži zemlju porijekla?
- Koja je ukupna vrijednost?

### 6.4 Contextual help u aplikaciji
PageIndex može postati izvor pomoći u okviru forme.

Primjeri:
- Zašto je ovo polje obavezno?
- Koji dokument nedostaje?
- Objasni ovu grešku.
- Na osnovu pravila, šta treba provjeriti?

### 6.5 Interna baza znanja za tim
Ako dokumentuješ internu metodologiju rada, PageIndex može služiti kao:
- onboarding pomoćnik
- interni proceduralni navigator
- knowledge assistant za operatere

---

## 7. Gdje PageIndex ne treba koristiti

Bitno je zadržati granicu između AI retrievala i poslovnog jezgra aplikacije.

PageIndex **ne treba** koristiti za:

- konačnu validaciju obaveznih polja
- obračune
- statusne tranzicije
- direktan upis u bazu bez provjere
- finalni izbor tarifnog broja bez servisne logike
- audit zaključke
- automatsko donošenje pravno osjetljivih odluka

Za to moraju ostati zaduženi:
- domain modeli
- validatori
- business services
- testirani workflow-i

Drugim riječima:

**PageIndex traži i objašnjava. Servisni sloj odlučuje i zapisuje.**

---

## 8. Predlog fazne implementacije

### Faza 1 — Propisi i uputstva
Najmanji rizik, a velika korist.

Scope:
- učitavanje ključnih PDF pravilnika i zakona
- izgradnja hijerarhijske strukture
- pitanja kroz chat panel
- odgovori sa referencama

Cilj:
- provjeriti da li korisnik brže dolazi do tačnog pravila

### Faza 2 — Dokumenti koje korisnik uploaduje
Scope:
- PageIndex nad fakturama i prilozima
- ekstrakcija ciljnih informacija
- source trace
- bez automatskog upisa

Cilj:
- pomoć pri čitanju i razumijevanju dokumenata

### Faza 3 — Hybrid retrieval
Scope:
- kombinacija baze + aktivne deklaracije + dokumenta + propisa
- bolji odgovori u agent panelu

Cilj:
- agent daje kontekstualno jače odgovore

### Faza 4 — Contextual help po rubrici
Scope:
- povezivanje polja u GUI-u sa odgovarajućim pravilima i internim metodologijama

Cilj:
- pomoć direktno u trenutku unosa

### Faza 5 — Poluautomatizovani prijedlozi
Scope:
- agent pronalazi vrijednosti i pravila
- servis vraća candidate vrijednosti
- korisnik potvrđuje

Cilj:
- ubrzanje rada bez gubitka kontrole

---

## 9. Praktična odluka: da li uključiti PageIndex

Da, ali pod jasnim uslovom:

**PageIndex kod tebe treba biti novi retrieval engine unutar postojećeg agenta, a ne novi paralelni agent i ne zamjena kompletne arhitekture.**

To znači:
- ne rušiti postojeći RAG
- ne dirati DB sloj bez potrebe
- ne miješati PageIndex sa validacijom i konačnim poslovnim odlukama
- koristiti ga tamo gdje dokument ima strukturu i gdje similarity retrieval često griješi

---

## 10. Konačna preporuka

Za `deklarant_pro` je najbolji sljedeći smjer:

1. Zadrži postojeći agent i postojeći RAG.
2. Dodaj `retrieval_router`.
3. Uvedi `pageindex_service` samo za strukturisane dokumente.
4. Kreni prvo sa pravilnicima i uputstvima.
5. Tek nakon toga proširi na fakture i druge priloge.
6. Sve finalne odluke i upise ostavi u postojećem servisnom sloju.

Najkraće:

**DB + RAG ostaju osnova. PageIndex ulazi kao precizniji dokumentni navigator.**

To je po meni realan, siguran i koristan put integracije.
