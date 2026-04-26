# Analiza poređenja XML fajlova  
**Predmet:** poređenje izvoza iz **ASYCUDA World** i izvoza iz **ASYCUDA_PRO**  
**Datum analize:** 2026-04-05

---

## Ulazni fajlovi

- **Referentni fajl (ASYCUDA World):** `ŠUMA-31.xml`
- **Testni fajl (ASYCUDA_PRO):** `ŠUMA-TEHNOGRIN-6-4-2026.xml`

---

## Sažetak

Poređenje pokazuje da XML koji generiše **ASYCUDA_PRO** trenutno **nije funkcionalno ekvivalentan** XML-u iz **ASYCUDA World** sistema.

Razlike nisu samo formalne ili kozmetičke. Problem je dublji: u više ključnih segmenata drugi fajl je:
- nepotpun,
- djelimično pogrešno mapiran,
- strukturno odstupan od referentnog modela,
- bez obračunskih i poreskih podataka koje referentni fajl sadrži.

Zbog toga se trenutni izlaz iz **ASYCUDA_PRO** ne može posmatrati kao vjerna replika World izvoza, već prije kao **parcijalno popunjen nacrt deklaracije**.

---

## Kratki zaključak

Najveći problemi u XML-u iz **ASYCUDA_PRO** su:

1. nedostaju važna zaglavlja deklaracije,
2. transportna polja nisu ispravno mapirana,
3. valuation dio je praktično nedovršen,
4. porezi po stavkama nisu obračunati/popunjeni,
5. Attached documents nisu preneseni kao u referentnom fajlu,
6. pojedina polja su prazna iako u referentnom izvozu imaju vrijednosti,
7. na nekim mjestima ni sama XML struktura nije potpuno ista kao u ASYCUDA World izvozu.

---

## Detaljna analiza

## 1. Opšti identitet deklaracije

### Referentni fajl (ASYCUDA World)
- `Total_number_of_forms = 11`
- `Total_number_of_items = 31`

### ASYCUDA_PRO
- `Total_number_of_forms = 12`
- `Total_number_of_items = 35`

### Zaključak
Ovo znači da fajlovi ne predstavljaju isti rezultat 1:1. Postoje samo dvije realne mogućnosti:

- aplikacija **ASYCUDA_PRO** drugačije grupiše robu i razbija stavke,
- ili ulazni podaci nisu bili identični.

U oba slučaja, za preciznu validaciju izvoza, ovo je ozbiljan signal da se logika kreiranja stavki razlikuje od World sistema.

### Procjena problema
**Visok prioritet**, jer broj stavki i formulara direktno utiče na cijelu deklaraciju.

---

## 2. Office / carinska ispostava

### Referentni fajl
Popunjeno:
- `Customs_clearance_office_code = BA097012`
- `Customs_Clearance_office_name = CI Bijeljina`

### ASYCUDA_PRO
Polja su prazna:
- `Customs_clearance_office_code = ""`
- `Customs_Clearance_office_name = ""`

### Zaključak
Ovo nije sitna razlika. Radi se o osnovnom identifikacionom podatku deklaracije. Ako ASYCUDA_PRO ne prenosi ured carinjenja, zaglavlje deklaracije je formalno nepotpuno.

### Mogući uzrok
- polja nisu mapirana iz baze,
- nisu vezana za UI,
- ili su prisutna u modelu, ali ne ulaze u XML serializer.

### Procjena problema
**Kritično.**

---

## 3. Podaci o deklarantu i referenci

### Referentni fajl
- `Declarant_code = 400338660009`
- `Declarant_name = DM-PROMET DOO ...`
- `Reference/Number = TEHNOGREEN-1821`

### ASYCUDA_PRO
- `Declarant_code = 400338660009`
- `Declarant_name = DM-PROMET DOO ...`
- `Reference/Number = SUMA642026`

### Zaključak
Ovaj dio djeluje funkcionalno popunjen. Razlika u referenci sama po sebi nije greška ako je drugačiji interni broj dokumenta.

### Procjena problema
**Nije problem**, osim ako referenca treba striktno pratiti neki poslovni obrazac.

