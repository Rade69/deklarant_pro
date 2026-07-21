# Dubinska tehnička analiza aplikacije Deklarant Pro

**Datum:** 20.07.2026.
**Status:** analiza postojećeg koda, bez izmjena ponašanja aplikacije
**Obuhvat:** arhitektura, GUI, draft model, uvoz faktura, tarifno odlučivanje, naimenovanja, XML izvoz, agentski mod, baze, testovi i distribuciona kopija

**Dopuna 21.07.2026:** izvršena je runtime provjera `dist_client` i lokalnih PyInstaller artefakata, provjera DB test preduslova, audit zapisa i domenskih pretpostavki grupisanja. Dopuna mijenja redoslijed rada: paritet isporučenog koda i kontrolisana test baza postaju preduslovi Faze 0.

## 1. Sažetak

Deklarant Pro je desktop aplikacija za pripremu carinskih deklaracija. Njena glavna vrijednost nije samo unos podataka, nego povezivanje više izvora u jedan radni nacrt deklaracije: faktura i prateći dokumenti, naučena tarifna mapiranja, istorijski podaci, službena tarifa, pravila o porijeklu i kontrolni dokumenti. Iz tog nacrta aplikacija formira naimenovanja i izvozi ASYCUDA XML.

Arhitektura ima dobru osnovu:

- `DeclarationDraft` je centralni izvor stanja deklaracije;
- importeri su odvojeni po dobavljačima i formatima;
- PostgreSQL služi kao zajednička poslovna baza, a SQLite za lokalne i referentne podatke;
- tarifni sloj kombinuje tačna mapiranja, fuzzy pretragu, istoriju i službenu tarifu;
- agentski mod je u novijim fazama dobio mutation gate, `ToolResult`, idempotenciju i centralni `LLMProvider`;
- ASYCUDA ograničenja su izdvojena u specijalizovane buildere i pokrivena ciljanim testovima.

Najveći problem nije izbor tehnologija nego neujednačena primjena novih pravila kroz starije i novije dijelove sistema. Prije izmjena mora se dokazati koji artefakt koristi konkretna klijentska instalacija. Najvažniji rizici su:

1. lokalni buildovi nisu vezani manifestom za tačno instalirani klijentski artefakt;
2. aktivna tarifna putanja još može tražiti od LLM-a da bez zatvorenog skupa dokaza proizvede tarifni broj;
3. safety testovi tarifnog odlučivanja nemaju kontrolisanu PostgreSQL test bazu;
4. dio DB i tarifnih operacija radi sinhrono u Qt UI niti, uz ponovljene upite po svakoj stavci;
5. istorijski dokumenti se na jednom mjestu iz prijedloga odmah prenose u aktivni draft;
6. XML builder mijenja draft tokom izvoza umjesto da izvoz bude čista transformacija;
7. GUI auto-fill nema dovoljan audit trag, a postojeći agent audit ne serijalizuje `extra.operation_id`;
8. testni paket je velik, ali standardno pokretanje trenutno nije potpuno zeleno i dio vrijednih testova pytest uopšte ne otkriva.

Preporuka nije veliki redizajn. Najbolji odnos koristi i rizika daje postepeno zatvaranje navedenih putanja, uz zadržavanje postojećeg draft modela, parsera, DB infrastrukture i XML buildera.

## 2. Metod analize

Analiza je rađena kombinovanjem:

- čitanja projektne memorije iz `docs/CONTEXT.md`;
- GitNexus grafa: 43.811 simbola, 67.730 veza i 300 evidentiranih procesa;
- pregleda aktivnih pozivalaca ključnih servisa;
- statičkog pregleda velikih modula, DB poziva, `processEvents`, širokih `except` blokova i direktnih LLM klijenata;
- pregleda razlika između izvornog stabla i `dist_client`;
- ciljanog i punog pytest pokretanja.

GitNexus tekstualna pretraga procesa nije davala pune rezultate jer indeks nema FTS/embedding sloj, pa su zaključci o ponašanju potvrđeni direktnim pregledom pozivalaca i izvornog koda. Za dokumentacionu analizu nisu mijenjani programski simboli.

## 3. Tehnološki izbori i zašto imaju smisla

### 3.1 PySide6 i desktop model

PySide6 je razuman izbor jer je aplikacija radni alat deklaranta, a ne javni web sistem. Potrebni su:

- rad sa lokalnim PDF, Excel i XML fajlovima;
- složene tabele i forme;
- Windows distribucija;
- dijalozi za pregled, potvrdu i ispravku prijedloga;
- offline ili djelimično offline rad.

Qt pruža zreo model signala, tabela, thread workera i štampe. Problem nastaje kada se DB ili parserski posao vrati u UI nit, a ne zbog samog Qt izbora.

### 3.2 PostgreSQL i SQLite

Podjela baza je funkcionalno opravdana:

- PostgreSQL čuva zajedničke kataloge, istoriju i podatke koji moraju biti dostupni svim klijentima;
- `deklarant_sistem.db` čuva lokalne mape i operativne podatke;
- `zvanicna_tarifa.db` je lokalna read-only referenca službene tarife.

Postojeći PostgreSQL sloj već ima `ThreadedConnectionPool`, timeout upita i circuit breaker. To je dobra zaštita od zaglavljivanja cijele aplikacije. Ipak, timeout od 15 sekundi je i dalje neprihvatljivo dug ako se upit izvršava direktno iz UI event handlera.

### 3.3 Centralni `DeclarationDraft`

