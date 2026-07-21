# Dubinska tehnička analiza aplikacije

## Datum

20.07.2026.

## Agent

Codex

## Scope

- `docs/architecture/DEKLARANT_PRO_TEHNICKA_ANALIZA_2026-07-20.md`
- arhitektura i aktivni tokovi u `app/`, `core/`, `gui/`, `services/`, `importers/`, `exporters/`, `database/`, `tests/` i `dist_client/`
- analiza bez izmjene programskog ponašanja

## Status izvora

| Izvor | Status | Upotreba |
| --- | --- | --- |
| `docs/CONTEXT.md` | aktivan | Projektne odluke, poznati bugovi i obavezni obrasci |
| `AGENTS.md` | aktivan | Projektna pravila i procedura analize/predaje |
| GitNexus indeks `deklarant_pro` | aktivan, bez FTS/embedding sloja | Simboli, pozivaoci, veze i strukturne metrike |
| Izvorni kod | aktivan, autoritativan | Potvrda stvarnog ponašanja i aktivnih putanja |
| `dist_client/` | runtime kopija, djelimično odstupa | Procjena distribucionog rizika |
| Raniji agent reporti i implementacioni plan agentskog moda | aktivni gdje su potvrđeni kodom | Status faza A-D i preostale faze E-F |

## GitNexus impact

Prije pisanja nisu mijenjani funkcije, klase ni metode, pa pre-change impact pojedinačnih simbola nije bio potreban. `gitnexus_detect_changes(scope="all")` je prijavio `LOW` rizik i nijedan pogođen izvršni proces. Prikazane promjene `AGENTS.md` i `CLAUDE.md` postojale su prije ovog zadatka i nisu dirane.

## Šta je urađeno

- mapirana je arhitektura aplikacije i end-to-end tokovi pokretanja, importa, tarifnog odlučivanja, formiranja naimenovanja, dokumentnih prijedloga, XML izvoza i agentskog chata;
- objašnjeni su tehnološki izbori i razlozi zbog kojih odgovaraju domenu aplikacije;
- identifikovana su uska grla u UI niti, DB pristupu, tarifnim upitima, draft mutacijama, agentskim provider putanjama, testnom discovery-ju i distribucionoj kopiji;
- nalazi su rangirani kao P0, P1 i P2;
- predložen je fazni plan unapređenja sa kriterijumima prihvatanja i mjerljivim metrikama;
- napravljena je detaljna analiza u `docs/architecture/DEKLARANT_PRO_TEHNICKA_ANALIZA_2026-07-20.md`.

## Zašto je urađeno

Korisnik je tražio analizu koja ne opisuje samo funkciju aplikacije, nego ulazi u implementaciju, objašnjava korištene obrasce i pronalazi stvarna uska grla. Cilj dokumenta je da posluži kao tehnička osnova za naredne zadatke, bez pokretanja širokog refactora prije potvrde prioriteta.

## Kako je urađeno

- pregledana je zajednička projektna memorija;
- korišteni su GitNexus `list_repos`, repository context, `context`, `cypher`, `query` i `detect_changes`;
- direktno su pregledani aktivni pozivaoci i relevantni blokovi koda;
- prebrojani su veliki moduli, DB reference u GUI sloju, široki exception blokovi, `processEvents` i direktni provider klijenti;
- upoređeno je izvorno stablo sa `dist_client` kopijom;
- pokrenuti su ciljani i puni pytest profili;
- preporuke su ograničene na postepene izmjene koje čuvaju postojeće domenske ugovore.

## Šta nije dirano

- nije mijenjan aplikacioni kod;
- nisu mijenjani modeli, baze, parseri, GUI ili XML izlaz;
- nisu mijenjani `AGENTS.md`, `CLAUDE.md` ni postojeće korisničke promjene;
- nisu brisani ili sinhronizovani fajlovi iz `dist_client`;
- nisu popravljani pronađeni testovi, jer je zadatak bio analiza.

## Verifikacija