---

## 4. General information / country segment

### Referentni fajl
Ima dodatno:
- `Country_of_origin_name = МНОГО`
- `Value_details = 290.0`

### ASYCUDA_PRO
- `Country_of_origin_name` je prazno
- `Value_details` je prazno

### Zaključak
Vidljivo je da ASYCUDA_PRO ne prenosi više opštih informacija koje postoje u World izvozu.

Posebno je bitno da je struktura drugačija:
- u World fajlu se `Country_of_origin_name` nalazi unutar `General_information -> Country`
- u PRO fajlu se pojavljuje na drugačijem nivou i ostaje prazno

To znači da problem vjerovatno nije samo “nedostaje vrijednost”, nego i da **struktura XML generatora nije potpuno usklađena sa referentnim modelom**.

### Procjena problema
**Srednji do visok prioritet.**

---

## 5. Transport segment

Ovdje se vidi jedna od ozbiljnijih grešaka.

### Referentni fajl
- `Departure_arrival_information/Identity = K92E231`
- `Departure_arrival_information/Nationality = BA`
- `Border_information/Identity = K92E231`
- `Border_information/Nationality = BA`
- `Inland_mode_of_transport = null`

### ASYCUDA_PRO
- `Departure_arrival_information/Identity = E25A456`
- `Departure_arrival_information/Nationality = E25A456`
- `Border_information/Identity = E25A456`
- `Border_information/Nationality = E25A456`
- `Inland_mode_of_transport = 30`

### Zaključak
Ovdje je vrlo vjerovatna **direktna greška mapiranja**:
- vrijednost identiteta vozila je upisana i u polje `Nationality`.

U referentnom fajlu nacionalnost je oznaka države (`BA`), što ima smisla.
U PRO fajlu je nacionalnost zapravo broj/oznaka vozila, što nema smisla.

### Dodatna razlika
Kod mjesta utovara:
- World:
  - `Place_of_loading/Code = BABIJ`
  - `Place_of_loading/Name = BIJELJINA`
- PRO:
  - oba polja prazna

### Procjena problema
**Kritično**, jer je ovo jasna logička greška u eksportu.

---

## 6. Finansijski segment

### Referentni fajl
Popunjeno:
- `Deffered_payment_reference = 97012170259`
- `Mode_of_payment = ПЛАЋАЊЕ`
- `Global_taxes = 0.0`
- `Totals_taxes = 3063.85`

### ASYCUDA_PRO
- `Deffered_payment_reference = prazno`
- `Mode_of_payment = PLACANJE`
- `Global_taxes = 0`
- `Totals_taxes = prazno`

### Zaključak
ASYCUDA_PRO evidentno ne generiše kompletan finansijski rezultat.

Najvažniji problem je što `Totals_taxes` ostaje prazan, dok referentni fajl ima konkretan obračun. To potvrđuje da exporter iz PRO aplikacije ne završava puni finansijski obračun u XML-u.

### Procjena problema
**Kritično.**

---

## 7. Valuation — globalni nivo

Ovo je vjerovatno najvažniji funkcionalni jaz.

### Referentni fajl
Sadrži kompletno popunjene podatke:
- `Total_cost = 290.0`
- `Total_CIF = 13707.89`
- `Gs_Invoice/Amount_national_currency = 13527.89`
- `Gs_Invoice/Amount_foreign_currency = 6916.7`
- `Currency_code = EUR`
- `Currency_rate = 1.95583`
- troškove prevoza, unutrašnjeg prevoza, osiguranja, odbitaka
- `Total_invoice = 6916.7`
- `Total_weight = 352.0`

### ASYCUDA_PRO
Ima samo djelimično:
- `Gross_weight = 266`
- `Total_cost = 605.0`
- `Total_CIF = prazno`
- `Gs_Invoice/Amount_national_currency = prazno`
- `Gs_Invoice/Amount_foreign_currency = prazno`
- `Total_invoice = prazno`
- `Total_weight = 253`

### Zaključak
Globalni valuation u PRO fajlu je **nedovršen**.

