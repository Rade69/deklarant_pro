# Opus review i dopuna tehničke analize

## Datum

21.07.2026.

## Agent

Codex

## Scope

- `docs/architecture/DEKLARANT_PRO_TEHNICKA_ANALIZA_2026-07-20.md`
- `docs/CONTEXT.md`
- read-only provjera `dist_client`, Nuitka/PyInstaller artefakata, DB testova, audita i grupisanja
- minimalna DOC Guard korekcija u source i dist `smart_pdf_importer.py`

## Status izvora

| Izvor | Status | Upotreba |
| --- | --- | --- |
| Opus 4.8 komentar | aktivan review | Hipoteze i promjena prioriteta za provjeru |
| `docs/CONTEXT.md` | aktivan | Distribucioni i agentski projektni ugovori |
| Source i `dist_client` | aktivni, ali nisu dokaz udaljene instalacije | Import rezolucija, hash i diff provjera |
| PyInstaller `Analysis-00.toc`/`PYZ-00.toc` | aktivni lokalni build trag | Potvrda modula uključenih u lokalni EXE |
| UINO uputstvo o popunjavanju deklaracije | primarni domenski izvor | Item-level polja 37, 39 i 41 |
| GitNexus | aktivan uz degradiran FTS | Impact i detect-changes provjera |

## GitNexus impact

Dokumentacione izmjene ne pogađaju izvršne procese. DOC Guard komentar neposredno ispred `_parse_master_frigo` GitNexus je mapirao na funkciju:

- source: `LOW`, 3 pogođena simbola, 1 direktni pozivalac, 0 procesa;
- dist: `LOW`, 1 direktni pozivalac; prijavljeni proces je samo postojeći `parse_smart_pdf` tok;
- stvarna izmjena je isključivo skraćivanje `# DOC:` komentara, bez promjene funkcije.

Završni staged `gitnexus_detect_changes` za dokumentaciju: `LOW`, 0 pogođenih izvršnih procesa.

## Šta je urađeno

- dokazana je stvarna import rezolucija u `dist_client`;
- potvrđeno je da aktivni dist hibridni tarifni agent sadrži `_decide_free()`;
- potvrđeno je da lokalni PyInstaller build uključuje hibridni agent, fasadu i XML builder;
- upoređeni su source i dist hashovi hibridnog agenta i XML buildera;
- provjereni su DB characterization testovi i nepostojanje kontrolisanog DB fixture-a;
- potvrđeno je da GUI auto-fill nema tarifni audit;
- pronađeno je da `AuditEvent.extra.operation_id` nije serijalizovan u logger zapis;
- četiri ključa grupisanja preformulisana su iz univerzalnog aksioma u trenutno projektno pravilo koje traži domenski pregled za druge postupke;
- u plan je dodana Faza -1 i realni solo kalendarski okvir;
- DOC Guard `BROKEN` linkovi su svedeni na važeću putanju.

## Zašto je urađeno

Opus review je ispravno primijetio da se sigurnosna izmjena ne smije planirati prije dokaza šta isporučeni klijent izvršava i prije pouzdane DB testne mreže. Cilj dopune je razdvojiti dokazani lokalni runtime od još nepotvrđene konkretne klijentske instalacije i ukloniti preširoke tvrdnje iz prvobitne analize.

## Kako je urađeno

- `importlib.util.find_spec()` je pokrenut iz `dist_client` okruženja;
- kompajlirana `TariffFacade.suggest()` je behavioral probom natjerana kroz mapping/RAG promašaj i potvrđen je poziv `_try_ai()`;
- SHA-256 i `git diff --no-index` korišteni su za kritične module;
- PyInstaller TOC i git istorija korišteni su za vremensku potvrdu lokalnih artefakata;
- pregledani su `tests/conftest.py`, DB testovi, pytest markeri i auto-fill/audit implementacija;
- konsultovano je službeno UINO uputstvo za item-level deklaracijska polja;
- analiza, kontekst i izvještaji ažurirani su bez promjene aplikacionog ponašanja.

## Šta nije dirano

- nije uklonjen `_decide_free()`;
- nisu mijenjani tarifni, XML, audit ili DB servisi;
- nije napravljena test baza;
- nije promijenjeno grupisanje naimenovanja;
- nisu sinhronizovani niti rebuildani distribucioni artefakti;
- nisu dirane korisničke promjene u `AGENTS.md`, `CLAUDE.md` i ostalim nepovezanim fajlovima.

