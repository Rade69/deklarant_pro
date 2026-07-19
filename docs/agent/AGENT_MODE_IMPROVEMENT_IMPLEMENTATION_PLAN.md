# Plan unapređenja agentskog moda rada

**Datum:** 2026-07-19  
**Status:** Spremno za implementaciju  
**Namjena:** Handoff plan za agenta koji će realizovati unapređenja agentskog moda u Deklarant Pro aplikaciji  
**Polazna analiza:** pregled aktivnog toka u `gui/tabs/agent/`, `services/agent/` i ciljnih offline testova

## 1. Cilj

Cilj je unaprijediti postojeći agentski mod bez ponovnog pisanja sistema i bez promjene carinske poslovne logike. Implementacija treba da:

1. spriječi da LLM neposredno mijenja draft bez eksplicitne potvrde deklaranta;
2. ukloni direktne pozive pojedinačnim LLM providerima i uskladi fallback politiku sa projektnim pravilima;
3. učini puni automatski pipeline pouzdanim, sa tačnim statusom svake faze i kontrolisanim prekidom poslije kritične greške;
4. standardizuje rezultate lokalnih alata, porijeklo podataka i audit trag;
5. uvede integracione testove za glavne agentske tokove;
6. razloži preveliki chat handler tek nakon što ponašanje bude zaključano testovima.

## 2. Važeće arhitekturne odluke

Sljedeće odluke su scope lock i ne smiju se mijenjati tokom ovog zadatka:

- Lokalni servis, baza ili deterministički router imaju prioritet nad LLM-om.
- `TOOL_RESULT` je autoritativan. LLM smije samo formatirati potvrđen rezultat.
- Status `unknown` ili `needs_review` ne smije biti dopunjen LLM pretpostavkom.
- Tarifni broj, zemlja porijekla i povlastica ne smiju se izmišljati.
- Povlastica i PE1/PE2/PE3 ostaju predmet eksplicitne potvrde deklaranta.
- Grupiranje naimenovanja ostaje u `CreateNaimenovanjaService.create_smart_group()`.
- `LLMProvider` ostaje jedina dozvoljena ulazna tačka za LLM pozive.
- Svi LLM i duži servisni pozivi ostaju izvan UI threada.
- Postojeći srpski nazivi polja u `InvoiceLine` ostaju nepromijenjeni.
- `dist_client/` se ne ažurira parcijalnim kopiranjem bez provjere načina distribucije i potrebnog rebuilda.

## 3. Obavezna priprema prije izmjena

Agent koji implementira plan mora prije kodiranja:

1. pročitati `AGENTS.md` i `docs/CONTEXT.md`;
2. pročitati:
   - `docs/decisions/001-tool-use-refactoring.md`;
   - `docs/decisions/002-tool-dispatcher-integration.md`;
   - `docs/sections/agent-origin-query-routing.md`;
3. provjeriti `git status --short` i evidentirati postojeće korisničke izmjene;
4. provjeriti svježinu GitNexus indeksa;
5. za svaki simbol koji će mijenjati pokrenuti `gitnexus_impact(..., direction="upstream")`;
6. ako je rezultat HIGH ili CRITICAL, prije izmjene napraviti obavezni `project_rooms/YYYY-MM-DD_*.md` i prijaviti rizik korisniku formatom iz `AGENTS.md`;
7. koristiti ručnu `rg` analizu kao dopunu jer je GitNexus indeks za ovaj repo ranije imao degradirane rezultate;
8. pokrenuti postojeće ciljane testove i sačuvati početno stanje:

```bash
python -m pytest \
  tests/unit/test_tool_dispatcher.py \
  tests/unit/test_tool_result.py \
  tests/unit/test_llm_provider_fallback.py -q
```

## 4. Ciljna arhitektura

### 4.1 Tok chat poruke

