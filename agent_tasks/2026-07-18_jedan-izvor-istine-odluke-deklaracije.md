# Agent Task - Jedan izvor istine za odluke deklaracije

**Datum:** 2026-07-18  
**Kreirao:** Codex (nadzorni/verifikacioni agent)  
**Executor:** Pi agent  
**Reviewer:** Codex  
**Status:** CEKA IMPLEMENTACIJU  
**Nivo dozvole:** lokalni commit po fazi, bez push-a i bez spajanja prije Codex verifikacije

---

## 1. Problem koji rjesavamo

Formiranje deklaracije trenutno koristi vise djelimicno preklopljenih puteva:

- parseri upisuju cinjenice iz fakture i packing liste u `InvoiceLine`
- `TariffMappingService` pretrazuje lokalna mapiranja i istoriju
- `AutoFillService` ima sopstveni tok popunjavanja tarifa i zemlje
- Agent "puna automatizacija" poziva Faktura UI metode
- istorijska validacija koristi `Evidence` i `TariffDecision`
- validacija ponovo tumaci trenutno stanje drafta
- kreiranje naimenovanja izravno kopira vrijednosti iz `InvoiceLine`
- XML exporter izvozi trenutno stanje, bez jedinstvenog dokaznog traga

Posljedica je da ista stavka moze dobiti drugaciji rezultat zavisno od toga da li je
obradjena rucno u Faktura tabu, kroz Agent tab, kroz Validaciju ili kroz istorijski
prijedlog. Korisnik ne moze uvijek jasno razlikovati:

1. sta je procitano iz dokumenta
2. sta je samo prijedlog baze znanja
3. sta je deklarant potvrdio
4. sta je stvarno primijenjeno u deklaraciji

Ovaj zadatak uvodi **jedan izvor istine za odluke**, ali ne jednu novu bazu podataka.
Postojece baze, XML istorija, parseri i tarifni sifrarnici ostaju izvori dokaza.
Jedan servis postaje jedino mjesto koje te dokaze rangira, donosi status odluke i
dozvoljava upis izvedenih vrijednosti u aktivni `DeclarationDraft`.

---

## 2. Glavni cilj

Uvesti kanonski tok:

```text
Dokumenti / baze / istorija / korisnik
                  |
                  v
          kandidati + Evidence
                  |
                  v
      DeclarationDecisionService
       |         |            |
       |         |            +--> konflikt / unknown
       |         +---------------> ceka potvrdu
       +-------------------------> potvrdjena i primijenjena odluka
                  |
                  v
          DeclarationDraft
                  |
        +---------+----------+
        |         |          |
     Faktura   Validacija  Naimenovanja
                              |
                           XML export
```

Nakon migracije:

- UI ne odlucuje poslovna pravila
- Agent ne koristi poseban put za iste odluke
- Validacija ne mijenja podatke
- kreiranje naimenovanja ne pogadja sta je potvrdeno
- XML exporter ne pretrazuje bazu znanja i ne popravlja deklaraciju u letu
- svaki primijenjeni izvedeni podatak ima izvor, razlog i status potvrde

---

## 3. Najvaznija poslovna odluka

Treba strogo razdvojiti **kvalitet dokaza** od **dozvole za primjenu**.

Postojeci `Evidence` govori koliko je izvor jak. To nije isto sto i potvrda deklaranta.
Na primjer, parser moze pouzdano detektovati PE2 izjavu u dokumentu, ali parser ne moze
sam potvrditi da je izjava pravno primjenjiva na konkretnu robu.

Zato nova odluka mora imati najmanje ova dva nezavisna podatka:

- `evidence`: odakle kandidat dolazi i koliko je pouzdan
- `status`: da li je kandidat samo predlozen, potvrdjen, odbijen ili u konfliktu

Za povlasticu vazi bez izuzetka:

```text
detektovan PE1/PE2/PE3 -> CANDIDATE
potvrda deklaranta     -> CONFIRMED + vrijednost se smije primijeniti
odbijanje deklaranta   -> REJECTED + Rub.36 ostaje prazan
```

