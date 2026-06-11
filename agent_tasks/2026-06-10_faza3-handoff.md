# Faza 3 — Istorijski prijedlozi tarifa — HANDOFF za sljedećeg agenta

> Prethodna sesija je prekinuta zbog potrošenih tokena. Analiza je završena,
> **NIJE napravljena nijedna izmjena koda**. Ovaj fajl sadrži tačan plan za
> nastavak. Plan-fajl: `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`
> (Faza 3, linije 133-161). Faza 1 i Faza 2 su završene (commits `eb2b044`,
> `e73bb01`, `5f6e455`, `048534e`, `7f790cd`, `8f8832a`).

## 0. Šta prvo pročitati

1. `AGENTS.md` i `docs/CONTEXT.md` (obavezno prije svakog zadatka — checklist u planu, linije 339-346)
2. `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md` linije 133-161 (puna specifikacija Faze 3) i linije 328-346 ("Zabranjeno" + checklist)
3. Fajlove navedene u sekciji 2 ovog dokumenta (već pročitani u prethodnoj sesiji, sadržaj relevantnih dijelova je ovdje citiran)

## 1. Analiza — šta JE VEĆ riješeno (ne dirati)

Od 3 glavna mehanizma Faze 3, **2 već postoje** iz ranijih sesija:

1. **"Nema fallback-a na drugog izvoznika"** — već implementirano u
   `services/agent/validation/historical_tariff_search_service.py::_search_one()`,
   commit `a034fc7` (2026-05-23), dokumentovano u
   `agent_reports/2026-05-23_historical-tariff-exporter-filter.md`. Kad je
   `_supplier_key(izvoznik)` neprazan, `_execute()` dodaje `AND supplier ILIKE %s`
   bez fallback-a na druge izvoznike. **Ne diraj ovaj fajl.**
2. **Exporter-scoped istorijsko učenje** — `services/agent/learning/exporter_xml_indexer.py`,
   `services/agent/learning/historical_learning_service_safe.py`,
   `services/agent/tariff/tariff_suggestion_service.py::_get_historical_candidates`
   — sva tri već filtriraju po `exporter_normalized`. **Ne diraj ove fajlove.**

Van scope-a (flagovano, ne dirati ovu fazu):
- `services/agent/chat/tariff_history_analysis_service.py::_score_mapping_row` —
  `supplier_match` je samo +10 bonus (ne hard filter), `_render_row` ne prikazuje
  `candidate.supplier`. Posebna feature (chat "analiziraj tarifne", OK/PROVJERI/RIZIK
  vokabular). Ostaviti za buduću fazu, eventualno spomenuti u "Šta nije urađeno".
- Nekonzistentan vokabular povlastica (EUPR/CEFTAR vs EUP/CEFTAP) — pre-existing,
  van scope-a (već flagovano u Fazi 2).

## 1.5 Tip promjene / Prihvatljiv ishod / Nivo dozvole (scope lock po promjeni)

Prije svake izmjene prijaviti korisniku rizik u formatu:
"GitNexus impact za `<simbol>` je `<risk>`: zavise od njega `<ko/koliko simbola>`.
Promjena je mala po obimu ali `<visoka/niska>` po sistemskoj važnosti jer `<razlog>`.
Scope ostaje ograničen na: `<šta NE diraš>`. Obavezni izlaz: `<šta MORA postojati>`."

