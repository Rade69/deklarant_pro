# Agent Report: Premještanje stranih firmi iz Uvoznika u Izvoznike

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je primijetio da se u katalogu Uvoznici (Primaoci) nalaze i firme iz
Srbije i Makedonije, što po poslovnom pravilu nije moguće — `catalogs.uvoznici`
smije sadržavati samo firme iz Bosne i Hercegovine (Izvoznici/Pošiljaoci su
strani partneri). Korisnik je odabrao opciju **"Premjesti u Izvoznike"** —
zapise treba premjestiti u ispravan katalog sa ispravljenom državom, a ne
brisati ih ili samo zakrpiti polje `drzava` na mjestu.

Rezultat: **48 zapisa** premješteno iz `catalogs.uvoznici` u `catalogs.izvoznici`
sa ispravnim državama (Srbija, Crna Gora, Hrvatska, Makedonija, Slovenija,
Švedska, Cyprus) i novim `EX#####` šiframa. `catalogs.uvoznici`: 717 → 669
(svi preostali su `drzava='BIH'`). `catalogs.izvoznici`: 2096 → 2144.

## Kako je urađeno

1. **Identifikacija sumnjivih zapisa**: Prvobitna pretraga ključnim riječima
   (gradovi/nazivi država u nazivu/adresi) davala je lažne pozitivce
   ('UNIS GINEX' i 'UNIS - ENERGETIKA' — genuine BiH firme čiji naziv sadrži
   substring "NIS"). Precizniji filter: šifra oblika `UV#####`
   (`jib ~ '^UV[0-9]{5}$'`) — ova auto-generisana šifra dodjeljuje se SAMO
   kada izvor nije imao ispravan 13-cifreni BiH JIB. Vratio je 50 kandidata.

2. **Ručna provjera kandidata**: Od 50, dva su genuine BiH firme kojima
   samo nedostaje ispravan JIB u izvornim podacima — `Bisprom` (Prnjavor,
   Republika Srpska) i `MODUL` (Banja Luka) — eksplicitno izuzete iz
   premještanja (`EXCLUDE_JIBS` u skripti).

3. **Određivanje ispravne države**: Za 40 od 48 zapisa, polje `adresa` ili
   `grad` doslovno sadrži naziv strane države (npr. `adresa='SRBIJA'`,
   `adresa='CRNA GORA'`) — vjerovatno zato što izvorni XML nije imao stvarnu
   adresu pa je import stavio naziv države u to polje. Za preostalih 8 (gdje
   su polja sadržavala stvarnu ulicu/grad bez naziva države — npr.
   'RINGIER AXEL SPRINGER' / 'Žorža Klemansoa 19, Beograd'), država je ručno
   mapirana po poznatom sjedištu firme (`DRZAVA_OVERRIDE` rječnik u skripti).

4. **Skripta `scripts/move_strane_uvoznike_u_izvoznike.py`** (dry-run/--execute
   pattern, isti kao kod merge-a duplikata):
   - generiše plan: stari `UV#####` zapis → novi `EX#####` zapis sa
     ispravljenom `drzava`
   - prije izvršenja pravi CSV backup svih premještanih/brisanih zapisa
     (`scripts/_uvoznici_move_backup_deleted_<timestamp>.csv`, gitignore-ovan
     jer sadrži poslovne podatke partnera)
   - INSERT u `catalogs.izvoznici` sa novim `EX#####` šiframa (generisane
     traženjem prve slobodne sekvence, počevši od `EX00001`), DELETE iz
     `catalogs.uvoznici`

5. Pokrenuto najprije u dry-run modu — prikazan plan korisniku kroz
   `AskUserQuestion` (48 firmi po državama, 2 izuzeća), korisnik potvrdio
   ("Da, pokreni --execute"), zatim izvršeno sa `--execute`.

6. Provjera nakon izvršenja: `catalogs.uvoznici` sada ima 669 zapisa, svi sa
   `drzava='BIH'`; `catalogs.izvoznici` poraslo sa 2096 na 2144.

## Zašto

**Uzrok** je u `database/import_partners_from_xml.py:105`:
```python
"drzava": "BIH" if jib else "",   # FLAWED: pretpostavka da svaki Consignee
                                  # sa šifrom = BiH firma
```
Logika je pretpostavljala da svaki strani partner-primalac (Consignee) koji
ima šifru u XML-u mora biti BiH firma — pogrešna pretpostavka koja je
ignorisala stvarno porijeklo firme. Greška se prenijela u seed fajl
`database/consignees.json` (svih 733 zapisa ima `country: 'BIH'`, uključujući
očigledno strane firme poput 'ENMON BG'/'FARMAVITA DOOEL'/'A.M.D. GRUP dooel').

Ovo je migracioni/import alat koji se ne pokreće u runtime-u aplikacije —
nije hitno popravljati njegovu logiku, ali ako se ponovo pokrene import iz
XML-a, ista greška će se ponoviti za nove strane partnere bez pravog BiH JIB-a.
Vrijedi imati ovo na umu za buduće sesije (vidi napomenu u memoriji).

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `eb96c80` | fix | Premještanje 48 stranih firmi iz uvoznika u izvoznike (skripta + izvršenje na produkcionoj bazi) |

---

## Napomena za buduće sesije

`jib ~ '^UV[0-9]{5}$'` filter je dobar polazni signal za "potencijalno strane
firme u uvoznicima", ali NIJE 100% pouzdan — uvijek ručno provjeriti grad/adresu
prije masovnih operacija (vidi slučaj Bisprom/MODUL — genuine BiH firme bez
ispravnog JIB-a). Ako se problem ponovi nakon novog XML importa, razmotriti
i popravku `import_partners_from_xml.py:105` (zamijeniti `"BIH" if jib else ""`
detekcijom stvarne države iz adresnih podataka). Vidi
[[strane-firme-u-uvoznicima-premjestene]] za pun kontekst i listu firmi.
