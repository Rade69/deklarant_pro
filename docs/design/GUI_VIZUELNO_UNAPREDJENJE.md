# Deklarant Pro — prijedlog vizuelnog unapređenja

## Status dokumenta

Ovaj dokument definiše predloženi vizuelni pravac za Deklarant Pro. Prateći
QSS nacrt nalazi se u `styles/gui_visual_refresh_proposal.qss`.

QSS nije uključen u `MainWindow.load_stylesheet()` i trenutno ne utiče na
izgled aplikacije. Aktiviranje treba uraditi tek nakon vizuelne provjere svakog
taba na podržanim rezolucijama.

## Cilj

Cilj nije zamijeniti postojeći stručni raspored generičnim modernim interfejsom.
Aplikacija treba ostati brza i informacijski gusta za deklaranta, ali sa jasnijom
hijerarhijom, manjim brojem konkurentnih boja i dosljednim ponašanjem istih
komponenti na svim ekranima.

## Glavni nalazi

### Više konkurentnih stilskih sistema

Centralni QSS fajlovi, lokalni stilovi u View klasama i zasebni Admin stilovi
često definišu iste komponente. Konačan izgled zato zavisi od specifičnosti
selektora i redoslijeda učitavanja, a isto dugme ili polje ne izgleda jednako na
svakom tabu.

Predloženo rješenje je jedan završni vizuelni sloj koji koristi postojeće object
name i property selektore. Nakon potvrde izgleda, duplirane lokalne definicije
treba postepeno uklanjati, ekran po ekran.

### Previše boja istovremeno nosi značenje

Trenutno se koriste plava, zelena, ljubičasta, tirkizna, smeđa i crvena za
različite grupe akcija. To povećava vizuelni šum i zahtijeva da korisnik pamti
značenje palete.

Predložena semantika:

- plava — glavna akcija, izbor i navigacija;
- neutralna bijela/siva — standardne i sekundarne akcije;
- crvena — isključivo destruktivne akcije;
- zelena — potvrđen uspjeh i validno stanje;
- ljubičasta — Agent i AI podrška;
- žuta — upozorenje ili stanje koje zahtijeva pregled.

### Zelena treba biti status, ne osnovna pozadina

Velike zelene površine umanjuju značenje uspjeha i otežavaju razlikovanje
validnog reda od običnog sadržaja. Osnovne površine treba da budu bijele ili
neutralno sive. Zelena ostaje za potvrđene rezultate, oznake validacije i male
statusne elemente.

### Nedosljedne dimenzije i razmaci

Polja i dugmad koriste mnogo različitih fiksnih visina, širina i radijusa.
Predložena skala:

| Element | Predložena vrijednost |
| --- | --- |
| Kompaktno stručno polje | 28 px |
| Standardno polje | 32 px |
| Standardno dugme | 34 px |
| Toolbar dugme | 36 px |
| Mali radius | 4 px |
| Standardni radius | 6 px |
| Razmaci | 4, 8, 12, 16 i 24 px |
| Osnovni font | Segoe UI, 13 px |

## Paleta

| Uloga | Boja | Namjena |
| --- | --- | --- |
| Pozadina aplikacije | `#F4F6F8` | neutralna radna površina |
| Površina | `#FFFFFF` | forme, tabele i kartice |
| Sekundarna površina | `#F8FAFC` | zaglavlja i pomoćne zone |
| Primarni tekst | `#17212B` | sadržaj i naslovi |
| Sekundarni tekst | `#5F6B76` | pomoćni tekst |
| Obrub | `#C9D2DC` | polja i sekcije |
| Primarna plava | `#2F6F9F` | glavna akcija i izbor |
| Tamna plava | `#245779` | hover/pressed stanje |
| Uspjeh | `#2F7D5A` | potvrđeno validno stanje |
| AI | `#6A55A3` | Agent i pametna pomoć |
| Upozorenje | `#A66A17` | potrebna provjera |
| Greška | `#A6403D` | greška i destruktivna akcija |

### Funkcionalna paleta dugmadi

Ista funkcija mora koristiti istu porodicu boje na svim tabovima. Naimenovanja
su pilot za postepeno uvođenje ove palete; ostali tabovi se usklađuju zasebno,
nakon vizuelne potvrde, bez masovne promjene cijelog interfejsa.

| Funkcionalna uloga | Osnovna boja | Primjeri |
| --- | --- | --- |
| Kreiranje i čuvanje | `#2D5A48` | Dodaj, Sačuvaj, Snimi |
| Brisanje | `#7A3432` | Obriši, Briši, Očisti |
| Poništavanje | `#6B7280` | Poništi, Otkaži |
| AI pomoć | `#5E4272` | Sugeriši, Auto-popuni, Agent |
| Standardna akcija | `#3D6A8A` | navigacija, uvoz, izvoz, pregled, inspekcije |

Boje su namjerno prigušene. Bijeli tekst i ikone ostaju zajednički, hover je
nešto svjetliji, a disabled stanje neutralno sivo. Zelena ovdje označava
namjernu radnju kreiranja ili čuvanja; status uspjeha i dalje se prikazuje
zasebnim indikatorom, ne velikom obojenom površinom.

## Zajedničke komponente

### Glavna navigacija

- Smanjiti vizuelnu težinu neaktivnih tabova.
- Aktivni tab označiti plavom površinom i donjom linijom.
- Zadržati redoslijed poslovnog toka: Faktura, Naimenovanja, Zaglavlje.
- Šifrarnici, Admin i Agent ostaju sistemske cjeline.
- Izlaz treba izgledati kao zasebna komanda, a ne kao sedmi tab.

### Dugmad

