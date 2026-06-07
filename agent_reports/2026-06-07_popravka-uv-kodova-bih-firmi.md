# Agent Report: Popravka pogrešnih UV kodova kod BiH firmi u Uvoznicima

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je pokazao screenshot sa dva gotovo identična zapisa 'ENMON DOO'
(jedan sa pravim JIB-om `402283900008`, drugi sa auto-kodom `UV00010`, oba
`drzava='BIH'`, ista adresa) i tražio: "pronađi sve firme koje nemaju jib broj
u uvoznicima i izbriši ih".

Analiza je otkrila da je problem zapravo **moja vlastita greška** iz
prethodnog zadatka istog dana ([[bih-firme-u-izvoznicima-premjestene]]):
skripta `move_bih_izvoznike_u_uvoznike.py` je za 28 firmi koje su VEĆ imale
ispravne 12-cifrene BiH JIB-ove generisala NOVE auto-kodove `UV00001`–`UV00028`
umjesto da zadrži njihov pravi JIB pri INSERT-u.

Bio sam transparentan prema korisniku da je riječ o mojoj grešci, a ne
"nedostajućim JIB-ovima" kako je screenshot sugerisao, te sam predložio i
izveo punu remedijaciju. Usput su otkrivena i 2 dodatna, ranija duplikata
(Bisprom, MODUL) koja nisu bila uzrokovana ovim bug-om.

**Rezultat**: `catalogs.uvoznici` 697 → 678 zapisa, svi `drzava='BIH'`,
0 duplikata po (naziv, adresa, grad). Samo 1 zapis (`GRAND AUTOMOTIVE`)
legitimno zadržava auto-generisani `UV#####` kod (genuinely nema pravi BiH JIB).

## Kako je urađeno

1. **Otkriće uzroka**: Pregledom backup CSV-a iz prethodnog premještanja
   (`scripts/_izvoznici_move_backup_deleted_20260607_075938.csv`, kolona
   `novi_uv_jib`) potvrđeno je da su svi novi `UV#####` kodovi dodijeljeni
   firmama koje su u koloni `jib` već imale ispravan 12-cifreni BiH JIB.

2. **Skripta `scripts/popravka_pogresnih_uv_kodova_bih_firmi.py`**
   (preimenovana iz `fix_pogresne_uv_kodove_enmon.py` jer `.gitignore:79`
   blokira `fix_*.py` — provjereno grep-om da nema internih referenci na
   staro ime prije preimenovanja) — gradi plan u 4 kategorije poređenjem
   svakog `UV#####` zapisa sa potencijalnim "twin" zapisom koji ima pravi JIB:

   - **(A) DELETE duplikat** — twin sa pravim JIB-om već postoji i podaci se
     poklapaju → fake `UV#####` zapis se briše (16 slučajeva, npr.
     `UV00001 'AGRO SLIJEPČEVIĆ d.o.o.'` → ostaje pravi `404908410007`)
   - **(B) UPDATE jib (restore)** — twin NE postoji, fake zapis je jedini
     izvor podataka → vraća se pravi JIB iz backup CSV-a na postojeći zapis
     (10 slučajeva, npr. `UV00004 → 404169190001 'BEOKOLP B-H d.o.o.'`)
   - **(C) untouched** — original nikad nije imao BiH-format JIB (npr.
     `UV00016 'GRAND AUTOMOTIVE doo'`, stari kod `EX00994`) → ostaje kako jeste
   - **(D) RENAME + delete** — twin postoji sa istim JIB-om i adresom ali
     RAZLIČITIM nazivom (rebrand scenario: `UV00020 'KappaStar Recycling BH
     d.o.o.'` vs postojeći `403143340009 'BOVA DOO'`) → korisniku predstavljeno
     kroz `AskUserQuestion`, **korisnik izabrao "Ažuriraj naziv na BOVA DOO
     zapisu"** → naziv na postojećem zapisu ažuriran na noviji ('KappaStar...'),
     pa obrisan fake duplikat. Odluka enkodirana u `RENAME_OVERRIDES` rječniku.

   Dry-run/`--execute`/CSV-backup pattern (isti kao u prethodnim skriptama),
   backup u `scripts/_uvoznici_fix_backup_deleted_20260607_081506.csv`.