```text
Korisnička poruka
  -> injection i length provjera
  -> konverzacijski follow-up i aktivni pending prijedlog
  -> deterministički lokalni router
  -> LLMProvider.complete_with_tools() samo ako lokalni router nema rezultat
  -> validacija ToolCall naziva i argumenata
  -> ToolPolicy klasifikacija: READ_ONLY | PROPOSE | MUTATE
  -> izvršenje READ_ONLY alata ili kreiranje prijedloga
  -> eksplicitna potvrda korisnika za MUTATE
  -> servisna izmjena drafta
  -> strukturisani ToolResult + audit događaj
  -> prikaz rezultata u GUI-ju
```

### 4.2 Tok pune automatizacije

```text
Parsirane fakture
  -> CALCULATE_MASSES
  -> AUTO_FILL_TARIFFS
  -> VALIDATE_LINES
  -> WAITING_DECLARANT_CONFIRMATION
  -> CREATE_NAIMENOVANJA
  -> FINAL_VALIDATION
  -> COMPLETED | PARTIAL | FAILED | CANCELLED
```

Kritična faza ne smije biti označena uspješnom ako je servis bacio izuzetak, vratio neuspjeh ili nije bio dostupan.

## 5. Faza A - sigurnosna kapija za mutirajuće alate

### 5.1 Namjera

Odvojiti čitanje i prijedloge od stvarnih izmjena drafta. Nijedan LLM tool-call ne smije neposredno pozvati servis koji mijenja draft.

### 5.2 Planirani simboli i fajlovi

- `services/agent/chat/tool_definitions.py`
  - dodati ili izdvojiti metapodatke o politici alata;
  - ne oslanjati se na opis alata kao sigurnosnu kontrolu.
- novi modul, preporučeno `services/agent/chat/tool_policy.py`
  - `ToolEffect` enum: `READ_ONLY`, `PROPOSE`, `MUTATE`;
  - registry koji mapira svaki poznati alat na efekat;
  - funkcija koja odbija nepoznat alat zatvorenim režimom, bez izvršenja.
- `gui/tabs/agent/services/chat_intent_handler.py`
  - `_execute_tool()` ne smije direktno izvršiti `MUTATE` alat;
  - za `upisi_u_kolonu` prvo razriješiti kolonu i validirati vrijednost, zatim kreirati strukturisani prijedlog;
  - potvrđeni prijedlog izvršiti kroz jedan kontrolisani mutation executor;
  - postojeće proposal kartice ponovo koristiti, ne praviti drugi mehanizam potvrde.
- po potrebi novi modul `gui/tabs/agent/services/draft_mutation_handler.py`
  - priprema prijedloga;
  - izvršenje samo potvrđenog prijedloga;
  - vraćanje `ToolResult` rezultata.
- `services/agent/chat/tool_result.py`
  - po potrebi proširiti rezultat identifikatorom operacije, efektom alata i informacijom da li je potrebna potvrda;
  - ne mijenjati značenje postojećih statusa.

### 5.3 Pravila izvršenja

- `READ_ONLY` se izvršava odmah.
- `PROPOSE` smije izračunati i prikazati prijedlog, ali ne smije mijenjati draft.
- `MUTATE` uvijek kreira pending akciju ili proposal karticu.
- Nepoznat alat mora vratiti `ToolResultStatus.UNKNOWN` i ne smije biti izvršen.
- Argumenti tool-calla moraju biti validirani prije prikaza prijedloga.
- Potvrda mora biti vezana za konkretan prijedlog, ne za bilo koju buduću akciju.
- Odbijanje ili reset sesije mora ukloniti pending mutaciju.
- Ponovljeni signal ili dvostruki klik ne smije izvršiti istu mutaciju dva puta.

### 5.4 Kriterijumi prihvata