| Promjena | Tip promjene | Prihvatljiv ishod (scope lock) | Nivo dozvole |
| --- | --- | --- | --- |
| 1 — `evidence_from_tariff_decision` | mapping correction (centralno mapiranje dokaza) | `decide_tariff_match()` i istorijski search ostaju netaknuti; mijenja se SAMO Evidence mapiranje za izvore bez pravog supplier-a (HISTORIJA/+/A/prazno); postojeći testovi sa smislenim izvorom (npr. "MEDICO PHARM SERVIS") moraju proći nepromijenjeni | test gate required + mandatory GitNexus impact (sa `target_uid`) prije izmjene — centralna funkcija, koriste je i validation service i GUI dijalog |
| 2 — `tariff_confidence_label` + `_TARIFF_CONFIDENCE_LABELS` | additive (novi helper) | čisto dodatna funkcija, ne mijenja postojeće pozivaoce u `evidence_model.py` | draft change only dok se ne poveže sa Promjenom 3 |
| 3 — `tariff_validation_dialog.py` (3a/3b/3c) | GUI safety patch (uklanja zavaravajući prikaz "nepoznat izvoznik" kao legitimnog izvora) | ponašanje "Prihvati jake" za postojeće show_strong/supplier_match slučajeve OSTAJE ISTO; dodaje se SAMO dodatno isključenje za UNKNOWN evidence; signal `tariffs_accepted` i njegov format ostaju nepromijenjeni | mandatory review (tekst na srpskom + boje) + test gate required |
| 4 — testovi (sva 3 fajla) | safety patch (test coverage) | samo dodaje/proširuje testove, ne mijenja produkcijski kod | no auto-merge dok testovi za 1-3 ne prođu |

**Generalni scope lock za preostali dio Faze 3**: ne dirati `decide_tariff_match()`
(tariff_decision_model.py), `_search_one()`/`_execute()`
(historical_tariff_search_service.py), niti `exporter_xml_indexer.py` /
`historical_learning_service_safe.py` — već provjereni kao usklađeni (sekcija 1).
Jedini dozvoljeni dodatak u toj zoni je NOVI izolacioni test (Promjena 4, drugi dio)
koji ne mijenja postojeći kod, samo ga testira.

## 2. PREOSTALI POSAO — preostali GAP koji treba zatvoriti

**Problem**: U `gui/tabs/agent/widgets/tariff_validation_dialog.py` i dalje se
prikazuje "Izvor: nepoznat izvoznik" kao da je legitiman izvor (linije ~151-160),
i `evidence_from_tariff_decision()` ne provjerava da li je `source` smislen prije
nego što vrati `SUGGESTED_BY_SIMILARITY`/`WEAK_GUESS` — pa npr. `source="HISTORIJA"`
(placeholder) i dalje izgleda kao "srednji"/"slab" prijedlog umjesto `unknown`.
Izvještaj `agent_reports/2026-06-06_windows-gui-bugfixes.md` (sekcija 11) tvrdi da
je ovo već popravljeno, ali trenutni kod to opovrgava — popravka nikad nije
implementirana ili je vraćena.

### Promjena 1 — `services/agent/validation/evidence_model.py` (+ `dist_client/` mirror)

Importovati `has_meaningful_source` iz `services.agent.validation.tariff_decision_model`
(funkcija na linijama 193-195 tog fajla: `bool(source and source not in {"-", "—", "+", "A", "HISTORIJA"})`).
Nema cirkularnog importa — `tariff_decision_model.py` ne importuje `evidence_model`.

U `evidence_from_tariff_decision()` (trenutno linije 67-105) dodati PRVU provjeru,
PRIJE grananja po `decision_outcome`:

```python
from services.agent.validation.tariff_decision_model import has_meaningful_source

def evidence_from_tariff_decision(
    decision_outcome: str,
    supplier_match: bool,
    usage_count: int,
    source: str,
) -> Evidence:
    """Mapira ishod decide_tariff_match() (show_strong/show_weak/suppress) na Evidence."""
    data = {"usage_count": usage_count, "source": source, "supplier_match": supplier_match}

    if not has_meaningful_source(source):
        return build_evidence(
            DecisionSource.TARIFF_DATABASE,
            DecisionConfidence.UNKNOWN,
            "Istorijski zapis nema poznat izvor (izvoznik/XML) — prijedlog se ne moze potvrditi kao istorija.",
            data,
        )

    if decision_outcome == "show_strong":
        ... # ostatak nepromijenjen
```

