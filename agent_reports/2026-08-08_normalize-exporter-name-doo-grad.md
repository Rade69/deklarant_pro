## Datum
2026-08-08

## Agent
Claude Sonnet 5 (Claude Code)

## Scope
`services/agent/learning/exporter_xml_indexer.py`, `dist_client/services/
agent/learning/exporter_xml_indexer.py` (funkcija `normalize_exporter_name`),
`catalogs.exporter_xml_index` (podaci, ne šema).

## Status izvora
Nastavak `agent_reports/2026-08-08_prethodna-deklaracija-auto-index.md` —
taj fix (prazan indeks) je bio ispravan i potreban, ali NIJE bio jedini
uzrok. Korisnik je nakon njega i dalje dobijao "nije pronađeno" za realnu
fakturu.

## Impact analiza
GitNexus `impact()` za `normalize_exporter_name` (root fajl): **CRITICAL**,
29 povezanih simbola, `direct: 3` (`scan_xml_folder`, `find_xml_for_pair`,
`find_xml_by_consignee`), 5 `affected_processes` (uključujući agent chat
`_build_session_zone`/`_build_context`, `header_autofill_service.
auto_fill_header_from_history`, `xml_workflow_service.primjeni_xml_template`,
`mcp_facade.find_exporter_xml_template`, Admin Learning panel
`_ReindexWorker`), `modules_affected: 6` (Learning, Agent, Workflow, Unit,
Widgets, Faktura). Korisnik obaviješten po AGENTS.md "Handoff visokog
rizika" formatu, potvrdio nastavak (AskUserQuestion → "Da, uradi fix +
reindex"). `project_rooms/2026-08-08_normalize-exporter-name-doo-grad.md`
napravljen prije izmjene (sada spojen u ovaj izvještaj).

Nakon izmjene, `detect_changes(scope=unstaged)`: risk **MEDIUM** (diff-scope
provjera, ne blast-radius), 2 `affected_processes` (`Run →
Normalize_exporter_name`), scope tačno odgovara planu.

## Reprodukcija prije izmjene
1. Korisnikov screenshot: "Nije pronađena prethodna deklaracija za
   izvoznika 'CMANA DOO KRNJEVO'" — NAKON što je DB konekcija već bila
   popravljena (provjereno `SELECT 1` uspješno prije ovog koraka).
2. Direktna reprodukcija u Python konzoli: `find_xml_for_pair('CMANA DOO
   KRNJEVO')` → `None`, dok `find_xml_for_pair('CMANA')` → pronađeno.
3. Root cause potvrđen poređenjem `normalize_exporter_name('CMANA DOO
   KRNJEVO')` → `'CMANA DOO KRNJEVO'` (nepromijenjeno) naspram uskladištenog
   `exporter_normalized = 'CMANA'` za arhivski zapis `'CMANA DOO'`.

## Kontekst korišćen
`services/agent/learning/exporter_xml_indexer.py` (cijela funkcija
`normalize_exporter_name` + `find_xml_for_pair` pročitane), GitNexus
`impact()` puni izlaz (29 simbola, 5 procesa) pregledan prije odluke o
scope-u izmjene.

## Šta je urađeno
1. Dodat drugi regex prolaz u `normalize_exporter_name()`
   (`suffixes_with_city_to_remove`) koji uklanja pravni oblik (`DOO`,
   `D.O.O.`, `LTD`, `LLC`, `A.D.`, `GMBH`, `S.R.O.`) PLUS 1-2 riječi grada
   (bez brojeva) odmah iza njega, na kraju stringa. Primijenjen PRIJE
   postojeće logike — imena bez grada prolaze kroz staru logiku
   nepromijenjeno.
2. Identična izmjena u `dist_client/services/agent/learning/
   exporter_xml_indexer.py`.
3. `reindex()` ponovo pokrenut protiv `H:\New folder\NOVA ASIKUDA` da se
   svi `exporter_normalized`/`consignee_normalized` ključevi u bazi
   preračunaju dosljedno sa novom logikom.

## Zašto je urađeno
Docstring funkcije je već tvrdio `'KONZUM DOO BEOGRAD' → 'KONZUM'` kao
podržan slučaj — nikad nije bio implementiran (regex usidren na `$` bez
mogućnosti grada iza). "Firma DOO Grad" je uobičajen format naziva
izvoznika na fakturama u regionu — bug je pogađao SVAKOG izvoznika sa
gradom u imenu, ne samo CMANA, i sve callere `normalize_exporter_name`
(agent chat, auto-popuna zaglavlja, XML template primjena), ne samo
"Prethodna deklaracija" dugme.

## Kako je urađeno
Nova regex lista testirana lokalno (izolovano, van GUI-ja) na skupu
poznatih realnih naziva (CMANA, ENMON, Šumaprom, KONZUM iz docstring-a,
Blagić Loren, Leburić Komerc) prije primjene na oba fajla — potvrđeno da
postojeći radni slučajevi (bez grada) ostaju identični, a novi slučajevi
(sa gradom) se sada ispravno normalizuju. `reindex()` pokrenut kao
pozadinski proces (isti obrazac kao u prethodnom fix-u).

## Šta nije dirano
- `HistoricalLearningServiceSafe.normalize_exporter_name` — zasebna,
  drugačija implementacija u `historical_learning_service_safe.py`, van
  scope-a (nije ista funkcija, GitNexus je prikazao kao poseban kandidat).
- Logika prioriteta u `find_xml_for_pair` (exact_jib → exact_name →
  exporter_only → fuzzy) — nepromijenjena.
