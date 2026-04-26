# Kako primijeniti 12 Claude Code principa na `deklarant_pro` bez overengineeringa

## Svrha dokumenta

Ovaj dokument prevodi principe iz analize Claude Code transkripta u **praktičnu, umjerenu arhitekturu** za `deklarant_pro`.

Cilj nije kopirati složenost velikog produkcijskog sistema, nego izvući ono što je stvarno korisno za tvoju aplikaciju:

- stabilniji Agent tab
- bolji recovery nakon prekida rada
- jasnije dozvole za akcije agenta
- bolju preglednost šta agent radi
- manje haosa u tool sloju
- više kontrole bez nepotrebnog multi-agent overengineeringa

---

## Osnovni stav

Za `deklarant_pro` ne treba graditi “mini Claude Code”.

Treba uzeti **princip**, a ne **puni obim implementacije**.

To u praksi znači:

- mali i čist tool registry
- jasno odvojeni conversation state i workflow state
- permission model po nivou rizika
- typed system events u UI-ju
- token budget i context discipline
- 2–3 agent uloge maksimalno
- verifikacija prije mutacija nad podacima

---

## 1. Tool registry with metadata-first design

### Šta princip znači

Agent ne bi smio “znati” alate samo implicitno iz koda.  
Treba imati **centralni registar alata** sa opisom svakog alata prije izvršenja.

### Kako to primijeniti u `deklarant_pro`

Napravi centralni registry, npr. `agent_tools_registry.py`, gdje svaki alat ima:

- `name`
- `description`
- `category`
- `risk_level`
- `input_schema`
- `output_schema`
- `requires_confirmation`
- `allowed_agent_roles`

### Minimalan skup alata

Preporučeni početni alati:

1. `query_active_declaration`
2. `search_regulations`
3. `search_uploaded_documents`
4. `extract_invoice_fields`
5. `extract_transport_fields`
6. `suggest_tariff_candidates`
7. `validate_candidate_data`
8. `apply_confirmed_fields`

### Zašto je ovo korisno

Bez ovoga ćeš brzo završiti u haosu tipa:

- agent ne zna koji alat da koristi
- alati se preklapaju
- teško je uvoditi dozvole
- teško je prikazati korisniku šta se desilo

### Šta ne raditi

Ne graditi ogroman registry od 50+ alata unaprijed.  
Kreni sa malim skupom koji stvarno koristiš.

---

## 2. Permission system i trust tiers

### Šta princip znači

Nisu sve akcije jednako rizične.  
Čitanje propisa nije isto što i upis u deklaraciju.

### Predlog nivoa dozvola za `deklarant_pro`

#### Nivo 1 — Read only
Agent smije:

- čitati aktivnu deklaraciju
- čitati učitane dokumente
- čitati propise
- čitati pomoćne šifrarnike

#### Nivo 2 — Suggest only
Agent smije:

- dati prijedlog vrijednosti
- dati kandidat tarifnog broja
- označiti nedostajuća polja
- sastaviti strukturisani prijedlog

Ne smije ništa upisivati.

#### Nivo 3 — Confirm required
Agent može izvršiti akciju tek nakon korisničke potvrde:

- prenijeti predložene vrijednosti u formu
- ažurirati određena polja
- pokrenuti import koji mijenja radno stanje

#### Nivo 4 — Restricted mutating
Dozvoljeno samo za pažljivo odabrane tokove i uz validaciju:

- unos potvrđenih polja
- kreiranje pomoćnih zapisa
- update radne sesije

#### Nivo 5 — Admin only
Samo za administrativne ili osjetljive radnje:

- brisanje
- masovne izmjene
- reset workflowa
- promjene konfiguracije agenta

### Važno

Ovo ne treba rješavati samo u UI-ju.  
Dozvole moraju postojati i u servisnom sloju.

---

## 3. Session persistence that survives crashes

### Šta princip znači