Ostatak funkcije (show_strong / show_weak / suppress grane) ostaje **nepromijenjen**.

### Promjena 2 — novi helper u istom fajlu (+ mirror)

Dodati mapu i funkciju za UI labelu (jak/srednji/slab/nepoznat):

```python
_TARIFF_CONFIDENCE_LABELS: dict[DecisionConfidence, str] = {
    DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY: "jak",
    DecisionConfidence.SUGGESTED_BY_SIMILARITY: "srednji",
    DecisionConfidence.WEAK_GUESS: "slab",
    DecisionConfidence.UNKNOWN: "nepoznat",
}


def tariff_confidence_label(evidence: Evidence) -> str:
    """Mapira Evidence.confidence na jak/srednji/slab/nepoznat (Faza 3)."""
    return _TARIFF_CONFIDENCE_LABELS.get(evidence.confidence, "nepoznat")
```

`CONFIRMED_FROM_DOCUMENT` nije u mapi (ne pojavljuje se u tarifnim prijedlozima,
samo kod povlastica) — `.get(..., "nepoznat")` fallback je dovoljan.

### Promjena 3 — `gui/tabs/agent/widgets/tariff_validation_dialog.py` (+ `dist_client/` mirror)

Dodati import na vrh fajla:
```python
from services.agent.validation.evidence_model import DecisionConfidence, tariff_confidence_label
```

**3a. Source label** (`_make_row`, trenutno linije ~151-160):

Trenutni kod:
```python
        # Meta info — supplier ima prednost, fallback na source (XML filename)
        supplier = (match.source or '').strip()
        if not supplier:
            source_lbl = "<span style='color:#aaa; font-size:13px;'>nepoznat izvoznik</span>"
        elif supplier.lower().endswith('.xml'):
            xml_name = supplier.rsplit('.', 1)[0][:40]
            source_lbl = f"<span style='color:#888; font-size:13px;'>XML: {xml_name}</span>"
        else:
            source_lbl = f"<span style='color:#374151; font-size:13px; font-weight:600;'>{supplier[:45]}</span>"
```

Zamijeniti sa (ključno: `evidence.confidence is DecisionConfidence.UNKNOWN` hvata i
slučaj kad `match.source == "HISTORIJA"`/`"+"`/`"A"` itd. — ne samo prazan string;
`evidence is None` fallback čuva staro ponašanje za testne mock-ove bez `.evidence`):

```python
        # Meta info — supplier ima prednost, fallback na source (XML filename)
        evidence = getattr(match, "evidence", None)
        is_unknown_source = (
            evidence.confidence is DecisionConfidence.UNKNOWN
            if evidence is not None
            else not (match.source or '').strip()
        )
        supplier = (match.source or '').strip()
        if is_unknown_source or not supplier:
            source_lbl = "<span style='color:#b45309; font-size:13px;'>izvor nepoznat — nije potvrđena historija</span>"
        elif supplier.lower().endswith('.xml'):
            xml_name = supplier.rsplit('.', 1)[0][:40]
            source_lbl = f"<span style='color:#888; font-size:13px;'>XML: {xml_name}</span>"
        else:
            source_lbl = f"<span style='color:#374151; font-size:13px; font-weight:600;'>{supplier[:45]}</span>"
```

Pažnja: `evidence` se ovdje izračunava prije nego što se koristi niže u `evidence_label`
bloku (3b) — provjeriti da se varijabla ne računa duplo (samo jednom, na vrhu, i
ponovo koristi niže).

**3b. Evidence/confidence label** (trenutno linije ~176-183):

Trenutni kod:
```python
        evidence_label = None
        evidence = getattr(match, "evidence", None)
        if evidence is not None:
            evidence_label = QLabel(
                f"<span style='color:#9ca3af; font-size:12px;'>"
                f"Status dokaza: {evidence.confidence.value}</span>"
            )
            evidence_label.setTextFormat(Qt.RichText)
```

