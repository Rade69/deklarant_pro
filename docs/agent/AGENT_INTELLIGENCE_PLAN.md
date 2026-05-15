# Plan unapređenja inteligencije agenta

**Datum:** 2026-05-15  
**Status:** Faza 3 započeta, Faza 4 započeta strukturnim izdvajanjem odluke
**Scope:** istorijska validacija tarifa, objašnjivi prijedlozi, evaluacija kvaliteta i učenje iz odluka korisnika

---

## Sažetak

Agent je već dobio dvije važne zaštite: slab istorijski prijedlog se filtrira, a prijedlog se sada procjenjuje u kontekstu cijele fakture. Time je smanjen rizik da agent predloži tarifni broj iz potpuno nepovezanog poglavlja samo zato što postoji jedan star ili loš istorijski zapis.

Preostali posao nije samo "još malo heuristike". Sljedeći korak mora uvesti mjerljivost: evaluacioni set, očekivane ishode i metrike. Tek poslije toga ima smisla uvoditi jači scoring ili učenje iz korisničkih odluka, jer bez mjerenja nećemo znati da li je agent stvarno pametniji ili samo tiši.

---

## Trenutno implementirano

### Faza 1 — Filter slabih istorijskih prijedloga

**Status:** implementirano  
**Commit:** `275b4e1 fix(import): medicopharm mase i istorijska validacija`

Agent odbacuje slabe cross-chapter prijedloge kada istorijski zapis nema dovoljno ponavljanja, nema smislen izvor ili ima nisku pouzdanost. Ovo rješava problem gdje jedan loš istorijski zapis može korisniku ponuditi tarifni broj iz potpuno pogrešnog poglavlja.

**Efekat:**
- manje šuma u TariffValidationDialog-u
- manje opasnih prijedloga za ručno prihvatanje
- istorija ostaje korisna, ali više nije automatski autoritet

**Kompleksnost završene faze:** niska do srednja  
**Rizik završene faze:** nizak  
**Glavni rizik:** false negative, tj. agent može sakriti rijedak ali tačan istorijski prijedlog ako nema dovoljno dokaza.

---

### Faza 2 — Profil fakture i objašnjenje odluke

**Status:** implementirano  
**Commit:** `f43f0cc feat(validation): profil fakture za istorijske tarife`

Agent sada gradi profil trenutne fakture iz postojećih tarifnih brojeva. Gleda koja poglavlja i tarifne glave već postoje u fakturi, pa prijedlog van tog profila mora imati jači dokaz da bi prošao.

Dodano je i polje `decision_reason`, koje objašnjava zašto je prijedlog prošao filter. Taj razlog se prikazuje u dijalogu i ulazi u kopirani izvještaj.

**Efekat:**
- prijedlozi se procjenjuju u kontekstu cijele fakture
- cross-chapter prijedlog više nije zabranjen, ali mora biti bolje potkrijepljen
- korisnik vidi razlog prijedloga umjesto crne kutije

**Kompleksnost završene faze:** srednja  
**Rizik završene faze:** srednji  
**Glavni rizik:** profil fakture može biti loš ako su postojeće tarife u fakturi već pogrešne ili prazne.

---

## Preostali plan

### Faza 3 — Evaluacioni set za kvalitet prijedloga

**Status:** započeto; dodana prva JSON fixture verzija, parametrizovani unit test, metrički test i CLI izvještaj
**Procjena kompleksnosti:** srednja  
**Procjena trajanja:** 1 do 2 radna dana za prvu korisnu verziju  
**Rizik:** nizak za aplikaciju, visok za zaključke ako se set loše napravi

#### Cilj

Napraviti mali, ali pouzdan skup test-slučajeva na kojem se može mjeriti da li agent daje dobre tarifne prijedloge. Bez ovoga svaka nova heuristika ostaje subjektivna.

#### Šta treba obuhvatiti

Evaluacioni set treba imati poznate slučajeve:

