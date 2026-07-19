# Plan unapređenja agentskog moda rada

**Datum:** 2026-07-19  
**Status:** Spremno za implementaciju  
**Namjena:** Handoff plan za agenta koji će realizovati unapređenja agentskog moda u Deklarant Pro aplikaciji  
**Polazna analiza:** pregled aktivnog toka u `gui/tabs/agent/`, `services/agent/` i ciljnih offline testova  
**Dograđeno:** 2026-07-19 (Claude Sonnet 5) — dodana obavezna veza sa Decision Service migracijom
(`agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md`, završena dan prije ovog plana) i
potvrđeni nalazi protiv stvarnog koda — vidi §5.6, §6.6, §7.7, §10.4 i §19.

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
- `DeclarationDecisionService` (`services/decision/declaration_decision_service.py`) je, od 2026-07-18, jedini
  servis koji smije primjenjivati izvedene odluke (tarifa, zemlja porijekla, povlastica) u `InvoiceLine.decision_state`.
  Faza A ovog plana **mora graditi na tom servisu** (pozivati `evaluate_line`/`apply_candidate`/`confirm_manual_value`
  iz `services/decision/integration.py`), ne smije uvoditi drugi, paralelan mehanizam potvrde za ista polja — vidi §5.6.
- Politike po polju (`services/decision/decision_policy.py`) — redoslijed izvora, fuzzy threshold 0.92, zabrana
  automatske povlastice — ostaju važeće i za agent-chat tokove, ne samo za Faktura tab.

## 3. Obavezna priprema prije izmjena

Agent koji implementira plan mora prije kodiranja:

1. pročitati `AGENTS.md` i `docs/CONTEXT.md`;
2. pročitati:
   - `docs/decisions/001-tool-use-refactoring.md`;
   - `docs/decisions/002-tool-dispatcher-integration.md`;
   - `docs/sections/agent-origin-query-routing.md`;
   - `agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md` (Decision Service — kanonski model odluke);
   - `agent_reports/2026-07-18_zavrsni-jedan-izvor-istine.md` (šta je od tog plana stvarno završeno, šta je xfail);
   - `services/decision/decision_policy.py` i `services/decision/integration.py` (kratak pregled javnog API-ja);
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

**Ovo NIJE nova sigurnosna arhitektura od nule.** Za tarifu, zemlju porijekla i povlasticu, `DeclarationDecisionService`
već postoji i već je jedini dozvoljeni upisni put (Decision Service migracija, 2026-07-18). `ToolPolicy`/`MUTATE`
klasifikacija iz ove faze ne smije duplirano implementirati potvrdu/upis za ta tri polja — mora ih delegirati na
`apply_candidate()`/`confirm_manual_value()` iz `services/decision/integration.py`. Novi mehanizam potvrde (proposal
kartica, `operation_id`, idempotencija) je i dalje potreban za DRUGA polja koja Decision Service ne pokriva
(npr. procedura, oznake, pakovanje, valuta, napomena — vidi `NaimenovanjaIntentService._resolve_kolona`), kao i za
sam UI sloj potvrde iznad Decision Service-a. Vidi §5.6 za tačan spisak koje putanje već prolaze kroz Decision
Service, a koje ga trenutno zaobilaze.

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
- Za `ToolEffect.MUTATE` nad tarifom/zemljom porijekla/povlasticom: registry mora mapirati direktno na
  `services/decision/integration.py` funkcije (`sync_decision_state_after_manual_edit` i srodne), ne na novu
  implementaciju upisa — vidi §5.6 za postojeće pozivaoce koje treba zadržati.

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

### 5.6 Potvrđeni nalazi (2026-07-19, provjereno protiv koda prije handoff-a)

Sljedeće je direktno pročitano u kodu, ne pretpostavka — implementacioni agent može krenuti od ovoga umjesto
ponovnog otkrivanja:

- **Gap koji Faza A stvarno mora zatvoriti**: `gui/tabs/agent/services/chat_intent_handler.py:1210` (Tool Use put,
  unutar `_execute_tool`, grana `upisi_u_kolonu`) i `chat_intent_handler.py:1328` (regex fallback put, unutar
  `_handle_message_regex_fallback`) oba pozivaju `ctrl.naim_intent_svc.execute(atribut, vrijednost, tab)` /
  `svc.execute(...)` **direktno, bez ijedne potvrde korisnika**. `NaimenovanjaIntentService.execute()` (pozvano iz
  `agent_controller.py:822`, `_upisi_u_kolonu`) odmah piše u draft. Ovo je stvaran, danas prisutan bug — poruka
  "upiši zemlju porijekla RS" zaista mijenja draft prije bilo kakve potvrde.