Zamijeniti sa (koristi `evidence` izračunat u 3a, ne računati ponovo):
```python
        evidence_label = None
        if evidence is not None:
            evidence_label = QLabel(
                f"<span style='color:#9ca3af; font-size:12px;'>"
                f"Pouzdanost prijedloga: <b>{tariff_confidence_label(evidence)}</b></span>"
            )
            evidence_label.setTextFormat(Qt.RichText)
```

**3c. `_can_accept_all`** (trenutno linije ~340-341):

Trenutni kod:
```python
    def _can_accept_all(self, match) -> bool:
        return not self._is_weak_match(match)
```

Zamijeniti sa:
```python
    def _can_accept_all(self, match) -> bool:
        if self._is_weak_match(match):
            return False
        evidence = getattr(match, "evidence", None)
        if evidence is not None and evidence.confidence is DecisionConfidence.UNKNOWN:
            return False
        return True
```

### Promjena 4 — testovi

**`tests/unit/test_evidence_model.py`**:
- Postojeći `test_suggested_by_similarity` (linije 39-49) koristi `source="HISTORIJA"`
  i očekuje `SUGGESTED_BY_SIMILARITY`/`SIMILARITY`. Nakon Promjene 1 ovo VIŠE NE VAŽI
  (HISTORIJA nije meaningful source → UNKNOWN). **Promijeniti test**: zamijeniti
  `source="HISTORIJA"` sa nečim smislenim npr. `source="MEDICO PHARM SERVIS"` (uz
  `supplier_match=False`) — i dalje testira SUGGESTED_BY_SIMILARITY granu.
- Dodati novi test `test_unknown_source_literal_historija_is_unknown`:
  ```python
  def test_unknown_source_literal_historija_is_unknown():
      evidence = evidence_from_tariff_decision(
          decision_outcome="show_strong",
          supplier_match=False,
          usage_count=8,
          source="HISTORIJA",
      )
      assert evidence.confidence is DecisionConfidence.UNKNOWN
      assert evidence.source is DecisionSource.TARIFF_DATABASE
      assert evidence.requires_confirmation is True
  ```
  (provjeriti i sa `source=""`, `source="+"`, `source="A"` — opciono parametrizovati)
- Dodati test za `tariff_confidence_label()` — provjeriti mapiranje za sva 4 stanja
  (CONFIRMED_FROM_SAME_EXPORTER_HISTORY→"jak", SUGGESTED_BY_SIMILARITY→"srednji",
  WEAK_GUESS→"slab", UNKNOWN→"nepoznat"). Import `tariff_confidence_label` u vrh fajla.
- Provjeriti `test_unknown_for_suppressed_decision` (linije 65-75, `source=""`) —
  i dalje treba proći (UNKNOWN/TARIFF_DATABASE), samo sad se vraća iz nove rane
  provjere umjesto iz `suppress` grane — rezultat je isti, test ne treba mijenjati.

**`tests/unit/test_historical_tariff_validation.py`** — novi test za acceptance
kriterijum #1 ("dva izvoznika, ista šifra proizvoda, ne curi tuđa tarifa"):

Napraviti fake DB cursor/connection koji simulira `supplier ILIKE %s` filter na
malom in-memory skupu redova (dva reda sa istim `naziv_robe`, ali različitim
`supplier` i `commodity_code`), monkeypatch-ovati `database.db.get_db_connection`
(lokalni import unutar `_search_one`) i `HistoricalTariffSearchService._tariff_exists`
(staticmethod, monkeypatch preko instance attributa: `monkeypatch.setattr(svc, "_tariff_exists", lambda code: True)`).

