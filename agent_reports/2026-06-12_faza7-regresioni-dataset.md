# Agent report — Faza 7: regresioni dataset agenta

**Datum:** 2026-06-12
**Agent:** Claude Sonnet 4.6
**Scope:** `tests/fixtures/agent/agent_decision_regression_cases.json` (novo),
`tests/unit/test_agent_decision_regression.py` (novo),
`agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`

## Sta je uradjeno

- Novi fixture `tests/fixtures/agent/agent_decision_regression_cases.json` —
  9 anonimizovanih slucajeva, isti format kao postojeci
  `tests/fixtures/agent/tariff_validation_cases.json` (Faza 3), koji pokrivaju
  svih 7 predlozenih scenarija iz plana:
  1. `pe2_izjava_o_porijeklu` — Faktura sa PE2 izjavom
  2. `eur1_obrazac_pe1` — Faktura sa EUR.1 obrascem
  3. `eu_zemlja_bez_dokaza_porijekla` — Faktura bez dokaza porijekla (slab prijedlog)
  4. `cn_roba_bez_povlastice` — CN roba bez povlastice (unknown)
  5. `izvoznik_a_potvrdjena_istorija_tarife` + `izvoznik_b_bez_sopstvene_istorije`
     — Isti proizvod kod dva izvoznika sa razlicitim tarifama
  6. `blagic_faktura_46_pe2_potvrdjeno` + `blagic_faktura_703_bez_izjave`
     — Blagic/Loren scenario sa vise faktura i izjavama
  7. `istorija_slab_prijedlog_zahtjeva_potvrdu` — Slucaj gdje istorija daje
     slab prijedlog
- Novi `tests/unit/test_agent_decision_regression.py`:
  - `test_agent_decision_regression_cases` — data-driven test, parametrizovan
    po svih 9 slucajeva, poredi `Evidence.source/confidence/score/score_category/
    requires_confirmation/should_recommend/auto_applicable` (i `data["doc_code"]`
    gdje je relevantno) sa `expected` poljem iz JSON-a.
  - `test_two_exporters_same_product_dont_share_tariff_evidence` — Faza 3
    acceptance ("isti proizvod kod dva izvoznika ne vraca tudju potvrdu").
  - `test_multi_invoice_draft_lines_have_independent_evidence` — Blagic/Loren:
    stavke iz razlicitih faktura imaju nezavisnu evidenciju.
  - `test_weak_history_proposal_is_never_auto_applicable` — Faza 3 pravilo:
    slab prijedlog nikad nije `auto_applicable`.
- Azuriran `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`:
  Faza 7 status postavljen na "ZAVRSENO 2026-06-12", dodan "Uradjeno" odjeljak.

## Kako je uradjeno

Svi slucajevi su izgradjeni preko dvije postojece, ciste funkcije iz
`services/agent/validation/evidence_model.py` (Faza 1/2, nema izmjena u
produkcionom kodu):

- `evidence_from_preference(item: InvoiceLine)` — za scenarije 1-4, 6 (PE1/PE2/
  EUR.1/CN/Blagic-Loren), gdje JSON nosi `invoice_line` dict koji se direktno
  prosljedjuje u `InvoiceLine(**...)`.
- `evidence_from_tariff_decision(decision_outcome, supplier_match, usage_count,
  source)` — za scenarije 5 i 7 (istorijski prijedlozi po izvozniku), gdje JSON
  nosi `tariff_decision` dict.

Test fajl ucitava JSON, gradi `Evidence` preko `_evidence_for(case)` na osnovu
`case["kind"]` ("preference" ili "tariff_decision"), i poredi sva polja
relevantna za UI (score, score_category, requires_confirmation,
should_recommend, auto_applicable) — isti vokabular koji `ChatPanel`/
`TariffValidationDialog` koriste za prikaz (Faza 5/6).

## Zasto ovako (i sta je namjerno izostavljeno)