- Poruka `upiši zemlju porijekla RS` ne mijenja draft prije klika na potvrdu.
- Nakon potvrde mijenja se samo očekivano polje i osvježava odgovarajući tab.
- Odbijanje ostavlja draft identičnim.
- Nepoznat alat ili nevažeća kolona ne mijenjaju draft.
- `READ_ONLY` alati i dalje rade bez dodatnog dijaloga.
- Povlastica ostaje pod postojećim strožim pravilima potvrde deklaranta.

### 5.5 Testovi

Dodati ciljane testove, preporučeno:

- `tests/unit/test_tool_policy.py`;
- `tests/unit/test_agent_mutation_gate.py`;
- test da `MUTATE` ne poziva `NaimenovanjaIntentService.execute()` prije potvrde;
- test potvrde, odbijanja i dvostrukog signala;
- test nepoznatog alata i nevažećih argumenata;
- test da read-only pretraga ne otvara proposal karticu.

## 6. Faza B - jedinstveni LLM provider i fallback politika

### 6.1 Namjera

Ukloniti direktni DeepSeek API put iz Tool Dispatchera i osigurati da chat, tool use i batch pozivi koriste istu konfiguraciju, fallback, audit i obradu grešaka.

### 6.2 Važeća politika

Prema `AGENTS.md`, produkcijski redoslijed je:

1. Groq kao primarni provider;
2. Gemini kao fallback;
3. samo dozvoljeni besplatni modeli;
4. DeepSeek isključen;
5. direktan poziv provideru van `LLMProvider` je zabranjen.

Ako vlasnik projekta želi zadržati OpenRouter ili DeepSeek, to je kontradiktorna poslovna odluka i mora se potvrditi prije implementacije. Agent ne smije sam promijeniti kanonsku politiku.

### 6.3 Planirani simboli i fajlovi

- `gui/tabs/agent/widgets/llm_provider.py`
  - dodati strukturisani `complete_with_tools(messages, tools, ...)` API;
  - vratiti neutralni rezultat, npr. `ProviderToolResponse`, bez provider-specifičnih objekata;
  - objediniti timeout, rate-limit, greške, audit metapodatke i fallback;
  - ukloniti ili deaktivirati providere koji nisu dozvoljeni kanonskim pravilima.
- `services/agent/chat/tool_dispatcher.py`
  - ukloniti direktni `OpenAI(... base_url="https://api.deepseek.com")` poziv;
  - koristiti isključivo `LLMProvider.complete_with_tools()`;
  - zadržati lokalni router kao prvi korak;
  - validirati da je ime vraćenog alata u dozvoljenom registru.
- `services/agent/chat/intent_classifier.py`
  - potvrditi da koristi `LLMProvider` i dozvoljeni model;
  - ukloniti zastarjele DeepSeek tvrdnje iz komentara i prompt dokumentacije.
- dokumentacija odluke
  - ažurirati `docs/decisions/001-tool-use-refactoring.md` i `002-tool-dispatcher-integration.md` tako da opisuju stvarni provider tok.

### 6.4 Kriterijumi prihvata

- U aktivnom agentskom kodu nema direktnog kreiranja Groq, Gemini, OpenRouter ili DeepSeek klijenta izvan `LLMProvider`.
- Tool Use radi preko istog fallback mehanizma kao standardni chat.
- Lokalni router ne poziva mrežu kada prepozna namjeru.
- Greška prvog providera prelazi na dozvoljeni fallback.
- Audit bilježi provider koji je stvarno završio poziv, ne samo primarni provider.
- Poruka bez dostupnog providera ostaje jasna i ne pokreće mutaciju.

### 6.5 Testovi

- proširiti `tests/unit/test_llm_provider_fallback.py` za `complete_with_tools()`;
- test lokalnog route hita bez provider poziva;
- test pada primarnog i uspjeha fallback providera;
- test nevažećeg JSON-a i nepoznatog tool imena;
- test da dispatcher više ne zahtijeva `DEEPSEEK_API_KEY`;
- test audit metapodataka za stvarno korišten provider.

