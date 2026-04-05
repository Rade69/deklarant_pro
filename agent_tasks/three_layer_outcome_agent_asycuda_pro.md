# Kako primijeniti three-layer outcome agent arhitekturu na `asycuda_pro`

## Svrha dokumenta

Ovaj dokument prevodi ideju **three-layer outcome agent** arhitekture u praktičan model za `asycuda_pro`.

Cilj nije praviti generički “AI agent za sve”, nego stabilan i kontrolisan agentni sloj koji:

- koristi tvoju bazu podataka
- koristi postojeći RAG
- može koristiti PageIndex za strukturisane dokumente
- proizvodi editabilne i provjerljive izlaze
- ne preskače poslovna pravila aplikacije
- postaje korisniji kroz vrijeme

---

## Osnovna ideja

Outcome agent nije samo chat.

Da bi agent u `asycuda_pro` radio ozbiljan posao, trebaš tri sloja:

1. **Knowledge Store**  
   mjesto gdje žive podaci, dokumenti, znanje i kontekst

2. **Agent Recipes**  
   unaprijed definisani tokovi rada za konkretne domenske zadatke

3. **Scheduling / Execution Loop**  
   sloj koji izvršava, prati, nastavlja i po potrebi ponavlja radne tokove

Ova tri sloja zajedno daju:

- memoriju
- editabilne artefakte
- kumulativni kontekst

To su tri stvari bez kojih “outcome agent” ostaje samo demo.

---

# 1. Layer: Knowledge Store

## Šta je to u `asycuda_pro`

Knowledge Store nije samo baza podataka.

U tvom slučaju to treba biti objedinjeni sloj koji sadrži:

- relacione podatke iz aplikacije
- aktivne i historijske deklaracije
- korisnički učitane dokumente
- propise i pravilnike
- interne procedure i uputstva
- PageIndex / RAG indekse
- pomoćne šifrarnike
- rezultate ranijih analiza

Drugim riječima:  
to je memorijski i retrieval sloj agenta.

## Šta sve ulazi unutra

### A. Poslovni podaci
- deklaracije
- stavke
- klijenti
- šifarnici
- historija unosa
- statusi i workflow zapisi

### B. Dokumenti
- fakture
- transportni dokumenti
- certifikati
- packing liste
- drugi prilozi

### C. Regulativa
- zakoni
- pravilnici
- carinska uputstva
- pomoćni dokumenti
- interne procedure rada

### D. Agent memorija
- prethodne analize
- raniji prijedlozi
- potvrđene odluke
- session summaries
- workflow state snapshotovi

---

## Kako ga organizovati

Ne pokušavaj sve gurati u jedan mehanizam.

Napraviti razdvajanje na 4 retrieval zone:

### 1. `db_context`
Za:
- aktivnu deklaraciju
- historijske podatke
- prethodne unose
- šifrarnike
- statusne informacije

### 2. `vector_rag_context`
Za:
- manje strukturisane dokumente
- brzu semantičku pretragu
- multi-document lookup
- pomoćni knowledge sloj

### 3. `pageindex_context`
Za:
- propise
- pravilnike
- velike PDF-ove
- dokumente sa jasnom hijerarhijom
- sekcijsko i logičko pretraživanje

### 4. `session_memory_context`
Za:
- trenutni tok rada
- šta je agent već uradio
- koji prijedlog postoji
- šta čeka potvrdu
- korisnikove korekcije u toj sesiji

---

## Zašto je ovo važno

Ako sve tretiraš kao jedan isti “RAG”, izgubićeš razliku između:

- strukturisanih poslovnih podataka
- neurednih dokumenata
- propisa
- aktivnog konteksta sesije

To vodi do toga da agent:
- vuče previše konteksta
- daje mutne odgovore
- ne zna šta je izvor istine
- teško objašnjava zašto je nešto predložio

---

# 2. Layer: Agent Recipes

## Šta su recipes u tvom slučaju

Recipes nisu promptovi.  
Recipes nisu ni “samo skillovi”.

Recipes su **domenski tokovi rada** koje agent može pokretati nad postojećim izvorima i alatima.