- **Putanje koje VEĆ prolaze kroz Decision Service — ne duplirati, samo zadržati/iskoristiti**:
  `chat_intent_handler.py:1969` (`_on_accepted` tok) poziva
  `sync_decision_state_after_autofill(changed_lines, action_type="dialog_confirmed")`;
  `chat_intent_handler.py:2139-2141` (`_apply_single_tariff_to_line`) poziva
  `sync_decision_state_after_manual_edit(line, DecisionField.TARIFF, code)`. Nova `ToolPolicy`/mutation-gate
  implementacija ne smije zamijeniti ove pozive niti obrisati postojeću sinhronizaciju — treba ih tretirati kao
  referentni obrazac za ostale mutirajuće alate nad istim poljima.
- Zaključak: `upisi_u_kolonu` grana za tarifu/zemlju/povlasticu treba biti **preusmjerena** da koristi isti
  `services/decision/integration.py` put kao gornje dvije putanje, umjesto da ostane direktan poziv
  `NaimenovanjaIntentService.execute()`. Za ne-decision kolone (procedura, oznake, pakovanje, valuta, napomena),
  novi `ToolPolicy`/proposal mehanizam iz ove faze je i dalje potreban jer Decision Service te kolone ne pokriva.

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

### 6.6 Potvrđeni nalazi (2026-07-19)

Direktan DeepSeek klijent **i dalje postoji** u `services/agent/chat/tool_dispatcher.py` — ovo nije zastarjela
primjedba iz starije dokumentacije, potvrđeno čitanjem trenutnog koda:

- Linija 172: `if not provider.has_deepseek():` — provjera postojanja DeepSeek ključa unutar dispatchera.
- Linije 181-182: `OpenAI(api_key=provider.deepseek_key, base_url="https://api.deepseek.com")`.
- Linija 191: `model="deepseek-chat"`.

Ovo je direktno kršenje AGENTS.md pravila "Pozivati Groq/Gemini direktno bez `LLMProvider` [je zabranjeno]" i
"DeepSeek isključen". Napomena: ranija sesijska memorija (`2026-06-12_faza8-llm-provider-fallback.md`) navodi da je
DeepSeek "naknadno isključen" — ta izmjena je očito pokrila samo glavni `LLMProvider` fallback lanac
(`gui/tabs/agent/widgets/llm_provider.py`), ne i ovaj zaseban put u `tool_dispatcher.py`. Faza B mora obuhvatiti oba.

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

### 7.7 Potvrđeni nalazi (2026-07-19)

`_puna_auto_pipeline()` (`gui/tabs/agent/services/import_pipeline_service.py:203-281`) je direktno pročitan —
problem je ozbiljniji nego što zvuči apstraktno opisan u §7.1:

- Korak 1 (izračun masa, linije ~208-213), korak 2 (auto-popuna tarifa, ~220-225), korak 3 (validacija, ~232-237) i
  korak 5 (kreiranje naimenovanja, ~265-270) svi imaju identičan obrazac:
  `try: ... except Exception as e: chat.add_activity(f"⚠️ Greška ...: {e}")` — bez `return`, bez ikakvog praćenja
  ishoda. Pipeline nastavlja na sljedeći korak čak i ako je servis bacio izuzetak.
- Korak 4 (potvrda deklaranta, `QMessageBox.question`) je jedini koji ISPRAVNO prekida (`return`) ako korisnik
  odgovori Ne — dobar postojeći obrazac koji Faza C treba generalizovati na ostale korake, ne izmišljati nov.
- Linija ~276: poruka `"🎉 <b>Puna automatizacija završena!</b>"` se ispisuje **bezuslovno**, na kraju funkcije, bez
  provjere da li je ijedan od koraka 1/2/3/5 zapravo uspio. Praktična posljedica: ako izračun masa (korak 1) baci
  izuzetak, pipeline i dalje "pokuša" auto-popunu, validaciju i kreiranje naimenovanja nad potencijalno netačnim
  podacima, i na kraju korisniku tvrdi da je "puna automatizacija završena" — bez obzira na stvarni ishod bilo kog
  koraka. Ovo je aktivan, ne hipotetički rizik za carinski alat.

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

### 10.4 Potvrđeni nalazi (2026-07-19)

