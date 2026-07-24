## Datum

2026-07-23

## Agent

OpenAI Codex

## Scope

- `docs/UPUTSTVO_TASTATURNA_NAVIGACIJA.md`

## GitNexus impact

Promjena je isključivo dokumentaciona i ne mijenja nijedan simbol, izvršni tok
ili funkcionalnost aplikacije. Provjera radnog stabla pokazuje i ranije,
nepovezane izmjene korisnika koje nisu uključene u ovaj zadatak.

## Šta je urađeno

Kreirano je zasebno korisničko uputstvo za tastaturnu navigaciju i arhivirano u
`docs` folderu. Uputstvo obuhvata globalne prečice, kretanje kroz zapise i
prečice dostupne na svim glavnim karticama.

## Zašto je urađeno

Standardizovane prečice treba da budu dostupne korisniku na jednom preglednom
mjestu, bez potrebe da ih otkriva pregledom koda ili pojedinačnih tooltipova.

## Kako je urađeno

Uputstvo je organizovano po karticama i sadrži tabele prečica, napomene o
sigurnom korišćenju i preporučeni tok rada.

## Šta nije dirano

- Nije mijenjan programski kod.
- Nije mijenjan postojeći veliki korisnički priručnik.
- Nisu dirane ranije nepovezane izmjene u radnom stablu.

## Verifikacija

- `git diff --check` je prošao bez grešaka.
- Provjeren je prikaz dijakritika u novom Markdown fajlu.
- Pre-commit provjera je prošla.
- Ručna DOC Guard skripta nije pokrenuta jer `bash` nije dostupan u trenutnom
  Windows okruženju; novi dokument ne sadrži interne Markdown linkove.

## Pronađeni problemi

Postojeći `docs/KORISNICKO_UPUTSTVO.md` sadrži zastario i teško održiv ugrađeni
sadržaj. Nije mijenjan jer nije dio ovog zadatka.

## Konflikti / kontradiktorni izvori

Nema konflikta. Novo uputstvo dokumentuje trenutno implementirane prečice.

## Commitovi

| Hash | Poruka |
|---|---|
| `5ea2fc3` | `docs(gui): dodaj korisničko uputstvo za tastaturu` |

## Rizici / ograničenja

Uputstvo treba ažurirati ako se prečice kasnije promijene.

## Potreban follow-up

Nije potreban za ovaj zadatak.

## Potrebna korisnička potvrda

Poželjno je da korisnik pregleda terminologiju i potvrdi da je dovoljno jasna
za krajnje korisnike aplikacije.