## Verifikacija

- `dist_client` import:
  - `services.tariff_facade` -> `.pyd`;
  - `services.tariff_mapping_service` -> `.pyd`;
  - `services.agent.tariff.hybrid_tariff_agent` -> `.py`;
  - `exporters.asycuda_xml_builder` -> `.py`;
- hibridni agent source/dist SHA-256 je identičan;
- dist fajl sadrži `_decide_free` definiciju i poziv;
- behavioral proba kompajlirane fasade završila je u kontrolisanoj AI grani;
- PyInstaller TOC sadrži sva tri kritična modula;
- XML builder diff nema promjenu XML poslovne logike;
- `py_compile` je prošao za oba DOC Guard korigovana importer fajla;
- DOC Guard poslije korekcije: `BROKEN: 0`, preostala su 58 ranije nastalih `STALE` upozorenja;
- GitNexus: `LOW`, bez pogođenih procesa za dokumentacionu predaju.

## Pronađeni problemi

- trenutni lokalni dist/runtime dokaz nije automatski dokaz stanja na klijentskoj mašini;
- postoje paralelni Nuitka `dist_client` i PyInstaller installer tokovi bez zajedničkog manifesta;
- DB testovi sa živom bazom su pogrešno smješteni u `unit` i nisu označeni markerom;
- DB testovi zavise od konkretnih produkcijskih zapisa i nemaju rollback fixture;
- `AuditEvent.extra` se ne emituje u log;
- GUI auto-fill nema actor/provenance audit;
- `InvoiceLine` nema polja za postupak i kvotu, iako su ta polja na nivou naimenovanja;
- DOC Guard je imao dva postojeća `BROKEN` linka i 55 početnih `STALE` upozorenja; nakon minimalne korekcije BROKEN je 0, a broj STALE je porastao zbog vremena izmjene dva importer fajla.

## Konflikti / kontradiktorni izvori

Pitanje je bilo da li produkcijski `.pyd` sadrži `_decide_free()`. Precizan nalaz je da sama funkcija nije u tarifnom `.pyd`, nego u običnom `.py` modulu koji kompajlirana fasada aktivno učitava. Zato je praktični odgovor "da, distribucioni runtime ima tu putanju", ali nije tehnički tačno reći da je definicija unutar `.pyd` fajla.

Tvrdnja da su četiri ključa univerzalno dovoljna nije potvrđena. Kao važeće ostaje trenutno projektno pravilo, dok UINO item-level polja zahtijevaju poseban domenski review prije proširenja proizvoda.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `bb703c00e7f498d4febde8b07cc873e2e6875aba` | `docs(import): popravi DOC Guard putanju` |
| `40c10ccb14daf286ba7ea70379a8091c943a8f1c` | `docs(arhitektura): dopuni analizu runtime dokazima` |

## Rizici / ograničenja

- nije očitan hash sa stvarne udaljene klijentske instalacije;
- postojeći installer i PyInstaller EXE imaju različite datume builda;
- XML parity zaključak važi za trenutno dostupne source/dist fajlove, ne za svaki ranije isporučeni installer;
- službeno uputstvo potvrđuje item-level polja, ali konačnu matricu grupisanja mora potvrditi carinski domenski stručnjak;
- puni pytest nije ponovljen jer nije mijenjan izvršni kod; prethodni puni rezultat ostaje 822 passed, 14 failed i 1 error.

## Potreban follow-up

1. Napraviti malu dijagnostičku komandu koja na klijentu ispisuje build ID i hash kritičnih modula.
2. Uvesti kontrolisani PostgreSQL integration fixture.
3. Tek zatim mijenjati tarifnu AI putanju.
4. Proširiti audit na svaki GUI/agent/auto tarifni upis.
5. Organizovati domenski review matrice grupisanja prije podrške dodatnim postupcima i kvotama.

## Potrebna korisnička potvrda

- koji distribucioni tok trenutno koriste stvarni klijenti: Nuitka `dist_client`, PyInstaller installer ili oba;
- da li je moguće očitati verziju/hash na bar jednoj aktivnoj klijentskoj mašini;
- ko može potvrditi domensku matricu grupisanja za postupke, kvote i dopunske jedinice.
