**Deklarant Pro — Korisničko uputstvo**  
   
 **Verzija:** 1.0 (Maj 2026)  
   
    
   
  **Za:** Operatere carinske deklaracije  
   
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANklEQVR4nO3OQQmAABRAsSfYxZq/lGeDGMACBrCCNxG2BFtmZquOAAD4i3Ot7mr/egIAwGvXA7GXBdccwx8KAAAAAElFTkSuQmCC)  
   
 **Sadržaj**  
1. [Pokretanje aplikacije](#anchor-1 "#anchor-1")  
2. [Uvoz fakture](#anchor-2 "#anchor-2")  
3. [Pregled uvezenih stavki](#anchor-3 "#anchor-3")  
4. [Naimenovanja](#anchor-4 "#anchor-4")  
5. [Zaglavlje deklaracije](#anchor-5 "#anchor-5")  
6. [XML export za Asycuda](#anchor-6 "#anchor-6")  
7. [Česti problemi  
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSPBCUZfDq7YGVDAgAU2QtIq6DIzW7UHAMBfHGt1V+fXEwAAXrseHCgGBJWaMWkAAAAASUVORK5CYII=)  
 **1. Pokretanje aplikacije**  
   
 Dvaput kliknite na ikonu **Deklarant Pro** na radnoj površini.  
   
 Kad  se aplikacija pokrene, provjerite da li je server uključen,tako što odete na admin zab i u meniju sa strane nađite “Bza podataka”,u polju sa desne strane imate veliko plavo dugme  **"** **Testira konekciju ** **"**.Kad ga kliknete u polju iznad “”Status” će se pojaviti “Spojen”.Ispod je zeleno dugme kojim osvježavamo ispis podataka koji se nalaze u bazi.![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OYQ1AABSAwY8JIIKoL4Z8Eoiggn9mu0twy8wc1RkAAH9xbdVa7V9PAAB47X4A9DIEIm50tIwAAAAASUVORK5CYII=)  
 **2. Uvoz fakture**  
 **Korak 1 — Odaberite tab "Faktura"**  
   
 Kliknite na tab **"Faktura"** na vrhu prozora.  
 **Korak 2 — Učitajte fakturu**  
   
 Kliknite na dugme **"Uvezi fakturu"** i odaberite PDF ili Excel fajl fakture.  
   
 Aplikacija automatski prepoznaje format fakture (Blagić, Leburic/Pekabesko, IMAMOGLU, Šumaprom i drugi). Ako je faktura u kombinovanom formatu (Excel + PDF), odaberite oba fajla istovremeno — aplikacija će ih sama spojiti.  
   
    
   
    
 **Korak 3 — Provjerite uvezene stavke**  
   
 Nakon uvoza vidjet ćete tabelu sa stavkama. Provjerite:](#anchor-7 "#anchor-7")  
- Nazive robe  
- Količine i težine  
- Cijene u EUR  
- Zemlja porijekla  
   
 Ako nešto nije ispravno, možete ručno ispraviti vrijednost dvostrukim klikom na ćeliju.  
 **Korak 4 — Povlastice (ako postoje)**  
   
 Ako faktura sadrži EUR.1 obrazac ili izjavu o porijeklu, aplikacija će automatski otvoriti dijalog za unos povlastica.  
- **EUR.1 obrazac** → odaberite zemlje i unesite broj obrasca  
- **Izjava o porijeklu na fakturi** → odaberite koje stavke imaju povlasticu (PE2)  
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSPBCUZfDq7YGVDAgAU2QtIq6DIzW7UHAMBfHGt1V+fXEwAAXrseHCgGBJWaMWkAAAAASUVORK5CYII=)  
 **3. Pregled uvezenih stavki**  
   
 U tabeli fakture svaka stavka prikazuje:  
   
 | | |  
   
 |-|-|  
   
 | **Kolona** |  **Opis** |  
   
 | Naziv robe | Opis artikla iz fakture |  
   
 | Šifra | Interni kod dobavljača |  
   
 | Kol. | Količina |  
   
 | JM | Jedinica mjere |  
   
 | Cijena | Cijena po JM u EUR |  
   
 | Ukupno | Ukupna vrijednost stavke |  
   
 | Zemlja | Zemlja porijekla |  
   
 | Povlastica | Vrsta tarifne povlastice (prazno = nema) |  
   
 | Tarifni br. | HS tarifni broj (automatski predložen) |  
   
    
 **Auto-popunjavanje tarifnih brojeva**  
   
 Kliknite na dugme **"Auto-popuni tarifne"** — aplikacija će automatski predložiti tarifne brojeve za stavke koje je vidjela ranije. Provjerite predložene brojeve i po potrebi ih ispravite.  
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OQQ2AQBAAsSHhiQMcoWp9ngBsYIEfIWkVdJuZs5oAAPiLe6+O6vp6AgDAa+sBhZgEOcyZTEcAAAAASUVORK5CYII=)  
   
    
   
    
 **4. Naimenovanja**  
   
 Tab **"Naimenovanja"** prikazuje grupisane stavke po tarifnom broju i zemlji porijekla — jedna naimenovanja = jedna pozicija u deklaraciji.  
 **Kreiranje naimenovanja**  
1. Kliknite na dugme **"Kreiraj naimenovanja"**  
2. Aplikacija automatski grupiše stavke i popunjava polja  
3. Prođite kroz svako naimenovanje i provjerite:  
- **Tarifni broj** (Rub. 33) — 8 cifara  
- **Zemlja porijekla** (Rub. 34)  
- **Povlastica** (Rub. 36) — ako postoji  
- **Bruto/neto težina** (Rub. 35)  
- **Statistička vrijednost** (Rub. 46)  
- **Priloženi dokumenti** (Rub. 44) — npr. EUR.1 broj  
 **Navigacija između naimenovanja**  
   
 Koristite strelice **"◀ Prethodno"** i   **"Sljedeće ▶"** ili kliknite direktno na broj u listi lijevo.  
 **Brisanje naimenovanja**  
   
 Odaberite naimenovanje i kliknite **"Obriši"**. Stavke iz obrisanog naimenovanja vraćaju se u neasignirane.  
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAM0lEQVR4nO3OUQmAABBAsaeIGMOoF8R0JrGCfyJsCbbMzFldAQDwF/dWrdXx9QQAgNf2B/NoAzRnuYaXAAAAAElFTkSuQmCC)  
 **5. Zaglavlje deklaracije**  
   
 Tab **"Zaglavlje"** sadrži opće podatke koji se odnose na cijelu deklaraciju.  
 **Obavezna polja**  
   
 | | | |  
   
 |-|-|-|  
   
 | **Polje** |  **Opis** |  **Primjer** |  
   
 | Rub. 2 — Pošiljalac | Naziv i adresa dobavljača | MASTER TOOLS d.o.o. |  
   
 | Rub. 8 — Primalac | Naziv i adresa uvoznika | FIRMA DOO, Sarajevo |  
   
 | Rub. 14 — Deklarant | Šifra deklaranta | prikazano automatski |  
   
 | Rub. 25 — Vid transporta | Kod vida prijevoza | 3 (drumski) |  
   
 | Rub. 20 — Uslovi isporuke | Incoterms + mjesto | CIF SARAJEVO |  
   
 | Rub. 22 — Valuta i iznos | Valuta i ukupna vrijednost | EUR / 18.500,00 |  
   
 | Rub. 31 — Oznaka | Opis robe ukratko | alati i pribor |  
   
    
   
    
   
    
 **Priloženi dokumenti (Rub. 44)**  
   
 U tabeli priloženih dokumenata dodajte sve dokumente koji prate pošiljku:  
- **FAKT** — broj fakture  
- **CMR** — broj tovarnog lista  
- **EUR1** — broj EUR.1 obrasca (ako postoji)  
- **SAN**,   **FITO**,   **VET** — sanitarni/fitosanitarni/veterinarski certifikati  
   
 Dvaput kliknite na red da dodate šifru i referencu dokumenta.  
 **Čuvanje zaglavlja**  
   
 Kliknite **"Sačuvaj"** — podaci se čuvaju lokalno i ostaju do sljedećeg uvoza.  
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSNBCkJfEnKYmFDBhAU2QtIq6DIzW7UHAMBfnGt1V8fXEwAAXrse/xMF7vZtYGoAAAAASUVORK5CYII=)  
 **6. XML export za Asycuda**  
   
 Kada su naimenovanja i zaglavlje popunjeni:  
1. Kliknite na dugme **"Export XML"**  
2. Odaberite folder za snimanje  
3. Aplikacija kreira XML fajl spreman za uvoz u Asycuda World  
 **Provjera prije exporta**  
   
 Aplikacija automatski provjerava ispravnost prije exporta i prikazuje upozorenja:  
- **Crvena** — greška koja blokira export (npr. nedostaje tarifni broj)  
- **Narančasta** — upozorenje (npr. neobično velika vrijednost)  
- **Plava** — informacija (npr. preporuka za grupiranje)  
   
 Greške je potrebno ispraviti prije exporta. Upozorenja možete ignorisati ako ste sigurni da su podaci ispravni.  
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSNhYEECHpD4OzrxgQU2QtIq6DIzR3UFAMBf3Gu1VefXEwAAXtsfSqoDWC0RgVEAAAAASUVORK5CYII=)  
 **7. Česti problemi**  
 **Aplikacija ne prepoznaje format fakture**  
   
 Prikazuje se poruka "Nepoznat format". Provjeri:  
- Je li fajl PDF ili Excel (.xlsx)?  
- Je li faktura od poznatog dobavljača (Blagić, Leburic, IMAMOGLU, Šumaprom)?  
- Za novi format fakture, obratite se administratoru  
 **Težine su nula ili pogrešne**  
   
 Aplikacija nije uspjela pročitati težine iz fakture. Ručno unesite ukupnu bruto i neto težinu u polje na dnu taba Faktura, pa kliknite **"Rasporedi težine"**.  
 **Tarifni broj nije predložen**  
   
 Aplikacija nema prethodnih podataka za taj artikal. Ručno unesite tarifni broj — aplikacija će ga zapamtiti za sljedeći put.  
 **XML export ne radi**  
   
 Provjeri:  
- Je li svako naimenovanje ima tarifni broj (8 cifara)?  
- Je li zaglavlje snimljeno?  
- Je li folder za export dostupan za pisanje?  
 **Aplikacija se ne može spojiti na bazu**  
   
 U donjem desnom uglu piše crveno. Provjeri:  
- Je li server (Ubuntu računar) uključen i dostupan na mreži?  
- Je li mrežni kabl/WiFi spojen?  
- Pozovite administratora ako problem ostaje.  
 ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANElEQVR4nO3OQQmAABRAsad4EFMY9fewnUms4E2ELcGWmTmrKwAA/uLeqrU6vp4AAPDa/gDzYgM3ZPdzEgAAAABJRU5ErkJggg==)  
 *Deklarant Pro — interna aplikacija. Za tehničku podršku obratite se administratoru.*  