Ako se aplikacija zatvori, Agent tab ne smije izgubiti sve.

Ali nije dovoljno sačuvati samo chat.

### Šta treba čuvati u sesiji

Predlog strukture `AgentSessionState`:

- `session_id`
- `created_at`
- `updated_at`
- `active_declaration_id`
- `uploaded_document_ids`
- `chat_messages`
- `selected_mode` (`analiza`, `uvezi`, `automatizacija`)
- `token_usage_summary`
- `permission_decisions`
- `tool_history`
- `retrieval_mode_history`
- `current_workflow_id`
- `current_step`
- `pending_confirmations`

### Kada snimati stanje

Ne samo na shutdown.

Snimi nakon svakog važnog događaja:

- upload dokumenta
- završene ekstrakcije
- promjene retrieval moda
- predloga unosa
- potvrde korisnika
- greške ili prekida

### Zašto je bitno

Ako nemaš ovo:

- korisnik gubi tok rada
- agent ne zna gdje je stao
- mogu se duplirati koraci
- teže je debugovati šta se desilo

---

## 4. Workflow state odvojiti od conversation state

### Najvažniji princip iz cijelog skupa

Chat i workflow nisu ista stvar.

#### Conversation state odgovara na:
- šta je korisnik pitao
- šta je agent rekao

#### Workflow state odgovara na:
- koji je aktivni dokument
- da li je ekstrakcija završena
- da li postoji prijedlog za unos
- da li čeka potvrdu
- da li je nešto već upisano
- da li je retry bezbjedan

### Predlog workflow stanja za Agent tab

#### `IDLE`
Nema aktivnog procesa.

#### `DOCUMENT_UPLOADED`
Dokument učitan, ali nije analiziran.

#### `INDEXING`
Radi preprocessing / PageIndex / RAG priprema.

#### `ANALYZING`
Agent vrši analizu dokumenta ili propisa.

#### `PROPOSAL_READY`
Postoji strukturisani prijedlog.

#### `WAITING_USER_CONFIRMATION`
Čeka potvrdu korisnika.

#### `APPLYING`
Prenos potvrđenih podataka u formu ili servis.

#### `COMPLETED`
Workflow završen.

#### `FAILED`
Greška, uz mogućnost retry ili resume.

### Važno pravilo

Svaki workflow korak mora znati:

- da li je idempotentan
- da li se smije ponovo izvršiti
- šta je rezultat koraka
- šta je naredni dozvoljeni korak

---

## 5. Token budget tracking

### Šta princip znači

Agent ne smije trošiti neograničeno.

### Šta pratiti

Po sesiji i po tasku prati:

- input tokene
- output tokene
- ukupan trošak
- broj tool poziva
- veličinu konteksta prije poziva
- retrieval izvor (`db`, `vector`, `pageindex`, `hybrid`)

### Kako to koristiti

Uvedi pragove, na primjer:

- soft warning nakon X tokena
- hard stop nakon Y tokena
- compact conversation poslije Z poruka
- ne dozvoli novu “tešku” analizu bez fresh session ili compaction

### UI ideja

U Agent tabu možeš prikazati:

- “Sesija: 0 aktivnih zadataka”
- plus mali indikator:
  - token usage
  - retrieval mode
  - broj učitanih dokumenata
  - zadnji tool call

To bi bilo korisnije od “black box” agenta.

---

## 6. Structured streaming events

### Šta princip znači

Korisnik ne treba da vidi samo konačan odgovor.

Treba da vidi i šta se dešava u toku rada.

### Predlog event tipova za `deklarant_pro`

- `session_started`
- `document_uploaded`
- `document_indexing_started`
- `document_indexing_finished`
- `retrieval_mode_selected`
- `tool_selected`
- `tool_completed`
- `proposal_generated`
- `validation_warning`
- `confirmation_required`
- `apply_started`
- `apply_completed`
- `workflow_failed`

### Kako to prikazati u UI-ju

