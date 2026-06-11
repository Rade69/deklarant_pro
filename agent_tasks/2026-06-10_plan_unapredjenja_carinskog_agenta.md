# Agent Task — Plan unapređenja Carinskog Agenta

**Datum:** 2026-06-10  
**Kreirao:** Codex  
**Executor:** Qwen / Claude / drugi agenti  
**Status:** ČEKA  

---

## Kontekst

Carinski Agent u Deklarant Pro aplikaciji već ima korisnu osnovu: može čitati kontekst
deklaracije, koristiti istoriju XML-a, predlagati tarife, raditi validacije i komunicirati
sa korisnikom. Ipak, inteligencija još nije dovoljno pouzdana za produkcioni nivo jer
agent ponekad miješa dokaz, istorijski obrazac, sličnost i LLM pretpostavku.

Cilj ovog plana je da se agent pretvori u disciplinovanog carinskog kopilota:
prvo deterministička pravila i baza, zatim istorija, zatim scoring, a LLM samo za
objašnjenje i razgovor. LLM ne smije biti izvor istine za carinsku odluku.

---

## Glavni cilj

Implementirati dokazivo, objašnjivo i testabilno odlučivanje agenta za:

- tarife
- povlastice i porijeklo
- priložene dokumente PE1/PE2/PE3/EUR1
- istorijske prijedloge po izvozniku
- korisničke odgovore u Agent tabu

Agent mora uvijek znati da kaže:

- `confirmed_from_document`
- `confirmed_from_same_exporter_history`
- `suggested_by_similarity`
- `weak_guess`
- `unknown`

---

## Arhitektonsko pravilo

LLM je samo prezentacioni i konverzacijski sloj. Konačna odluka mora doći iz servisa.

Prioritet izvora:

1. Eksplicitni podaci iz učitanih dokumenata
2. Deklaracija / draft stanje u aplikaciji
3. Zvanična tarifna baza i šifrarnici
4. Istorijski XML istog izvoznika
5. Sličnost proizvoda i fuzzy matching
6. LLM objašnjenje, nikad LLM kao dokaz

---

## Faza 1 — Evidence model

**Status:** ZAVRŠENO 2026-06-11

**Urađeno:**

- postojeći `Evidence` model je proširen umjesto uvođenja paralelnog modela
- `DecisionSource` sada pokriva dokument, istoriju istog izvoznika, tarifnu bazu, sličnost, parser, korisnika i LLM
- `Evidence.to_dict()` daje strukturisan payload za Agent UI i buduće tool rezultate
- LLM izvor ne može proizvesti potvrđen dokaz; takav pokušaj se spušta na `weak_guess`

### Cilj

Uvesti zajednički model za dokazni trag svake preporuke.

### Fajlovi za čitanje

- `services/agent/validation/tariff_decision_model.py`
- `services/agent/validation/declaration_validator_service.py`
- `services/agent/validation/historical_tariff_search_service.py`
- `services/agent/tariff/tariff_suggestion_service.py`
- `services/agent/chat/tariff_intent_service.py`
- `gui/tabs/agent/agent_controller.py`
- `gui/tabs/agent/widgets/chat_worker.py`

### Zadatak

Definisati model tipa `Evidence`, `DecisionSource`, `DecisionConfidence` ili proširiti
postojeći decision model ako već postoji.

Svaka preporuka mora nositi:

- izvor: dokument, XML istorija, tarifa baza, korisnik, parser, LLM
- nivo pouzdanosti
- tekstualni razlog
- podatak koji je korišten kao dokaz
- da li je preporuka automatski primjenjiva ili traži potvrdu korisnika

### Acceptance kriteriji

- Nijedna tarifa/povlastica ne smije se prikazati bez izvora.
- UI tekst ne smije govoriti “preporučujem” bez objašnjenja odakle podatak dolazi.
- Test pokriva barem 5 različitih izvora odluke.

---

## Faza 2 — Povlastice i porijeklo

**Status:** ZAVRŠENO 2026-06-11

**Urađeno:**

- Faktura tab i Agent import pipeline vise ne primjenjuju povlasticu samo zato sto parser vidi zemlju porijekla ili PE2 kandidat.
- Automatski izvori (`auto-fill`, tariff mapping i product master list) vise ne pisu Rub.36/povlasticu u aktivni draft.
- Potvrda povlastice se vizuelno prikazuje samo kada postoji PE1/PE2/PE3 dokaz koji je korisnik/deklarant prihvatio kroz dijalog ili rucni unos.
- Preflight upozorenje sada razlikuje povlasticu sa PE dokazom od povlastice bez PE1/PE2/PE3 dokaza.

**Kljucna odluka:** parser je samo detektor kandidata. Povlastica se primjenjuje tek nakon eksplicitne potvrde deklaranta.

### Cilj

Agent i tabela fakture ne smiju tretirati zemlju porijekla kao dokaz povlastice.
Povlastica smije biti potvrđena samo ako postoji validan PE dokaz.

### Fajlovi za čitanje