- ciljani testni skup: 149 passed za 12,31 s;
- puni testni skup: 822 passed, 58 skipped, 5 xfailed, 14 failed i 1 error za 21,85 s;
- GitNexus indeks: 43.811 simbola, 67.730 veza i 300 procesa;
- `gitnexus_detect_changes`: LOW, 0 pogođenih procesa;
- nalazi o aktivnoj AI tarifnoj putanji potvrđeni su preko `TariffFacade`, `HybridTariffAgent` i njihovih pozivalaca;
- nalazi o UI/DB putanjama potvrđeni su u Faktura, Naimenovanja, Zaglavlje i Šifrarnici View modulima.

## Pronađeni problemi

- aktivna tarifna AI putanja može generisati broj bez zatvorenog skupa dokaza i zaobilazi `LLMProvider`;
- preview i apply auto-fill tokovi mogu ponoviti tarifno odlučivanje u UI niti;
- `find_mapping()` pravi potencijalni N+1 obrazac sa više DB upita po stavci;
- istorijski dokumenti se direktno dodaju u draft umjesto da ostanu prijedlozi;
- XML builder može promijeniti draft tokom izvoza;
- automatsko učenje ručnih tarifa nema dovoljan lifecycle/provenance;
- formiranje naimenovanja nije potpuno atomsko;
- `dist_client` odstupa u važnim runtime modulima;
- test suite nije potpuno zelen, a tri praćena test fajla nisu standardno otkrivena;
- veliki View i agentski handler moduli miješaju više odgovornosti.

## Konflikti / kontradiktorni izvori

Projektna pravila zahtijevaju da svi LLM pozivi idu kroz `LLMProvider` i da se bez lokalnih dokaza ne izmišlja tarifni broj. Aktivni `HybridTariffAgent` još koristi direktni Groq/Ollama klijent i `_decide_free()`. Kao važeći cilj tretirana su novija pravila i agentske faze A-D; postojeći hibridni kod je evidentiran kao legacy putanja koju treba uskladiti. Korisnička potvrda je potrebna prije implementacije zbog uticaja na ponašanje tarifnih prijedloga.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `bb703c00e7f498d4febde8b07cc873e2e6875aba` | `docs(import): popravi DOC Guard putanju` |
| `40c10ccb14daf286ba7ea70379a8091c943a8f1c` | `docs(arhitektura): dopuni analizu runtime dokazima` |

## Rizici / ograničenja

- GitNexus nema FTS/embedding indeks, pa konceptualni query nije vratio sve procese; nalazi su zato potvrđeni direktnim kodom i pozivaocima;
- PostgreSQL nije bio dostupan za dio integracionih testova;
- statički broj DB/exception referenci je indikator, ne dokaz da je svako mjesto greška;
- razlike u `dist_client` nisu sve regresije, jer dio modula može biti namjerno kompajliran u `.pyd`;
- nije rađen profiler na produkcionim količinama ni mjerenje stvarnih OCR faktura.

## Potreban follow-up

1. Potvrditi prioritete faze 0: zatvaranje slobodnog LLM tarifnog generisanja i istorijskih dokumentnih mutacija.
2. Napraviti implementacioni zadatak za `TariffProposalBatch` i batch DB lookup.
3. Ispraviti test discovery i odvojiti DB integration profil.
4. Definisati manifest i smoke test za `dist_client` build.
5. Izmjeriti stvarne PDF/Excel/OCR dokumente iz `najavauvoza/` prije paralelizacije importa.

## Potrebna korisnička potvrda

- da li tarifni prijedlog bez službenog/lokalnog kandidata uvijek treba završiti kao `UNKNOWN`;
- da li službeni rule-based dokumenti smiju ostati automatski aktivni, dok istorijski uvijek traže potvrdu;
- koji prioritet ima odziv auto-fill GUI-a u odnosu na dekompoziciju agentskih handlera;
- da li `dist_client` trenutno predstavlja stvarni release artefakt ili razvojnu kopiju.