Drugim riječima:
to su unaprijed definisani operativni obrasci.

## Zašto su ti potrebni

Bez recipes sloja završićeš sa jednim agentom koji:
- sve pokušava rješavati istim načinom
- miješa objašnjenje, ekstrakciju i mutaciju
- teško se testira
- teško se kontroliše
- teško postaje pouzdan

Recipes uvode disciplinu.

---

## Preporučeni početni recipes za `asycuda_pro`

## 1. Recipe: Analiza učitanog dokumenta
Cilj:
- pročitati dokument
- odrediti tip dokumenta
- pronaći ključne sekcije
- izdvojiti osnovne entitete
- pripremiti pregled za korisnika

Ulazi:
- uploadovani dokument
- metadata o dokumentu
- aktivni kontekst deklaracije

Izlazi:
- tip dokumenta
- pronađena ključna polja
- confidence
- source references
- preporuka retrieval moda

---

## 2. Recipe: Pomoć za rubriku / polje
Cilj:
- objasniti korisniku šta ide u polje
- naći relevantno pravilo
- povezati pravilo s aktivnim slučajem

Ulazi:
- aktivna rubrika
- aktivna deklaracija
- propisi i interne procedure

Izlazi:
- objašnjenje
- relevantni član / tačka / sekcija
- upozorenja i izuzeci
- eventualni kandidat prijedloga

---

## 3. Recipe: Ekstrakcija iz fakture ili priloga
Cilj:
- izvući ciljane podatke iz dokumenta
- vratiti ih kao strukturisani artefakt

Ulazi:
- PDF ili drugi prilog
- schema traženih polja

Izlazi:
- lista polja
- vrijednosti
- confidence
- source trace
- flag za ručnu provjeru

---

## 4. Recipe: Prijedlog unosa u deklaraciju
Cilj:
- spojiti:
  - aktivni dokument
  - podatke iz baze
  - pravila
  - ranije potvrđene obrasce
- i dati prijedlog šta bi moglo ući u deklaraciju

Ulazi:
- aktivna deklaracija
- dokumenti
- retrieval rezultati
- poslovna pravila

Izlazi:
- strukturisani prijedlog
- lista nesigurnih polja
- objašnjenje po polju
- šta traži potvrdu

---

## 5. Recipe: Provjera usklađenosti
Cilj:
- uporediti dokument, deklaraciju i pravila
- označiti nedostatke i rizike

Ulazi:
- aktivna deklaracija
- dokumenti
- propisi
- interne validacije

Izlazi:
- lista grešaka
- lista upozorenja
- nedostajući dokumenti/podaci
- preporučeni sljedeći korak

---

## 6. Recipe: Confirmed apply
Cilj:
- prenijeti samo potvrđene i validirane podatke
- bez preskakanja servisnog sloja

Ulazi:
- potvrđeni prijedlog
- validation rezultat

Izlazi:
- mutacija kroz servisni sloj
- log promjene
- status workflowa

---

## Važna granica

Recipe može:
- čitati
- analizirati
- predlagati
- strukturisati
- objašnjavati

Recipe ne smije:
- zaobići business validation
- direktno pisati u bazu mimo servisa
- donositi konačne pravno osjetljive odluke bez guardrails

---

# 3. Layer: Scheduling / Execution Loop

## Šta je to

To je sloj koji ne govori “šta agent zna”, nego:

- kada nešto pokreće
- kojim redom
- kako prati status
- kako nastavlja nakon prekida
- kako radi retry
- kako zatvara workflow

U praksi, to je ono što outcome agenta pretvara iz chata u stvarni operativni sistem.

---

## Šta ti treba odmah, a šta kasnije

Ne trebaš odmah složeni scheduler.

Ali trebaš makar **workflow execution loop** unutar Agent taba.

### Minimalni execution loop treba da zna:
- koji recipe je pokrenut
- nad kojim entitetom / dokumentom
- u kojem je stanju
- da li čeka korisnika
- da li je pao
- da li smije retry
- da li je završen

---

## Predlog workflow stanja