- `FUZZY_MATCH_THRESHOLD = 0.92` — nedirano.
- `_ensure_exporter_index_ready()` iz prethodnog fix-a — nepromijenjena,
  samo je njen output (indeks) sada tačniji zbog ove izmjene.

## Verifikacija
- Lokalni test 8 realnih naziva prije primjene na fajlove (svi ispravni,
  vidi "Kako je urađeno").
- `diff` root/dist_client fajlova nakon izmjene → identično (exit 0).
- `python -m py_compile` oba fajla → OK.
- End-to-end na realnoj `dmserver` bazi (nakon `reindex()`):
  `find_xml_for_pair('CMANA DOO KRNJEVO')` → pronađeno, isti `match_type`
  kao `'CMANA'`.
- `pytest tests/unit -q` (pun suite): 1552 passed, 71 skipped, 5 xfailed,
  3 failed — identična tri pre-existing neuspjeha kao u sva prethodna
  mjerenja danas (vidi `agent_reports/2026-08-08_spajanje-grana-windows-
  main-push.md`), NE regresija.

## Nezavisna provjera
- Checker korišćen: NE
- Obavezno za CRITICAL po AGENTS.md, ali nije sproveden kao poseban
  agent/model — umjesto toga: (a) korisnik eksplicitno upoznat sa punim
  CRITICAL nalazom prije izmjene i potvrdio nastavak, (b) izmjena je po
  prirodi additiv/uska (jedan dodatni regex prolaz, ne mijenja postojeću
  logiku), (c) verifikovana na 8 realnih naziva + pun test suite + realna
  DB provjera. Preporuka: ako se u budućnosti otkrije lažni pozitivni
  match (dva različita izvoznika se stope u isti normalizovan ključ),
  potrebna je nezavisna provjera prije daljeg širenja ove logike.
- Šta NIJE provjereno: da li postoje realni izvoznici u arhivi čiji
  imena sadrže legitimne "grad-slične" riječi kao dio stvarnog naziva
  firme (kolizija rizik) — nije pronađen nijedan takav slučaj u 2480
  reindeksiranih parova, ali nije ni sistematski provjeravano.

## Pronađeni problemi
Isti obrazac po treći put u istoj sesiji: docstring/dokumentacija tvrdi
funkcionalnost koja u kodu nikad nije bila potpuno implementirana
(vidi `MIN_SIMILARITY_THRESHOLD` i `_ensure_exporter_index_ready` u
prethodnim izvještajima). Vrijedno šireg audita ako se pattern nastavi.

## Odbačene opcije
- Opcija: popraviti samo `_on_load_previous_declaration` (caller-specific
  workaround — probaj "prva riječ prije DOO" ako pun naziv ne uspije).
- Zašto je razmatrana: manji GitNexus blast radius (samo jedan caller).
- Zašto je odbačena: bug je generički (bilo koji caller normalize_
  exporter_name pati od istog problema — agent chat, auto-popuna
  zaglavlja bi imali isti bug samo neotkriven), popravka na izvoru
  rješava sve odjednom i usklađuje kod sa sopstvenim docstring-om.
- Kada odluku ponovo otvoriti: ako se otkrije kolizija (dva različita
  izvoznika sa istim normalizovanim ključem) — tad razmotriti uže,
  caller-specific rješenje umjesto šire normalizacije.

## Konflikti / kontradiktorni izvori
Nema — docstring i stvarno ponašanje su bili u konfliktu (docstring
tačan, kod netačan); kod je ispravljen da odgovara dokumentovanoj namjeri.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `f69a3ec` | fix(faktura): normalizacija imena izvoznika ne uklanja grad iza DOO/D.O.O. |

## Rizici / ograničenja
- Heuristika "sve poslije pravnog oblika je grad" može teoretski
  pogrešno odsjeći dio stvarnog imena firme ako neka firma ima riječ
  odmah iza DOO/D.O.O. koja NIJE grad (npr. "FIRMA DOO PLUS" gdje je
  "PLUS" dio imena, ne lokacija) — nije pronađen takav slučaj u 2480
  parova, ali rizik postoji za buduće/nove izvoznike.
- Grad ograničen na 1-2 riječi bez brojeva — trorječni gradovi (rijetko,
  ali mogući) ne bi bili prepoznati (nedostaje u ovoj arhivi, nije testirano).

## Potreban follow-up
Ako se u budućnosti primijeti da dva različita izvoznika dijele isti
normalizovan ključ (kolizija), preispitati širinu ove heuristike.

## Potrebna korisnička potvrda
Ručna provjera u pokrenutoj aplikaciji: klik na "Prethodna deklaracija"
za CMANA fakturu treba sada prikazati "Pronađena prethodna deklaracija...
Učitati?" (ne više "Nije pronađena").

## Ljudsko usvajanje rezultata
- Odgovorna osoba: <<< >>>
- Izvještaj pročitan u cijelosti: <<< DA/NE >>>
- Ključne odluke razumljive i prihvaćene: <<< DA/NE/PARCIJALNO >>>
- Ključne tvrdnje/rezultati provjereni (ne samo agentova tvrdnja da radi): <<< DA/NE/NIJE PRIMJENJIVO >>>
- Rezultat predstavlja stvarno prihvaćeno stanje: <<< DA/NE >>>
- Dijelovi koji još nisu ljudski potvrđeni: <<< >>>
- Dozvoljena naredna akcija: <<< >>>
