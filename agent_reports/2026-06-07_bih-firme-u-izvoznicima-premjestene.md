# Agent Report: Premještanje BiH firmi iz Izvoznika nazad u Uvoznike

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je primijetio da katalog Izvoznici (Pošiljaoci — smiju biti samo
strani partneri) sadrži i domaće, BiH firme, i tražio "IZBRIŠI TO". Po
analogiji sa prethodnim slučajem ([[strane-firme-u-uvoznicima-premjestene]],
isti dan, suprotan smjer) — to su validni partneri sa ispravnim BiH podacima,
samo zavedeni u pogrešan katalog — odlučeno je da se **premjeste** u ispravan
katalog (`catalogs.uvoznici`), a ne brišu.

Rezultat: **28 zapisa** premješteno iz `catalogs.izvoznici` u `catalogs.uvoznici`
sa `drzava='BIH'` i novim `UV#####` šiframa. `catalogs.izvoznici`: 2144 → 2116
(0 preostalih sa BiH JIB-om). `catalogs.uvoznici`: 669 → 697 (svi `BIH`).

## Kako je urađeno

1. **Identifikacija**: Pretraga po polju `drzava ILIKE '%BIH%'` vratila je
   samo 1 zapis (`EX00994` GRAND AUTOMOTIVE, `drzava='BOSNA I HERCEGOVINA'`).
   Pretraga po poznatim BiH gradovima u adresi/gradu otkrila je dodatne
   kandidate, ali i lažne pozitivce (Turske firme 'ASE PLASTIK'/'PAFLEX
   PAZARLAMA' imaju `adresa='TUZLA/ISTANBUL'` — Tuzla je naziv okruga u
   Istanbulu, ne BiH grad). **Precizan filter**: ispravan BiH JIB je
   12-cifren numerički kod (`jib ~ '^[0-9]{12}$'`) — strani partneri u
   izvoznicima uvijek dobijaju auto-generisan `EX#####` kod, nikad domaći
   numerički format. Filter je vratio 27 zapisa, plus eksplicitni `EX00994`
   slučaj — ukupno 28, **bez ijednog lažnog pozitivca** (svi gradovi —
   Banja Luka, Bijeljina, Tuzla, Prnjavor, Sarajevo, Gračanica, Usora,
   Dvorovi, Kozarska Dubica, Visoko, Istočno Sarajevo, Banja Vrućica-Tešić —
   provjereni kao stvarni BiH gradovi).

2. **Otkriven dodatni data-quality bug**: Kod ovih 28 zapisa polje `drzava`
   NIJE sadržavalo naziv države, već **stvarnu ulicu/adresu** (npr.
   `drzava='BANJALUČKI PUT 21'`, dok su `adresa` i `grad` oba sadržavala
   isti naziv grada 'PRNJAVOR' — duplikat, prava adresa "procurila" u
   pogrešno polje). Skripta `scripts/move_bih_izvoznike_u_uvoznike.py`
   detektuje da li `drzava` sadrži prepoznatljiv naziv države
   (BIH/BOSNA I HERCEGOVINA/...) ili stvarnu ulicu, i u potonjem slučaju
   realignuje: `drzava` vrijednost (ulica) → nova `adresa`, `grad` ostaje
   nepromijenjen, `drzava` postaje ispravno `'BIH'`.

3. **Skripta** (dry-run/--execute/CSV-backup pattern, isti kao u prethodna
   dva slučaja): generiše plan starа→nova vrijednost za svako polje, pravi
   CSV backup (`scripts/_izvoznici_move_backup_deleted_<timestamp>.csv`,
   gitignore-ovan), zatim INSERT u `catalogs.uvoznici` sa novim `UV#####`
   šiframa i DELETE iz `catalogs.izvoznici`.

4. Plan prikazan korisniku kroz `AskUserQuestion` (28 firmi, realignment
   primjer objašnjen), korisnik potvrdio ("Da, pokreni --execute"), izvršeno.

5. Provjera nakon izvršenja: `catalogs.uvoznici` 697 zapisa (svi `BIH`),
   `catalogs.izvoznici` 2116 zapisa (0 preostalih sa 12-cifrenim BiH JIB-om
   ili `drzava` koja pominje Bosnu/Hercegovinu).

## Zašto

Vjerovatno potiče iz istog uzroka kao i suprotan problem (strane firme u
uvoznicima) — `database/import_partners_from_xml.py` koristi nepouzdanu
heuristiku za određivanje da li je partner domaći ili strani, i/ili netačno
mapira XML strukturu na kolone kataloga (otud i field-shift bug gdje je
ulica završila u `drzava` polju umjesto u `adresa`). Ovo je migracioni alat
koji se ne pokreće u runtime-u — trenutno popravljeno samo na nivou podataka,
ne i u import logici.

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `ecc4cb5` | fix | Premještanje 28 BiH firmi iz izvoznika nazad u uvoznike + realignment adresa/grad/drzava |

---

## Napomena za buduće sesije

Filter `jib ~ '^[0-9]{12}$'` (ispravan BiH numerički JIB format) je vrlo
pouzdan signal za "BiH firma u pogrešnom katalogu" — bolji od filtera po
gradu/nazivu (koji daje lažne pozitivce poput Turskih firmi sa "Tuzla" u
adresi). Ako se ponovo pojavi sumnja na zamijenjene kataloge, ovaj JIB-format
filter je provjeren prvi korak. Takođe, **field-shift bug (drzava polje
sadrži ulicu) vjerovatno postoji i u drugim BiH zapisima van ovog filtera** —
vrijedi šire provjeriti ako korisnik prijavi pogrešne adrese. Vidi
[[bih-firme-u-izvoznicima-premjestene]] i [[strane-firme-u-uvoznicima-premjestene]]
za pun kontekst oba (suprotna) slučaja istog dana.
