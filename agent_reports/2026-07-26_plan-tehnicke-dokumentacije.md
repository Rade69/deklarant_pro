# Plan tehničke dokumentacije

## Datum

2026-07-26

## Agent

Codex

## Scope

- `docs/technical/PLAN_IZRADE_TEHNICKE_DOKUMENTACIJE.md`

## Status izvora

- `AGENTS.md` — aktivan, kanonski izvor projektnih pravila;
- `docs/CONTEXT.md` — aktivan izvor poslovnih i arhitekturnih odluka;
- GitNexus indeks — svjež, ali konceptualna FTS pretraga degradirana;
- postojeći `docs/` dokumenti — mješovit status, predviđena pojedinačna provjera
  prije korišćenja u budućoj tehničkoj dokumentaciji.

## GitNexus impact

Staged provjera prijavila je LOW rizik, bez promijenjenih simbola i bez pogođenih
izvršnih procesa. Izmjena je isključivo dokumentaciona.

## Šta je urađeno

Napravljen je detaljan plan izrade modularne tehničke dokumentacije, sa:

- obimom i ciljnim publikama;
- hijerarhijom izvora istine;
- predloženom strukturom `docs/technical/`;
- osam faza izrade;
- standardom pojedinačnih poglavlja i dijagrama;
- matricom provjere;
- kriterijumima završetka;
- rizicima i redoslijedom commitova.

## Zašto je urađeno

Korisnik je tražio da se prije same tehničke dokumentacije napravi i sačuva plan.
Plan smanjuje rizik da nova dokumentacija objedini zastarjele analize ili predstavi
planirano ponašanje kao trenutno implementirano.

## Kako je urađeno

Plan je zasnovan na kanonskim projektnim pravilima, zajedničkom kontekstu,
inventaru postojeće dokumentacije i ranijem pregledu glavnih modula aplikacije.

## Šta nije dirano

Nisu pisana poglavlja tehničke dokumentacije i nisu mijenjani aplikacijski kod,
testovi, konfiguracija, baze, postojeća dokumentacija niti `dist_client`.

## Verifikacija

- `git diff --check` bez grešaka;
- GitNexus staged provjera: LOW rizik i 0 pogođenih procesa;
- pre-commit hook završen uspješno.

Test suite nije pokretan jer nema izmjene izvršnog koda.

## Pronađeni problemi

GitNexus konceptualni upit prijavio je nedostajući FTS sloj i vratio prazan
rezultat iako je indeks svjež. Buduća izrada će koristiti direktni kontekst
simbola, izvršne tokove i izvorni kod kao dopunu.

## Konflikti / kontradiktorni izvori

Postojeća dokumentacija sadrži dokumente iz više razvojnih faza. Plan zato
propisuje da se svaka važna tvrdnja potvrdi trenutnim kodom, testom ili novijom
kanonskom odlukom. Korisnička potvrda trenutno nije potrebna.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `4ab2acf` | `docs(tehnicka): dodaj plan izrade dokumentacije` |

## Rizici / ograničenja

Plan ne potvrđuje da su sva buduća poglavlja već tehnički provjerena. Provjera je
dio faza izrade i mora se obaviti prije objavljivanja svakog poglavlja.

## Potreban follow-up

Nakon korisničke potvrde strukture započeti Fazu 1: inventar i provjeru izvora.

## Potrebna korisnička potvrda

Prije pune izrade poželjno je potvrditi strukturu, potrebu za PDF/HTML izdanjem i
politiku prema starim dokumentima.
