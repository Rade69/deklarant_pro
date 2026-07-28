# Zvučna obavještenja o završetku procesa

## Datum

2026-07-28

## Agent

Codex

## Scope

Windows zvučna obavještenja za završetak Pune automatizacije, ručnog uvoza,
Excel/PDF izvoza, pregleda faktura i ASYCUDA XML izvoza, u root i
`dist_client` runtime-u.

## Status izvora

- `docs/CONTEXT.md` — aktivan, kanonski izvor projektnih pravila.
- Windows grana `24a7272` — aktivna osnova radne grane.
- Postojeće UI izmjene u četiri generisana UI fajla — korisničke promjene,
  nisu dio zadatka i nisu dirane.

## GitNexus impact

- `_finish_puna_auto_pipeline`: LOW, jedan direktni pozivalac; obuhvaćeni tok
  Pune automatizacije i njegovi testovi.
- `_on_export_xml`: LOW.
- `_show_manual_import_workflow_result`: LOW, jedan direktni pozivalac.
- `_on_export_pdf`: LOW.

Nije pronađen HIGH ili CRITICAL impact.

## Šta je urađeno

- Uveden je zajednički, asinhroni Windows servis sa odvojenim zvukovima za
  uspjeh, upozorenje i grešku.
- Puna automatizacija zvučno razlikuje uspjeh, parcijalni rezultat i grešku;
  otkazivanje namjerno ostaje bez zvuka.
- Ručni pojedinačni i grupni uvoz zvučno označavaju konačni rezultat.
- Excel, PDF, pregled faktura i ASYCUDA XML izvoz daju zvuk neposredno prije
  postojećeg modalnog obavještenja.
- Implementacija je preslikana u `dist_client`.
- Dodani su testovi servisa i ishoda Pune automatizacije.
- Naknadnom živom provjerom otkriven je i zatvoren nepokriven legacy put
  parsiranja, koji se koristi kada je glavna lista već učitana ili rezultat
  nije `ImportResult`.
- Druga živa provjera pokazala je da EUR.1/PE dijalog blokira završni modal.
  Zvuk ručnog parsiranja zato je pomjeren neposredno prije prvog interaktivnog
  dijaloga, a kasniji dupli zvuk je uklonjen.

## Zašto je urađeno

Dugi procesi ne moraju biti stalno u fokusu korisnika. Zvuk daje nenametljiv
signal da je proces završen, dok modal ostaje autoritativna poruka sa detaljima.
Sistemski Windows aliasi izbjegavaju distribuciju dodatnih audio fajlova.

## Kako je urađeno

Servis koristi `winsound.PlaySound` sa `SND_ALIAS`, `SND_ASYNC` i
`SND_NODEFAULT`. Sve očekivane platformne i runtime greške se presreću, pa
zvučna obavijest ne može promijeniti ishod poslovnog procesa. Varijabla
`PROCESS_COMPLETION_SOUND=false` potpuno isključuje reprodukciju.

## Šta nije dirano

- Nisu mijenjani algoritmi uvoza, izvoza, validacije niti kreiranja XML-a.
- Nisu mijenjani tekstovi i ponašanje postojećih modalnih poruka.
- Nisu dirane postojeće korisničke izmjene u UI fajlovima.
- Promjene nisu spojene u `windows` niti u glavnu granu.

## Verifikacija

- Ciljani regresioni testovi, uključujući redoslijed zvuk → EUR.1: 32 prošla.
- Kompletan test paket nakon promjene redoslijeda: 1381 prošlo, 72 preskočena,
  5 očekivano neuspješnih.
- Root i `dist_client` kopije provjerene su na funkcionalni paritet.
- `git diff --check` ne prijavljuje greške u promjenama ovog zadatka.

## Pronađeni problemi

Prvi testni prolaz bez lokalne konfiguracije i razvojne SQLite baze dao je
nepovezane DB greške. Nakon korišćenja lokalnih, git-ignorisanih testnih
kopija konfiguracije i baze kompletan paket je prošao.

Živa korisnička provjera pokazala je da prvi obuhvat nije uključio legacy
završne callbackove Faktura taba. Novi objedinjeni put je bio pokriven, ali
rad sa prethodno učitanom glavnom listom namjerno ostaje na legacy toku.
Zvučni pozivi su zato dodani i tom toku, uključujući uspjeh, upozorenje i
grešku.

Prvobitno mjesto uspješnog zvuka bilo je iza EUR.1/PE dijaloga. Pošto je taj
dijalog modalni i blokirajući, korisnik opravdano nije čuo signal kada se
parsiranje završilo. Regresioni test sada eksplicitno zahtijeva redoslijed
`sound:success` prije poziva `_show_eur1_dialog()`.

## Konflikti / kontradiktorni izvori

Nema funkcionalnih konflikata. GitNexus analiza je privremeno promijenila samo
generisane brojače u `AGENTS.md` i `CLAUDE.md`; te promjene nisu dio zadatka i
vraćene su. Korisnička potvrda nije potrebna.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `f2ed838` | `feat(obavjestenja): dodaj zvuk zavrsetka procesa` |
| `eff49c2` | `fix(uvoz): dodaj zvuk legacy zavrsetku parsiranja` |
| `37cabc9` | `fix(uvoz): pusti zvuk prije eur1 dijaloga` |

## Rizici / ograničenja

Zvuk zavisi od Windows sistemske zvučne konfiguracije, izlaznog uređaja i
korisničke jačine zvuka. Na platformi bez `winsound` servis se bezbjedno
isključuje i aplikacija nastavlja bez zvuka.

## Potreban follow-up

Nema obaveznog tehničkog follow-upa. Po želji se kasnije može dodati korisnička
postavka u Admin tabu umjesto upravljanja kroz `.env`.

## Potrebna korisnička potvrda

Nakon pokretanja Windows builda ručno potvrditi da su tri sistemska zvuka
dovoljno prepoznatljiva na stvarnom računaru i podešenoj jačini zvuka.