- tačan istorijski prijedlog u istom heading-u
- tačan istorijski prijedlog u istom poglavlju, ali drugom heading-u
- tačan cross-chapter prijedlog sa jakim dokazom
- netačan cross-chapter prijedlog koji mora biti sakriven
- stavka bez trenutne tarife gdje istorija treba pomoći
- stavka gdje istorija postoji, ali je izvor slab ili prazan
- faktura sa mješovitim poglavljima
- faktura gdje je profil fakture varljiv jer ima malo stavki

#### Predložena struktura

Dodati test fixture, npr:

```text
tests/fixtures/agent/tariff_validation_cases/
```

Prva implementirana verzija koristi jedan JSON fajl:

```text
tests/fixtures/agent/tariff_validation_cases.json
```

Minimalna struktura slučaja:

```json
{
  "name": "bort_weak_cross_chapter_noise",
  "invoice_lines": [
    {
      "naziv_robe": "BORT 112900 B.R.Z.palac lev XL",
      "tarifni_broj": "63079099",
      "exporter": "MEDICOPHARM"
    }
  ],
  "history_matches": [
    {
      "naziv_robe": "BORT 112900 B.R.Z.palac lev XL",
      "commodity_code": "11010015",
      "supplier": "",
      "usage_count": 1,
      "source": "",
      "confidence": 0.60
    }
  ],
  "expected": {
    "action": "suppress",
    "reason_contains": null
  }
}
```

#### Metrike

Prva verzija ne treba biti akademska. Implementirane su ove metrike:

- **true positive:** agent prikaže dobar prijedlog
- **false positive:** agent prikaže loš prijedlog
- **true negative:** agent sakrije loš prijedlog
- **false negative:** agent sakrije dobar prijedlog
- **explanation coverage:** svaki prikazani prijedlog ima `decision_reason`

Trenutni fixture set ima očekivani zbir:

```text
true_positive: 7
true_negative: 6
false_positive: 0
false_negative: 0
wrong_tariff: 0
explanation_missing: 0
```

Metrike se mogu provjeriti i bez pytest detalja:

```bash
python scripts/agent_tariff_eval_report.py
```

#### Testovi

Dodati jedan parametrizovani pytest koji učitava sve slučajeve i provjerava očekivani ishod. Ne spajati se na PostgreSQL; `_search_one` treba mockovati kao i u postojećim unit testovima.

#### Zašto je ovo sljedeći korak

Ovo je temelj za svaku dalju inteligenciju. Ako se odmah uvede složeniji scoring, postoji realan rizik da se popravi jedan primjer, a pokvari pet drugih bez da to iko primijeti.

---

### Faza 4 — Scoring model i učenje iz korisničkih odluka

**Status:** započeto; postojeća odluka izdvojena u `tariff_decision_model.py`, bez promjene scoring ponašanja
**Procjena kompleksnosti:** visoka  
**Procjena trajanja:** 3 do 6 radnih dana za konzervativnu verziju; više ako se uvodi trajno učenje i administracija  
**Rizik:** srednji do visok

#### Cilj

Zamijeniti rasute pragove jednim jasnim scoring modelom koji kombinuje više signala i daje objašnjivu odluku: prikazati prijedlog, sakriti ga ili prikazati kao slabo upozorenje.

#### Signali koje scoring treba koristiti

Predloženi signali:

- poklapanje poglavlja
- poklapanje heading-a
- da li je prijedlog van profila fakture
- `usage_count`
- smislenost izvora
- supplier/exporter match
- confidence iz istorijskog servisa
- sličnost naziva robe
- da li je korisnik ranije prihvatao ili odbijao slične prijedloge
- da li je trenutna tarifa prazna ili već popunjena

#### Predloženi ishod scoring-a

Umjesto čistog `True/False`, servis bi trebao vratiti odluku:

```text
SHOW_STRONG       prikazati kao jak prijedlog
SHOW_WEAK         prikazati oprezno, bez "Prihvati sve" automatike
SUPPRESS          sakriti
```

Svaka odluka mora imati:

- finalni score
- listu razloga koji su povećali score
- listu razloga koji su smanjili score
- kratak `decision_reason` za UI

