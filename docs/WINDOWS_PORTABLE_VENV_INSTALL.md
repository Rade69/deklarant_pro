# Deklarant Pro - Windows instalacija preko dist_client + .venv

Ovo uputstvo opisuje prakticnu instalaciju aplikacije na drugi Windows racunar bez
pravljenja `.exe` builda. Ovaj nacin je trenutno najstabilniji za internu upotrebu,
jer se aplikacija pokrece kroz Python virtualno okruzenje (`.venv`) koje je vec
pripremljeno u `dist_client` folderu.

## 1. Sta se prenosi na drugi racunar

Na drugi Windows racunar prenosi se cijeli folder:

```text
C:\Users\38765\Desktop\deklarant_pro\dist_client
```

Mozes ga kopirati na USB, eksterni disk ili preko mreze.

Na ciljnom racunaru preporucena lokacija je, na primjer:

```text
C:\DeklarantPro\dist_client
```

ili:

```text
C:\Users\<korisnik>\Desktop\dist_client
```

Bitno je da se prenese kompletan folder, ukljucujuci:

```text
.venv\
run.py
.env
assets\
gui\
services\
importers\
database\
```

Ne kopirati samo `run.py` ili samo dio foldera.

> ⚠️ **VAZNO — `.venv` NIJE zaista samodovoljan ("portable")**
>
> `.venv\Scripts\python.exe` je samo mali "launcher stub" (~255 KB), ne puna
> Python instalacija. On u `pyvenv.cfg` cita putanju do BAZNE Python instalacije
> i odatle u runtime-u ucitava `python3xx.dll` i standardnu biblioteku. Provjeri:
>
> ```text
> dist_client\.venv\pyvenv.cfg
> home = C:\Users\38765\AppData\Local\Programs\Python\Python314
> executable = C:\Users\38765\AppData\Local\Programs\Python\Python314\python.exe
> ```
>
> To znaci da ce kopiranje `.venv` raditi **samo** ako ciljni racunar ima
> identicnu Python instalaciju (verzija + arhitektura) na **tacno toj putanji**.
> Ako je nema (drugi korisnik, druga verzija, ili Python uopste nije instaliran),
> aplikacija ce pucati sa nejasnim greskama tipa `DLL load failed` ili
> `No module named 'encodings'`.
>
> **Dvije opcije:**
> 1. Prije prenosa instalirati identicnu Python verziju na ciljnoj mašini na istoj
>    putanji (vidi preduslov u koraku 2), ili
> 2. Napraviti `.venv` sa `python -m venv --copies .venv` — ovo kopira pravi
>    `python.exe`/DLL umjesto stuba, cineci folder stvarno samodovoljnim
>    (i dalje vezano za istu major.minor verziju i arhitekturu OS-a, ali vise
>    ne zavisi od konkretne putanje na razvojnoj masini).

## 2. Preduslovi na ciljnom Windows racunaru

Prije pokretanja provjeri sljedece:

1. Racunar mora imati pristup PostgreSQL serveru aplikacije.
2. Firewall ne smije blokirati vezu prema serveru baze.
3. Ako ce se citati skenirani PDF-ovi, mora biti instaliran Tesseract OCR.
4. Ako se koristi licenciranje, licenca mora biti instalirana za taj racunar.
5. **Python 3.14.1 (64-bit) mora biti instaliran na ciljnom racunaru na putanji**
   `C:\Users\<korisnik>\AppData\Local\Programs\Python\Python314` — ili je `.venv`
   napravljen sa `--copies` (vidi upozorenje u koraku 1). Bez ovoga `.venv` se NE
   moze pokrenuti na drugoj masini (vidi objasnjenje gore).

Ako aplikacija cita samo PDF-ove sa normalnim tekstom, OCR nije obavezan.

## 3. Provjera .env konfiguracije

U folderu `dist_client` mora postojati fajl:

```text
.env
```

Otvori ga u Notepadu i provjeri podatke za bazu:

```env
DB_HOST=192.168.0.69
DB_PORT=5432
DB_NAME=deklarant_pro
DB_USER=...
DB_PASSWORD=...
```

Ako je server na drugoj IP adresi, promijeni `DB_HOST`.

Ne brisi `.env`, jer aplikacija iz njega cita konekciju, kljuceve i lokalna podesavanja.

## 4. Pokretanje aplikacije iz PowerShell-a

Otvori PowerShell i udji u folder:

```powershell
cd C:\DeklarantPro\dist_client
```

Ako je folder na Desktopu, primjer moze biti:

```powershell
cd C:\Users\<korisnik>\Desktop\dist_client
```

Pokreni aplikaciju:

```powershell
.venv\Scripts\python.exe run.py
```

Ako se GUI otvori, instalacija je uspjesna.

## 5. Pravljenje jednostavnog launcher fajla

Da korisnik ne bi svaki put kucao komandu, u `dist_client` folderu napravi fajl:

```text
Pokreni Deklarant Pro.bat
```

Sadrzaj fajla:

```bat
@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe run.py
pause
```