Troškovi prevoza/osiguranja postoje, ali centralne obračunske vrijednosti ne postoje:
- nema CIF-a,
- nema vrijednosti fakture,
- nema total invoice,
- nema pune finansijske veze između inputa i rezultata.

To znači da ili:
- obračun uopšte nije implementiran,
- ili postoji u aplikaciji, ali rezultat nije upisan u XML.

### Procjena problema
**Apsolutno kritično.**

---

## 8. Attached documents

### Referentni fajl
Sadrži više dokumenata:
- `ZUT`
- `OSI`
- `VOZ`
- `CMR`
- `FAK`
- `DIS`
- `DV1`
- `OST`

Uz to imaju reference poput:
- broj fakture,
- broj dispozicije,
- broj CMR-a,
- broj dokumenta osiguranja,
- prijava carinske vrijednosti itd.

### ASYCUDA_PRO
U prikazanom fajlu ovaj blok nije prisutan na isti način.

### Zaključak
To znači da PRO trenutno ne prenosi ili ne gradi attached documents segment kao referentni sistem.

Ako deklaracija u realnom radu zavisi od ovih podataka, ovo je ozbiljan funkcionalni nedostatak.

### Procjena problema
**Vrlo visok prioritet.**

---

## 9. Stavke robe — opšti utisak

### Referentni fajl
Za svaku stavku postoje:
- tarifni broj,
- opis,
- commercial description,
- zemlja porijekla,
- valuation item,
- izračunati iznosi po stavci,
- porezi po stavci,
- osnova i stopa,
- raspodjela troškova,
- statistička vrijednost,
- CIF po stavci,
- alpha coefficient.

### ASYCUDA_PRO
Za svaku stavku uglavnom postoje:
- tarifni broj,
- osnovni opis robe,
- zemlja porijekla,
- bruto/neto masa,
- invoice foreign currency,
- ali bez kompletiranog obračuna.

### Zaključak
ASYCUDA_PRO generiše dobar dio osnovne robne strukture, ali ne završava najvažniji dio: **obračunski i poreski sloj po stavci**.

To znači da exporter vjerovatno uzima podatke iz unosa robe, ali nema punu logiku za:
- raspodjelu troškova,
- obračun CIF-a,
- obračun dažbina,
- PDV osnovicu,
- finalne tax lines.

### Procjena problema
**Kritično.**

---

## 10. Taxation po stavkama

### Referentni fajl
Svaka stavka ima konkretno popunjeno:
- `Item_taxes_amount`
- `Taxation_line`
- `Duty_tax_code`
- `Duty_tax_Base`
- `Duty_tax_rate`
- `Duty_tax_amount`

Primjeri:
- `001`
- `090`
- stvarne osnovice i stvarni iznosi

### ASYCUDA_PRO
Polja su uglavnom prazna:
- `Item_taxes_amount = prazno`
- `Duty_tax_code = null`
- `Duty_tax_Base = prazno`
- `Duty_tax_rate = prazno`
- `Duty_tax_amount = prazno`

### Zaključak
Ovo je direktan dokaz da ASYCUDA_PRO trenutno **ne generiše funkcionalni poreski blok**.

To nije mala razlika. To je centralni dio carinskog XML-a.

### Procjena problema
**Apsolutno kritično.**

---

## 11. Value_item i raspodjela troškova po stavci

### Referentni fajl
Ima vrijednosti tipa:
- `0.87+0.53+0.24+0.00-0.24`
- `2.39+1.46+0.67+0.00-0.67`
- itd.

Dakle jasno se vidi:
- eksterni trošak,
- interni trošak,
- osiguranje,
- ostalo,
- odbitak

### ASYCUDA_PRO
`Value_item` je prazan.

### Zaključak
PRO ne izvozi raspodjelu troškova po stavci, iako globalni troškovi postoje. To potvrđuje da algoritam raspodjele ili ne postoji, ili rezultat nije povezan sa XML eksportom.

### Procjena problema
**Kritično.**

---

## 12. Valuation_item po stavci