- `services/import_service.py`
- `services/validation/validation_service.py`
- `services/agent/validation/declaration_validator_service.py`
- `services/agent/validation/historical_tariff_search_service.py`
- `gui/tabs/faktura_tab.py` ili aktivni Faktura view fajl
- `importers/vendors/blagic/blagic_loren_pdf_parser.py`
- `importers/vendors/blagic/blagic_combined_importer.py`

### Pravilo

Povlastica je potvrđena samo ako je utvrđeno jedno od:

- `PE1` — EUR.1 obrazac
- `PE2` — izjava na fakturi
- `PE3` — izjava ovlašćenog izvoznika

Zemlja porijekla, čak i EU/CEFTA zemlja, nije dovoljna sama po sebi.
Roba iz Kine, SAD ili druge nepodobne zemlje ne smije dobiti oznaku preferencijalnog
porijekla bez eksplicitnog dokaza.

### Acceptance kriteriji

- CN bez PE dokaza ostaje bez povlastice.
- EU/CEFTA zemlja bez PE dokaza dobija neutralan status ili upozorenje, ne potvrdu.
- PE2 izjava na fakturi se prikazuje kao dokaz i veže za relevantne fakture.
- Test pokriva PE1, PE2, PE3, CN bez povlastice i EU bez dokumenta.

---

## Faza 3 — Istorijski prijedlozi tarifa

**Status:** ZAVRŠENO 2026-06-11

**Commiti:**

- `b265350` — `fix(agent): unknown za istorijske izvore bez dokaza`
- `b2d786e` — `feat(agent): prikazi pouzdanost istorijskih prijedloga`

**Napomena:** `tariff_history_analysis_service.py` je ostavljen van scope-a ove faze. Taj chat tok i dalje koristi poseban OK/PROVJERI/RIZIK vokabular i treba ga obraditi u posebnoj fazi ako se želi isti standard izvora i pouzdanosti.

### Cilj

Istorijski prijedlog tarife mora biti striktno vezan za istog izvoznika i mora jasno
pokazati da li je riječ o snažnom ili slabom prijedlogu.

### Fajlovi za čitanje

- `services/agent/learning/exporter_xml_indexer.py`
- `services/agent/learning/historical_learning_service_safe.py`
- `services/agent/validation/historical_tariff_search_service.py`
- `services/agent/tariff/tariff_suggestion_service.py`
- `services/agent/chat/tariff_history_analysis_service.py`

### Pravila

- Nema fallbacka na drugog izvoznika za tariff history.
- Ako je izvor nepoznat, status mora biti `unknown`, ne “HISTORIJA”.
- Ako se koristi istorija, UI mora prikazati: izvoznik, broj korištenja, sličnost,
  posljednji XML ili deklaraciju iz koje potiče prijedlog.
- Slabi prijedlozi ne smiju biti automatski primijenjeni.

### Acceptance kriteriji

- Test sa dva različita izvoznika i istom šifrom proizvoda ne vraća tuđu tarifu.
- “Izvor: nepoznat izvoznik” se više ne pojavljuje kao legitiman izvor.
- Dijalog validacije razlikuje `jak`, `srednji`, `slab`, `nepoznat`.

---

## Faza 4 — Tool-first agent

**Status:** DJELIMIČNO ZAVRŠENO 2026-06-11

**Urađeno:**

- lokalni router prije DeepSeek tool-use fallbacka
- testovi za lokalno routanje najčešćih sigurnih namjera
- ChatWorker prompt guard: LLM ne smije izmišljati tarifni broj, porijeklo ili povlasticu kad je izvor nepoznat/unknown

**Ostaje za nastavak:** strukturisani tool rezultat koji LLM samo formatira, bez promjene značenja, za sve servise koji vrate `unknown` ili `needs_review`.

### Cilj

Agent mora prvo pozvati lokalne servise i alate, pa tek onda LLM za formulaciju odgovora.

### Fajlovi za čitanje

- `services/agent/chat/tool_definitions.py`
- `services/agent/chat/tool_dispatcher.py`
- `services/agent/chat/intent_classifier.py`
- `services/agent/chat/tariff_intent_service.py`
- `services/agent/mcp_facade.py`
- `gui/tabs/agent/widgets/chat_worker.py`

### Zadatak

Uvesti jasan tok:

1. Prepoznaj namjeru
2. Prikupi lokalni kontekst
3. Pozovi deterministički alat
4. Vrati strukturisan rezultat
5. LLM samo pretvara rezultat u razumljiv odgovor

### Acceptance kriteriji

- Ako LLM nije dostupan, agent i dalje može dati osnovni strukturisan odgovor.
- Ako servis vrati `unknown`, LLM ne smije izmisliti odgovor.
- Chat odgovor navodi izvor podataka.

---

## Faza 5 — Scoring i confidence

**Status:** ZAVRŠENO 2026-06-11

**Urađeno:**

- `Evidence` ima numerički `score` i `score_category`
- pragovi su implementirani kao zajednička funkcija `evidence_score_category()`
- `should_recommend` krije `unknown` i score `<50` iz preporuka
- `auto_applicable` je dozvoljen samo za potvrđene dokaze sa score `>=85`

### Cilj

Uvesti jedinstven scoring koji agent koristi za tarife, porijeklo i validaciju.

