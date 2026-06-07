# Agent Report: Pronalazak i spajanje duplikata u catalogs.izvoznici

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je poslao screenshot tabele "Pošiljaoci" sa tri gotovo identična zapisa
("19 SEPTEMBAR" / "19 SEPTEMBAR DOO" / "19. SEPTEMBAR DOO" — isti partner, tri JIB-a)
i pretpostavio da na serveru ima gomila sličnih duplikata. Zahtjev je bio da se
pronađu i obrišu svi takvi duplikati u katalogu izvoznika.

Rezultat: pronađeno **201 grupa** duplikata (248 "viška" zapisa od ukupno 2344),
spojeni su i obrisani — baza sada ima **2096** izvoznika sa **0** preostalih grupa
duplikata.

## Kako je urađeno

1. Napravljena skripta `scripts/find_izvoznici_duplikati.py` koja grupiše zapise
   po normalizovanom nazivu (uklanja "DOO"/"D.O.O."/tačke/zareze/višestruke
   razmake) i ispisuje grupe sa više od jednog zapisa. Pokrenuta na produkcionoj
   bazi — pronašla 201 grupu (167 sa 2, 24 sa 3, 9 sa 4, jedna — "DERBRI PLUS" —
   sa čak 7 zapisa pod 5 različitih JIB-ova).

2. Provjereno u `database/setup_db.py` da `catalogs.izvoznici` ima
   `jib VARCHAR(50) PRIMARY KEY` ali da **nijedna druga tabela ne čuva FK
   referencu** na taj PK — `catalogs.declarations` čuva `vendor`/`buyer` kao
   plain-text kopije. To znači da je brisanje duplikata bezbjedno za
   referencijalni integritet (čista katalog/autocomplete tabela).

3. Napravljena skripta `scripts/merge_izvoznici_duplikati.py`:
   - bira "kanonski" zapis u grupi po (a) broju popunjenih sporednih polja
     (telefon/email/kontakt/pdv_broj/maticni), (b) dužini naziva (npr.
     "DERBRI PLUS D.O.O." > "DERBRI Plus"), (c) JIB kao tie-breaker
   - dopunjava prazna polja kanonskog zapisa vrijednostima iz duplikata
     (UPDATE, ne gazi postojeće vrijednosti)
   - briše ostale zapise iz grupe (DELETE po jib)
   - **dry-run je default** — `--execute` flag pokreće stvarnu izmjenu
   - prije svakog DELETE-a pravi CSV backup obrisanih zapisa
     (`scripts/_izvoznici_merge_backup_deleted_<timestamp>.csv`, van git trackinga
     jer sadrži poslovne podatke partnera)

4. Pokrenuta najprije u dry-run modu radi provjere plana (uzorci: "19 SEPTEMBAR"
   → zadržava EX01504, "DERBRI PLUS" → zadržava EX00489 i briše 6 duplikata),
   zatim sa `--execute` po korisnikovoj potvrdi.

`gitnexus_detect_changes()` pokazao je da promjene zahvataju samo nove fajlove u
`scripts/` — rizik LOW, bez pogođenih izvršnih procesa.

## Zašto

Duplikati nastaju pri auto-importu faktura: kada parser ne pronađe tačan match po
JIB-u za izvoznika, kreira se nov zapis umjesto prepoznavanja postojećeg partnera
sa sličnim (ali ne identičnim) nazivom — razlike u sufiksu (DOO/D.O.O.),
dijakritikama (BEČEJ/BECEJ) ili formatu adrese. Ovo je zagušilo katalog
"Pošiljaoci" lažnim unosima i otežavalo pretragu/odabir prilikom kreiranja
deklaracija.

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `46702e1` | chore | Skripte za pronalazak i spajanje duplikata u catalogs.izvoznici |

---

## Napomena za buduće sesije

`catalogs.uvoznici` ima identičnu strukturu (`jib VARCHAR(50) PRIMARY KEY`, bez FK
referenci) i vjerovatno pati od istog problema — isti par skripti (uz promjenu
imena tabele) može se primijeniti i tamo ako korisnik primijeti slične duplikate.
Vidi [[izvoznici-duplikati-merge]] za detalje pristupa.