### Referentni fajl
Svaka stavka ima:
- `Total_cost_itm`
- `Total_CIF_itm`
- `Statistical_value`
- `Alpha_coeficient_of_apportionment`
- invoice u nacionalnoj i stranoj valuti
- troškove po kategorijama
- deductions

### ASYCUDA_PRO
Velik broj tih polja je prazan:
- `Total_cost_itm = prazno`
- `Total_CIF_itm = prazno`
- `Statistical_value = prazno`
- `Alpha_coeficient_of_apportionment = prazno`

### Zaključak
Ovdje se vidi da ASYCUDA_PRO nema izvedenu punu valuation logiku po stavci.

### Procjena problema
**Kritično.**

---

## 13. Description_of_goods i Commercial_Description

### Referentni fajl
Često koristi bogatije tekstualne opise:
- tarifni opis
- komercijalni opis
- nekad više artikala u jednoj stavci

### ASYCUDA_PRO
Često koristi kraći, direktniji opis:
- naziv artikla
- ponekad skraćena lista artikala sa `(+n više)`

### Zaključak
Ovo samo po sebi nije nužno greška, ali pokazuje da PRO drugačije modeluje stavku robe i opis robe.
Ako cilj nije samo “proći validaciju”, nego i **imitirati World eksport**, onda i ovaj dio treba uskladiti.

### Procjena problema
**Srednji prioritet.**

---

## 14. Pakovanja i oznake pakovanja

### Referentni fajl
Često se pojavljuje:
- `PP`
- `Komad`

### ASYCUDA_PRO
Pojavljuje se:
- `PK`
- `Paket` / `Pakovanje`

### Zaključak
Ovo može biti:
- legitimna razlika zbog druge robe,
- ali i drugačiji šifrarnik ili drugo mapiranje vrste pakovanja.

Ako je cilj potpuna kompatibilnost sa World praksom, treba provjeriti da li ASYCUDA_PRO koristi ispravan kod iz istog šifrarnika.

### Procjena problema
**Srednji prioritet.**

---

## 15. Strukturna usklađenost XML-a

Najvažnije zapažanje nije samo što su neka polja prazna, već to što se vidi da **generator u ASYCUDA_PRO nije potpuno modelovan po istom XML obrascu kao referentni sistem**.

To se vidi po:
- različitim mjestima nekih polja,
- drugačijem stepenu popunjenosti,
- odsustvu određenih blokova,
- djelimičnom postojanju globalnih troškova bez per-item rezultata,
- postojanju osnovnog kostura, ali ne i pune deklarativne logike.

### Zaključak
Problem nije samo “dopuniti još 5-6 polja”.
Potrebna je ozbiljna revizija:
- modela podataka,
- mapiranja u XML,
- obračunskog sloja,
- i reda generisanja XML-a.

---

## Procjena stanja ASYCUDA_PRO izvoza

Na osnovu ova dva fajla, trenutni izvoz iz ASYCUDA_PRO može se opisati ovako:

### Ono što radi relativno dobro
- osnovna XML struktura postoji,
- osnovni identitet deklaracije postoji,
- trader/declarant segment je uglavnom popunjen,
- stavke robe postoje,
- tarife i osnovni opisi robe postoje,
- dio transporta postoji,
- globalni troškovi postoje u tragovima.

### Ono što ne radi kako treba
- office segment nije popunjen,
- transportna nacionalnost je pogrešno mapirana,
- mjesto utovara nije popunjeno,
- referentni attached documents nedostaju,
- globalni valuation nije završen,
- valuation po stavkama nije završen,
- tax lines nisu generisane,
- item taxes nisu generisane,
- CIF i statističke vrijednosti nisu generisane,
- raspodjela troškova po stavkama nije generisana.

---

## Preporučeni prioriteti ispravke

## Prioritet 1 — kritične greške
Ovo treba rješavati prvo:

1. **Office segment**
   - `Customs_clearance_office_code`
   - `Customs_Clearance_office_name`

2. **Transport mapiranje**
   - ispraviti `Nationality`
   - validirati `Identity`
   - validirati `Inland_mode_of_transport`