`Evidence.auto_applicable` se ne smije koristiti kao univerzalna dozvola za upis.
Primjenjivost zavisi od polja i korisnicke akcije.

---

## 4. Scope lock

### U scope-u

- tarifni broj stavke
- zemlja porijekla stavke
- povlastica / Rub.36
- PE1/PE2/PE3 dokaz i EUR.1 broj
- dokazni trag i potvrda korisnika
- isti rezultat u Faktura i Agent toku
- read-only validacija istog rezultata
- prenos potvrdjenih vrijednosti u naimenovanja i XML
- prenos odluka kroz Deklarant Pro draft save/load

### Van scope-a

- novi dizajn GUI-a
- promjena parsera osim prilagodjavanja izlaza novom ugovoru
- nova PostgreSQL tabela za odluke
- promjena ASYCUDA XML sheme
- promjena Rb.31 formata
- promjena algoritma mase
- promjena header template whitelist-e
- refaktor svih Agent chat namjera
- automatsko pravno tumacenje LLM-om

### Prihvatljiv ishod

Svi postojeci parseri i baze nastavljaju davati iste sirove podatke. Mijenja se samo
nacin na koji se kandidati procjenjuju, potvrdjuju i primjenjuju. Povlastica nikad ne
smije postati automatska. ASYCUDA XML mora ostati funkcionalno isti za vec potvrdjene
deklaracije.

---

## 5. Obavezno citanje prije implementacije

- `AGENTS.md`
- `CLAUDE.md`
- `docs/CONTEXT.md`
- `core/draft/draft.py`
- `services/agent/validation/evidence_model.py`
- `services/agent/validation/tariff_decision_model.py`
- `services/tariff/tariff_mapping_service.py`
- `services/faktura/auto_fill_service.py`
- `services/agent/tariff/tariff_suggestion_service.py`
- `services/agent/validation/historical_tariff_search_service.py`
- `services/agent/validation/declaration_validator_service.py`
- `services/naimenovanja/create_naimenovanja_service.py`
- `gui/tabs/faktura_view.py`
- `gui/tabs/agent/services/import_pipeline_service.py`
- aktivni Deklarant Pro draft serializer/deserializer
- `tests/unit/test_evidence_model.py`
- `tests/unit/test_agent_decision_regression.py`
- `tests/unit/test_historical_tariff_validation.py`
- `tests/unit/test_tariff_suggestion_service.py`

Prije svake izmjene simbola obavezno uraditi GitNexus impact analizu. HIGH/CRITICAL
nalaz prijaviti prije izmjene prema formatu iz `AGENTS.md`.

---

## 6. Faza 0 - Karakterizacija postojeceg ponasanja

**Tip promjene:** test-only / characterization  
**Nivo dozvole:** test gate required  
**Commit:** `test(decision): zabiljezi postojece tokove odluka`

Prije produkcijskog koda napraviti testove koji pokazuju trenutnu razliku izmedju
rucnog i Agent toka. Ne popravljati testove tako sto ce se ocekivanja prilagoditi
trenutno pogresnom rezultatu; test treba jasno oznaciti zeljeni jedinstveni ugovor.

Obavezni scenariji:

1. Ista stavka bez tarife kroz rucni Auto-popuni i Agent pipeline daje isti kandidat.
2. Ista stavka sa tacnim `product_code` i istim izvoznikom bira isti izvor i score.
3. Slab fuzzy match ostaje kandidat i ne upisuje tarifu bez korisnicke akcije.
4. Dokumentovana zemlja porijekla ima prednost nad istorijom i mapping bazom.
5. Konflikt zemlje iz dokumenta i baze ne prepisuje dokument.
6. Detektovana PE2 izjava ne upisuje povlasticu prije potvrde deklaranta.
7. Potvrdjena PE2 upisuje povlasticu i PE2 dokument samo relevantnim stavkama/fakturama.
8. Odbijena PE2 ostavlja Rub.36 prazan.
9. EUR.1 tok cuva poseban broj po zemlji/grupi stavki.
10. Validacija ne mijenja nijedno polje stavke.

Napraviti i inventar svih direktnih writer-a:

```powershell
rg -n "tarifni_broj\s*=|zemlja_porijekla\s*=|povlastica\s*=|eur1_number\s*=" core services gui importers
```

Rezultat inventara dodati u agent report. Svako mjesto klasifikovati kao:

- parser/deserializer - dozvoljen sirovi unos
- manual edit adapter - dozvoljen samo kroz decision servis
- inferred writer - mora biti migriran
- exporter/validator - upis nije dozvoljen

---

## 7. Faza 1 - Kanonski model odluke

**Tip promjene:** behavior foundation / safety patch  
**Nivo dozvole:** mandatory review + test gate  
**Commit:** `feat(decision): uvedi kanonski model odluke deklaracije`

Ne uvoditi drugi paralelni `Evidence`. Postojeci model treba zadrzati i postepeno
premjestiti ili re-exportovati iz neutralnog core sloja, tako da `core` ne zavisi od
`services.agent`.

Predlozeni neutralni modeli:

```python
class DecisionField(Enum):
    TARIFF = "tariff"
    ORIGIN_COUNTRY = "origin_country"
    PREFERENCE = "preference"


class DecisionStatus(Enum):
    UNKNOWN = "unknown"
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class DecisionCandidate:
    candidate_id: str
    value: str
    evidence: Evidence


@dataclass
class FieldDecision:
    field: DecisionField
    status: DecisionStatus
    applied_value: str
    candidates: list[DecisionCandidate]
    selected_candidate_id: str = ""
    confirmed_by: str = ""
    confirmed_at: str = ""
    rejection_reason: str = ""


@dataclass
class LineDecisionState:
    tariff: FieldDecision
    origin_country: FieldDecision
    preference: FieldDecision
```

Nazivi se mogu minimalno prilagoditi postojecim konvencijama, ali semantika mora
ostati ista. `candidate_id` mora biti deterministicki ili stabilan tokom jedne sesije,
da UI ne potvrdi drugi kandidat nakon refresh-a.

`InvoiceLine` dobija kanonsko `decision_state`. Direktna polja (`tarifni_broj`,
`zemlja_porijekla`, `povlastica`, `eur1_number`) ostaju zbog kompatibilnosti i XML-a,
ali predstavljaju samo **primijenjenu vrijednost**. Kandidati se ne smiju upisivati u
ta polja.

Obavezno:

- `InvoiceLine.from_any()` mora bezbjedno ucitati staru strukturu bez decision state-a
- stari draftovi moraju ostati citljivi
- novi Deklarant Pro draft mora sacuvati i vratiti decision state
- ASYCUDA XML ne smije sadrzavati interne decision metapodatke
- `services/agent/validation/evidence_model.py` ostaje compatibility import dok se svi
  pozivaoci ne migriraju

---

## 8. Faza 2 - Jedini servis koji donosi i primjenjuje odluke

**Tip promjene:** behavior adjustment / centralization  
**Nivo dozvole:** mandatory review + test gate  
**Commit:** `feat(decision): centralizuj procjenu i primjenu kandidata`

Uvesti servis u neutralnom poslovnom sloju, predlozeno:

```text
services/decision/
    __init__.py
    declaration_decision_service.py
    decision_policy.py
    evidence_adapters.py
```

Javni API treba biti mali i stabilan:

```python
evaluate_line(line, context, fields=None) -> LineDecisionState
evaluate_draft(draft, context, fields=None) -> DecisionEvaluationReport
apply_candidate(line, field, candidate_id, authorization) -> FieldDecision
confirm_manual_value(line, field, value, authorization) -> FieldDecision
reject_candidate(line, field, candidate_id, authorization, reason="") -> FieldDecision
```

`DecisionContext` mora nositi samo podatke potrebne za odluku:

- normalizovan izvoznik
- broj fakture
- dokument reference
- tip korisnicke akcije (`preview`, `auto_fill_clicked`, `dialog_confirmed`,
  `manual_edit`, `draft_restore`)
- opcionalni identitet korisnika/deklaranta ako aplikacija vec ima taj podatak

Servis mora biti idempotentan: ponovljena evaluacija istog stanja ne smije duplirati
kandidate, povecavati usage_count ili mijenjati potvrdu korisnika.