`core/draft/draft.py` objedinjuje zaglavlje, fakture, naimenovanja, dokumente, upozorenja i izvorne fajlove. To je ispravan izbor za konzistentan XML izvoz i dijeljenje stanja između tabova.

Slabost nije centralizacija, već široka mutabilna površina:

- objekti i liste se mijenjaju na više mjesta;
- callback ne nosi precizan opis promjene;
- nije uvijek jasno da li operacija može ostaviti djelimično izmijenjen draft;
- dirty i refresh semantika zavise od discipline svakog pozivaoca.

Ne treba odmah razbijati javni model. Bolji naredni korak su `DraftChangeSet` događaji i atomske servisne operacije koje pripreme rezultat pa ga tek onda primijene.

### 3.4 Parseri po dobavljaču

Dobavljači imaju različite PDF i Excel obrasce, zbog čega je zaseban importer po formatu bolji od jednog univerzalnog parsera. `ImportService` daje zajednički ulaz, auto-detekciju i normalizaciju, dok specifični parseri rješavaju stvarne izuzetke.

Posebno je važan `consumed_paths`: kombinovani importer mora označiti drugi fajl koji je već iskoristio. Time se sprečava da agent isti račun ili packing list obradi drugi put i duplira stavke.

### 3.5 Hibridno tarifno odlučivanje

Kombinacija naučenih mapiranja, fuzzy sličnosti, istorijskih deklaracija, RAG kandidata i službene tarife je dobar domenski pristup. Tarifni broj nije običan tekstualni odgovor; potreban je trag dokaza i nivo pouzdanosti.

Zato LLM treba koristiti samo kao pomoć pri rangiranju zatvorenog skupa kandidata. Ne smije biti izvor novog tarifnog broja kada lokalni i službeni izvori ne vrate kandidata.

### 3.6 Agentski mod

Agentski mod je zamišljen kao prirodni jezički sloj iznad postojećih poslovnih servisa. Dobar dio novijih zaštita je već implementiran:

- `ToolDispatcher` koristi `LLMProvider` za izbor alata;
- `ToolEffect` klasifikuje alate kao read-only, proposal ili mutation;
- nepoznati alat se tretira fail-closed;
- `ToolResult` razlikuje `OK`, `NEEDS_REVIEW`, `UNKNOWN` i `ERROR`;
- mutacije prolaze kroz potvrdu;
- `operation_id` sprečava dvostruku primjenu iste potvrde;
- pipeline vraća rezultate faza i može prekinuti obradu kada prethodna faza nije uspjela.

Ovo je ispravna osnova: agent orkestrira provjerene servise, a LLM tumači namjeru i objašnjava rezultat. Problem su starije pomoćne putanje koje još zaobilaze taj model.

## 4. Ključni tokovi aplikacije

### 4.1 Pokretanje i glavni prozor

`app/run.py` inicijalizuje Qt aplikaciju, bazu, pozadinski MCP server i sinhronizaciju sličnosti proizvoda, zatim kreira `MainWindow`. `gui/main_window.py` formira jedan `DeclarationDraft` i predaje ga tabovima.

Faktura, Admin i Agent tab se inicijalizuju odmah, dok su Zaglavlje, Naimenovanja i Šifrarnici omotani u `LazyTab`. Lazy inicijalizacija smanjuje vrijeme prvog prikaza i izbjegava nepotrebne DB upite pri pokretanju.

Rizik je što `LazyTab.__getattr__` prije inicijalizacije vraća no-op funkciju za gotovo svaki nepoznat atribut. To sprečava prerano otvaranje taba, ali može sakriti tipografsku grešku ili poziv metode koja ne postoji. Bolje je dozvoliti samo eksplicitnu listu bezbjednih odloženih poziva, a ostalo prijaviti kao grešku.

### 4.2 Uvoz faktura i dokumenata

Aktivni tok ide kroz `services/import_service.py`, a agentski batch kroz `gui/tabs/agent/widgets/processing_worker.py`.

Worker namjerno koristi privatnu instancu `ImportService`, sortira ulazne fajlove, održava stanje prethodnog fajla i poštuje `consumed_paths`. To rješava uparivanje Invoice/Packing List i sprečava race condition sa singleton stanjem.

Obrada je sekvencijalna. To je trenutno potrebno jer odluka o paru može zavisiti od prethodnog fajla. Međutim, sekvencijalnost postaje usko grlo kod većih foldera, naročito kada PDF zahtijeva OCR.

Sigurno ubrzanje ima dvije faze:

1. prvo napraviti deterministički plan poslova i upariti fajlove bez parsiranja sadržaja koji mijenja stanje;
2. zatim nezavisne poslove izvršiti u ograničenom thread/process poolu, uz posebno mali limit za OCR.

Ne treba paralelizovati postojeću stateful instancu `ImportService` bez prethodnog planiranja parova.

### 4.3 Tarifni prijedlog i auto-popunjavanje

`FakturaView._on_auto_fill()` u `gui/tabs/faktura_view.py:4136` koristi `TariffFacade`. U interaktivnom režimu prvo se prikupljaju preview prijedlozi u `_collect_tariff_previews()` (`gui/tabs/faktura_view.py:4429`), a nakon potvrde se ponovo poziva `auto_populate_tariffs()`.

`TariffFacade.suggest_fast()` delegira `_try_mapping()`, dok `TariffFacade.auto_populate_tariffs()` prosljeđuje obradu `TariffMappingService`. Time se ista grupa stavki može pretražiti jednom za preview i ponovo za primjenu. Oba koraka se pokreću iz UI event handlera.

