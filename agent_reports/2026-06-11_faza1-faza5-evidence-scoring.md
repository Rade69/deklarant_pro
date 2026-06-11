# Agent Report — Faza 1 i Faza 5: evidence model i scoring

**Datum:** 2026-06-11
**Branch:** `windows`
**Scope:** Carinski Agent evidence/scoring model

## Kontekst

Plan za unapređenje Carinskog Agenta traži da svaka preporuka ima dokazni trag i
jedinstven score. U kodu je već postojao `services/agent/validation/evidence_model.py`,
pa sam ga proširio umjesto da uvodim novi paralelni model.

## Šta je urađeno

- `Evidence` sada ima `score`, `score_category`, `should_recommend`, `auto_applicable` i `to_dict()`.
- Dodan je `DecisionScoreCategory` sa pragovima iz plana:
  - `95-100`: `confirmed`
  - `85-94`: `strong_history`
  - `70-84`: `needs_review`
  - `50-69`: `weak_informational`
  - `<50`: `hidden`
- `DecisionSource` je proširen sa `PARSER`, jer plan traži eksplicitan izvor za parser.
- `build_evidence()` ostaje kompatibilan sa postojećim pozivima, ali prima opcioni `score`.
- Ako se pokuša napraviti potvrđen dokaz iz `DecisionSource.LLM`, model ga spušta na `weak_guess`.
- Mirror izmjena je urađena i u `dist_client/services/agent/validation/evidence_model.py`.

## Zašto ovako

Najvažnija odluka je da se ne uvodi novi model. Postojeći `Evidence` je već bio korišten
u istorijskoj validaciji tarifa, dijalogu za validaciju i provjeri povlastica. Proširenje
postojećeg modela smanjuje rizik i daje jedan izvor istine za Fazu 1, Fazu 5 i kasniji
Agent UI prikaz.

`LLM` je ostavljen kao mogući izvor radi transparentnosti, ali ne može biti potvrđen dokaz.
To čuva arhitektonsko pravilo iz plana: LLM smije objasniti, ali ne smije biti izvor carinske odluke.

## GitNexus

- `Evidence` root: MEDIUM impact, direktni potrošači su validator, historical search i tariff validation dialog.
- `build_evidence` root: HIGH impact zbog centralne fabrike i indirektnih procesa validacije.
- Promjena je zato urađena kompatibilno: postojeći potpis je samo proširen opcionim parametrom.

## Testovi

Pokrenuto:

```powershell
python -m pytest tests/unit/test_evidence_model.py tests/unit/test_historical_tariff_validation.py tests/unit/test_tariff_validation_dialog.py -q
python -m py_compile services\agent\validation\evidence_model.py dist_client\services\agent\validation\evidence_model.py tests\unit\test_evidence_model.py
```

Rezultat:

- `68 passed`
- `py_compile` bez greške

## Otvoreno za naredne faze

- Faza 6 treba vizuelno koristiti `score_category`, ne samo tekstualni label.
- Faza 4 nastavak može koristiti `Evidence.to_dict()` kao dio strukturisanog tool rezultata.