`evaluate_*` je read/evaluate operacija i ne smije mijenjati primijenjena polja.
Samo `apply_candidate()` i `confirm_manual_value()` smiju upisati izvedenu vrijednost.

---

## 9. Faza 3 - Jedinstvene politike po polju

**Tip promjene:** mapping correction / safety policy  
**Nivo dozvole:** mandatory review  
**Commit:** `feat(decision): uvedi jedinstvene politike tarifa i porijekla`

### 9.1 Tarifni broj

Redoslijed kandidata:

1. rucno potvrdjena vrijednost korisnika
2. tarifa iz vec ucitanog ASYCUDA/Deklarant Pro drafta
3. tacan product code istog izvoznika
4. prefix product code istog izvoznika
5. istorija istog izvoznika
6. lokalni mapping / fuzzy kandidat
7. unknown

Pravila:

- istorija drugog izvoznika je zabranjena
- fuzzy threshold ostaje najmanje projektnih `0.92`
- slab kandidat se prikazuje, ali se ne primjenjuje
- klik na `Auto-popuni` je eksplicitna batch autorizacija samo za kandidate koji
  zadovolje definisanu tariff policy
- LLM nikad ne stvara kandidat koji se moze primijeniti
- `usage_count` se ne povecava tokom preview/evaluate poziva
- servis mora vratiti razlog, izvor, score i podatak koji je matchovan

### 9.2 Zemlja porijekla

Redoslijed izvora:

1. rucna potvrda korisnika
2. eksplicitna zemlja po stavci iz packing liste/fakture/XML-a
3. parser kandidat iz jasno identifikovanog dokumenta
4. mapping/istorija samo kao informacija za provjeru
5. unknown

Pravila:

- baza i istorija ne smiju prepisati dokument
- konflikt se cuva kao `CONFLICT` sa oba izvora
- validator mora prikazati konflikt, ne samo crvenu boju reda
- nepoznata zemlja ostaje prazna

### 9.3 Povlastica i PE dokumenti

Politika je stroga:

- zemlja porijekla nije dokaz povlastice
- mapping baza nije dokaz povlastice
- istorija nije dokaz povlastice
- parser samo detektuje PE1/PE2/PE3 kandidat
- deklarant eksplicitno potvrdjuje ili odbija kandidat
- tek `CONFIRMED` odluka upisuje `povlastica`, `eur1_number`,
  `has_origin_statement`/`is_authorized_exporter` i vezani dokument
- PE1 broj ostaje vezan za odgovarajucu zemlju/grupu stavki
- odbijanje se pamti tokom sesije i kandidat se ne smije odmah ponovo automatski nuditi

Potvrda deklaranta mora dodati `DecisionSource.USER` evidenciju koja referencira
originalni dokument dokaz. Time se razlikuju "parser je nasao" i "deklarant je
potvrdio".

---

## 10. Faza 4 - Migracija svih potrosaca na isti servis

**Tip promjene:** controlled migration  
**Nivo dozvole:** commit po podfazi + mandatory review  

### 10.1 Faktura tab

**Commit:** `refactor(faktura): koristi jedinstveni servis odluka`

- `_on_auto_fill` dobija kandidate i primjenjuje samo policy-dozvoljene tarife
- UI prikazuje izvor, score i status iz `FieldDecision`
- manual edit ide kroz `confirm_manual_value()`
- PE/EUR1 dijalozi koriste `apply_candidate()` ili `reject_candidate()`
- ukloniti lokalno izvodjenje povlastice i zemlje iz UI metode

### 10.2 Agent pipeline

**Commit:** `refactor(agent): koristi isti tok odluka kao faktura`

- `_puna_auto_pipeline` ne poziva zasebnu poslovnu logiku
- smije orkestrirati mase, evaluaciju, prikaz i potvrdu
- za tarife poziva isti servis i istu policy kao Faktura tab
- za povlastice uvijek ceka isti deklarantski dijalog
- isti ulaz mora dati identican `DecisionEvaluationReport` u oba taba

### 10.3 Validacija

**Commit:** `refactor(validation): validiraj kanonsko stanje odluka`

