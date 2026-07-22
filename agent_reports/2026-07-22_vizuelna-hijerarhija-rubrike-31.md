## Datum

2026-07-22

## Agent

Codex

## Scope

`dist_client/styles/naimenovanja_components.qss`, pravila rubrike 31.

## Status izvora

Aktivni QSS i postojeći View koji zamjenjuje trgovački naziv sa `QTextEdit` tretirani su kao važeći. Poslovna pravila iz `docs/CONTEXT.md` o trgovačkom nazivu i ASYCUDA ograničenju ostala su autoritativna.

## GitNexus impact

Ciljana provjera `_setup_trading_name_field` vratila je LOW: jedan direktni pozivalac i nijedan pogođeni proces. Zbirni `detect_changes` je prikazao MEDIUM zbog nepovezanih PDF izmjena drugih zadataka; nisu uključene u ovaj commit.

## Šta je urađeno

Ublažena je pozadina rubrike 31, naslov je jasnije označen, a ulazna polja imaju ujednačene granice. Jarkoplava polja naziva pakovanja i trgovačkog naziva zamijenjena su mirnijom plavosivom obradom uz lijevu akcentnu liniju. Dodato je jasno fokusno stanje trgovačkog naziva.

## Zašto je urađeno

Rubrika 31 je bila vizuelno zasićenija od već uređenih blokova 32–46. Nova hijerarhija jasnije razlikuje referentne podatke i glavni trgovački naziv, uz prijatniju paletu za dugotrajan rad.

## Kako je urađeno

Izmijenjeni su isključivo postojeći QSS selektori grupe 31 i njenih polja. Nisu mijenjani widgeti ni runtime logika.

## Šta nije dirano

Nisu mijenjani fontovi, geometrija, sadržaj polja, auto-popunjavanje, formatiranje trgovačkih naziva, ograničenje od 280 znakova, signali, Controller ni Service.

## Verifikacija

- QSS zagrade su uparene.
- `git diff --check` je prošao.
- Ciljani testovi: 9/9 prošlo.
- Commit sadrži samo jedan stylesheet.

## Pronađeni problemi

Postojalo je kasnije QSS pravilo za `le_r31_vrsta_naziv` koje bi prebrisalo ranije pravilo; oba nivoa su usklađena.

## Konflikti / kontradiktorni izvori

Zbirni GitNexus rezultat sadrži nepovezane izmjene PDF exportera. Ciljani impact i staged diff tretirani su kao važeći za ovaj zadatak.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `a22a7ab` | `style(naimenovanja): uredi vizuelnu hijerarhiju rubrike 31` |

## Rizici / ograničenja

Rizik je nizak i vizuelan. Runtime inline stilovi tarifnih opisa i dalje imaju prednost nakon automatskog popunjavanja, što je namjerno zadržano.

## Potreban follow-up

Po vizuelnoj provjeri eventualno dodatno ublažiti runtime zelenu i plavu boju tarifnih opisa u zasebnom segmentu.

## Potrebna korisnička potvrda

Provjeriti čitljivost rubrike 31 sa stvarnim višelinijskim trgovačkim nazivom i fokusom u polju.
