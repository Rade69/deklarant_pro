## Datum
2026-08-08

## Agent
Claude Sonnet 5 (Claude Code)

## Scope
`gui/tabs/faktura_view.py`, `dist_client/gui/tabs/faktura_view.py`,
`catalogs.exporter_xml_index` (podaci, ne šema).

## Status izvora
`docs/flow_previous_declaration.md` (korisnikov fajl, nekomitovan prije ovog
zadatka) opisivao je `_ensure_exporter_index_ready()` kao gotovu
funkcionalnost — status: **zastario/aspirational**, funkcija nikad nije
stvarno ušla u kod (samo u dokumentaciji i u neprimijenjenom `git stash` od
zaustavljenog paralelnog agenta, vidi `agent_reports/2026-08-08_spajanje-
grana-windows-main-push.md`).

## Impact analiza
GitNexus `impact()` za `_on_load_previous_declaration`: risk LOW, 0 pogođenih
procesa/modula (signal handler bez upstream pozivalaca).
`detect_changes(scope=unstaged)` prije commit-a: risk LOW, 15 promijenjenih
simbola u 4 fajla (2 su GitNexus auto-osvježen banner u AGENTS.md/CLAUDE.md,
2 su moje ciljane izmjene), 0 affected_processes.

## Reprodukcija prije izmjene
Korisnikov opis (klik na "Prethodna deklaracija" uvijek javlja "nije
pronađeno") + direktna DB provjera: `SELECT COUNT(*) FROM catalogs.
exporter_xml_index` → 6 redova (arhiva ima ~5700 XML fajlova). `grep -r
_ensure_exporter_index_ready` u cijelom repou → jedini pogodak je
`docs/flow_previous_declaration.md`, nula pogodaka u `.py` fajlovima.

## Kontekst korišćen
`docs/flow_previous_declaration.md` (cijeli, korisnik tražio da se pročita),
`services/agent/learning/exporter_xml_indexer.py` (find_xml_for_pair,
reindex, scan_xml_folder, get_xml_folder — cijele funkcije pročitane).

## Šta je urađeno
1. Dodata `_ensure_exporter_index_ready()` metoda u `FakturaView` (oba
   fajla) — provjerava broj redova u `catalogs.exporter_xml_index`, ako je
   0, prikazuje status "⏳ Gradim indeks..." i pokreće `reindex()`.
2. Pozvana na početku `_on_load_previous_declaration()`, prije
   `find_xml_for_pair()`.
3. Jednokratno pokrenut `reindex()` ručno (pozadinski proces) protiv
   `H:\New folder\NOVA ASIKUDA` — popunio `catalogs.exporter_xml_index` sa
   2499 parova (2166 unikatnih izvoznika), zamijenio 6 zastarjelih redova.

## Zašto je urađeno
Korisnikov zahtjev: automatska pretraga treba da radi (pronađe fajl i pita
za potvrdu uvoza), umjesto da uvijek pada na ručni odabir. Root cause je bio
da funkcija koja bi to omogućila (auto-build indeksa) nikad nije ušla u kod
— dokumentacija je opisivala namjeru, ne stvarno stanje.

## Kako je urađeno
Nova metoda napisana nezavisno (ne kopirana iz zaostalog `git stash`-a — taj
stash nije nezavisno pregledan/testiran, pa po AGENTS.md "Eksterni/tuđi
predlog koda" pravilu nije usvojen bez provjere). Koristi isti
`self.lbl_validation` status-label pattern (`setProperty("status",...)` +
`unpolish/polish`) koji se već koristi drugdje u istom fajlu (npr. linija
1748-1751) — konzistentno sa postojećim konvencijama, ne novi UI element.

## Šta nije dirano
- Ostatak zaostalog `git stash@{0}` (druge izmjene u `xml_header_
  extraction.py`, `tariff_service.py`, `naimenovanja_controller.py`, UI
  fajlovi) — i dalje netaknut, van scope-a.
- Dijalog "Pronađena prethodna deklaracija... Učitati?" — nije mijenjan,
  već je tačno radio ono što korisnik traži (samo ranije skoro nikad nije
  imao šta da pronađe).
- `sync_tariff_knowledge_base()` i `sync_duim_rule_knowledge_base()` koje
  `reindex()` interno poziva — nisu modifikovane, samo pokrenute kao dio
  postojećeg `reindex()` toka.

## Verifikacija
- `python -m py_compile` na oba izmijenjena fajla — OK.
- End-to-end na realnoj `dmserver` bazi: `find_xml_for_pair('CMANA')` →
  pronađeno (`match_type: exporter_only`), prije fix-a bi vratilo `None`.
- `pytest tests/unit -q -k "exporter_xml_indexer or previous_declaration or
  faktura_controller"` → 42 passed, 2 failed — oba neuspjeha potvrđeno
  pre-existing (identična kao prije ovog fix-a, vidi prethodni agent_report
  za merge zadatak), NE regresija. `diff` root/dist_client fajlova oko nove
  metode → identično (0 linija razlike), potvrđuje da moja izmjena nije
  unijela novu drift u `test_dist_faktura_modules_match_root`.
- Blagic/Leburic/Sumaprom testirani — nisu pronađeni ni pod jednom
  varijantom imena u indeksu; provjereno da to NIJE bug (te firme genuinely
  nemaju XML u ovoj arhivi), ne lažni negativ.

## Nezavisna provjera
- Checker korišćen: NE
- N/A — LOW rizik po GitNexus-u, jednostavna dodatna funkcija bez promjene
  postojeće logike, verifikovana end-to-end na realnim podacima.

## Pronađeni problemi
Nema novih — isti obrazac kao `MIN_SIMILARITY_THRESHOLD` bug iz prethodnog
zadatka (dokumentacija/stash opisuje funkcionalnost koja nikad nije stvarno
spojena u kod).

## Odbačene opcije
- Opcija: primijeniti `_ensure_exporter_index_ready()` direktno iz zaostalog
  `git stash@{0}`.
- Zašto je razmatrana: već postojala gotova implementacija tamo.
- Zašto je odbačena: AGENTS.md zahtijeva nezavisnu provjeru tuđeg
  koda prije usvajanja (checkout, testovi, pregled diff-a) — taj stash
  sadrži i druge nepregledane izmjene umiješane u isti diff, rizičnije je
  cherry-pick-ovati dio iz njega nego napisati čistu, izolovanu verziju.
- Kada odluku ponovo otvoriti: ako se odluči da se ostatak stash@{0} ipak
  pregleda i primijeni, ovu metodu treba uporediti sa stash verzijom da se
  izbjegne duplikat.

## Konflikti / kontradiktorni izvori
`docs/flow_previous_declaration.md` je tvrdio da je `_ensure_exporter_index_
ready()` gotova — kod je pokazao suprotno. Kod je tretiran kao istina (grep
ne laže), dokumentacija je bila aspirational/opisivala planirani dizajn.
Sada je dokumentacija tačna (funkcija stvarno postoji i radi). Korisnička
potvrda: nije bila potrebna — jednoznačno provjerljivo grep-om.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `4bf9d1f` | fix(faktura): izgradi exporter_xml_index automatski ako je prazan |

## Rizici / ograničenja
- `reindex()` briše i ponovo gradi CIJEL indeks (`DELETE FROM ... `) — ako
  se pozove sa praznim/nedostupnim `XML_LEARNING_FOLDER`, `scan_xml_folder()`
  vraća prazan rezultat i `reindex()` rano izlazi bez brisanja (provjereno u
  kodu, linija 429-431) — sigurno, ali vrijedno napomene za buduće izmjene.
- Auto-build se okida samo kad je indeks TAČNO 0 redova — ako se ikad opet
  desi djelimično/zastarjelo punjenje (kao ranije 6 redova), auto-build se
  neće ponovo pokrenuti automatski (isti scenario koji je izazvao ovaj bug
  prvi put, samo sad barem prazan-indeks slučaj ima siguran fallback).

## Potreban follow-up
Nema — zadatak zatvoren, verifikovan na realnim podacima.

## Potrebna korisnička potvrda
Ručna provjera u pokrenutoj aplikaciji: klik na "Prethodna deklaracija" za
poznatog izvoznika (npr. CMANA) treba sada direktno prikazati "Pronađena
prethodna deklaracija... Učitati?" bez prethodnog "nije pronađeno" koraka.

## Ljudsko usvajanje rezultata
- Odgovorna osoba: <<< >>>
- Izvještaj pročitan u cijelosti: <<< DA/NE >>>
- Ključne odluke razumljive i prihvaćene: <<< DA/NE/PARCIJALNO >>>
- Ključne tvrdnje/rezultati provjereni (ne samo agentova tvrdnja da radi): <<< DA/NE/NIJE PRIMJENJIVO >>>
- Rezultat predstavlja stvarno prihvaćeno stanje: <<< DA/NE >>>
- Dijelovi koji još nisu ljudski potvrđeni: <<< >>>
- Dozvoljena naredna akcija: <<< >>>