Acceptance kriteriji Faze 7 trazu da testovi rade bez LLM-a, bez API kljuca, i
da koriste fixture/anonimizovane minimalne ulaze. Alternativa — pisanje novih
integracionih testova nad stvarnim PDF/Excel fajlovima iz `najavauvoza/`
(Blagic/Loren) — je odbacena jer:

1. Ti fajlovi NISU u repozitoriju (postojeci `test_blagic_loren_agent_import.py`
   ima 10 pre-existing `FileNotFoundError` padova upravo iz tog razloga — vidi
   `agent_reports/2026-06-12_faza6-chat-badge-i-kopiranje.md`).
2. `evidence_model.py` (Faza 1/2) je sloj koji predstavlja KONACNU odluku agenta
   po "Arhitektonskom pravilu" plana — regresija na tom nivou direktno testira
   ono sto je najbitnije (da agent ne izmislja dokaz), a stabilna je nezavisno
   od PDF parsiranja, baze ili UI sloja.

Scenario 5 ("dva izvoznika, isti proizvod, razlicite tarife") je modelovan kao
DVA odvojena slucaja — izvoznik A ima potvrdjenu istoriju (CONFIRMED_FROM_SAME_
EXPORTER_HISTORY, score 90, auto_applicable), izvoznik B nema sopstvenu istoriju
za taj proizvod (UNKNOWN, score 0) — sto direktno demonstrira da B ne "naslijedi"
A-ovu potvrdu/tarifu. Konkretni tarifni brojevi po izvozniku (npr. "izvoznik A
koristi 17049081, izvoznik B 21069092 za isti product_code") su veci nivo
detalja koji vec pokriva `tariff_validation_cases.json`/`HistoricalTariffSearchService`
(Faza 3, ZAVRSENO) — nije duplirano ovdje.

Scenario 6 ("Blagic/Loren vise faktura i izjava") je modelovan preko
`InvoiceLine.invoice_number` — dvije stavke iz dvije razlicite fakture
("46VP-2026" i "703VP-2025") u istom datasetu, sa razlicitim dokazima
porijekla, da se potvrdi da evidencija po stavki ostaje nezavisna unutar iste
deklaracije — bez potrebe za stvarnim Blagic/Loren fajlovima.

## GitNexus

- `gitnexus_detect_changes(scope=all)` → risk LOW, 0 affected processes.
  Promijenjeni simboli su samo auto-generisani GitNexus brojaci u
  `AGENTS.md`/`CLAUDE.md` (`38878→38927 symbols, 61043→61157 relationships`),
  nastali kao nuspojava `npx gitnexus analyze` pokretanja nakon Faze 6 commitova
  — ne odnose se na ovu izmjenu. Novi test fajlovi su cisto dodatni (nova
  funkcija/test nije pozvana iz postojecih execution flow-ova).
- `npx gitnexus analyze` pokrenut nakon commita.

## Testovi

```powershell
python -m py_compile tests\unit\test_agent_decision_regression.py
python -m pytest tests/unit/test_agent_decision_regression.py -q
python -m pytest tests/unit -k "agent or evidence or tariff" -q
```

Rezultat: `12 passed` za novi fajl; širi set `153 passed, 10 failed, 1 skipped` —
10 padova su pre-existing `FileNotFoundError` za `najavauvoza/` fixture fajlove,
nepovezano sa ovom izmjenom (ista baseline kao u Fazi 6).

## Commitovi

| Hash | Poruka |
| --- | --- |
| `37e4e9d` | `feat(agent): regresioni dataset za 7 scenarija odluka agenta (Faza 7)` |

## Otvoreno za naredne faze

- Faza 8 — LLM provider fallback (402/429/timeout) je sljedeca na redu po
  planu.
- Ako se zeli i Faza 3-stil dataset (konkretni tarifni brojevi po izvozniku za
  scenario 5), to ide u `tests/fixtures/agent/tariff_validation_cases.json` sa
  dodatnim `izvoznik`/`uvoznik` poljima u `history_matches` — van scope-a ove
  faze.