Desni panel već ima tabove:

- Agent
- Aktivnosti
- Pitanja

Tab **Aktivnosti** je idealan za sistemske evente.

Na primjer:

- Dokument indeksiran
- Retrieval režim: PageIndex
- Pronađena relevantna sekcija pravilnika
- Confidence: 0.78
- Potrebna potvrda za unos polja

To odmah diže povjerenje korisnika.

---

## 7. System event logging

### Šta princip znači

Pored prikaza događaja korisniku, treba imati i trajni log.

### Šta logovati

- tool selection
- tool input summary
- tool output summary
- permission granted / denied
- retrieval source
- workflow transition
- validation result
- crash reason
- retry action
- user confirmation action

### Zašto je korisno

Ovo ti pomaže za:

- audit
- debugging
- naknadnu analizu grešaka
- poboljšanje prompta i alata
- razumijevanje zašto je agent dao određeni prijedlog

### Šta ne logovati nekontrolisano

Ne čuvaj nepotrebno:

- pune osjetljive podatke ako nisu potrebni
- kompletne dokumente bez potrebe
- suvišan chain-of-thought stil sadržaja

Log treba biti operativan, ne bučan.

---

## 8. Verification na dva nivoa

### Nivo 1 — Verifikacija izlaza agenta
Prije bilo kakve mutacije provjeravaš:

- da li su obavezna polja prisutna
- da li su vrijednosti u očekivanom formatu
- da li postoji izvor za svaku izvedenu tvrdnju
- da li confidence prelazi prag
- da li pravila dozvoljavaju akciju

### Nivo 2 — Verifikacija harness promjena
Kad promijeniš Agent modul, testiraj da li su očuvani guardrails:

- destructive actions i dalje traže potvrdu
- read-only alati ne rade mutacije
- crash resume radi
- invalid retrieval ne ruši sesiju
- token budget stop radi ispravno
- workflow state nije oštećen

### Poenta

Nemoj testirati samo “je li agent dao dobar odgovor”.  
Testiraj i “jesmo li pokvarili samu infrastrukturu agenta”.

---

## 9. Tool pool assembly

### Šta princip znači

Ne treba svaki agent i svaki task da vidi sve alate.

### Kako to primijeniti kod tebe

Formiraj mali tool pool po zadatku.

#### Primjer A — Pitanje o propisu
Dostupni alati:

- `search_regulations`
- `search_uploaded_documents`
- `query_active_declaration`

Nema potrebe za `apply_confirmed_fields`.

#### Primjer B — Ekstrakcija iz fakture
Dostupni alati:

- `extract_invoice_fields`
- `search_uploaded_documents`
- `validate_candidate_data`

#### Primjer C — Prenos potvrđenih podataka
Dostupni alati:

- `validate_candidate_data`
- `apply_confirmed_fields`

### Dobit

- manje zabune za agenta
- manje rizika
- manji kontekst
- bolji performans

---

## 10. Transcript compaction

### Šta princip znači

Duge sesije ne smiju nekontrolisano rasti.

### Šta raditi

Poslije određenog broja poruka:

- sačuvaj rezime sesije
- zadrži posljednje relevantne poruke
- sačuvaj workflow state odvojeno
- odbaci nepotrebni razgovorni šum

### Šta ne smiješ izgubiti

- početni cilj zadatka
- aktivni workflow status
- pending confirmation
- posljednje validne prijedloge
- ključne sistemske evente

### Praktično pravilo

Za tvoj slučaj:

- chat compact nakon 12–20 poruka
- workflow state nikad ne smije zavisiti samo od chata

---

## 11. Permission audit trail

### Šta princip znači

Dozvola nije samo `True/False`.

Treba znati:

- ko je tražio akciju
- koji agent / alat
- nad čim
- kada
- da li je korisnik potvrdio
- zašto je odobreno ili odbijeno

### Minimalni zapis