3. **Place_of_loading**
   - vratiti pravilno mapiranje koda i naziva mjesta utovara

4. **Financial totals**
   - `Totals_taxes`
   - deferred payment reference
   - total invoice

5. **Taxation**
   - generisanje `Item_taxes_amount`
   - generisanje `Taxation_line`
   - duty code, base, rate, amount

---

## Prioritet 2 — obračunska logika
Ovo je suštinski dio koji XML čini upotrebljivim:

1. **Global valuation**
   - `Total_CIF`
   - invoice values
   - total invoice
   - complete currency conversion

2. **Per-item valuation**
   - `Total_cost_itm`
   - `Total_CIF_itm`
   - `Statistical_value`
   - `Alpha_coeficient_of_apportionment`

3. **Raspodjela troškova po stavci**
   - `Value_item`
   - item external freight
   - item internal freight
   - insurance
   - other cost
   - deduction

---

## Prioritet 3 — dokumenti i formalna usklađenost
1. `Attached_documents`
2. formalna usklađenost putanja u XML stablu
3. standardizacija praznih vrijednosti (`<null/>` naspram prazno)
4. usklađivanje naziva i kodova pakovanja sa referentnim sistemom

---

## Preporučena razvojna strategija

Umjesto da se exporter “krpi” polje po polje, bolji pristup je:

### Faza 1 — zaključavanje referentnog modela
Napraviti interni dokument:
- XML putanja
- izvor podataka u aplikaciji
- obavezno / opciono
- pravilo izračuna

Dakle tabela tipa:

| XML putanja | Izvor u aplikaciji | Status | Napomena |
|---|---|---:|---|
| `Identification/Office_segment/Customs_clearance_office_code` | settings / deklaracija | FAIL | prazno |
| `Transport/Means_of_transport/.../Nationality` | vozilo.drzava | FAIL | trenutno mapira identity |
| `Financial/Amounts/Totals_taxes` | obračun dažbina | FAIL | nije generisano |

### Faza 2 — odvojiti obračun od serializer-a
Ako exporter direktno piše XML iz sirovih podataka forme, to je loše.

Bolje:
1. domain model deklaracije
2. obračunski servis
3. validated export DTO
4. XML serializer

Bez toga ćeš stalno imati polupopunjen XML.

### Faza 3 — golden file testovi
Za ovakve stvari moraš imati:
- referentni XML,
- generisani XML,
- automatsko poređenje po ključnim poljima.

Ne mora biti byte-to-byte identičan, ali mora biti:
- strukturalno validan,
- semantički ekvivalentan,
- obračunski kompletan.

---

## Moj iskren zaključak

Trenutni XML iz **ASYCUDA_PRO** pokazuje da je aplikacija došla do faze gdje:
- zna da izgradi osnovni kostur deklaracije,
- zna da formira robne stavke,
- ali još **ne završava deklaraciju kao carinski dokument**.

Drugim riječima:

**UI i osnovni model vjerovatno postoje, ali obračunsko-izvozni sloj još nije na nivou ozbiljne replike ASYCUDA World sistema.**

Najveći problem nije to što neka polja fale.  
Najveći problem je što **nedostaje cijeli sloj poslovne logike između unosa i finalnog XML-a**.

Bez tog sloja:
- XML izgleda “na mjestu”,
- ali nije stvarno završen.

---

## Konačna ocjena

### ASYCUDA_PRO export trenutno:
- **strukturalno:** djelimično ispravan
- **sadržajno:** nepotpun
- **obračunski:** ozbiljno nedovršen
- **kompatibilnost sa World logikom:** niska do srednja
- **spreman za vjeran World eksport:** ne još

---

## Završna preporuka

Ako želiš pravi napredak, nemoj sada popravljati nasumično pojedina polja.
Prvo definiši **kompletan export contract**:

1. šta XML mora sadržati,
2. iz kojih internih objekata to dolazi,
3. šta se računa,
4. kojim redom se računa,
5. tek onda serializer.

U suprotnom ćeš i dalje imati XML koji izgleda solidno na prvi pogled, ali je suštinski polovičan.

---