## 7. Faza C - pouzdan status pune automatizacije

### 7.1 Namjera

Spriječiti nastavak pipeline-a poslije kritične greške i ukloniti završnu poruku koja može netačno tvrditi da je automatizacija završena.

### 7.2 Planirani model

Uvesti strukturisani rezultat faze, preporučeno u `gui/tabs/agent/workflow_state.py` ili posebnom servisnom modulu:

```python
class PipelineStageStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    WAITING_CONFIRMATION = "waiting_confirmation"
    CANCELLED = "cancelled"
```

`PipelineStageResult` treba minimalno da nosi:

- naziv faze;
- status;
- korisničku poruku;
- tehnički razlog za log;
- da li je dozvoljen nastavak;
- opcionu statistiku, bez osjetljivog sadržaja.

### 7.3 Planirani simboli i fajlovi

- `gui/tabs/agent/services/import_pipeline_service.py`
  - razložiti `_puna_auto_pipeline()` u male faze;
  - ukloniti obrazac `except -> upozorenje -> nastavi` za kritične faze;
  - finalni status izračunati iz rezultata svih faza;
  - eksplicitno razlikovati `COMPLETED`, `PARTIAL`, `FAILED` i `CANCELLED`.
- `gui/tabs/agent/workflow_state.py`
  - proširiti state machine samo ako postojeći model nema potrebne statuse;
  - ne duplirati dva nezavisna izvora workflow stanja.
- `gui/tabs/agent/agent_controller.py`
  - controller orkestrira faze i osvježavanje View-a;
  - zadržati javne metode kompatibilne gdje je moguće.
- odgovarajući Faktura controller/service
  - izložiti servisne operacije za mase, auto-popunu, validaciju i kreiranje naimenovanja;
  - pipeline servis ne treba da poziva privatne View event handlere.

### 7.4 Klasifikacija faza

Preporučeni početni režim:

| Faza | Neuspjeh | Nastavak |
| --- | --- | --- |
| Izračun masa | FAILED | NE |
| Auto-popuna tarifa | WARNING ako postoje ručno unesene ili neriješene tarife | DA, ali samo do validacije |
| Validacija stavki | FAILED za kritične greške | NE |
| Potvrda deklaranta | CANCELLED | NE |
| Kreiranje naimenovanja | FAILED | NE |
| Finalna validacija | WARNING ili FAILED | završni status PARTIAL/FAILED |

Tačna lista kritičnih validacionih grešaka treba da koristi postojeće validatore, bez nove paralelne poslovne logike.

### 7.5 Kriterijumi prihvata

- Greška obračuna masa zaustavlja pipeline prije kreiranja naimenovanja.
- Odbijena potvrda završava statusom `CANCELLED` ili `WAITING_USER_CONFIRMATION`, ne `COMPLETED`.
- Neriješene tarife su jasno prikazane u finalnom rezultatu.
- Poruka „Puna automatizacija završena“ postoji samo kad su obavezne faze uspješne.
- GUI ostaje responzivan i loading stanje se uvijek resetuje.
- Jedna faktura sa greškom ne označava cijeli batch uspješnim bez parcijalnog statusa.

### 7.6 Testovi

- test uspješnog toka svih faza;
- parametrizovani test pada svake kritične faze;
- test odbijene deklarantske potvrde;
- test parcijalnog batch rezultata;
- test da se loading status resetuje poslije izuzetka;
- test da se naimenovanja ne kreiraju kada validacija padne.

## 8. Faza D - standardizovani rezultati i observability

### 8.1 ToolResult kao jedinstveni ugovor

Svaki lokalni alat treba da vrati `ToolResult`, uključujući uspješne rezultate. HTML formatiranje mora ostati u GUI sloju.

Preporučena minimalna polja:

- `tool`;
- `status`;
- `message`;
- `source`;
- `data`;
- `next_action`;
- `effect`;
- `confirmation_required`;
- `operation_id` za mutacije.