Skica fake cursor-a — `execute(sql, params)` parsira: zadnji param je LIMIT, ako
`"supplier ilike" in sql.lower()` onda je pretposljednji param supplier pattern
(`%TERM%`), ostalo su `naziv_robe ILIKE` patterni. `fetchall()` vraća redove koji
zadovoljavaju sve `naziv_robe` pattern-e (substring, case-insensitive) i (ako
postoji) supplier pattern.

Test podaci — **VAŽNO**: koristiti različite ključne riječi za izvoznike (npr.
`"BLAGIC LOREN DOO"` → `_supplier_key()` = `"BLAGIC"`, i `"MEDICO PHARM SERVIS"` →
`"MEDICO"`), ne slične prefikse (npr. NE "EXPORTER ALPHA"/"EXPORTER BETA" — oba bi
sadržavala "EXPORTER" i test ne bi razlikovao izvoznike).

Primjer:
```python
rows = [
    {"naziv_robe": "GREJAC SPIRALA 220V", "commodity_code": "85167100",
     "supplier": "BLAGIC LOREN DOO", "usage_count": 10, "zemlja_porijekla": "DE", "source": ""},
    {"naziv_robe": "GREJAC SPIRALA 220V", "commodity_code": "73239300",
     "supplier": "MEDICO PHARM SERVIS", "usage_count": 50, "zemlja_porijekla": "TR", "source": ""},
]
# _search_one("GREJAC SPIRALA 220V", izvoznik="BLAGIC LOREN DOO")
#   -> tačno 1 match, tarifni_broj_historijski == "85167100" (NE "73239300")
# _search_one("GREJAC SPIRALA 220V", izvoznik="MEDICO PHARM SERVIS")
#   -> tačno 1 match, tarifni_broj_historijski == "73239300" (NE "85167100")
```

**`tests/unit/test_tariff_validation_dialog.py`** — postojeći `_match()` helper
(SimpleNamespace) NEMA `.evidence` atribut (`getattr(match, "evidence", None)` →
`None`, što čuva staro ponašanje — provjeri da Promjena 3a/3c rade ispravno i kad
je `evidence is None`). Proširiti helper sa opcionim `evidence=None` parametrom i
dodati test(ove) koji:
- kreiraju match sa `evidence=Evidence(source=DecisionSource.TARIFF_DATABASE, confidence=DecisionConfidence.UNKNOWN, ...)` i provjeravaju da se prikazuje "izvor nepoznat — nije potvrđena historija" i "nepoznat" label
- provjeravaju da `_can_accept_all()` vrati `False` za UNKNOWN evidence (čak i ako `decision_outcome != "show_weak"`)
- provjeravaju da match sa `evidence.confidence = CONFIRMED_FROM_SAME_EXPORTER_HISTORY` prikazuje "jak"

## 3. GitNexus

`mcp__gitnexus__impact` na `evidence_from_tariff_decision` i `_can_accept_all` je
vratio `"status": "ambiguous"` — po 2 kandidata (root fajl + `dist_client/` mirror,
score 0.94-0.96). Ovo je OČEKIVANO (mirror fajlovi imaju identične simbole).
Ponovi poziv sa `target_uid` da dobiješ konkretan rezultat, npr.:

```
mcp__gitnexus__impact(
  target="evidence_from_tariff_decision",
  direction="upstream",
  target_uid="Function:services/agent/validation/evidence_model.py:evidence_from_tariff_decision"
)
mcp__gitnexus__impact(
  target="_can_accept_all",
  direction="upstream",
  target_uid="Method:gui/tabs/agent/widgets/tariff_validation_dialog.py:TariffValidationDialog._can_accept_all#1"
)
```

Prijavi korisniku risk nivo prije izmjene (po CLAUDE.md, stani ako je HIGH/CRITICAL),
koristeći format iz sekcije 1.5 (tip promjene / prihvatljiv ishod / nivo dozvole).
Na osnovu Faze 1/2 iskustva, oba simbola su vjerovatno LOW/MEDIUM (ograničen broj
poziva unutar `historical_tariff_search_service.py` odnosno `tariff_validation_dialog.py`),
ali `evidence_from_tariff_decision` je centralno mapiranje koje koriste i validacija
i GUI i testovi — ako GitNexus pokaže veći broj zavisnih simbola/procesa nego
očekivano, tretirati kao CRITICAL i stati prije izmjene dok korisnik ne potvrdi.