- `IDLE`
- `QUEUED`
- `RUNNING`
- `WAITING_FOR_USER`
- `WAITING_FOR_EXTERNAL_RESULT`
- `READY_TO_APPLY`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

---

## Šta scheduler / execution loop radi u praksi

### Primjer 1: Analiza dokumenta
1. korisnik uploaduje dokument
2. workflow ulazi u `QUEUED`
3. preprocessing i indexing
4. ide u `RUNNING`
5. rezultat analize se generiše
6. artefakt ide u UI
7. workflow postaje `COMPLETED`

### Primjer 2: Prijedlog unosa
1. korisnik traži prijedlog
2. retrieval router vuče potrebni kontekst
3. proposal recipe radi
4. generiše artefakt
5. workflow ide u `WAITING_FOR_USER`
6. korisnik potvrdi ili odbije
7. tek onda `READY_TO_APPLY` / `COMPLETED`

### Primjer 3: Greška ili prekid
1. workflow padne tokom analize
2. session i workflow state ostaju sačuvani
3. korisnik može `Resume`
4. scheduler nastavlja od zadnje bezbjedne tačke

---

# Kako ova tri sloja rade zajedno

## Primjer: korisnik pita za rubriku 44

### Layer 1 — Knowledge Store
Agent uzima:
- aktivnu deklaraciju iz baze
- propise iz PageIndex sloja
- eventualno interne procedure

### Layer 2 — Agent Recipe
Pokreće se recipe:
- `field_help_recipe`

Recipe:
- prepoznaje kontekst
- nalazi relevantna pravila
- sklapa objašnjenje
- priprema kandidat prijedloga

### Layer 3 — Execution Loop
Sistem:
- prati korake
- loguje retrieval mode
- prikazuje sistemske evente
- čuva session stanje

Rezultat:
- korisnik dobija objašnjenje
- vidi izvor
- može odlučiti hoće li nešto primijeniti

---

## Primjer: korisnik uploaduje fakturu

### Layer 1 — Knowledge Store
Dokument ide u:
- document store
- text extraction
- eventualno vector ili PageIndex indeks

### Layer 2 — Agent Recipe
Pokreće se:
- `invoice_extraction_recipe`

Recipe vraća:
- broj fakture
- datum
- valuta
- incoterms
- iznose
- confidence i source trace

### Layer 3 — Execution Loop
Sistem:
- prikazuje napredak
- čuva rezultat
- nudi korisniku pregled i potvrdu
- nakon potvrde omogućava apply recipe

---

# Kako to vezati za tvoj postojeći Agent tab

Na osnovu onoga što već imaš, ne trebaš mijenjati koncept taba.

Trebaš ojačati unutrašnju arhitekturu.

## Postojeći UI elementi već odgovaraju modelu

### Lijevi dio
- upload dokumenata
- izbor moda rada
- status obrade

### Desni dio
- Agent
- Aktivnosti
- Pitanja

To je već gotovo prirodno mapiranje za three-layer model.

---

## Kako ga preslikati u UI

## Tab “Agent”
Prikazuje:
- glavni rezultat recipes
- objašnjenje
- strukturisani artefakt
- preporuku ili prijedlog

## Tab “Aktivnosti”
Prikazuje:
- execution loop događaje
- indexing start/finish
- retrieval mode
- odabrani alati
- čekanje potvrde
- validation warninge
- greške i retry status

## Tab “Pitanja”
Prikazuje:
- follow-up pitanja korisniku
- nedostajuće informacije
- potvrde koje agent traži

---

# Ključna tri svojstva koja moraš dobiti

## 1. Memorija
To znači:
- session state
- workflow state
- istorija potvrđenih prijedloga
- knowledge store koji raste

Bez ovoga agent stalno počinje iznova.

## 2. Editabilni artefakti
To znači:
- rezultat nije samo chat poruka
- rezultat je nešto što korisnik može:
  - pregledati
  - izmijeniti
  - potvrditi
  - odbiti

Primjeri:
- candidate field map
- compliance checklist
- extraction summary
- proposal card