Ne stavljati puni sadržaj faktura, API ključeve ili osjetljive deklaracijske podatke u audit log.

### 8.2 Audit događaji

Bilježiti strukturisano:

- izabrani routing sloj: contextual, local, tool-use, regex fallback ili plain chat;
- ime alata;
- efekat alata;
- trajanje;
- status;
- izvor podatka;
- korišteni provider;
- fallback razlog;
- da li je prijedlog potvrđen ili odbijen;
- pipeline fazu i njen status.

Aktivne `print()` pozive u runtime agentskom toku zamijeniti loggerom. CLI/test pomoćni ispisi van GUI runtime-a mogu ostati ako su jasno izolovani pod `if __name__ == "__main__":`.

### 8.3 Kriterijumi prihvata

- Svaki tool odgovor prikazuje izvor i status.
- Runtime agentski tok ne ispisuje emoji direktno na stderr/stdout.
- Audit pad ne ruši korisničku operaciju.
- Audit ne sadrži sadržaj dokumenata ni tajne.

## 9. Faza E - integracioni testovi prije refaktora handlera

Prije razlaganja `chat_intent_handler.py`, zaključati postojeće i novo željeno ponašanje scenario testovima.

### 9.1 Obavezni scenariji

1. Lokalno prepoznata tarifna pretraga ne poziva LLM.
2. Neprepoznata informativna poruka ide u standardni chat worker.
3. Provider greška prelazi na dozvoljeni fallback.
4. `unknown` i `needs_review` rezultat ne dobija LLM-dopunjenu činjenicu.
5. Upis kolone zahtijeva potvrdu.
6. Odbijena mutacija ne mijenja draft.
7. Prihvaćena mutacija mijenja samo ciljano polje.
8. Porijeklo koristi MCP pa lokalni SQLite fallback, bez automatskog upisa povlastice.
9. Puna automatizacija se zaustavlja poslije kritične greške.
10. Reset sesije uklanja pending mutaciju i aktivne reference workera.

### 9.2 Test infrastruktura

- Koristiti stvarni SQLite gdje servis radi sa SQLite bazom; ne mockovati samu bazu.
- Provider transport se smije zamijeniti determinističkim fake adapterom, jer test ne treba mrežu.
- Qt signale testirati sa `pytest-qt`.
- Za pipeline koristiti minimalan stvarni `DeclarationDraft` i `InvoiceLine` skup.
- Dodati bar jedan offscreen test korisničkog toka proposal kartice.

## 10. Faza F - razlaganje ChatIntentHandler-a

Ovu fazu raditi tek kada Faze A-E prolaze i scenario testovi zaključavaju ponašanje.

### 10.1 Ciljna podjela

Preporučeni moduli:

- `conversation_context.py` - posljednji subjekt, tarifa, naimenovanje i ponuđena akcija;
- `contextual_request_router.py` - follow-up i reference na trenutnu stavku;
- `tariff_tool_handler.py` - tarifna pretraga, validacija i istorijska analiza;
- `origin_tool_handler.py` - porijeklo i arhivski fallback;
- `application_context_handler.py` - čitanje Faktura/Naimenovanja/Zaglavlje stanja;
- `draft_mutation_handler.py` - priprema i potvrđeno izvršenje mutacija;
- `tool_execution_service.py` - registry alata i dispatch u odgovarajući handler;
- postojeći `chat_intent_handler.py` - tanak javni facade i orkestracija workera.

### 10.2 Pravila refaktora

- Jedna migracija domena po commitu.
- Ne mijenjati ponašanje i strukturu istovremeno.
- Stari import putevi mogu ostati kao kompatibilni stubovi dok `rg` ne potvrdi da nisu korišteni.
- Ne brisati regex fallback dok telemetrija i testovi ne potvrde da više nije potreban.
- Ne uvoditi novi dependency injection framework; koristiti postojeće konstruktore i callback obrasce.
- GUI HTML formatiranje ne smije preći u business servis.

