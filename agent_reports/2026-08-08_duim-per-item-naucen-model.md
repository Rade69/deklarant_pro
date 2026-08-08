## Datum
2026-08-08

## Agent
Claude Code (Sonnet 5)

## Scope
`exporters/asycuda_xml_builder.py`, `dist_client/exporters/asycuda_xml_builder.py`,
`services/agent/learning/exporter_xml_indexer.py`,
`dist_client/services/agent/learning/exporter_xml_indexer.py`,
`gui/tabs/zaglavlje_view.py`, `dist_client/gui/tabs/zaglavlje_view.py`,
nova PostgreSQL tabela `catalogs.tariff_duim_rules`,
`docs/NOVA ASIKUDA/BLAGIĆ-LOREN-7-8-asycuda.xml` (lokalni seed fajl, gitignored).

## Status izvora
Nastavak `agent_reports/2026-08-07_asycuda-from-rule-crveni-redovi.md` (N380/DIS/DV1
fix — potvrđen ispravan na stvarnom uvozu od strane korisnika prije ovog zadatka).
Eksterni predlog: Codex-ova analiza + SQLite baza zvanične BiH Liste robe dvojne
namjene (`C:\Users\38765\Downloads\DUIM\`) — nezavisno provjerena prije bilo kakve
odluke (vidi "Nezavisna provjera").

## Impact analiza
`gitnexus_impact` na `AsycudaXMLBuilder._add_items` (exporters/asycuda_xml_builder.py):
risk **HIGH** — 1 direktan pozivalac (`build()`), lanac do `export_to_xml()` →
`_izvezi_xml()` (agent workflow) / `_on_export_xml()` (Zaglavlje GUI dugme) —
funkcija kroz koju prolazi SVAKI XML export. Zbog HIGH rizika napravljen
`project_rooms/2026-08-07_duim-per-item-nauceno-pravilo.md` PRIJE izmjene, po
AGENTS.md proceduri. `gitnexus_detect_changes` prije commit-a: risk "high"
(dominantno zbog pred-postojećeg necommitovanog WIP-a drugih fajlova u working
tree-u — provjereno da nisu moji, vidi "Šta nije dirano").

## Reprodukcija prije izmjene
Korisnik je dao round-trip par (`BLAGIĆ-LOREN-7-8.xml` naš export vs.
`BLAGIĆ-LOREN-7-8-asycuda.xml` nakon ASYCUDA provjere) — direktno poređenje
potvrdilo: naš export ima DUIM samo na Item 1 (header-level, placeholder
referenca "1"); ASYCUDA-in izlaz nema taj zapis na Item 1 uopšte, nego dodaje
poseban DUIM zapis (from_rule=1, prazna referenca) na 11+ pojedinačnih stavki
čiji tarifni broj ASYCUDA prepoznaje. To su crveni redovi koje bi korisnik
morao ručno popuniti — po jedan za svaku takvu stavku.

## Kontekst korišćen
`services/tariff_controls_service.py` i `services/faktura/header_doc_sync_service.py`
pročitani u cijelosti da se potvrdi da NIJEDAN postojeći mehanizam ne generiše
DUIM po stavci (oba dedupliraju po šifri na nivou cijele deklaracije — header-level
koncept, ne per-item). `services/agent/learning/exporter_xml_indexer.py` pročitan u
cijelosti da se razumije postojeći XML-learning pattern (`sync_tariff_knowledge_base`)
i iskoristi isti princip za DUIM. Codex-ova SQLite baza (`dual_use_bih_65_19.sqlite`,
README, JSON, CSV) provjerena direktno (upiti, sample zapisi) prije donošenja odluke.

## Šta je urađeno
1. Nova funkcija `sync_duim_rule_knowledge_base()` u `exporter_xml_indexer.py` (i
   `dist_client/` kopiji) — skenira SVE XML-ove direktno iz `docs/NOVA ASIKUDA/`
   foldera (glob, ne preko `exporter_xml_index` tabele), za svaku `<Item>` traži
   `<Attached_documents>` sa `Attached_document_code=DUIM` i `..._from_rule=1`,
   upisuje `Commodity_code` (8 cifara) u novu `catalogs.tariff_duim_rules` tabelu.
   Pozvana iz `reindex()` pored postojećeg `sync_tariff_knowledge_base()`.
2. Nova `get_duim_tariff_codes()` — lookup helper za exporter.
3. `exporters/asycuda_xml_builder.py::_add_single_item()` (i `dist_client/` kopija)
   — za svaku stavku, ako je njen tarifni broj u naučenom skupu, dodaje NOVI,
   per-item `<Attached_documents>` blok (DUIM, referenca "ROBA NIJE DVOJNE NAMJENE",
   from_rule=1) direktno na tu `<Item>`, odvojeno od postojeće header_docs logike.
   `Attached_doc_item` (Rb.44 zbirni tag na nivou stavke) ažuriran da uključi "DUIM"
   za stavke koje ga imaju, bez obzira da li je prva stavka.
4. `gui/tabs/zaglavlje_view.py::get_data()` (i `dist_client/` kopija) — DUIM
   uklonjen iz `FROM_RULE_CODES` (header-level from_rule flag se više ne postavlja
   za ručno unesen DUIM red u Zaglavlju — per-item mehanizam ga zamjenjuje).
5. Seed podaci: `docs/NOVA ASIKUDA/BLAGIĆ-LOREN-7-8-asycuda.xml` (kompaktna,
   validna verzija sa svih 39 stavki, Exporter/Consignee metapodacima za
   indeksiranje, i potvrđenim DUIM/from_rule=1 zapisima tačno onako kako ih je
   korisnikov ASYCUDA round-trip pokazao) — sačuvan lokalno (folder je u
   `.gitignore`, sadrži customer podatke). Pokrenut `reindex()` — popunio
   `catalogs.tariff_duim_rules` sa 19 potvrđenih tarifnih brojeva (11 iz novog
   fajla + 8 dodatnih iz pred-postojećeg `BLAGIĆ-LOREN.xml` u istom folderu, koji
   je otkriven tek nakon ispravke opisane u tački 6).
6. Otkriven i ispravljen arhitektonski propust tokom implementacije: prva verzija
   `sync_duim_rule_knowledge_base()` je čitala fajlove iz `catalogs.exporter_xml_index`
   (deduplicirano — samo najnoviji XML po paru exporter+primalac), što bi izostavilo
   stariji `BLAGIĆ-LOREN.xml` (isti exporter/primalac par, izgubio "keep newest"
   poređenje). Ispravljeno da skenira `XML_FOLDER.glob("*.xml")` direktno — DUIM
   potvrda treba SVAKI istorijski XML, ne samo onaj zadržan za drugu (lookup-po-paru)
   svrhu.

## Zašto je urađeno
Korisnik je eksplicitno potvrdio (nakon što je pregledao Codex-ov predlog i moju
nezavisnu provjeru zvanične BiH liste) da je jedino praktično rješenje učenje iz
ASYCUDA-inog stvarnog ponašanja u ranijim deklaracijama — zvanična lista dvojne
namjene NIJE HS-kod tabela (kontrola se određuje po preciznim tehničkim
kriterijumima, ne po samom tarifnom broju), pa se ne može koristiti za automatsku
HS→DUIM odluku bez rizika lažno pozitivne/negativne pravne klasifikacije.

## Kako je urađeno
Isti "sync from historical XML" pattern koji već postoji za tarifno mapiranje
(`sync_tariff_knowledge_base`), primijenjen na novi signal (Attached_documents
DUIM+from_rule na Item nivou umjesto Commodity_code+naziv). Exporter promjena je
aditivna grana u postojećoj `_add_single_item` metodi — ne mijenja postojeću
header_docs/N380/DIS/DV1/PZT/N730/PE logiku.

## Šta nije dirano
- Postojeća `header_docs`/`_PREF_TO_DOC_CODE`/N380-DIS-DV1-PZT-N730 logika u
  `_add_items()`/`_add_single_item()` — netaknuta, potvrđeno testom da Item 2
  (bez DUIM tarife) i dalje ima prazan `Attached_doc_item` kao prije.
  `services/tariff_controls_service.py` (VET/SAN/FIT/UVK/AGL) — odvojen
  mehanizam, nedirano.
- Zvanična BiH Lista robe dvojne namjene (Codex-ova SQLite baza) — NIJE ugrađena
  u aplikaciju, ostaje samo kao eksterni referentni materijal na
  `C:\Users\38765\Downloads\DUIM\` za eventualni budući ručni-lookup GUI feature.
- FTAP/EUP/TRP (preferencijalni dokazi porijekla, `_PREF_TO_DOC_CODE` putanja) —
  kontrolni fajlovi iz ranijeg zadatka su pokazivali from_rule=1 i za njih, nije
  provjereno da li imaju isti per-item obrazac kao DUIM. Nije prijavljeni problem.
- Ostali fajlovi izmijenjeni u working tree-u prije ovog zadatka (AGENTS.md,
  CLAUDE.md, `dist_client/gui/dialogs/tariff_suggestion_dialog.py`,
  `dist_client/gui/tabs/naimenovanja_controller.py`,
  `services/naimenovanja/constants.py`, UI fajlovi) — pre-existing WIP,
  nepovezan sa ovim zadatkom, nije staged niti commitovan.

## Verifikacija
1. `python -m py_compile` na sve izmijenjene fajlove — OK.
2. `pytest tests/unit/test_asycuda_goods_description.py -q` — 35/35 prošlo, bez
   regresije.
3. `sync_duim_rule_knowledge_base()` pozvan direktno na stvarnoj PostgreSQL bazi
   (dmserver) — potvrđeno 19 jedinstvenih tarifnih brojeva upisano u
   `catalogs.tariff_duim_rules`, sa tačnim `first_seen_xml`/`confirm_count`
   vrijednostima provjerenim upitom.
4. Direktan end-to-end poziv stvarnog `AsycudaXMLBuilder.build()` sa draft-om od
   2 stavke (jedna sa tarifom iz naučenog skupa "85168080", jedna sa
   nepostojećom "12345678") — potvrđeno: Item 1 dobija N380 (header) I DUIM
   (per-item, "ROBA NIJE DVOJNE NAMJENE", from_rule=1), `Attached_doc_item`="N380
   DUIM "; Item 2 nema DUIM, `Attached_doc_item` prazan.
5. Nije rađen pun round-trip test (naš export → stvaran uvoz u ASYCUDA World →
   provjera da crveni redovi za DUIM nestanu na potvrđenim tarifama) jer ASYCUDA
   aplikacija nije dostupna u ovoj sesiji — preostaje ručna korisnička potvrda.

## Nezavisna provjera
- Checker korišćen: NE (u smislu posebne agent sesije), ALI izvršena je
  eksplicitna nezavisna provjera Codex-ovog predloga (druga AI sesija, tuđi
  predlog koda po AGENTS.md) prije donošenja odluke o pristupu: direktno
  upitana SQLite baza (broj zapisa, šema, sample kontrolni brojevi 0A001/1C350/
  3A001/5A002/9E102 potvrđeni prisutni), i konkretno provjeren sadržaj 2A001/2A101
  (ležajevi) da se potvrdi Codex-ova tvrdnja da HS kod sam po sebi nije dovoljan
  za pravnu klasifikaciju.
- Šta je potvrđeno: Codex-ova baza je legitimna i tačno opisana; Codex-ov
  arhitektonski prijedlog (dvoslojni pristup, HS→DUIM učenje odvojeno od
  pravnog izvora) je ispravan i primijenjen (samo Sloj 1, po korisnikovoj odluci).
- Šta NIJE potvrđeno/urađeno: Sloj 2 (link ka zvaničnoj bazi kao GUI referenca)
  — eksplicitno odbačen za ovaj zadatak, korisnik odlučio da nije potreban.
- Da li je promjena spremna za prihvatanje: DA za kod/logiku (testirano
  end-to-end na sintetičkim podacima), PARCIJALNO za stvarni ASYCUDA round-trip
  (nije ponovo testirano u ASYCUDA aplikaciji u ovoj sesiji — preporučena
  ručna potvrda na sledećem uvozu, isto kao za N380/DIS/DV1 fix).

## Pronađeni problemi
Arhitektonski propust otkriven i ispravljen TOKOM istog zadatka (vidi "Šta je
urađeno" tačka 6) — prva implementacija `sync_duim_rule_knowledge_base()` bi
tiho izgubila potvrđene podatke iz starijih XML-ova zbog "keep newest per pair"
dedup logike u `exporter_xml_index`. Otkriveno provjerom rezultata (12 umjesto
očekivano više jedinstvenih kodova), ne slijepim prihvatanjem prvog prolaza.

## Odbačene opcije
- Opcija: koristiti zvaničnu BiH Listu robe dvojne namjene (Codex-ova SQLite
  baza) za automatsko HS→DUIM pravilo.
- Zašto je razmatrana: Codex je predložio kao "pravni sloj", nezavisno
  provjerena kao legitimna (362 zapisa iz Sl. glasnika BiH 65/19).
- Zašto je odbačena: lista NIJE HS-kod tabela — kontrola se određuje po
  tehničkim kriterijumima koje ne možemo automatski provjeriti iz tarifnog
  broja (npr. ISO 492 klasa tolerancije za ležajeve). Korisnik eksplicitno
  potvrdio da je jedino praktično rješenje učenje iz ASYCUDA-inog stvarnog
  ponašanja.
- Kada odluku ponovo otvoriti: ako se ikad doda GUI feature "provjeri da li je
  roba stvarno dvojne namjene" kao pomoć korisniku (ne kao automatska odluka).

## Konflikti / kontradiktorni izvori
Nema — korisnikova odluka (učenje iz istorije, ne zvanična lista) je tretirana
kao konačna i primijenjena bez daljeg preispitivanja.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `f427261` | `feat(exporter): DUIM po stavci — naučeno pravilo iz ASYCUDA istorije` |

## Rizici / ograničenja
Naučeni skup (19 tarifnih brojeva) je zasnovan na SAMO 2 stvarna XML-a — mali
uzorak. Rizik: druge deklaracije mogu imati DUIM-relevantne tarifne brojeve koje
ASYCUDA označava a koji NISU u ovom skupu (fail-safe: ako tarifni broj nije u
skupu, jednostavno se ne dodaje DUIM — isto ponašanje kao prije ove izmjene za
te kodove, ne gore). Skup raste automatski kroz `reindex()` kad se novi XML-ovi
(uključujući buduće ASYCUDA-obrađene fajlove) dodaju u `docs/NOVA ASIKUDA/`.

## Potreban follow-up
- Ručna korisnička potvrda na sledećem stvarnom uvozu (kao za N380/DIS/DV1) da
  crveni DUIM redovi nestaju za potvrđene tarifne brojeve.
- FTAP/EUP/TRP — provjeriti da li imaju isti per-item obrazac kao DUIM (nije
  prijavljeni problem, samo primijećena mogućnost).
- Kontinuirano dodavati nove ASYCUDA-obrađene XML-ove u `docs/NOVA ASIKUDA/` i
  pokretati `reindex()` da naučeni skup raste sa stvarnim iskustvom.

## Potrebna korisnička potvrda
Sledeći stvarni izvoz+uvoz u ASYCUDA World da se potvrdi da DUIM crveni redovi
nestaju za tarifne brojeve iz naučenog skupa (kao što je već urađeno za
N380/DIS/DV1).

---

## Nastavak (isti dan) — Faza 2: pravi izvor podataka

Korisnik je uživo potvrdio Fazu 1 (screenshot ASYCUDA Rb.44, DUIM se pokazuje
tačno na stavkama za koje je naučen, ostale i dalje crvene — očekivano) i
otkrio da postoji pravi arhiv istorijskih ASYCUDA XML-ova na
`H:\New folder\NOVA ASIKUDA` (5706 fajlova, 202MB), ne mali
`docs/NOVA ASIKUDA` (8-9 fajlova) korišćen dotad.

**Šta je urađeno:** `.env` (gitignored, sadrži DB lozinku/API ključeve — nije
za commit) dopunjen sa `XML_LEARNING_FOLDER=H:\New folder\NOVA ASIKUDA` —
korisnikova eksplicitna odluka da NE odvaja poseban DUIM-only override, nego
da ovo bude trajni podrazumijevani folder za sve mehanizme učenja (tarifno
mapiranje, exporter/primalac uparivanje, DUIM).

**Verifikacija:** jednokratni `sync_duim_rule_knowledge_base()` (bez punog
`reindex()`, da se ne pokreće nepotrebno tarifno mapiranje/uparivanje u istom
koraku) — 5706 fajlova skenirano za 19.4s, 1210 DUIM potvrda, naučeni skup
narastao sa 26 na 262 tarifna broja. 4 korumpirana fajla (postojeći, ne
uzrokovana ovom sesijom) bezbjedno preskočena postojećim try/except.

**Nezavisna provjera:** nije rađena posebno — promjena je čisto
konfiguraciona (jedna `.env` linija) i podaci (poziv postojeće, već testirane
funkcije), bez izmjene koda.

## Nastavak (isti dan) — Faza 3: DUIM vidljiv pri kreiranju naimenovanja

Korisnik je predložio: DUIM treba biti vidljiv/provjerljiv već pri kreiranju
naimenovanja (Rb.44 u GUI), ne tek tiho ubačen u finalni XML pri exportu.
Alternativa koju je pomenuo — dodati DUIM kolonu direktno u
`product_tariff_mapping` (proizvod-keyed tabela) — razmotrena i preporučeno
ODBAČENA: DUIM je pokazao da je čisto TARIFNI okidač (isti tarifni broj
uvijek nosi DUIM nezavisno od naziva proizvoda), pa bi vezivanje za proizvod
stvorilo drugi izvor istine koji vremenom može da se raziđe od
`catalogs.tariff_duim_rules`.

### GitNexus impact
`collect_inspection_docs_from_items` (najbliži postojeći analogni mehanizam,
VET/SAN/FIT/UVK/AGL): risk **LOW**, 6 pogođenih simbola, 1 modul (Tabs),
poznat lanac `_sync_inspection_docs_to_header` → `_run_create_naimenovanja_post_actions`
→ `_create_naimenovanja_from_draft`. `_add_single_item` (export-time
idempotency izmjena): risk **LOW** u direktnom upstream-u, ali dio istog
core export lanca (build→export_to_xml) već označenog HIGH u Fazi 1 ovog
zadatka — tretiran s istim oprezom.

### Šta je urađeno
- `services/faktura/header_doc_sync_service.py` (+ `dist_client/` kopija) —
  nova `sync_duim_docs_to_items(items) -> int`. NAMJERNO odvojena funkcija,
  ne prošireno postojeće `collect_inspection_docs_from_items` dedup
  ponašanje — to bi header-level pravilo pogrešno primijenilo na DUIM (ista
  greška klase kao u Fazi 1, ovaj put izbjegnuta unaprijed). Dodaje DUIM
  direktno u `item.attached_documents` (postojeće `NaimenovanjeDraft` polje,
  Rb.44 struktura po stavci), idempotentno (provjerava da li DUIM već
  postoji na toj stavci prije dodavanja).
- `services/faktura/__init__.py` (+ `dist_client/`) — export nove funkcije.
- `gui/tabs/faktura_view.py` (+ `dist_client/`) — nova `_sync_duim_docs_to_items()`
  metoda, pozvana u `_run_create_naimenovanja_post_actions()` odmah nakon
  `_sync_inspection_docs_to_header()` (isti trigger — nakon kreiranja
  naimenovanja).
- `exporters/asycuda_xml_builder.py` (+ `dist_client/`) — export-time DUIM
  injekcija (iz Faze 1) učinjena idempotentnom: provjerava
  `item.attached_documents` za postojeći DUIM prije dodavanja duplikata.
  Ostaje kao fail-safe mreža za naimenovanja kreirana PRIJE ovog sync-a
  (npr. učitana iz starijeg drafta).

### Šta nije dirano
`collect_inspection_docs_from_items`/`collect_pe_docs_from_items` i njihov
header-level mehanizam — netaknuti, DUIM ide odvojenom putanjom.
`product_tariff_mapping` — nije dobio DUIM kolonu (odbačena opcija, vidi
gore).

### Verifikacija
1. `py_compile` na sve izmijenjene fajlove — OK.
2. `pytest tests/unit/test_asycuda_goods_description.py` — 35/35, bez
   regresije.
3. End-to-end skripta: `sync_duim_docs_to_items([item1(poznata tarifa),
   item2(nepoznata)])` → dodaje DUIM samo na item1 (added=1); ponovni poziv
   → `added=0` (nema duplikata); export tog drafta → tačno 1 `<Attached_documents>`
   DUIM blok na item1 (ne 2), 0 na item2, `Attached_doc_item` na item1 sadrži
   "DUIM" (potvrđeno da idempotency guard ne krši postojeći Rb.44 zbirni
   tag).

### Odbačene opcije (Faza 3)
- Opcija: DUIM kolona u `product_tariff_mapping`.
- Zašto razmatrana: korisnikov prijedlog, iskorišćava postojeću veliku
  infrastrukturu (product_code+naziv_robe+commodity_code).
- Zašto odbačena: DUIM je čisto tarifni signal (potvrđeno kroz sve dosadašnje
  podatke), ne proizvodni — vezivanje za proizvod uvodi drugi izvor istine.
- Kada ponovo otvoriti: ako se ikad pojavi dokaz da ASYCUDA razlikuje DUIM
  po opisu proizvoda unutar istog tarifnog broja (nije dosad primijećeno).

### Commitovi (nastavak)
| Hash | Poruka |
| --- | --- |
| `c710b81` | `feat(naimenovanja): DUIM po stavci pri kreiranju naimenovanja, ne samo pri exportu` |

### Nezavisna provjera
Nije rađena posebno (druga sesija/model) — self-verified kroz test suite +
end-to-end skriptu opisanu gore. Preporučeno: ručna GUI provjera (kreirati
naimenovanje sa poznatom DUIM tarifom, potvrditi da se Rb.44 polje odmah
popuni prije exporta) na sledećoj radnoj sesiji.

### Potreban follow-up (dopuna)
- Ručna GUI provjera da se DUIM red pojavljuje u Zaglavlje/Naimenovanja
  prikazu ODMAH nakon kreiranja naimenovanja, ne samo u exportovanom XML-u.
- Razmotriti da li isti "po stavci, vidljivo pri kreiranju" princip treba
  primijeniti i na FTAP/EUP/TRP (i dalje nezatvoreno iz Faze 1).