- validator je read-only
- ne trazi novi mapping i ne mijenja draft
- prijavljuje `UNKNOWN`, `CANDIDATE`, `CONFLICT` i nepotvrdjenu povlasticu
- svaka greska navodi konkretno polje, stavku, razlog i izvor
- istorijska validacija moze dodati kandidat samo preko decision servisa, ne direktno

### 10.4 Naimenovanja

**Commit:** `refactor(naimenovanja): prenesi samo potvrdjene odluke`

- `CreateNaimenovanjaService` cita primijenjene vrijednosti
- ako postoji povlastica bez `CONFIRMED` preference odluke, kreiranje se blokira ili
  vraca jasan preflight problem
- PE1/PE2/PE3 dokument se izvodi iz potvrdjene odluke, ne samo iz kombinacije bool polja
- grouping key ostaje tarifa + zemlja + povlastica + EUR.1 broj

### 10.5 XML export

**Commit:** `fix(xml): izvozi samo kanonsko potvrdjeno stanje`

- exporter ne poziva bazu znanja
- exporter ne mijenja vrijednosti tokom izvoza
- nepotvrdjena povlastica je preflight greska
- interni decision metadata ne ulazi u ASYCUDA XML
- postojece Rb.31 i AttachedDocument pravilo ostaje nepromijenjeno

---

## 11. Faza 5 - Kontrolisano ucenje baze znanja

**Tip promjene:** safety patch  
**Nivo dozvole:** mandatory review  
**Commit:** `fix(learning): uci samo iz potvrdenih odluka`

Postojeca pitanja korisniku pri promjeni tarife u Naimenovanja tabu treba zadrzati,
ali zapis u bazu mora imati dokaz da je vrijednost rucno potvrdjena.

Pravila:

- preview kandidat nikad ne ide u bazu znanja
- odbijen kandidat nikad ne ide u bazu znanja
- slab fuzzy kandidat koji je batch-popunjen ne postaje novi autoritet bez posebne potvrde
- manual edit + eksplicitno "azuriraj bazu znanja" smije sacuvati mapping
- zapis mora cuvati normalizovanog izvoznika, product code, tarifu i porijeklo izvora
- povlastica se ne uci kao automatsko pravilo za buducu primjenu

---

## 12. Faza 6 - Uklanjanje paralelnih puteva

**Tip promjene:** cleanup nakon migracije  
**Nivo dozvole:** no auto-merge + test gate  
**Commit:** `refactor(decision): ukloni paralelne writere odluka`

Tek nakon sto su svi potrosaci migrirani:

- `AutoFillService.fill_tariff_numbers()` postaje tanak wrapper nad decision servisom
  ili se uklanja ako nema pozivalaca
- `TariffMappingService.auto_populate_tariffs()` postaje evidence provider, ne writer
- istorijski servisi vracaju kandidate/Evidence, ne mijenjaju `InvoiceLine`
- UI lokalna logika za izvodjenje povlastice se uklanja
- compatibility importi ostaju samo gdje su potrebni za `dist_client`
- root i `dist_client` runtime kopije moraju biti identicne za izmijenjenu logiku

Na kraju ponoviti writer inventar. Dozvoljeni direktni upisi ostaju samo u:

- parser/deserializer granici za sirove dokument cinjenice
- decision servisu za izvedene/primijenjene odluke
- draft restore toku
- kontrolisanom manual edit adapteru koji odmah poziva decision servis

---

## 13. Test matrica

Svi testovi moraju raditi bez LLM-a, API kljuca i produkcijske baze. Koristiti fixture,
fake providere i anonimizovane stavke.