### 10.3 Kriterijumi prihvata

- `ChatIntentHandler` ostaje tanak facade sa jasnim javnim API-jem.
- Domenski handleri se testiraju bez pokretanja cijelog GUI-ja gdje je moguće.
- Nema kružnog importa sa `agent_controller.py`.
- Svi scenario testovi iz Faze E ostaju zeleni.

## 11. Dist client i kompatibilnost

Prije izmjene svakog aktivnog modula uporediti odgovarajući fajl u `dist_client/`.

- Ne kopirati automatski izvorne fajlove u `dist_client/` ako distribucija koristi kompajlirani `.pyd`.
- U agent reportu navesti da li je desktop distribucija pogođena.
- Ako je potreban rebuild, koristiti postojeću build proceduru i posebno verifikovati agentski tab u Windows runtime-u.
- Ako rebuild nije dio odobrenog scope-a, završni status mora biti `PARCIJALNO` i follow-up mora eksplicitno navesti distribuciju.

## 12. Predloženi commit redoslijed

Svaki commit mora biti logički samostalan, sa `Co-Authored-By` linijom i bez tuđih izmjena.

1. `test(agent): zakljucaj sigurnosna pravila alata`
2. `feat(agent): dodaj politiku efekata alata`
3. `fix(agent): zahtijevaj potvrdu prije izmjene drafta`
4. `refactor(llm): objedini tool use kroz llm provider`
5. `test(agent): pokrij provider i tool fallback tokove`
6. `feat(agent): uvedi rezultate faza automatskog pipelinea`
7. `fix(agent): zaustavi pipeline nakon kriticne greske`
8. `refactor(agent): standardizuj rezultate i audit dogadjaje`
9. `test(agent): dodaj integracione agentske scenarije`
10. zasebni `refactor(agent): izdvoji ... handler` commitovi po domenu
11. `docs(agent): uskladi odluke i agentski tok`

Ne mora svaki navedeni commit postojati ako promjena nije potrebna, ali sigurnosna kapija, provider politika i pipeline statusi ne smiju biti spojeni u jedan veliki commit.

## 13. Verifikaciona matrica

| Oblast | Obavezna provjera |
| --- | --- |
| Tool politika | unit test registry-ja i fail-closed ponašanja |
| Mutacije | proposal, potvrda, odbijanje, idempotencija |
| Provideri | primarni, fallback, bez ključa, rate limit, invalid tool call |
| ToolResult | OK, NEEDS_REVIEW, UNKNOWN, ERROR i izvor |
| Pipeline | success, warning, failure, cancellation, partial batch |
| GUI | offscreen proposal i loading state |
| Baza | stvarni SQLite test gdje se čita/piše lokalna baza |
| Regresija | puni `python -m pytest tests/ -q` |
| Sintaksa | `python -m py_compile` za izmijenjene Python fajlove |
| Dokumentacija | `bash scripts/doc_link_checker.sh .` |
| Scope | `gitnexus_detect_changes()` prije svakog commita |
| Distribucija | Windows/dist_client provjera ili eksplicitan follow-up |

## 14. Minimalni ručni acceptance test

Na kopiji ili testnom draftu izvršiti:

1. učitati stvarnu fakturu iz `najavauvoza/`;
2. pitati agenta za stanje Faktura taba;
3. pretražiti tarifni broj za konkretan proizvod;
4. zatražiti upis zemlje porijekla i potvrditi da draft nije promijenjen prije odobrenja;
5. odbiti prijedlog i potvrditi da nema izmjene;
6. ponoviti i prihvatiti prijedlog;
7. pokrenuti punu automatizaciju i odbiti deklarantsku potvrdu;
8. potvrditi da status nije `COMPLETED` i da naimenovanja nisu kreirana;
9. ponoviti uspješan tok i provjeriti finalnu validaciju;
10. privremeno simulirati pad primarnog providera i potvrditi fallback;
11. pregledati audit log i provjeriti da nema sadržaja fakture ili API ključeva.