## 4. Redoslijed rada

1. Pročitati `AGENTS.md`, `docs/CONTEXT.md` (checklist)
2. GitNexus impact (sekcija 3) — prijaviti risk
3. Promjena 1 + 2 u `services/agent/validation/evidence_model.py`, zatim kopirati
   identično u `dist_client/services/agent/validation/evidence_model.py`
4. Promjena 3 (3a+3b+3c) u `gui/tabs/agent/widgets/tariff_validation_dialog.py`,
   zatim mirror u `dist_client/gui/tabs/agent/widgets/tariff_validation_dialog.py`
5. Promjena 4 — testovi (3 fajla)
6. `python -m py_compile` na svih 4 izmijenjenih + 4 mirror/test fajla
7. `pytest tests/unit/test_evidence_model.py tests/unit/test_historical_tariff_validation.py tests/unit/test_tariff_validation_dialog.py -v`
8. `mcp__gitnexus__detect_changes(scope="all")` — provjeriti risk_level i affected_processes
9. Git commit(ovi) — predlog grupisanja:
   - `fix(agent): evidence_from_tariff_decision vraca unknown za izvore bez pravog dokaza (HISTORIJA/+/A/prazno)` — evidence_model.py (root+dist_client) + test_evidence_model.py
   - `feat(agent): dijalog validacije prikazuje jak/srednji/slab/nepoznat umjesto raw confidence i 'nepoznat izvoznik'` — tariff_validation_dialog.py (root+dist_client) + test_tariff_validation_dialog.py
   - `test(agent): test za izolaciju istorijskih tarifa po izvozniku (dva izvoznika, ista sifra)` — test_historical_tariff_validation.py
   - Sve sa `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`
10. Memorija: novi fajl `2026-06-10_faza3-istorijski-tarife-izvor-carinski-agent.md` u
    `C:\Users\38765\.claude\projects\c--Users-38765-Desktop-deklarant-pro\memory\`
    + update `MEMORY.md` indeksa. Linkovati na `[[carinski-agent-plan-faza1-pocetak]]`.
11. Agent report: `agent_reports/2026-06-10_faza3-istorijski-tarife-izvor.md` —
    format Šta/Kako/Zašto + tabela commitova (vidi `agent_reports/2026-06-10_faza2-povlastice-porijeklo.md` kao šablon)
12. Ažurirati status Faze 3 u `agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md`
    sa "ZAVRŠENO" + commit hashevi, i u sekciji "Šta nije urađeno" spomenuti
    `tariff_history_analysis_service.py` flag (sekcija 1 ovog dokumenta)
13. `gitnexus analyze` ako index zastario (provjeriti nakon commit-a)
14. Output format: `STATUS: OK | PARCIJALNO | BLOKIRANO` + IZMIJENJENI FAJLOVI +
    ŠTA JE URAĐENO + ŠTA NIJE URAĐENO + PITANJA (plan linije 350-358)

## 5. Napomene / rizici

- `evidence` varijabla u `_make_row` se sad mora izračunati JEDNOM (na vrhu, prije
  3a) i koristiti i u 3a i u 3b — ne dupliraj `getattr(match, "evidence", None)`.
- Pazi da Promjena 1 NE mijenja `decide_tariff_match()` (tariff_decision_model.py) —
  `should_show`/suppress logika ostaje ista, mijenja se SAMO mapiranje u Evidence.
- `dist_client/` mirroring: provjeri `Read` oba fajla prije `Edit` da potvrdiš da
  su trenutno identični (kao u Fazi 1/2), pa primijeni identičnu izmjenu.