`TariffMappingService.find_mapping()` (`services/tariff/tariff_mapping_service.py:382`) otvara konekciju i može izvršiti više upita: tačan/prefix match, majority-vote provjere i fuzzy upit. Evaluacija cijelog drafta zato može prerasti u približno pet upita po stavci.

Servis već ima `find_batch_by_product_codes()` (`services/tariff/tariff_mapping_service.py:325`), ali ga aktivne decision-evidence putanje ne koriste kao početni batch preload.

Najbolje rješenje je `TariffProposalBatch`:

- worker jednom učita sve tačne mape za jedinstvene product code vrijednosti;
- napravi prijedloge i dokaz za svaku stavku;
- UI samo prikaže gotov snapshot;
- potvrda primjenjuje isti snapshot, bez ponovnog DB/LLM odlučivanja;
- mutation se izvrši u glavnoj niti tek nakon uspješne pozadinske obrade.

### 4.4 Učenje tarifnih mapiranja

`FakturaView._auto_learn_edits()` (`gui/tabs/faktura_view.py:1586`) može odmah upisati ručnu izmjenu kao naučeno mapiranje. To je funkcionalno korisno, ali poznati obrazac greške je da jedna pogrešna ručna tarifa postane tačan match i ubuduće nadjača fuzzy logiku.

Pored rizika kvaliteta, upis se radi sinhrono po redu iz GUI-a.

Predloženi model:

- ručna izmjena prvo dobija status `candidate` ili `confirmed_correction`;
- čuvaju se dobavljač, product code, stari i novi broj, korisnik, vrijeme i izvor odluke;
- tek potvrđene korekcije ulaze u exact-match prioritet;
- upisi iz jedne izmjene tabele grupišu se u jednu transakciju u workeru;
- UI prikazuje da li je korekcija samo lokalna, čeka potvrdu ili je aktivno naučena.

### 4.5 Formiranje naimenovanja

`CreateNaimenovanjaService.create_smart_group()` grupiše fakture po četiri projektna ključa: tarifni broj, zemlja porijekla, povlastica i EUR.1 broj. To je trenutno kanonsko pravilo aplikacije i ne treba ga duplirati u drugim servisima. Ipak, ono nije ovom analizom dokazano kao univerzalno carinsko pravilo za sve buduće klijente i postupke.

Servis takođe poštuje ASYCUDA limit od 99 stavki i višak priprema za narednu deklaraciju. Međutim, tokom rada mijenja `draft.invoice_lines`, briše `draft.items` i zatim postepeno dodaje nova naimenovanja. Ako kasnija grupa izazove izuzetak, draft može ostati djelimično promijenjen.

Rješenje je priprema u privremenim strukturama:

- izračunati grupe i overflow bez izmjene drafta;
- izgraditi sva nova naimenovanja;
- validirati rezultat i ograničenja;
- jednom operacijom zamijeniti `draft.items` i eventualne linije;
- emitovati jedan `DraftChangeSet`.

`goods_trade_name` se pri kreiranju grupe puni nazivom prve stavke, dok projektno pravilo traži sve trgovačke nazive u grupi. XML je djelimično zaštićen jer `services/naimenovanja/rub31_builder.py:22` ponovo izvlači dodijeljene fakture i gradi Rub.31 sa svim nazivima. Ipak, model i GUI mogu prikazati samo prvi naziv. Servis treba popuniti listu jedinstvenih naziva, dok builder zadržava završno skraćivanje na tri linije i 280 znakova.