Za svakodnevno pokretanje korisnik moze dvostruko kliknuti na taj `.bat` fajl.

Ako zelis da se terminal zatvara samo kada aplikacija normalno radi, moze se koristiti i
varijanta bez `pause`:

```bat
@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe run.py
```

Za dijagnostiku je bolja verzija sa `pause`, jer ostavlja vidljivu gresku ako se aplikacija
ne pokrene.

## 6. Desktop precica

Za lakse pokretanje:

1. Desni klik na `Pokreni Deklarant Pro.bat`.
2. Izaberi `Create shortcut`.
3. Premjesti precicu na Desktop.
4. Desni klik na precicu, zatim `Properties`.
5. U polju `Start in` treba biti putanja do `dist_client` foldera.

Ako postoji `.ico` fajl u `assets\icons`, mozes ga postaviti preko `Change Icon`.

## 7. Tesseract OCR instalacija

OCR je potreban samo za skenirane PDF-ove i slike. Python paket `pytesseract` nije dovoljan
sam po sebi; Windows mora imati instaliran i Tesseract program.

Provjera da li je Tesseract instaliran:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

Ako komanda vrati verziju, Tesseract je instaliran.

Ako dobijes poruku da fajl nije pronadjen, instaliraj Tesseract OCR. Najjednostavnije:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Nakon instalacije provjeri iz Python okruzenja aplikacije:

```powershell
cd C:\DeklarantPro\dist_client
.venv\Scripts\python.exe -c "import pytesseract; pytesseract.pytesseract.tesseract_cmd=r'C:\Program Files\Tesseract-OCR\tesseract.exe'; print(pytesseract.get_tesseract_version())"
```

Ako se ispise verzija, OCR radi.

## 8. Licenca

Ako aplikacija trazi licencu:

1. Pokreni aplikaciju.
2. Idi na `Admin`.
3. Otvori panel `Licenca`.
4. Sacuvaj fingerprint ako licenca jos nije generisana.
5. Uvezi dobijeni `license.dat` ili odgovarajuci licencni fajl.

Tipicna lokacija licence na Windowsu je:

```text
C:\ProgramData\DeklarantPro\license.dat
```

Licenca se obicno veze za konkretan racunar, pa kopiranje licence sa drugog racunara ne mora
raditi.

## 9. Nadogradnja aplikacije

Kada se napravi nova verzija:

1. Zatvori aplikaciju.
2. Napravi backup postojeceg `dist_client` foldera.
3. Prekopiraj novi `dist_client` preko starog ili ga stavi u novi folder.
4. Sacuvaj postojece lokalne fajlove ako su bitni:

```text
.env
license.dat / licencni fajl
lokalne baze ako postoje
```

5. Pokreni aplikaciju preko launchera.

Ako nova verzija ima novu `.venv`, prenesi i nju. Ako nema, moze se zadrzati postojeca
`.venv`, ali sigurnije je prenijeti kompletan provjereni `dist_client`.

## 10. Najcesci problemi

### Aplikacija se ne pokrece

Pokreni iz PowerShell-a:

```powershell
cd C:\DeklarantPro\dist_client
.venv\Scripts\python.exe run.py
```

Procitaj zadnju gresku koja se ispise.

### Ne moze se spojiti na bazu

Provjeri:

1. Da li je `DB_HOST` u `.env` tacan.
2. Da li je server baze ukljucen.
3. Da li Windows racunar vidi server preko mreze.
4. Da li firewall propusta port `5432`.

### OCR nije dostupan

Ako log pise:

```text
OCR nije dostupan - pytesseract nije instaliran
```

provjeri:

```powershell
cd C:\DeklarantPro\dist_client
.venv\Scripts\python.exe -m pip install pytesseract pillow
.venv\Scripts\python.exe -c "import pytesseract; print('pytesseract OK')"
```

Ako Python paket postoji, ali OCR i dalje ne radi, vjerovatno nedostaje Tesseract program.
Instaliraj ga prema koraku 7.

### Putanja sa razmakom ne radi

Ako pokreces program iz `C:\Program Files`, putanja mora biti pod navodnicima:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

Bez `&` i navodnika PowerShell cita samo `C:\Program`, pa javlja gresku.

## 11. Kada ima smisla praviti .exe build

`.exe` build ima smisla kada:

1. GUI i logika vise nisu u intenzivnim izmjenama.
2. Poznati su svi hidden importi.
3. Qt pluginovi, assets, OCR i konfiguracije su stabilno spakovani.
4. Instalacija treba biti jednostavna za krajnjeg korisnika.

Dok se aplikacija jos aktivno popravlja, `dist_client + .venv` je prakticniji i stabilniji
nacin distribucije.

## 12. Kratka verzija instalacije

Ako je sve vec pripremljeno:

```text
1. Kopiraj kompletan dist_client na Windows racunar.
2. Provjeri .env.
3. Instaliraj Tesseract OCR ako treba OCR.
4. Pokreni:
   .venv\Scripts\python.exe run.py
5. Napravi .bat launcher i Desktop precicu.
6. Uvezi licencu ako aplikacija trazi licencu.
```