| Scenario | Tarifa | Zemlja | Povlastica | Ocekivani status |
| --- | --- | --- | --- | --- |
| Tacan product code, isti izvoznik | kandidat/jak | bez promjene | bez promjene | tariff candidate |
| Isti kod, drugi izvoznik | nema tudjeg matcha | bez promjene | bez promjene | unknown |
| Fuzzy 0.91 | ne primjenjuje | bez promjene | bez promjene | unknown/hidden |
| Fuzzy >=0.92, bez autorizacije | kandidat | bez promjene | bez promjene | candidate |
| Klik Auto-popuni, policy prosao | primijenjena | bez promjene | bez promjene | confirmed by batch action |
| Packing lista ima zemlju | bez promjene | dokument vrijednost | prazna | origin confirmed/document |
| DB zemlja protiv dokumenta | bez promjene | dokument ostaje | prazna | conflict warning |
| CN bez PE dokaza | bilo koja | CN | prazna | no preference |
| EU zemlja bez PE dokaza | bilo koja | EU | prazna | no preference |
| PE2 detektovan | bez promjene | dokument zemlja | prazna | preference candidate |
| PE2 potvrdjen | bez promjene | dokument zemlja | primijenjena | confirmed/user+document |
| PE2 odbijen | bez promjene | dokument zemlja | prazna | rejected |
| PE1 vise zemalja | bez promjene | po grupi | po potvrdi | zasebni brojevi EUR.1 |
| Validacija | ne mijenja | ne mijenja | ne mijenja | read-only |
| Draft save/load | isto | isto | isto | decision trace sacuvan |
| ASYCUDA export | primijenjeno | primijenjeno | samo potvrdjeno | bez internog metadata |

Obavezni novi ili prosireni testovi:

- `tests/unit/test_declaration_decision_model.py`
- `tests/unit/test_declaration_decision_service.py`
- `tests/unit/test_decision_tariff_policy.py`
- `tests/unit/test_decision_origin_policy.py`
- `tests/unit/test_decision_preference_policy.py`
- `tests/integration/test_manual_agent_decision_parity.py`
- `tests/integration/test_decision_to_naimenovanja.py`
- `tests/integration/test_decision_draft_roundtrip.py`
- `tests/integration/test_decision_xml_preflight.py`

Postojece regression fixture iz
`tests/fixtures/agent/agent_decision_regression_cases.json` prosiriti, ne praviti
paralelni fixture za iste scenarije.

---

## 14. Backward compatibility i migracija

- Stari `DeclarationDraft` bez decision state-a ucitava se bez greske.
- Pri prvom ucitavanju, postojece vrijednosti se klasifikuju kao legacy stanje:
  - rucno/Deklarant Pro draft porijeklo, ako je poznato -> USER ili DOCUMENT
  - nepoznato porijeklo vrijednosti -> `CANDIDATE`/`UNKNOWN`, ne lazno potvrdjeno
- Postojeci ASYCUDA XML import ostaje podrzan.
- Root kod je primarni izvor. Svaka runtime izmjena se preslikava u `dist_client` u
  istom commitu i provjerava byte/diff poredenjem gdje je moguce.
- Ne raditi PostgreSQL migraciju za decision state.
- Ne mijenjati korisnicke `.env` fajlove.

---

## 15. Observability i izvjestaj

`DecisionEvaluationReport` treba omoguciti UI-u i logu da kazu:

```text
Stavka 17 - Tarifni broj
Kandidat: 85168080
Izvor: istorija istog izvoznika PIP FOOD GROUP DOO, koristeno 6x
Pouzdanost: 90%
Status: ceka potvrdu / primijenjeno kroz Auto-popuni
```

Log ne smije sadrzavati tajne, API kljuceve ili cijeli sadrzaj fakture. Za svaki
primijenjeni kandidat logovati samo stavku, polje, izvor, status i candidate ID.

---

## 16. Zabranjeno

- Ne uvoditi novu bazu podataka kao "single source of truth".
- Ne dozvoliti GUI-u ili Agent controlleru da direktno izvede povlasticu.
- Ne tretirati `Evidence.auto_applicable` kao univerzalno pravilo.
- Ne primjenjivati PE1/PE2/PE3 bez potvrde deklaranta.
- Ne uciti iz odbijenih ili nepotvrdjenih kandidata.
- Ne spustati fuzzy threshold ispod `0.92`.
- Ne koristiti istoriju drugog izvoznika.
- Ne dozvoliti LLM-u da mijenja status, izvor, score ili vrijednost kandidata.
- Ne mijenjati XML vrijednosti tokom validacije ili exporta.
- Ne raditi veliki rename/find-and-replace bez GitNexus rename alata.
- Ne dirati postojece nepovezane izmjene u radnom stablu.