Domenski pregled mora provjeriti dodatne item-level razdjelnike prije širenja proizvoda na druge postupke i firme. UINO uputstvo definiše kvotu u polju 39, postupak u polju 37 i dopunsku jedinicu u polju 41 na nivou naimenovanja. Posebno navodi da dopunska jedinica može biti presudna za obračun duga. Zato najmanje `procedure_code`, `quota_code` i režim dopunske jedinice moraju biti dio formalne analize grupisanja, čak i ako se u sadašnjem toku postavljaju tek nakon grupisanja. Izvor: [UINO uputstvo o popunjavanju carinske deklaracije](https://www.uino.gov.ba/portal/wp-content/uploads/PROPISI/3_Carina/3_Uputstva/5_Carinska_prijava/B/B-1-U-o-popunjavanju-car-prijave-i-deklaracije-za-priv-smjestajslist-9-23-10-02-23.pdf).

### 4.6 Dokumenti uz naimenovanje

`NaimenovanjaView._perform_tariff_lookup()` (`gui/tabs/naimenovanja_view.py:1894`) nakon debounce perioda radi više sinhronih provjera: opis tarife, inspekcijsko upozorenje, službene kontrolne dokumente i istorijske dokumente.

`_add_history_docs()` (`gui/tabs/naimenovanja_view.py:1954`) istorijske rezultate direktno dodaje u `draft.header_attached_documents`. Istorija je dokaz da je dokument ranije korišten, ali nije pravilo da je dokument obavezan u novoj deklaraciji.

Potrebno je razdvojiti:

- `RULE_REQUIRED`: službeno pravilo, može biti aktivno automatski uz jasan izvor;
- `HISTORY_SUGGESTED`: samo prijedlog, ne ulazi u XML dok ga korisnik ne potvrdi;
- `USER_CONFIRMED`: potvrđen dokument sa audit tragom.

### 4.7 XML izvoz

`exporters/asycuda_xml_builder.py` je aktivni builder. Ima dobru podjelu Rub.31 logike i dokumentnih elemenata, ali `AsycudaXMLBuilder.build()` prije generisanja poziva `_apply_known_tariff_corrections()` (`exporters/asycuda_xml_builder.py:236`). Ta metoda mijenja `item.tariff_code` i upozorenja na originalnom draftu.

Izvoz bi trebalo da bude čista transformacija: isti snapshot uvijek proizvodi isti XML, bez skrivene promjene korisničkog stanja.

Preporučeno:

- preflight servis vraća listu korekcija i grešaka;
- korekcije se eksplicitno primijene prije izvoza ili se builderu proslijedi kopija;
- XML se prvo piše u privremeni fajl, zatim atomski preimenuje;
- `export_to_xml()` (`exporters/asycuda_xml_builder.py:1199`) vraća `ExportResult`, ne samo `bool`;
- `ExportResult` sadrži putanju, upozorenja, kod greške i poruku za korisnika;
- učenje upotrebe dokumenata poslije izvoza grupiše se u jednu SQLite transakciju.

Postoje dva velika XML buildera: `asycuda_xml_builder.py` i `deklarant_xml_builder.py`. Njihove uloge treba eksplicitno dokumentovati i zajedničke normalizacije izdvojiti u jedan sloj, bez spajanja različitih izlaznih formata u monolit.

### 4.8 Agentski chat i kontekst

`ChatWorker` (`gui/tabs/agent/widgets/chat_worker.py`) radi LLM pozive u `QThread`, što je ispravno. `_build_context()` ipak sastavlja više zona prema fiksnim limitima redova i znakova, a kontrola veličine dolazi nakon prikupljanja dijela sadržaja.

To može stvoriti:

- duplirane podatke o istim stavkama;
- nepredvidiv broj tokena;
- veće kašnjenje i trošak;
- izbacivanje važnijih dokaza zbog manje važnog konteksta.

Predlaže se `ContextAssembler` sa:

- budžetom tokena po zoni;
- prioritetima `errors > current selection > draft summary > history > help text`;
- deduplikacijom po stabilnom identifikatoru;
- evidencijom šta je uključeno, sažeto ili izostavljeno;
- testovima za mali, veliki i konfliktni draft.

`chat_intent_handler.py` ima oko 2.793 linije, `chat_worker.py` oko 1.192, a `agent_controller.py` oko 855. Handler trenutno miješa routing, kontekst, domenske akcije, HTML prikaz i lifecycle workera. Planirane faze E i F imaju smisla: prvo integrativni scenario testovi, zatim izdvajanje `TariffIntentHandler`, `OriginIntentHandler`, `ArchiveIntentHandler` i renderera, uz tanak controller.

## 5. Kritični i visoki prioriteti

| Prioritet | Nalaz | Posljedica | Preporučena mjera |
| --- | --- | --- | --- |
| GATE | Nije vezan instalirani klijentski artefakt za analizirani commit | Moguće je popravljati kod koji konkretni klijent ne izvršava | Fingerprint instalacije i parity zapis prije Faze 0 |
| GATE | DB safety testovi nemaju kontrolisanu test bazu | Najrizičnija tarifna izmjena nema rutinski pouzdanu mrežu | Izolovana PostgreSQL baza i transakcioni fixture prije izmjene |
| P0 | LLM može slobodno proizvesti tarifni broj | Pogrešan broj bez provjerljivog izvora | Ukloniti `_decide_free`; LLM samo rangira službene/lokalne kandidate |
| P1 | Direktni i ponovljeni DB/tarifni pozivi u UI niti | Zamrzavanje GUI-a i nepotrebni upiti | Jedan proposal worker, batch preload i primjena snapshot-a |
| P1 | Istorijski dokument odmah ulazi u draft | Prijedlog može završiti u XML-u kao aktivan dokument | Statusi required/suggested/confirmed i obavezna potvrda |
| P1 | XML builder mijenja draft | Skrivena promjena tokom izvoza, teško ponavljanje i audit | Preflight + čisti builder nad snapshot-om |
| P1 | Ručna tarifa se odmah uči kao exact match | Jedna greška postaje trajni sistemski rezultat | Provenance, potvrda korekcije i karantin kandidata |
| P1 | `dist_client` odstupa od izvornog koda | Testiran source nije nužno runtime koji koristi korisnik | Deterministički build manifest i parity provjera |
| P1 | GUI auto-fill i agent audit nemaju potpun trag potvrde | Nije dokazivo ko je prihvatio broj i iz kog izvora | Jedinstven audit za sve tarifne mutacije; serijalizovati `operation_id` i provenance |
| P1 | Standardni test paket nije zelen | Regresije se teže razlikuju od poznatih kvarova | Markeri, ispravka discovery-ja i stabilan DB integration profil |
| P2 | Direktni DB pozivi u View klasama | Kršenje 3-layer granice i teško testiranje | Postepeno premještanje u servise/workere |
| P2 | Grupisanje naimenovanja nije atomsko | Djelimično izmijenjen draft pri grešci | Staging rezultata pa jedna primjena |
| P2 | Veliki handleri i mnogo širokih `except` blokova | Skriveni kvarovi i visok trošak izmjena | Karakterizacioni testovi pa domenska dekompozicija |
| P2 | Import je potpuno sekvencijalan | Spora obrada velikih foldera | Planiranje parova pa ograničena paralelizacija |

## 6. Detaljni nalazi

### 6.0 GATE: šta lokalni distribucioni artefakti stvarno izvršavaju

Runtime proba iz korijena `dist_client` dokazala je sljedeću rezoluciju importa:

```text
services.tariff_facade                         -> tariff_facade.cp314-win_amd64.pyd
services.tariff_mapping_service                -> tariff_mapping_service.cp314-win_amd64.pyd
services.agent.tariff.hybrid_tariff_agent      -> hybrid_tariff_agent.py
exporters.asycuda_xml_builder                  -> asycuda_xml_builder.py
```

Kompajlirana `TariffFacade.suggest()` je probom potvrđena da nakon promašaja mapping i RAG sloja poziva `_try_ai()`. Hibridni agent koji zatim učitava nije skriven u `.pyd`: obični dist fajl ima isti SHA-256 kao source (`3097C382...940121`) i sadrži poziv `_decide_free()` na liniji 140 i definiciju na liniji 194. Zato je precizan odgovor na gate pitanje:

> `_decide_free()` nije u tarifnom `.pyd` modulu, ali je aktivno prisutan u modulu koji kompajlirana fasada učitava. Trenutni `dist_client` može izvršiti tu putanju.

I lokalni PyInstaller TOC uključuje `services.agent.tariff.hybrid_tariff_agent`, `services.tariff_facade` i `exporters.asycuda_xml_builder`. `_decide_free()` postoji u git istoriji od 31.05.2026, dok su lokalni installer/EXE artefakti građeni poslije tog datuma. To potvrđuje problem u lokalno izgrađenim artefaktima. Ipak, konačan produkcijski dokaz zahtijeva hash/verziju fajlova ili build manifesta sa konkretne klijentske mašine; lokalni folder nije dovoljan dokaz šta je tamo instalirano.

### 6.1 P0: stara AI putanja zaobilazi agentska pravila

`services/agent/tariff/hybrid_tariff_agent.py` direktno inicijalizuje Groq, zatim Ollama fallback. Kada nema RAG kandidata, `decide_tariff()` poziva `_decide_free()` (`hybrid_tariff_agent.py:194`) i traži od modela tarifni broj.

Ovo je u sukobu sa dva novija projektna pravila:

- provideri se pozivaju isključivo kroz `LLMProvider`;
- bez lokalnog ili službenog dokaza rezultat mora biti `UNKNOWN`, ne generisana činjenica.

`TariffFacade.suggest()` ima aktivnu Level 3 AI putanju, a fasada se koristi iz GUI-a i agentskih workera. Zato ovo nije izolovan ili mrtav kod.

Minimalna bezbjedna izmjena:

1. ako nema kandidata, vratiti `TariffResult` bez broja, `needs_review=True`, izvor `no_evidence`;
2. LLM-u dozvoliti samo izbor indeksa iz zatvorenog skupa kandidata;
3. sve chat pozive provući kroz `LLMProvider`;
4. Ollama ukloniti ili uvesti kao formalno podržan provider sa istim pravilima, ne kao privatni fallback;
5. testirati da modelov odgovor koji sadrži broj izvan kandidata nikada ne postane prijedlog.

### 6.2 P1: N+1 upiti i dupli tarifni rad

`DeclarationDecisionService` evaluira svaku fakturu i za svaku posebno traži tarifne, porijeklosne i preferencijalne dokaze. Tarifni adapter pravi novu instancu `TariffMappingService`, a `find_mapping()` koristi više upita i široko guta izuzetke.

U GUI auto-fill toku preview i apply rade dva prolaza. `HybridMatchingService` se u `auto_populate_tariffs()` kreira unutar petlje (`tariff_mapping_service.py:211`).

Predložena struktura:

```text
TariffProposalWorker
  -> batch exact lookup za sve product_code vrijednosti
  -> jedan HybridMatchingService po poslu
  -> fuzzy/RAG samo za preostale jedinstvene nazive
  -> TariffProposalBatch + evidence + source + confidence
  -> dijalog za potvrdu
  -> apply_proposals(batch_id, accepted_ids)
```

Prihvatljiv rezultat:

- najviše jedan batch exact upit po fakturi;
- nema DB poziva u UI niti;
- potvrda ne ponavlja odlučivanje;
- 100 stavki ostavlja GUI responzivnim;
- broj upita i trajanje su vidljivi u logu/metrici.

### 6.3 P1: nekontrolisano auto-učenje

Tačan product code match ima opravdano najveći prioritet. Upravo zato pogrešan naučeni zapis ima velik domet. Brisanje lošeg zapisa poslije incidenta nije dovoljno rješenje.

Potrebna je kontrola životnog ciklusa mapiranja:

```text
suggested -> user_corrected -> confirmed -> active
                         \-> rejected/quarantined
```

Za automatsko aktiviranje može se tražiti više nezavisnih potvrda ili eksplicitna korisnička potvrda. `supplier/exporter` treba postati dio dokaza i budućeg ključa, jer isti product code različitih dobavljača ne mora značiti isti proizvod.

### 6.4 P1: prijedlog istorijskog dokumenta postaje podatak

Istorijski dokumenti su korisni za podsjetnik, ali ne smiju imati isti status kao službeno pravilo. Trenutna mutacija u View-u dodatno otežava testiranje i audit.

Rješenje je servis koji vraća `DocumentEvidence` objekte, a controller odlučuje šta se prikazuje i šta korisnik potvrđuje. View prikazuje status, ali ne pristupa bazi i ne mijenja draft direktno.

### 6.5 P1: izvoz nije bez sporednih efekata

Automatska korekcija tarife unutar buildera može pomoći da XML bude prihvaćen, ali skriva da je draft bio neispravan. Ako build kasnije padne, dio drafta je već promijenjen.

Preflight treba vratiti:

- fatalne greške;
- korekcije koje je bezbjedno automatski primijeniti;
- korekcije koje traže potvrdu;
- upozorenja koja ne blokiraju izvoz.

Builder tada dobija validiran snapshot. Ovo poboljšava ponovljivost, audit i testove bez promjene ASYCUDA strukture.

### 6.6 P1: distribuciona kopija nije deterministički artefakt

Poređenje 368 Python parova između izvornog stabla i `dist_client` pokazalo je 43 razlike. Među njima su `app/run.py`, `gui/main_window.py`, `asycuda_xml_builder.py`, `processing_worker.py`, `chat_worker.py`, `import_pipeline_service.py`, `import_service.py` i tarifni servis.

Detaljna provjera dva kritična modula daje precizniju sliku:

- hibridni tarifni agent je identičan sourceu i dokazano sadrži `_decide_free()`;
- dist XML builder jeste različitog hasha, ali trenutni diff mijenja BOM, komentare/docstringove i logger/`print` izlaz, ne XML poslovnu logiku; sporedna mutacija drafta postoji u obje kopije.

Zato dijagnostika kritičnih artefakata ide prije Faze 0, dok puni deterministički build sistem može ostati kasnija infrastrukturna faza.

Neke razlike su očekivane zbog `.pyd` builda, zato rješenje nije slijepo kopiranje cijelog stabla. Potreban je manifest:

- source moduli koji se kopiraju identično;
- moduli koji se kompajliraju;
- konfiguracioni fajlovi koji su runtime-specifični;
- verzija commita i hash svakog artefakta;
- smoke test koji se pokreće iz stvarnog `dist_client` okruženja.

Release treba pasti ako kritični runtime fajl nema očekivani hash ili build porijeklo.

### 6.7 P1: testovi daju lažan osjećaj potpunosti

Ciljani skup od 149 testova za large-batch, decision-to-naimenovanja, XML preflight, agent pipeline/router/provider i XML helper-e prošao je: **149 passed za 12,31 s**.

Puni skup je prikupio 900 testova i završio sa:

- **822 passed**;
- **58 skipped**;
- **5 xfailed**;
- **14 failed**;
- **1 error**;
- ukupno **21,85 s**.

Glavne grupe problema:

- decision characterization testovi zavise od nedostupnog PostgreSQL-a i aktivnog circuit breakera;
- dva testa tarifnog dijaloga očekuju stariji tekst interfejsa;
- lokalni root testovi imaju nedostajući fixture, encoding problem i hardkodovanu Linux putanju;
- tri praćena fajla završavaju sa `_test.py`, pa ih standardni pytest discovery ne pokreće:
  - `tests/unit/asycuda_item_limit_test.py`;
  - `tests/unit/pdf_faktura_pregled_fonts_test.py`;
  - `tests/unit/pdf_invoice_exporter_fonts_test.py`.

DB test problem je ozbiljniji od običnog skip podešavanja. `tests/conftest.py` samo postavlja Qt offscreen i Python path. DB karakterizacioni testovi su u `tests/unit/test_decision_characterization.py`, nisu označeni `integration`, oslanjaju se na poznate produkcijske zapise i neutralizuju samo `_increment_usage`. Ne postoji izolovana baza, migracioni setup ni transakcioni rollback fixture. Prije izmjene tarifnog odlučivanja treba napraviti kontrolisanu PostgreSQL test bazu sa minimalnim determinističkim datasetom i automatskim rollbackom po testu.

Preporučena podjela:

- `unit`: bez mreže i bez spoljne baze;
- `integration_db`: pravi PostgreSQL, ali jasan skip ako okruženje nije dostupno;
- `real_documents`: stvarne fakture iz `najavauvoza/`;
- `gui`: Qt offscreen i ciljane interakcije;
- `benchmark`: nije dio brzog pre-commit profila.

Testovi sa pravim bazama ne treba da koriste mock. Potrebna je kontrolisana test baza ili transakcioni fixture koji radi nad pravim SQLite/PostgreSQL slojem.

### 6.8 P2: poslovna logika i DB u View sloju

Statički pregled je našao oko 85 GUI linija koje direktno referišu DB konekcije ili SQL izvršavanje. Primjeri:

- `zaglavlje_view.py` uvozi `get_db_connection` i ima više `_load_*_from_db` funkcija;
- `naimenovanja_view.py` direktno koristi pool i konekcije;
- `sifarnici_view.py` direktno uvozi `psycopg2`;
- `faktura_view.py` direktno otvara SQLite.

To krši projektni View/Controller/Service obrazac. Migraciju treba raditi po korisničkom toku, ne kao masovni refactor:

1. tarifni lookup i dokumentni lookup;
2. auto-učenje;
3. zaglavlje šifrarnici;
4. preostali read-only helperi.

Svaki izdvojeni servis treba vratiti strukturisani rezultat, a controller ga prenosi View-u signalom.

### 6.9 P2: široki `except Exception` blokovi

Približni broj širokih catch blokova u glavnim stablima:

- GUI: 270;
- services: 251;
- importers: 96;
- database: 26;
- exporters: 15;
- core: 12.

Dio je opravdan za fallback parsere i opcionalne providere. Problem su mjesta koja na grešku vraćaju praznu listu, `True`, `None` ili samo nastave, jer sistem tada razlikuje "nema podatka" od "provjera nije uspjela" samo implicitno.

Ne treba mehanički zamijeniti sve catch blokove. Prioritet su tarifno odlučivanje, dokumenti, XML preflight, DB lookup i agentske mutacije. Rezultat treba razlikovati `NOT_FOUND`, `UNAVAILABLE`, `INVALID_INPUT` i `INTERNAL_ERROR`.

### 6.10 P2: veličina modula i trošak izmjene

Najveći pregledani moduli:

| Fajl | Približno linija |
| --- | ---: |
| `gui/tabs/faktura_view.py` | 5.135 |
| `gui/tabs/naimenovanja_view.py` | 3.789 |
| `gui/tabs/sifarnici_view.py` | 3.654 |
| `gui/tabs/agent/services/chat_intent_handler.py` | 2.793 |
| `gui/tabs/zaglavlje_view.py` | 2.485 |
| `services/zaglavlje_service.py` | 1.947 |
| `importers/leburic_pdf_importer.py` | 1.500 |
| `services/sifarnici_service.py` | 1.414 |
| `exporters/asycuda_xml_builder.py` | 1.250 |
| `gui/tabs/agent/widgets/chat_worker.py` | 1.192 |
| `services/tariff/tariff_mapping_service.py` | 1.175 |

Velik fajl nije sam po sebi bug. Ovdje je signal problematičan kada se poklopi sa više odgovornosti, DB pristupom, UI prikazom i worker lifecycle-om. Dekompoziciju treba voditi po domenskoj odgovornosti i uz karakterizacione testove, ne po proizvoljnom broju linija.

### 6.11 P1: audit ne pokriva sve tarifne mutacije

Postojeći `services/agent/chat/audit_log.py` prati agentski routing, ali GUI `FakturaView._on_auto_fill()` ne zapisuje ko je prihvatio prijedlog, izvor kandidata, staru i novu vrijednost ni identitet distribucionog artefakta. To je rupa upravo u najčešćem putu tarifne odluke.

Dodatno, `AuditEvent.extra` prima `operation_id`, ali ga `record()` ne uključuje u format loggera. Zato je operation ID koristan za runtime idempotenciju, ali nije stvarno prisutan u emitovanom audit logu.

Audit ugovor treba važiti za svaku tarifnu mutaciju, bez obzira da li dolazi iz agentskog chata, GUI auto-fill dijaloga, ručne ispravke ili automatizovanog pipeline-a. Minimalni zapis je:

- `operation_id`;
- korisnik ili sistemski actor;
- vrijeme i verzija/build hash aplikacije;
- identifikator fakture i stavke, bez nepotrebnog sadržaja proizvoda u opštem logu;
- stara i nova tarifa;
- izvor, confidence i identifikator prijedloga;
- način potvrde: GUI, agent proposal, ručni unos ili auto pipeline;
- uspjeh, odbijanje ili rollback.

## 7. Plan poboljšanja

### Faza -1: dokaz runtime-a i testni preduslovi, prije izmjena

1. Na svakoj aktivnoj klijentskoj instalaciji zabilježiti verziju, build datum i hash kritičnih modula/EXE-a.
2. Potvrditi da instalirani artefakt učitava istu tarifnu i XML putanju koja je analizirana.
3. Uvesti izolovanu PostgreSQL test bazu sa migracijama, minimalnim tarifnim datasetom i rollback fixture-om.
4. Premjestiti/označiti DB karakterizacione testove kao `integration` i obezbijediti jednu pouzdanu komandu za njihovo pokretanje.
5. Dodati test koji dokazuje da dist/runtime import putanja ne pada na neočekivanu staru kopiju modula.

**Izlaz:** poznato je šta konkretni klijent izvršava i postoji pouzdana safety mreža za promjenu tarifne odluke.

### Faza 0: sigurnost odluka, 1-2 sedmice

1. Ukloniti slobodno LLM generisanje tarifnog broja.
2. Prebaciti hibridni tarifni servis i KB reranking na formalne provider apstrakcije.
3. Odvojiti istorijski prijedlog dokumenta od aktivnog dokumenta.
4. Dodati testove koji dokazuju fail-closed ponašanje bez dokaza.
5. Ispraviti tri pogrešno imenovana test fajla i tarifni dijalog test drift.
6. Proširiti audit na GUI auto-fill i serijalizovati `operation_id`/provenance.

**Izlaz:** nijedan tarifni broj ili dokument ne može postati aktivan bez lokalnog/službenog dokaza ili eksplicitne potvrde.

### Faza 1: odziv GUI-a i DB efikasnost, 2-4 sedmice

1. Uvesti `TariffProposalWorker` i `TariffProposalBatch`.
2. Batch učitati exact product-code mapiranja.
3. Koristiti jednu instancu matching servisa po poslu.
4. Izbaciti DB operacije iz auto-fill i history lookup UI niti.
5. Grupisati auto-learning upise u jednu transakciju.
6. Dodati metrike broja upita i trajanja po batchu.

**Izlaz:** auto-fill 100 stavki ne blokira UI, ne odlučuje dva puta i ne radi N+1 exact upite.

### Faza 2: atomske domenske operacije, 3-6 sedmica

1. Uvesti `DraftChangeSet` i preciznije draft događaje.
2. Napraviti atomsko formiranje naimenovanja.
3. Razdvojiti XML preflight, korekciju i build.
4. Uvesti `ExportResult` i atomski upis fajla.
5. Dodati provenance i lifecycle tarifnih mapiranja.

**Izlaz:** greška u bilo kojoj fazi ne ostavlja djelimično promijenjen draft ili polovičan XML.

### Faza 3: održivost agentskog i GUI koda, 4-8 sedmica

Ovu fazu ne započinjati dok Faza 0 nije stabilna u produkciji najmanje nekoliko sedmica i dok nema otvorenih P0/P1 regresija.

1. Završiti integrativne agentske scenario testove.
2. Izdvojiti domenske intent handlere i renderer iz `chat_intent_handler.py`.
3. Uvesti `ContextAssembler` sa token budžetima.
4. Premještati DB helper-e iz View klasa u servise po toku.
5. Zamijeniti `LazyTab` univerzalni no-op eksplicitnim odloženim API-jem.

**Izlaz:** controller ostaje tanak, View nema business/DB logiku, a agentski kontekst je predvidiv i mjerljiv.

### Faza 4: release i performanse, poslije stabilizacije

1. Uvesti deterministički `dist_client` manifest i runtime smoke test.
2. Napraviti real-document benchmark za PDF/Excel/OCR.
3. Razdvojiti planiranje import parova od izvršenja.
4. Paralelizovati samo nezavisne import poslove sa ograničenom konkurentnošću.

**Izlaz:** build koji koristi korisnik je dokazivo izveden iz testiranog commita, a performanse se mjere na stvarnim dokumentima.

Navedena trajanja su fokusirane inženjerske sedmice, ne kalendarski rok za jednog autora. Za solo razvoj uz podršku korisnicima i nove funkcije realan kalendarski okvir cijelog programa je približno 6-12 mjeseci. Fazu 3 treba svjesno držati iza sigurnosnih i produkcionih kriterijuma jer je tehnički privlačna, ali poslovno manje hitna.

## 8. Predložene metrike i kriterijumi prihvatanja

### Pouzdanost

- 0 tarifnih prijedloga izvan zatvorenog skupa kandidata;
- 0 istorijskih dokumenata u XML-u bez statusa `RULE_REQUIRED` ili `USER_CONFIRMED`;
- 0 djelimičnih draft mutacija poslije neuspjelog grupisanja ili izvoza;
- svaka tarifna mutacija, uključujući GUI auto-fill, ručni unos, agent i auto pipeline, ima `operation_id`, actor, staru/novu vrijednost, izvor i audit zapis;
- emitovani audit zapis zaista sadrži `operation_id`, ne samo in-memory `AuditEvent.extra`.

### Performanse

- vrijeme do prvog prikaza glavnog prozora;
- p50/p95 vrijeme uvoza po dobavljaču i tipu dokumenta;
- p50/p95 auto-fill za 10, 50 i 100 stavki;
- broj PostgreSQL/SQLite upita po auto-fill batchu;
- maksimalno vrijeme blokade UI event loopa, cilj ispod 100 ms za obične akcije;
- broj LLM poziva i tokena po agentskom zahtjevu.

### Testovi

- brzi `unit` profil uvijek zelen;
- DB testovi imaju jasan marker i preduslov;
- standardni discovery uključuje ASYCUDA limit i PDF font testove;
- najmanje jedan stvarni dokument po važnom importeru;
- `dist_client` smoke test provjerava pokretanje, import, draft, naimenovanja i XML preflight.

## 9. Šta ne treba mijenjati bez posebnog razloga

- srpske nazive polja u `InvoiceLine` i engleske ASYCUDA nazive u `NaimenovanjeDraft`;
- centralizaciju grupisanja u `CreateNaimenovanjaService`; postojeća četiri ključa ne širiti niti mijenjati bez zasebnog domenskog pregleda kvote, postupka, dopunskih jedinica i drugih item-level mjera;
- `consumed_paths` ugovor kombinovanih importera;
- internu tarifu od osam cifara i PG konverziju na deset cifara;
- punu preciznost težina;
- PostgreSQL connection pool, timeout i circuit-breaker koncept;
- `LLMProvider`, mutation gate, `ToolResult` i `operation_id` kao centralne agentske mehanizme;
- specijalizovane importer-e samo radi smanjenja broja fajlova;
- ASYCUDA Rub.31 završno ograničenje od 280 znakova i tri linije.

## 10. Zaključak

Deklarant Pro je već iznad nivoa jednostavne forme nad bazom. U kodu postoji stvarno domensko znanje: uparivanje dokumenata, tarifna istorija, kontrola porijekla, grupisanje naimenovanja, ASYCUDA ograničenja i ljudska potvrda agentskih akcija.

Najveća dobit sada ne dolazi iz dodavanja novih AI mogućnosti, nego iz ujednačavanja postojećih: jedan dokazni model za tarife, jedan statusni model za prijedloge, jedan atomski put za mutacije i jedan provider sloj. Nakon toga optimizacija upita, izdvajanje UI business logike i kontrolisan release proces mogu se raditi bez velikog prepisivanja sistema.

Redosljed je važan: prvo dokazati isporučeni runtime i obezbijediti kontrolisanu DB safety mrežu, zatim zatvoriti mogućnost nedokazanih odluka, pa ukloniti blokiranje UI-a i N+1 upite. Razlaganje velikih modula i paralelizacija importa dolaze tek nakon produkcione stabilizacije sigurnosnih izmjena.