- `timestamp`
- `session_id`
- `workflow_id`
- `tool_name`
- `requested_action`
- `risk_level`
- `decision`
- `decision_source` (`user`, `policy`, `system`)
- `reason`

Ovo je jako korisno za osjetljive mutacije.

---

## 12. Agent type system

### Ne pretjerivati

Ne treba ti 6 ugrađenih agent tipova.

Za `deklarant_pro` je dosta 3.

### 1. Retrieval Agent
Odgovoran za:

- pretragu propisa
- pretragu uploadovanih dokumenata
- dohvat konteksta iz baze

Ne radi mutacije.

### 2. Proposal Agent
Odgovoran za:

- sastavljanje strukturisanog prijedloga
- mapiranje ekstraktovanih podataka
- objašnjenje šta bi moglo ići u deklaraciju

Ne radi direktan upis bez daljih provjera.

### 3. Verification Agent
Odgovoran za:

- provjeru prijedloga
- traženje nedostajućih elemenata
- označavanje rizika i konflikata
- pripremu finalnog “safe to apply” signala

### Zašto je ovo dovoljno

Jer ti ne praviš univerzalni coding agent.  
Praviš domenski asistirani workflow agent.

Previše uloga prerano bi ti samo zakomplikovalo održavanje.

---

## Preporučena minimalna arhitektura

```text
AgentTab
 ├── AgentSessionManager
 ├── WorkflowStateManager
 ├── ToolRegistry
 ├── PermissionService
 ├── RetrievalRouter
 │    ├── DatabaseRetriever
 │    ├── VectorRagRetriever
 │    └── PageIndexRetriever
 ├── ProposalService
 ├── VerificationService
 ├── EventStreamService
 └── ApplyService
```

---

## Šta implementirati prvo

### Faza 1 — Stabilnost i preglednost
Prvo uradi:

- `ToolRegistry`
- `PermissionService`
- `AgentSessionManager`
- `WorkflowStateManager`
- `EventStreamService`

Bez toga nemaš zdravu osnovu.

### Faza 2 — Retrieval disciplina
Zatim uvedi:

- `RetrievalRouter`
- PageIndex samo za propise i strukturisane PDF-ove
- minimal context delivery

### Faza 3 — Proposal + Verification
Tek onda:

- strukturisani prijedlog
- verifikacija
- confirm-required apply tokovi

### Faza 4 — Napredniji automation
Na kraju:

- djelimična automatizacija
- hibridni retrieval
- složeniji workflowi

---

## Šta ne raditi

Nemoj odmah:

- uvoditi swarm agente
- praviti koordinatore i sub-agent orkestratore
- praviti ogroman plugin marketplace
- spajati workflow state u chat transcript
- dati agentu previše mutacionih ovlaštenja
- gurati sve dokumente i sav kontekst svakom tasku

To su tipične zamke overengineeringa.

---

## Moj konačni prijedlog

Ako ovo svedem na jednu rečenicu:

**Za `deklarant_pro` uzmi iz Claude Code pristupa disciplinu sistema, a ne njegovu veličinu.**

Najveća vrijednost za tebe nije da imitiraš veliki agentni framework, nego da uvedeš:

- jasne alate
- jasne dozvole
- jasno stanje workflowa
- jasan event trag
- jasnu verifikaciju prije mutacija

To je dovoljno da Agent tab prestane biti “chat sa alatima” i postane stvarno kontrolisan radni modul.

---

## Kratka checklista

- [ ] Imam centralni registry alata
- [ ] Svaki alat ima nivo rizika
- [ ] Session state i workflow state su odvojeni
- [ ] Postoje sistemski eventi vidljivi korisniku
- [ ] Postoji trajni event log
- [ ] Imam token budget po sesiji / tasku
- [ ] Tool pool se sužava po zadatku
- [ ] Dugi transcript se kompaktuje
- [ ] Sve mutacije traže verifikaciju
- [ ] Agent role su ograničene i jasne
