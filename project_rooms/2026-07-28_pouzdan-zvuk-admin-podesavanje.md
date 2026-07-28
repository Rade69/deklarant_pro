# Pouzdan zvuk i Admin podešavanje

## Cilj

Zamijeniti Windows sistemske aliase pouzdanim lokalno generisanim WAV
signalima i omogućiti korisniku uključivanje, isključivanje i probu zvuka u
Admin tabu.

## Pogođeno

`play_process_completion_sound` ima HIGH impact: 65 zavisnih simbola i testova
u Faktura, Agent, Zaglavlje i Services modulima. Admin settings simboli imaju
LOW impact.

## Plan

1. Zadržati postojeći API i asinhrono ponašanje zvučnog servisa.
2. Generisati kratke WAV signale u korisničkom settings folderu i reprodukovati
   ih kao fajlove, bez oslanjanja na Windows sound scheme.
3. Dodati `completion_sound_enabled` u kanonski SettingsService.
4. Dodati checkbox i dugme za probu u Settings panel.
5. Povezati postojeće, trenutno nepovezane Settings signale u AdminController.
6. Preslikati root promjene u `dist_client` i pokriti servis/UI/controller
   testovima.

## Šta NE dirati

- Parsere i sadržaj parsiranih rezultata.
- Redoslijed i poslovnu logiku uvoza/izvoza.
- Postojeće modale i njihove odluke.
- Četiri ranije korisnički izmijenjena UI fajla.
- `windows` i glavnu granu.

## Konflikti

Raniji izvještaj je Admin kontrolu naveo kao opcioni follow-up, dok je korisnik
očekivao da bude dio implementacije. Korisnikovo aktuelno očekivanje tretira se
kao važeće; potvrda nije potrebna.