### Predložena skala

- `95-100`: potvrđeno dokumentom ili ručno potvrđeno
- `85-94`: ista roba + isti izvoznik + istorijski XML
- `70-84`: dobar fuzzy match, traži potvrdu
- `50-69`: slab prijedlog, samo informativno
- `<50`: ne prikazivati kao preporuku

### Fajlovi za čitanje

- `services/agent/validation/tariff_decision_model.py`
- `services/agent/tariff/tariff_suggestion_service.py`
- `services/agent/learning/product_similarity_memory_service.py`
- `services/agent/learning/product_similarity_embedding_service.py`

### Acceptance kriteriji

- Svaka preporuka ima numerički score i kategoriju.
- UI ne koristi isti vizuelni stil za 95% dokaz i 60% pretpostavku.
- Testovi potvrđuju pragove.

---

## Faza 6 — Agent UI prikaz

### Cilj

Korisnik mora odmah vidjeti zašto agent nešto tvrdi.

### Fajlovi za čitanje

- `gui/tabs/agent/agent_controller.py`
- `gui/tabs/agent/widgets/chat_panel.py`
- `gui/tabs/agent/widgets/chat_worker.py`
- `gui/tabs/agent/widgets/processing_worker.py`
- `gui/tabs/faktura_tab.py` ili aktivni Faktura view fajl

### UI pravila

Poruka agenta treba imati:

- zaključak
- izvor
- pouzdanost
- šta korisnik može uraditi

Primjer:

```text
Tarifa 85168080 je jak prijedlog.
Izvor: istorijski XML istog izvoznika PIP FOOD GROUP DOO, korišteno 6x.
Pouzdanost: 91%.
Potrebna potvrda korisnika prije upisa.
```

### Acceptance kriteriji

- Nema poruka tipa “mislim da je” bez izvora.
- Slabi prijedlozi su vizuelno drugačiji od potvrđenih.
- Korisnik može kopirati kratki izvještaj odluke.

---

## Faza 7 — Test dataset

### Cilj

Napraviti minimalni set stvarnih ili anonimizovanih slučajeva za regresiju agenta.

### Predloženi slučajevi

- Faktura sa PE2 izjavom
- Faktura sa EUR.1 obrascem
- Faktura bez dokaza porijekla
- CN roba bez povlastice
- Isti proizvod kod dva izvoznika sa različitim tarifama
- Blagić/Loren scenario sa više faktura i izjavama
- Slučaj gdje istorija daje slab prijedlog

### Acceptance kriteriji

- Testovi se mogu pokrenuti bez vanjskog LLM-a.
- Testovi ne zavise od privatnog API ključa.
- Testovi koriste fixture podatke ili anonimizovane minimalne ulaze.

---

## Faza 8 — LLM provider fallback

### Cilj

Agent mora civilizovano raditi kad API vrati 402, 429 ili timeout.

### Fajlovi za čitanje

- `gui/tabs/agent/widgets/llm_provider.py`
- `gui/tabs/agent/widgets/chat_worker.py`
- `services/agent/chat/tool_dispatcher.py`

### Pravila

- 402 `Insufficient Balance`: prikazati jasnu poruku bez stack trace-a.
- Ako LLM padne, koristiti lokalni tool rezultat ako postoji.
- Ne pokušavati beskonačne retry petlje.

### Acceptance kriteriji

- Test ili mock za 402 grešku.
- Agent vraća lokalni odgovor ako ga ima.
- UI poruka je razumljiva korisniku.

---

## Redoslijed delegiranja

1. Agent A: Faza 1 i Faza 5 — evidence model i scoring.
2. Agent B: Faza 2 — povlastice i porijeklo.
3. Agent C: Faza 3 — istorijski prijedlozi po izvozniku.
4. Agent D: Faza 4 i Faza 8 — tool-first tok i LLM fallback.
5. Agent E: Faza 6 i Faza 7 — UI prikaz i regression dataset.

Ne raditi sve odjednom. Svaka faza mora imati poseban commit.

---

## Zabranjeno

- Ne spuštati fuzzy threshold ispod projektnih pravila bez eksplicitnog razloga.
- Ne hardkodovati izvoznike, tarife ili IP adrese.
- Ne dozvoliti LLM-u da direktno upisuje tarifu/povlasticu.
- Ne miješati GUI logiku u servisni sloj.
- Ne uvoditi novu bazu ili eksterni servis bez odluke vlasnika projekta.
- Ne mijenjati `dist_client` bez mirror izmjene u root kodu, ako se dira runtime logika.

---

## Obavezna provjera prije predaje svake faze

- [ ] Pročitani `AGENTS.md` i `docs/CONTEXT.md`
- [ ] GitNexus impact analiza za mijenjane simbole
- [ ] Unit testovi za novu logiku
- [ ] `python -m py_compile` za mijenjane Python fajlove
- [ ] `gitnexus_detect_changes()` prije commita
- [ ] Agent report ako je donesena nova bitna odluka

---

## Output format za izvršioca

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratak opis
ŠTA NIJE URAĐENO: razlog ako postoji
PITANJA: otvorene nejasnoće
```