## 3. Compound context
To znači:
- deseti sličan task je lakši od prvog
- recipes postaju bolji
- retrieval postaje precizniji
- historija potvrda postaje korisna
- knowledge store raste kontrolisano

---

# Šta ne treba raditi

## 1. Nemoj praviti jednog “super agenta”
To zvuči moćno, ali se loše testira i loše održava.

## 2. Nemoj miješati sve tipove memorije
- poslovni podaci
- dokumentni retrieval
- session state
- workflow state  
to nisu iste stvari

## 3. Nemoj recipe miješati sa servisima
Recipe predlaže i orkestrira.  
Servis potvrđeno izvršava.

## 4. Nemoj pokušati odmah puni scheduler
Za sada ti treba workflow loop unutar aplikacije, ne distribuirani orchestration sistem.

## 5. Nemoj outcome agent tretirati kao zamjenu za validatore
Outcome agent treba da bude:
- pametni pomoćnik
- navigator
- predlagač
- analitičar

ne:
- izvor konačne istine mimo poslovne logike

---

# Preporučena minimalna arhitektura

```text
AgentTab
 ├── KnowledgeStoreFacade
 │    ├── DatabaseContextProvider
 │    ├── VectorRagProvider
 │    ├── PageIndexProvider
 │    └── SessionMemoryProvider
 │
 ├── RecipeRegistry
 │    ├── DocumentAnalysisRecipe
 │    ├── FieldHelpRecipe
 │    ├── InvoiceExtractionRecipe
 │    ├── ProposalRecipe
 │    ├── ComplianceCheckRecipe
 │    └── ConfirmedApplyRecipe
 │
 ├── ExecutionLoopManager
 │    ├── WorkflowStateManager
 │    ├── EventStreamManager
 │    ├── RetryManager
 │    └── ConfirmationManager
 │
 ├── VerificationService
 ├── PermissionService
 └── ApplyService
```

---

# Faze implementacije

## Faza 1 — Knowledge Store disciplina
Prvo uvedi jasno razdvajanje na:

- DB kontekst
- vector RAG kontekst
- PageIndex kontekst
- session memory kontekst

Bez toga three-layer model neće imati smisla.

## Faza 2 — Recipes
Zatim uvedi 3 osnovna recipes:

- analiza dokumenta
- pomoć za rubriku
- prijedlog unosa

## Faza 3 — Execution Loop
Dodaj:

- workflow state
- session persistence
- event stream
- confirmation handling

## Faza 4 — Editabilni artefakti
Svaki recipe mora vraćati izlaz koji korisnik može pregledati i potvrditi.

## Faza 5 — Compound context
Tek tada uvodi:
- reuse prethodnih potvrda
- bolji historical guidance
- recipe refinement
- pametnije retrieval routing

---

# Moj konkretan prijedlog za `asycuda_pro`

Ako ovo svedem na vrlo praktičan zaključak:

## Knowledge Store
Neka bude mjesto gdje agent nalazi istinu i kontekst.

## Recipes
Neka budu domenski predefinisani načini rada.

## Execution Loop
Neka bude kontrolisani tok koji pretvara agenta iz chata u stvarni radni modul.

To je pravi put za tvoj projekat.

Ne treba ti hype “outcome agent” priča.  
Treba ti:

- dobra memorija
- dobar retrieval
- jasan recipe sloj
- jasan execution loop
- editabilni rezultati
- potvrda prije mutacija

To je dovoljno da tvoj Agent tab postane ozbiljan alat, a ne samo AI dodatak.

---

# Kratka checklista

- [ ] Imam knowledge store podijeljen na jasne retrieval zone
- [ ] Imam recipes za konkretne domenske zadatke
- [ ] Imam workflow execution loop
- [ ] Session state i workflow state su odvojeni
- [ ] Agent vraća editabilne artefakte
- [ ] Korisnik može potvrditi ili odbiti prijedlog
- [ ] Context se kumulira kroz vrijeme
- [ ] PageIndex koristim samo gdje ima smisla
- [ ] Poslovna logika ostaje u servisima i validatorima
- [ ] Agent nije zamjena za jezgro aplikacije nego kontrolisani radni sloj