- Na jednom ekranu treba postojati najviše jedna dominantna primarna akcija.
- Standardne akcije koriste neutralnu površinu i plavi tekst.
- Brisanje uvijek koristi crvenu semantiku i fizički razmak od sigurnih akcija.
- AI akcije jedine koriste ljubičastu.
- Disabled stanje mora ostati čitljivo, ali jasno neaktivno.

### Polja

- Fokus je plavi obrub širine 2 px.
- Read-only polja koriste blago sivu pozadinu.
- Greška i upozorenje treba da se postavljaju dinamičkim svojstvima
  `validationState="error"` i `validationState="warning"`.
- Automatski popunjeno polje može koristiti `dataSource="automatic"`.

### Tabele

- Osnovna pozadina je bijela, sa vrlo blagim alterniranjem redova.
- Selekcija je plava i ne smije biti zamijenjena bojom validacije.
- Tarifne brojeve treba prikazati monospaced fontom kada widget to dozvoljava.
- Validnost se prikazuje indikatorom ili posebnom kolonom, ne punom zelenom
  pozadinom cijelog reda.

## Preporuke po ekranima

### Faktura

- Ukloniti pastelne pozadine cijelih toolbar grupa i zadržati neutralne zone.
- Istaknuti samo dugme **Kreiraj naimenovanja**.
- Odvojiti **Očisti sve** od akcija **Dodaj** i **Obriši**.
- Bruto, neto i provjeru objediniti kao kompaktan panel kontrolnih masa.
- Zamijeniti punu zelenu tabelu neutralnim redovima i statusnim indikatorima.
- U donjem statusu smanjiti broj separatora i sažeti pregled država.

### Naimenovanja

- Zadržati raspored carinskog obrasca i brojeve rubrika.
- Zamijeniti debele crne granice tanjim neutralnim obrubom.
- Jasno razlikovati oznaku rubrike, naziv, unos, read-only i master polje.
- Prikaz `54 od 94` oblikovati kao kompaktan navigator.
- **Sačuvaj nacrt** treba biti glavna akcija, a **Poništi** sekundarna.
- Zbirne vrijednosti na dnu uskladiti sa Faktura statusnom trakom.

### Zaglavlje

- Organizovati sadržaj u tri cjeline: učesnici, deklaracija i dokumenti.
- Brojeve rubrika prikazati kao sekundarne oznake.
- Rijetko korištene cjeline učiniti sklopivim u kasnijoj funkcionalnoj fazi.
- **Završna provjera** treba biti glavna akcija prije izvoza.
- **Briši** odvojiti od glavnog poslovnog toka.
- Ne mijenjati postojeću logiku, draft sinhronizaciju ni značenje rubrika.

### Agent

- Smanjiti upload zonu i dati više prostora tabeli i chatu.
- Tri režima obrade prikazati kao kompaktan izbor režima.
- Prevesti tehničke statuse na srpski u posebnoj funkcionalnoj izmjeni.
- Pouzdanost vizuelno razlikovati od napretka izvršenja.
- **Reset** u budućnosti preimenovati u **Nova sesija**.
- Chat panel ostaviti u podesivom splitteru.

### Admin

- Status konekcije prikazati kao sažetu statusnu karticu.
- Test konekcije i osvježavanje vratiti na normalnu širinu dugmeta.
- Brojeve zapisa prikazati kao male statističke kartice ili urednu tabelu.
- Ograničiti maksimalnu širinu sadržaja na velikim ekranima.
- Uskladiti bočnu navigaciju sa Šifrarnicima.

### Šifrarnici

- Smanjiti visinu pretrage i dominantnost dugmeta **Pretraži**.
- Panel detalja prikazivati tek nakon izbora reda u kasnijoj funkcionalnoj fazi.
- Tarifne nivoe vizuelno razlikovati uvlačenjem i tipografijom.
- Ujednačiti navigaciju kroz rezultate i ukloniti nejasne duple strelice.
- Status prikazati kao `Prikazano 126 od 12.686`.

## Redoslijed implementacije

1. Aktivirati QSS samo u razvojnom režimu ili na posebnoj grani.
2. Provjeriti glavne tabove, dijaloge i popup menije na 1366×768 i 1920×1080.
3. Ispraviti konflikte selektora bez dodavanja novih inline stilova.
4. Vizuelno potvrditi Faktura tab kao referentni ekran.
5. Prilagoditi Naimenovanja i Zaglavlje bez promjene poslovne logike.
6. Uskladiti Šifrarnike, Admin i Agent.
7. Tek nakon potvrde ukloniti duplirane legacy QSS definicije.
8. Ponoviti PyInstaller build nakon konačne aktivacije.

## Granice ovog nacrta

- Ne mijenja raspored widgeta ni poslovnu logiku.
- Ne mijenja signale, controllere, servise ili modele.
- Ne rješava tekstualne izmjene poput prevođenja statusa.
- Ne uklanja postojeće QSS fajlove.
- Ne aktivira novi stil automatski.
- Ne garantuje da lokalni inline QSS neće nadjačati pojedine selektore; to se
  provjerava tokom ekran-po-ekran implementacije.

## Kriteriji prihvatanja buduće aktivacije

- Sve funkcije ostaju dostupne i na 1366×768 bez preklapanja.
- Fokus, hover, pressed, disabled i read-only stanja su jasno vidljiva.
- Greška, upozorenje i uspjeh ne zavise isključivo od boje.
- Faktura tabela ostaje čitljiva sa najmanje 15 vidljivih redova na 1080p.
- Naimenovanja zadržavaju prepoznatljivu strukturu ASYCUDA rubrika.
- Zaglavlje ne gubi nijedno postojeće polje.
- Agent splitter i skrolovanje ostaju funkcionalni.
- Admin i Šifrarnici koriste isti vizuelni jezik kao osnovni tabovi.