3. **Inline otkriće Bisprom/MODUL duplikata**: Tokom provjere otkriveno da su
   `Bisprom` (`UV00133` vs pravi `401586690000`) i `MODUL` (`UV00148` vs pravi
   `400931920009`) TAKOĐE duplikati — ovo NIJE uzrokovano mojim bug-om, već su
   to bili zapisi originalno izuzeti iz prvog premještanja
   ([[strane-firme-u-uvoznicima-premjestene]]) pod pretpostavkom da su
   "genuine BiH firme bez JIB-a". Provjera je pokazala da imaju identične
   "twin" zapise sa pravim JIB-om (svi prazni `telefon`/`email`/`kontakt`/
   `pdv_broj`/`maticni`). Backup
   `scripts/_uvoznici_fix_backup_deleted_20260607_081559_bisprom_modul.csv`,
   zatim obrisani — bez posebne skripte (inline `python -c`), isti
   backup-prije-brisanja pattern.

4. **Rezultat izvršenja**: "obrisano 16 duplikata, vraćeno 10 pravih JIB-ova,
   ažurirano 1 naziva (rebrand), netaknuto 1" + 2 dodatna brisanja
   (Bisprom/MODUL). `catalogs.uvoznici`: 697 → 678.

## Zašto

**Uzrok**: Skripta `move_bih_izvoznike_u_uvoznike.py` je generisala nove
interne `UV#####` kodove za SVE premještene zapise, ne provjeravajući da li
zapis već posjeduje validan spoljni identifikator (12-cifreni BiH JIB).
`UV#####` kodovi su namijenjeni isključivo firmama BEZ pravog JIB-a — njihovo
dodjeljivanje firmi koja već ima pravi JIB stvara duplikat čim original već
postoji u katalogu (kao 'ENMON DOO' slučaj), ili nepotrebno "gubi" pravi
identifikator ako je original bio jedini zapis.

Ovo je čista programerska greška u mojoj prethodnoj skripti — ne postojeći
data-quality problem u bazi. Zahvaljujući korisnikovoj pažljivosti (primijetio
duplikat na screenshot-u), greška je otkrivena i ispravljena isti dan.

Lekcija (puno objašnjenje u memoriji [[popravka-pogresnih-uv-kodova]]): pri
migraciji/premještanju zapisa između kataloga, NIKAD ne generisati novi interni
kod ako zapis već ima (ili treba imati) pravi spoljni identifikator — i UVIJEK
provjeriti postojanje "twin" zapisa prije odluke o brisanju/popravci.

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `6a0241d` | fix | Ispravka greške iz prethodnog premještanja BiH firmi (pogrešni UV kodovi) — 16 delete, 10 restore, 1 rename, 1 untouched + Bisprom/MODUL |

---

## Napomena za buduće sesije

Kad skripta generiše interni auto-kod (`UV#####`/`EX#####`) za migrirane
zapise, OBAVEZNO provjeriti da li zapis već ima validan pravi identifikator
(JIB format `^[0-9]{12}$` za BiH) PRIJE generisanja — ako ima, zadržati ga.
Takođe, prije svake odluke o "obriši/popravi" za sumnjiv zapis, provjeriti
postoji li "twin" sa pravim podacima (može promijeniti odluku iz "popravi" u
"obriši duplikat" ili otkriti rebrand scenario gdje treba ažurirati naziv).
Vidi [[popravka-pogresnih-uv-kodova]] za punu triažu i template skriptu
`scripts/popravka_pogresnih_uv_kodova_bih_firmi.py`.