- `gui/tabs/agent/services/chat_intent_handler.py` ima **2621 liniju** (izmjereno `wc -l`) — ocjena "prevelik" iz
  §10 nije preuveličana.
- Za poređenje: `gui/tabs/agent/agent_controller.py` ima danas **845 linija** — ranije (`AGENT_IMPROVEMENT_PLAN.md`,
  2026-04-20) je imao 2000+ i bio meta sličnog refaktora. Taj refaktor je uspio (logika je izvučena iz controllera),
  ali se bloat preselio u `chat_intent_handler.py`, koji je sad meta OVE faze. Zaključak za implementacionog agenta:
  samo izdvajanje modula nije dovoljno bez trajne discipline (jasne granice odgovornosti po handleru, §10.1) —
  inače se isti obrazac ponovi za 3 mjeseca u novom fajlu. Vidi §19 za kompletnu vezu sa starijim planom.

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
- Ne graditi novi paralelni mutation-writer za tarifu/zemlju porijekla/povlasticu — te tri politike već ima
  `services/decision/` (vidi §2, §5.6); novi `ToolPolicy` mora ih pozivati, ne duplirati.

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
- nijedna postojeća nepovezana korisnička izmjena nije ušla u commit;
- mutacije nad tarifom/zemljom porijekla/povlasticom prolaze kroz `DeclarationDecisionService` — nema novog
  paralelnog upisnog puta za ta polja (vidi §2, §5.6).

## 18. Obavezni završni izvještaj implementacionog agenta

Pored standardnih sekcija iz `AGENTS.md`, završni agent report mora eksplicitno navesti:

- tabelu svih alata i njihov konačni `ToolEffect`;
- listu mutacija koje sada zahtijevaju potvrdu;
- konačan provider redoslijed;
- ponašanje svake pipeline faze pri grešci;
- test scenarije koji dokazuju da nema direktne LLM mutacije;
- da li je `dist_client` rebuildan i kako je provjeren;
- preostale legacy module i razlog zašto nisu uklonjeni;
- svako odstupanje od ovog plana i zašto je bilo potrebno;
- da li su mutacije nad tarifom/zemljom porijekla/povlasticom prošle kroz `DeclarationDecisionService`, ili je
  napravljen paralelan upisni put i zašto (mora biti obrazloženo, ne samo konstatovano).

## 19. Napomena o povezanim planovima i brojanju faza

Postoje još dva dokumenta u ovom repozitoriju sa nezavisnom numeracijom "Faza" koja se **ne odnose** na ovaj plan
— u commit porukama i diskusiji eksplicitno navesti "Faza A/B/C/D/E/F (agent mode improvement plan, 2026-07-19)"
da se izbjegne zabuna:

- `AGENT_IMPROVEMENT_PLAN.md` (korijen repoa, 2026-04-20) — koristi "Faza 1/2/3" (Kratkoročne/Srednjoročne/
  Dugoročne). Istorijski plan; provjereno 2026-07-19 da je najveći dio već riješen (`agent_controller.py` sada
  ima 845 linija, ne 2000+; PDF+Excel duplikat riješen `consumed_paths` pravilom iz `AGENTS.md`). Nije potrebno
  čitati prije implementacije ovog plana, ali ne brisati bez provjere da li još nešto od preostalih stavki važi.
- `docs/decisions/002-tool-dispatcher-integration.md` — pominje sopstvenu "Fazu 3" (brisanje regex sloja nakon
  2-3 nedjelje stabilnosti Tool Use-a). Ovo JE relevantno za §10 (Faza F) ovog plana — provjeriti pri implementaciji
  da li je taj uslov (regex sloj se briše tek kad telemetrija potvrdi da nije potreban) već ispunjen ili i dalje
  otvoren, i uskladiti sa §10.2 pravilom "Ne brisati regex fallback dok telemetrija i testovi ne potvrde".

Treći, aktivan izvor sa svojom fazama je Decision Service migracija (`agent_tasks/2026-07-18_jedan-izvor-istine-
odluke-deklaracije.md`, Faze 0-6) — ta numeracija je ZAVRŠENA i odnosi se na drugi zadatak, ali njen kod
(`services/decision/`) je direktna zavisnost ovog plana (vidi §2, §5.1, §5.6). Ne miješati "Fazu 0-6" (decision
service, gotovo) sa "Fazom A-F" (ovaj plan, u toku) u komunikaciji sa korisnikom ili u commit porukama.
