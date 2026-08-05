## Datum
2026-08-05

## Agent
Crush (DeepSeek V4 Pro)

## Scope
`services/agent/chat/tool_definitions.py`, `services/agent/chat/tool_policy.py`, `gui/tabs/agent/services/chat_intent_handler.py`, `services/agent/application_context_service.py`, `services/agent/chat/tariff_history_analysis_service.py`, `services/agent/chat/similar_products_analysis_service.py`, `core/draft/draft.py`

## GitNexus impact
Audit zadatak — nije mijenjan kod. Nema GitNexus impact analize za sâm audit. Za predložene nove alate (`agregiraj_stavke`, `filtriraj_stavke`): navedeni su fajlovi koje bi trebalo dirati u implementacionom koraku.

## Reprodukcija prije izmjene
Nije primjenjivo — ovo je audit, ne bugfix. Polazna tačka je SUSSINA bug (korisnikov stvaran chat transkript, dokumentovan u `agent_reports/2026-08-05_agent-pretraga-stavki-po-nazivu.md`) koji je pokazao klasu problema: LLM mora ručno brojati/računati iz sirovog teksta jer ne postoji alat za tu operaciju.

## Šta je urađeno
1. Pročitano svih 7 obaveznih fajlova (tool_definitions.py, tool_policy.py, chat_intent_handler.py, draft.py, application_context_service.py, tariff_history_analysis_service.py, similar_products_analysis_service.py) + referentni SUSSINA report
2. Klasifikovano svih 10 alata u `TOOLS` po kategoriji: DETERMINISTIČKI (3), STRUKTURIRAN (2), SIROV TEKST (1), N/A-akcioni (3), plus 1 stari alias
3. Identifikovano 15 konkretnih korisničkih upita za koje trenutno NE postoji deterministički put do tačnog odgovora
4. Upiti kategorisani u 5 grupa: Agregacija (5), Brojanje sa uslovima (3), Filtriranje po polju (3), Sortiranje/rangiranje (2), Duplikati/skupovi (2)
5. Predložena 2 nova alata (`agregiraj_stavke`, `filtriraj_stavke`) + 2 proširenja postojećih
6. Nalazi rangirani po prioritetu (KRITIČNO → VISOKO → SREDNJE → NISKO)
7. Kreiran izvještaj `docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md` u istom stilu kao `docs/agent/AGENT_TAB_CODE_AUDIT.md`

## Zašto je urađeno
SUSSINA bug je otkrio strukturni problem: arhitektura alata je dizajnirana oko unaprijed definisanih operacija (`provjeri`, `pretrazi_tarifu`), ali realni korisnički upiti su ad-hoc i zahtijevaju fleksibilnu agregaciju/filtriranje. `prikazi` — jedini alat za opšti uvid u draft — vraća sirovi HTML/tekst iz kojeg LLM mora SAM da računa sve što nije eksplicitno pokriveno nekim drugim alatom. Ovaj audit mapira KOLIKO je ta rupa široka i predlaže konkretne alate za zatvaranje.

## Kako je urađeno
Statička analiza implementacije svakog alata — za svaki je utvrđeno:
- Šta alat STVARNO vraća (čitanjem dispatch funkcija i pozvanih servisa)
- Da li je rezultat gotov/izračunat (DETERMINISTIČKI) ili sirovi tekst koji LLM mora dalje obrađivati (SIROV TEKST)
- Koje realne upite taj alat NE može da pokrije
Zatim su identifikovani obrasci (agregacija, filtriranje, sortiranje) i za svaki je testirano da li postojeći set alata može da odgovori.

## Šta nije dirano
- Nijedan produkcioni fajl — samo novi audit .md fajl
- Stara imena alata (`prikazi_naimenovanja`, `provjeri_naimenovanja`, `provjeri_tarife`, `validuj_deklaraciju`) — namjerno van scope-a
- `ChatIntentHandler` refaktor (monolit, 3035 linija) — konstatovano kao relevantan kontekst, ali nije predmet ovog audita
- `tests/test_origin_intent_routing.py` — poznato slomljen, van scope-a

## Verifikacija
Audit zadatak — nema koda za testiranje. Izvještaj je pregledan, svi alati su klasifikovani, svih 15 upita je testirano protiv postojećeg seta alata. Provjera: pročitane su sve dispatch funkcije i servisi koje pozivaju.

## Nezavisna provjera
Nije primjenjivo — audit zadatak bez izmjene koda. Preporuka: kod implementacije predloženih alata (`agregiraj_stavke`, `filtriraj_stavke`) uraditi nezavisnu provjeru (GitNexus impact + code review).

## Pronađeni problemi
1. `prikazi` — centralni alat za uvid u draft — je SIROV TEKST. Ovo je root cause svih 15 identifikovanih rupa.
2. Samo 3 od 10 alata su DETERMINISTIČKI (vraćaju tačan, izračunat rezultat).
3. `ChatIntentHandler` (3035 linija) je monolit — svaki novi alat dodaje još jednu elif granu i funkciju u isti fajl, pogoršavajući tehnički dug.

## Odbačene opcije
- Predlaganje potpuno novog "query engine"-a (SQL-like upiti nad draftom) — odbačeno, preambiciozno za prvi korak; `agregiraj_stavke` + `filtriraj_stavke` pokrivaju 80% realnih upita sa minimalnom implementacijom
- Spajanje `agregiraj_stavke` i `filtriraj_stavke` u jedan alat — odbačeno, različite su operacije (agregacija vs. filtriranje), jasnije razdvojeno

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
|------|--------|
| (pending) | `docs(agent): audit pokrivenosti agent alata — SUSSINA-klasa bugova` |

## Rizici / ograničenja
- Audit identifikuje RUPE, ali NE garantuje da su SVI mogući upiti pokriveni — fokus je na realnim, čestim upitima tokom rada na deklaraciji
- Predloženi alati (`agregiraj_stavke`, `filtriraj_stavke`) su konceptualni — tačan API i implementacija zavise od korisnikove potvrde
- Rangiranje prioriteta je procjena autora na osnovu poznavanja domenskog toka rada — korisnikova potvrda je potrebna

## Potreban follow-up
1. Korisnikova potvrda: da li implementirati `agregiraj_stavke` i/ili `filtriraj_stavke`, i kojim redoslijedom
2. Implementacija Prioritet 1 (`agregiraj_stavke`) — procijenjeno 4 fajla, ~150-200 linija koda
3. Implementacija Prioritet 2 (`filtriraj_stavke`) — procijenjeno 4 fajla, ~200-250 linija koda
4. End-to-end testiranje svakog novog alata kroz stvarnu GUI chat sesiju

## Potrebna korisnička potvrda
1. Da li se slažeš sa prioritizacijom? (agregacija → filtriranje → proširenje pretrazi_stavke)
2. Da li `agregiraj_stavke` API (operacija, polje, filter, top_n) pokriva tvoje realne upite?
3. Da li odmah implementirati Prioritet 1 ili prvo pregledati kompletan audit?
