# Revizija plana Faktura 3-layer refaktora

## Datum

2026-07-28

## Agent

Codex

## Scope

Provjera i korekcija
`project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md` prema
trenutnom `windows@c46a6ce`. Produkcioni kod nije mijenjan.

## Status izvora

- Pi plan od 2026-07-27 — aktivan, ali djelimično zastario.
- `windows@c46a6ce` — autoritativan za trenutno stanje.
- `docs/CONTEXT.md` i `AGENTS.md` — aktivni projektni standardi.
- GitNexus indeks root Windows worktreea — aktivan.

## GitNexus impact

- `FakturaView`: HIGH, 20 direktnih importera, 33 ukupno pogođena simbola.
- `_load_data_from_draft`: HIGH, 17 direktnih, 39 ukupno pogođenih simbola,
  četiri modula.
- `_on_create_naimenovanja`: graf navodi LOW, ali ručna pretraga potvrđuje
  dodatne dinamičke Agent/Qt pozivaoce koje graf ne vidi.

## Šta je urađeno

- Ažurirano stvarno stanje na 6.329 linija i 148 metoda.
- LOW procjena blast radiusa zamijenjena potvrđenom HIGH procjenom.
- Dodani MainWindow/Agent direktni ugovori i plan javnih wrapper adaptera.
- Sačuvan `auto=True` ugovor pune automatizacije.
- Ispravljena granica View/Service za čitanje QTableWidget ćelija.
- Razjašnjeno da QTimer chunkovanje nije rad van UI threada.
- Generation token postavljen u Controller orkestraciju.
- Dodani public-contract i samostalni dist testovi.
- Faza 7 podijeljena na 7A i 7B.
- Procjena povećana na 53–83 sata.
- Branch base više nije hardkodovan unaprijed.

## Zašto je urađeno

Prvobitni plan je bio kvalitetan po strukturi, ali je potcijenio broj direktnih
pozivalaca i imao nekoliko arhitektonskih kontradikcija koje bi mogle dovesti
do novog polurefaktora: Service bi čitao widgete, Controller/View bi dijelili
vlasništvo nad validacionim lancem, a agent `auto=True` tok nije bio dovoljno
eksplicitno zaštićen.

## Kako je urađeno

Plan je poređen sa trenutnim Windows kodom, spoljnim pozivima iz MainWindowa,
Agent Controllera i import pipelinea, te GitNexus upstream rezultatima.
Promijenjen je samo planski dokument.

## Šta nije dirano

- Produkcioni Python kod.
- `windows`, `main` i aktivne feature/refactor grane.
- Korisničke UI izmjene.
- Trenutno izmijenjeni root/dist Naimenovanja modeli.
- `.env`.

## Verifikacija

- Pretraga zastarjelih brojki i formulacija.
- Provjera svih faznih naslova.
- Provjera Git statusa i scope-a.
- GitNexus impact za dva centralna simbola.

## Pronađeni problemi

GitNexus ne vidi pouzdano dinamičke Qt signalne i `hasattr` Agent pozive.
Plan zato zahtijeva kombinaciju grafa, `rg` provjere i karakterizacionih testova.

## Konflikti / kontradiktorni izvori

Prvobitni plan navodi LOW blast radius, a svježi GitNexus rezultat HIGH.
Svježi rezultat i direktna pretraga koda tretirani su kao važeći.
Korisnička potvrda za korekciju plana nije potrebna.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `ed52e9e` | `docs(faktura): azuriraj plan 3layer refaktora` |

## Rizici / ograničenja

Ovo je revidiran plan, ne dokaz da je refaktor implementiran. Procjena vremena
zavisi od kvaliteta Faze 0 i broja stvarnih faktura koje pokrivaju legacy tok.

## Potreban follow-up

Prije implementacije potvrditi koji commit `windows` grane je base i koje
aktivne grane su prethodno integrisane.

## Potrebna korisnička potvrda

Odobrenje za kreiranje posebne `refactor/faktura-3layer` grane i realizaciju
isključivo Faze 0.
