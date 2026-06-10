# Faza 1 — Evidence model za Carinski agent (2026-06-10)

## Šta je urađeno

Implementirana Faza 1 iz `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`:
zajednički vokabular za izvor i pouzdanost odluka agenta (`Evidence`/`DecisionSource`/
`DecisionConfidence`), integrisan u tok historijske validacije tarifnih brojeva.

- Novi modul `services/agent/validation/evidence_model.py` (+ mirror u `dist_client/`):
  - `DecisionSource` — `document`, `exporter_history`, `tariff_database`, `similarity`,
    `user`, `llm`
  - `DecisionConfidence` — tačno 5 statusa iz plana: `confirmed_from_document`,
    `confirmed_from_same_exporter_history`, `suggested_by_similarity`, `weak_guess`,
    `unknown`
  - `Evidence` (frozen dataclass): `source`, `confidence`, `reason`, `data: dict`,
    `requires_confirmation: bool`
  - `build_evidence(...)` — generički builder, `requires_confirmation` se po defaultu
    izvodi iz `confidence` (False samo za `confirmed_from_*`)
  - `evidence_from_tariff_decision(decision_outcome, supplier_match, usage_count, source)`
    — mapira ishod `decide_tariff_match()` na `Evidence`
- `TariffHistoryMatch` (services/agent/validation/historical_tariff_search_service.py)
  proširen NOVIM opcionim poljem `evidence: Evidence | None = None` — bez izmjene
  postojećih polja/signatura
- `_is_actionable_match()` poziva `evidence_from_tariff_decision(...)` i postavlja
  `match.evidence`
- `TariffValidationDialog._make_row()` prikazuje novi label
  "Status dokaza: `<confidence_value>`"
- Sve izmjene mirrorovane u `dist_client/` (runtime logika)
- `tests/unit/test_evidence_model.py` — 5 testova, po jedan za svaki
  `DecisionConfidence` status

## Kako je urađeno

**Mapiranje `decision_outcome` → `DecisionConfidence`** (samo za historijske tarifne
prijedloge, Faza 1):

| decision_outcome | supplier_match | DecisionConfidence | DecisionSource |
| --- | --- | --- | --- |
| `show_strong` | `True` | `confirmed_from_same_exporter_history` | `exporter_history` |
| `show_strong` | `False` | `suggested_by_similarity` | `similarity` |
| `show_weak` | `True` | `weak_guess` | `exporter_history` |
| `show_weak` | `False` | `weak_guess` | `similarity` |
| `suppress` / ostalo | — | `unknown` | `tariff_database` |

`confirmed_from_document` se NE generiše iz ovog toka (rezervisano za buduće faze —
podaci potvrđeni iz učitanih dokumenata, npr. EUR.1/PE2). Testirano direktno preko
`build_evidence()`.

**GitNexus impact analiza prije izmjene:**

| Simbol | Risk | Napomena |
| --- | --- | --- |
| `TariffHistoryMatch` | MEDIUM (12 impacted) | sve IMPORTS lanci, additivno polje ne kvari ništa |
| `_is_actionable_match` | **HIGH** (7 impacted, 1 direktan) | upozorenje korisniku — izmjena je SAMO dodavanje novog atributa, ne mijenja postojeći return/`decision_reason`/`decision_outcome`/`decision_score` |
| `_make_row` | LOW (2 impacted) | dodavanje labela, bez promjene postojećih |

`gitnexus_detect_changes(scope=all)` nakon izmjene: `risk_level: low`,
`affected_processes: []`.

## Zašto

Plan zahtijeva da odluke agenta budu dokazive/objašnjive/testabilne, sa LLM-om strogo
kao prezentacionim slojem (nikad izvor dokaza). `TariffHistoryMatch`/`TariffDecision`
već imaju ad-hoc vokabular (`decision_outcome` = show_strong/show_weak/suppress) koji
ostaje netaknut (CRITICAL risk za `decide_tariff_match`, 11 zavisnosti — ne dirati
signaturu). `Evidence` je dodatni, deklarativni sloj koji standardizuje vokabular za
SVE faze (2/3/6 će ga koristiti za document-based i similarity-based dokaze), bez
ikakvog rizika za postojeću logiku jer je čisto additivan.

Provjera `origin/dev` grane (ranija sesija) potvrdila da ni `dev` ni `windows` nemaju
ovaj vokabular — implementacija ide od nule, faza po fazu, svaka faza poseban commit
(po instrukciji korisnika "Kreni od Faze 1 pa dalje").

## Commitovi

| Hash | Poruka |
| --- | --- |
| `e73bb01` | chore(gitnexus): osvjezi indeks brojeve i ukloni BOM iz AGENTS.md/CLAUDE.md |
| `eb2b044` | feat(agent): Evidence model za izvor i pouzdanost tarifnih prijedloga (Faza 1) |

## Testovi

- `python -m py_compile` — čisto na svih 6 izmijenjenih/novih `.py` fajlova (root + dist_client)
- `pytest tests/unit/test_evidence_model.py` — 5/5 prošlo
- `pytest tests/unit/test_historical_tariff_validation.py tests/unit/test_tariff_validation_dialog.py`
  — 33/33 prošlo (regresija — postojeći testovi netaknuti)

## Šta nije urađeno / sljedeći koraci

Faze 2 (LLM strogo prezentacioni sloj), 3 (istorijski prijedlozi striktno po
izvozniku — provjeriti da li postojeći `WHERE supplier ILIKE %s` zadovoljava plan),
4+8 (tool-first tok + 402/429 LLM fallback) i 6 (bogatiji UI prikaz izvora/pouzdanosti)
nisu rađene u ovoj fazi — slijede u zasebnim commitovima.
