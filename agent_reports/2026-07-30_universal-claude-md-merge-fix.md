## Datum
2026-07-30

## Agent
Claude (Sonnet 5)

## Scope
`templates/agent-md/UNIVERSAL_CLAUDE.md` — Korak 0 (case: postojeći CLAUDE.md).

## Impact analiza
Nema — dokumentacija.

## Reprodukcija prije izmjene
N/A — nije bugfix koda, nego korekcija procedure/uputstva nakon što je korisnik primijetio grešku u mojim prethodnim delivery-instrukcijama (ne u samom fajlu).

## Šta je urađeno
Korisnik je primijetio da moje uputstvo iz prethodnog zadatka ("kopiraj `UNIVERSAL_CLAUDE.md` i preimenuj u `CLAUDE.md`") fizički prepisuje postojeći `CLAUDE.md` PRIJE nego što agent ikad dobije priliku da primijeni "ne prepisivati bez pitanja" zaštitu koja je već postojala u Koraku 0. Za ovog korisnika ovo nije edge case — svi njegovi ciljani projekti (van deklarant_pro) već imaju CLAUDE.md.

Prošireno Korak 0 pravilo u eksplicitan 5-koračni merge postupak: pročitaj postojeći `CLAUDE.md` u cijelosti → zadrži SVE iz njega doslovno (ne sažimati/preformulisati — ljudski kurirano znanje je po pravilu tačnije od svježeg skena) → dodaj SAMO strukturne dijelove kojih nema, sa uputstvom da se ne duplira ako postojeći fajl već ima ekvivalent pod drugim imenom → prikaži predlog spojenog teksta korisniku PRIJE upisa → upiši tek nakon potvrde. Eksplicitno navedeno da fajl kojim se principi prenose treba OSTATI pod drugim imenom (ne `CLAUDE.md`) dok se merge ne završi — da fizičko kopiranje/preimenovanje samo po sebi ne može obrisati original.

## Zašto je urađeno
Direktna korekcija na osnovu korisnikove opaske — realan rizik gubitka postojećih projektnih instrukcija koje sam ja, ne fajl, nenamjerno predložio.

## Kako je urađeno
Jedan Edit na postojećem pasusu u `UNIVERSAL_CLAUDE.md`, proširen sa 3 rečenice na eksplicitnu proceduru.

## Šta nije dirano
Ostatak `UNIVERSAL_CLAUDE.md` (Sekcije 1-3, ostatak Sekcije 0) — netaknuto. Ostalih 7 fajlova u `templates/agent-md/` — netaknuto.

## Verifikacija
Grep provjera na Cyrillic raspon — 0 pogodaka. `git log --oneline -1` provjeren prije/poslije stage-a — bez sudara sa paralelnim radom.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: LOW rizik, čisto dokumentaciona korekcija.

## Pronađeni problemi
Originalna greška je bila moja (delivery-instrukcija u prethodnom odgovoru korisniku), ne u samom fajlu — fajl je već imao ispravan princip, samo nedovoljno konkretan da spriječi grešku u mom uputstvu kako da se koristi.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `5b2ef1f` | docs(templates): ojacaj merge proceduru za postojeci CLAUDE.md u UNIVERSAL_CLAUDE.md |

## Rizici / ograničenja
I dalje neverifikovano na stvarnom projektu korisnika (isto ograničenje kao u prethodnom izvještaju za ovaj fajl).

## Potreban follow-up
Isto kao ranije — prva stvarna primjena (sad uključujući merge sa postojećim CLAUDE.md) je jedini pravi test.

## Potrebna korisnička potvrda
Kad korisnik prvi put uradi merge na stvarnom projektu, potvrditi da li je 5-koračni postupak dovoljno jasan agentu koji ga izvršava (ne samo meni koji ga čitam sada).
