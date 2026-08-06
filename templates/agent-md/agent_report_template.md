<!--
TEMPLATE. Kopirati kao agent_reports/YYYY-MM-DD_naziv-zadatka.md i popuniti.
Objašnjenje ZAŠTO svaka sekcija postoji: templates/agent-md/METHOD.md #6.
Sekcije bez sadržaja ostaviti sa "Nema." — ne brisati sekciju.
-->

## Datum
YYYY-MM-DD

## Agent
<<< ime/model agenta koji je radio >>>

## Scope
<<< fajlovi/moduli na koje se zadatak odnosi >>>

## Status izvora
<!-- Samo za kompleksne/rizične zadatke. Ukloniti ako nije primjenjivo. -->
<<< koji raniji agent_reports/memory/kod fajlovi su korišćeni kao osnova i njihov status: aktivan / zastario / duplikat / treba potvrdu >>>

## Impact analiza
<<< rezultat provjere prije izmjene — rizik, broj/koji pogođeni simboli/procesi. "Nema" ako izmjena ne dira kod (npr. čista dokumentacija). >>>

## Reprodukcija prije izmjene
<!-- Za bugfix zadatke. Vidi AGENTS.md "Reprodukcija i provjera prije rada". -->
<<< dokaz da je problem reprodukovan PRIJE izmjene — failing test, konkretan ulaz, log, screenshot/video, precizan ručni postupak. Ako nije reprodukovano: šta je pokušano, zašto nije uspjelo, na kojoj pretpostavci se izmjena zasniva, koji rizik ostaje. "N/A" ako zadatak nije bugfix. >>>

## Kontekst korišćen
<!-- Samo za kompleksne/rizične zadatke. Koji veći fajlovi su pročitani u cijelosti i zašto (ne samo pretraženi/grep-ovani). -->
<<< POPUNI ili "Nema — samo ciljana pretraga." >>>

## Šta je urađeno
<<< kratki pregled promjena >>>

## Zašto je urađeno
<<< poslovni razlog, bug uzrok, odluka i razmotrena alternativa >>>

## Kako je urađeno
<<< tehnički pristup, koje funkcije/fajlovi >>>

## Šta nije dirano
<<< eksplicitno navesti šta je OSTAVLJENO netaknuto, uključujući nepovezan WIP koji je zatečen >>>

## Verifikacija
<<< kako je dokazano da promjena radi — testovi, ručna provjera, ispis prije/poslije. Mora odgovarati "Definition of Done" za tip promjene (vidi AGENTS.md). >>>

## Nezavisna provjera
<!-- Obavezno za HIGH/CRITICAL (vidi AGENTS.md "Nezavisna provjera"). Za LOW/MEDIUM ostaviti "N/A — nije zahtijevano". -->
- Checker korišćen: <<< DA/NE >>>
- Checker agent/model: <<< >>>
- Šta je checker provjerio nezavisno: <<< >>>
- Koje pretpostavke je pokušao oboriti: <<< >>>
- Šta je potvrđeno: <<< >>>
- Šta nije potvrđeno: <<< >>>
- Da li je promjena spremna za prihvatanje: <<< DA/NE/PARCIJALNO >>>

## Pronađeni problemi
<<< uključujući lažno pozitivne zaključke tokom rada. "Nema" ako zaista nema. >>>

## Odbačene opcije
<!-- Ako je bilo razmotrenih alternativa. "Nema" ako je rješenje bilo očigledno/jedino. -->
- Opcija: <<< >>>
- Zašto je razmatrana: <<< >>>
- Zašto je odbačena: <<< >>>
- Kada odluku ponovo otvoriti: <<< >>>

## Konflikti / kontradiktorni izvori
<<< ako postoje dva izvora koja se ne slažu (stari report vs. kod, dvije memorije, paralelan agent...), navesti oba, koji je tretiran kao važeći i zašto, i da li treba korisnička potvrda (DA/NE). "Nema" ako nema. >>>

## Commitovi
| Hash | Poruka |
| --- | --- |
| <<< >>> | <<< >>> |

## Rizici / ograničenja
<<< POPUNI >>>

## Potreban follow-up
<<< šta NIJE zatvoreno. "Nema" ako je zadatak potpuno zatvoren. >>>

## Potrebna korisnička potvrda
<<< šta korisnik treba ručno provjeriti (npr. vizuelni izgled, ponašanje na stvarnim podacima). "Nema" ako ništa ne zahtijeva ručnu potvrdu. >>>

## Ljudsko usvajanje rezultata
<!-- Popunjava ODGOVORNA OSOBA nakon pregleda ovog izvještaja — NE agent koji ga je napisao. Prazno dok se ne pregleda; agentovo popunjavanje ovog polja u svoje ime se ne računa. -->
- Odgovorna osoba: <<< >>>
- Izvještaj pročitan u cijelosti: <<< DA/NE >>>
- Ključne odluke razumljive i prihvaćene: <<< DA/NE/PARCIJALNO >>>
- Ključne tvrdnje/rezultati provjereni (ne samo agentova tvrdnja da radi): <<< DA/NE/NIJE PRIMJENJIVO >>>
- Rezultat predstavlja stvarno prihvaćeno stanje: <<< DA/NE >>>
- Dijelovi koji još nisu ljudski potvrđeni: <<< >>>
- Dozvoljena naredna akcija: <<< npr. merge/deploy/nastavak sledeće faze — ili "nijedna dok se ne potvrdi" >>>