#### Učenje iz korisničkih odluka

Kada korisnik prihvati ili odbije prijedlog, sistem treba zapamtiti minimalan događaj:

- naziv robe ili normalizovani ključ naziva
- trenutni tarifni broj
- predloženi istorijski tarifni broj
- exporter/importer ako postoje
- da li je korisnik prihvatio ili odbio
- datum
- izvor odluke, npr. TariffValidationDialog

Ovo ne treba odmah koristiti kao automatsku istinu. U prvoj verziji korisničke odluke treba koristiti kao dodatni signal, sa ograničenom težinom.

#### Predložena implementacija

Interni model odluke je započet u:

```text
services/agent/validation/tariff_decision_model.py
```

Trenutna odgovornost tog modula:

- prima `TariffHistoryMatch`, trenutni tarifni broj i profil fakture
- primjenjuje postojeće pragove bez promjene ponašanja
- vraća boolean odluku i puni `decision_reason`

Sljedeći korak Faze 4 je proširiti ga na eksplicitne ishode `SHOW_STRONG`, `SHOW_WEAK` i `SUPPRESS`, ali tek nakon dodatnih realnih evaluacionih slučajeva.

`HistoricalTariffSearchService` ostaje zadužen za pretragu i orkestraciju, ali ne treba beskonačno širiti `_is_actionable_match`.

#### Zašto je kompleksno

Ovo dira poslovno ponašanje agenta, ne samo UI. Loše podešen scoring može imati dva loša ishoda:

- agent počne sakrivati korisne prijedloge
- agent opet počne prikazivati opasne prijedloge, samo sa ljepšim objašnjenjem

Zato Faza 4 ne treba početi prije Faze 3.

---

## Procjena po fazama

| Faza | Status | Kompleksnost | Rizik | Procjena |
|------|--------|--------------|-------|----------|
| 1. Filter slabih prijedloga | završeno | niska-srednja | nizak | završeno |
| 2. Profil fakture + razlog | završeno | srednja | srednji | završeno |
| 3. Evaluacioni set | započeto | srednja | nizak/srednji | fixture + metrike + CLI izvještaj dodani; proširiti realnim slučajevima |
| 4. Scoring + učenje | započeto | visoka | srednji/visok | strukturno izdvajanje urađeno; scoring još nije uveden |

---

## Preporučeni redoslijed

1. Proširiti evaluacioni fixture set realnim fakturama i poznatim odlukama.
2. Proširiti `tariff_decision_model.py` na eksplicitne odluke tek kada evaluacija pokriva dovoljno slučajeva.
3. Uvesti scoring bez trajnog učenja.
4. Tek nakon stabilnog scoring-a dodati pamćenje korisničkih odluka.

---

## Minimalna sljedeća iteracija

Ako se želi najkorisniji sljedeći korak bez velikog rizika:

1. Dodati još 3-5 ručno odabranih slučajeva iz realnih faktura.
2. Tek onda širiti Fazu 4 na scoring.

Ova iteracija ne mijenja ponašanje aplikacije, ali daje osnovu da sljedeće promjene budu kontrolisane.

---

## Kritične granice

- Ne spuštati pragove samo da bi agent "našao više".
- Ne uvoditi automatsko prihvatanje cross-chapter prijedloga bez jakog dokaza.
- Ne koristiti korisničko prihvatanje kao apsolutnu istinu; korisnik može prihvatiti pogrešan prijedlog pod pritiskom.
- Ne spajati evaluacione testove na živu bazu.
- Ne širiti UI dok odluka nije stabilna u servisu.

---

## Zaključak

Plan od 4 tačke je otprilike na pola puta. Prve dvije faze su bile zaštitne: smanjile su šum i učinile prijedloge objašnjivim. Treća faza treba da uvede mjerenje kvaliteta. Četvrta faza je prava nadogradnja inteligencije, ali je i najrizičnija, pa je treba raditi tek kada postoje evaluacioni slučajevi koji hvataju regresije.