## 15. Šta ne raditi

- Ne dozvoliti LLM-u direktno pisanje u draft.
- Ne dodavati novu carinsku logiku u router ili prompt.
- Ne tretirati prompt instrukcije kao jedinu sigurnosnu barijeru.
- Ne uklanjati ljudsku potvrdu za porijeklo, povlastice i PE dokumente.
- Ne pisati novi mehanizam grupiranja naimenovanja.
- Ne pozivati providere direktno.
- Ne blokirati UI thread mrežnim ili DB operacijama.
- Ne pretvarati `chat_intent_handler.py` u veliki refaktor prije testova ponašanja.
- Ne brisati compatibility stubove samo zato što izgledaju duplirano.
- Ne mijenjati `dist_client/` naslijepo.
- Ne commitovati postojeće nepovezane korisničke izmjene.

## 16. Rizici i mitigacije

### Promjena semantike postojećih komandi

Rizik: korisnik je navikao da određeni upisi budu trenutni.  
Mitigacija: read-only komande ostaju trenutne; samo mutacije dobijaju jasnu proposal potvrdu.

### Dupli signal i dvostruko izvršenje

Rizik: Qt signal može ostati povezan ili korisnik može dvaput potvrditi.  
Mitigacija: `operation_id`, atomarno uklanjanje pending akcije i idempotency test.

### Provider razlike u tool-call formatu

Rizik: Groq i Gemini mogu vratiti različite strukture.  
Mitigacija: provider adapter normalizuje rezultat prije Tool Dispatchera.

### Prevelik refaktor

Rizik: razlaganje handlera može promijeniti skrivena follow-up ponašanja.  
Mitigacija: scenario testovi prije pomjeranja funkcija i jedan domen po commitu.

### Distribucija zaostaje za izvorom

Rizik: razvojna verzija radi, Windows klijent ostane na starom kodu.  
Mitigacija: eksplicitna dist matrica i build/verifikacija kao zaseban izlaz.

## 17. Definition of done

Zadatak je završen samo ako su ispunjeni svi uslovi:

- nijedan mutirajući alat ne mijenja draft prije potvrde;
- svi LLM pozivi idu kroz `LLMProvider`;
- aktivni provider redoslijed odgovara `AGENTS.md`;
- pipeline ne nastavlja poslije kritične greške;
- finalni status tačno razlikuje uspjeh, parcijalni rezultat, neuspjeh i otkazivanje;
- svi alati vraćaju strukturisan rezultat sa izvorom;
- ciljane i integracione provjere prolaze;
- puni test suite je pokrenut ili je tačno dokumentovan blocker;
- GitNexus scope je provjeren prije svakog commita;
- odluke `001` i `002` su usklađene sa stvarnim kodom;
- `docs/CONTEXT.md` je ažuriran samo za nove ne-očigledne odluke;
- agent report sadrži impact, izmjene, testove, commitove, rizike i dist status;
- nijedna postojeća nepovezana korisnička izmjena nije ušla u commit.

## 18. Obavezni završni izvještaj implementacionog agenta

Pored standardnih sekcija iz `AGENTS.md`, završni agent report mora eksplicitno navesti:

- tabelu svih alata i njihov konačni `ToolEffect`;
- listu mutacija koje sada zahtijevaju potvrdu;
- konačan provider redoslijed;
- ponašanje svake pipeline faze pri grešci;
- test scenarije koji dokazuju da nema direktne LLM mutacije;
- da li je `dist_client` rebuildan i kako je provjeren;
- preostale legacy module i razlog zašto nisu uklonjeni;
- svako odstupanje od ovog plana i zašto je bilo potrebno.