---

## 17. Obavezna provjera nakon svake faze

1. GitNexus impact prije izmjene svakog simbola.
2. Ciljani pytest testovi za fazu.
3. `py_compile` svih izmijenjenih Python fajlova.
4. Root/dist_client mirror provjera.
5. `git diff --check`.
6. GitNexus `detect_changes` prije commita.
7. Jedan logicki commit po fazi.
8. Agent report sa odlukama, rizicima i test rezultatima.
9. Bez push-a dok Codex ne zavrsi nezavisnu verifikaciju.

Minimalni zavrsni test gate:

```powershell
.venv\Scripts\python.exe -m pytest tests\unit\test_evidence_model.py -q
.venv\Scripts\python.exe -m pytest tests\unit\test_agent_decision_regression.py -q
.venv\Scripts\python.exe -m pytest tests\unit\test_declaration_decision_model.py -q
.venv\Scripts\python.exe -m pytest tests\unit\test_declaration_decision_service.py -q
.venv\Scripts\python.exe -m pytest tests\integration\test_manual_agent_decision_parity.py -q
.venv\Scripts\python.exe -m pytest tests\integration\test_decision_to_naimenovanja.py -q
.venv\Scripts\python.exe -m pytest tests\integration\test_decision_draft_roundtrip.py -q
.venv\Scripts\python.exe -m pytest tests\integration\test_decision_xml_preflight.py -q
```

Ako projekat koristi `dist_client\.venv`, executor mora prijaviti tacan interpreter
koji je koristio; ne smije tvrditi da su testovi prosli ako nisu pokrenuti.

---

## 18. Codex verifikacioni protokol

Kada Pi agent prijavi zavrsetak, Codex ce nezavisno provjeriti:

1. Da li postoji samo jedan servis koji primjenjuje izvedene odluke.
2. Da li rucni i Agent tok daju isti rezultat za isti ulaz.
3. Da li je validator stvarno read-only.
4. Da li preference kandidat ostaje prazan do potvrde deklaranta.
5. Da li odbijanje ostaje zapamceno tokom sesije.
6. Da li naimenovanja i XML koriste samo primijenjene vrijednosti.
7. Da li draft roundtrip cuva dokazni trag bez curenja u ASYCUDA XML.
8. Da li baza znanja uci samo nakon eksplicitne potvrde.
9. Da li su svi direktni writer-i inventarisani i opravdani.
10. Da li su root i `dist_client` kopije uskladjene.
11. Da li su testovi stvarno pokrenuti i reproduktivni bez LLM-a.
12. Da li svaki commit ostaje u scope-u svoje faze.

Codex nece odobriti implementaciju ako samo postoji novi servis, a stari paralelni
putevi i dalje mogu direktno mijenjati ista polja.

---

## 19. Definition of Done

Zadatak je zavrsen samo ako su ispunjeni svi uslovi:

- postoji kanonski model kandidata, dokaza i statusa odluke
- postoji jedan servis za procjenu i primjenu izvedenih odluka
- Faktura i Agent koriste isti servis i istu policy
- Validacija je read-only i daje konkretan razlog greske
- povlastica zahtijeva eksplicitnu potvrdu deklaranta
- naimenovanja i XML ne koriste nepotvrdjene vrijednosti
- decision state se cuva u Deklarant Pro draftu, ali ne u ASYCUDA XML-u
- baza znanja ne uci iz nepotvrdjenih/odbijenih kandidata
- svi relevantni testovi prolaze bez vanjskog LLM-a
- GitNexus detect changes potvrdi ocekivani scope
- Codex zavrsi nezavisnu verifikaciju

---

## 20. Output format Pi agenta

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
FAZA: broj i naziv faze
COMMIT: hash i poruka
IZMIJENJENI FAJLOVI: lista
GITNEXUS IMPACT: simboli i rizik
STA JE URADJENO: kratak opis
TESTOVI: tacne komande i rezultati
WRITER INVENTAR: novi/preostali direktni writer-i
STA NIJE URADJENO: razlog
PITANJA: otvorene nejasnoce
```

