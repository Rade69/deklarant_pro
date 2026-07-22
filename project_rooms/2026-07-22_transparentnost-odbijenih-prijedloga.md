# Transparentnost za ODBIJENE istorijske prijedloge

## Cilj

Simetrično sa `_notify_auto_applied_tariffs()` (za ranije PRIHVAĆENE prijedloge, već
implementirano) — dodati vidljivost i za ranije ODBIJENE prijedloge. Trenutno
`HistoricalTariffSearchService.validate_lines()` u `feedback_action == "reject"` grani
potpuno tiho `continue`-uje — korisnik nikad ne vidi DA je nešto preskočeno niti ZAŠTO.

## Pogođeno

- `HistoricalTariffSearchService.validate_lines` — HIGH (30 impactedCount, transitivno kroz
  `chat_intent_handler._prikaz_tarifnih_trenutnih`, `scripts/agent_tariff_eval_report.py`).
  Izmjena: dodaje se NOVI instance atribut `self.last_auto_rejected` (analogan postojećem
  `self.last_auto_applied`) — POVRATNA VRIJEDNOST metode (`results` lista) i njen potpis
  ostaju POTPUNO nepromijenjeni. Nijedan postojeći pozivalac ne čita `last_auto_rejected`
  danas, pa je ovo aditivna izmjena bez efekta na postojeće ponašanje.
- `FakturaView._run_historical_tariff_validation` — LOW (potpis nepromijenjen).

## Plan

1. `HistoricalTariffSearchService.__init__`: dodati `self.last_auto_rejected: list[tuple[int, str]] = []`.
2. `validate_lines()`: resetovati `self.last_auto_rejected = []` na početku (kao
   `last_auto_applied`); u `reject` grani dodati `self.last_auto_rejected.append((idx,
   best.tarifni_broj_historijski))` prije `continue`.
3. `FakturaView._run_historical_tariff_validation`: dohvatiti `auto_rejected = getattr(svc,
   'last_auto_rejected', [])`, remapirati indekse (isti obrazac kao `auto_applied` kad je
   `row_indexes is not None`), i pozvati novu `_notify_auto_rejected_tariffs(auto_rejected)`
   SAMO kad `not auto` — simetrično sa `_notify_auto_applied_tariffs`.

## Šta NE dirati

- `_feedback_action()`, `tariff_feedback_service.py`, `user_feedback` tabela — logika
  odlučivanja accept/reject se ne mijenja, samo se dodaje VIDLJIVOST postojeće odluke.
- `_notify_auto_applied_tariffs()` — ostaje netaknuta, nova metoda je zasebna.
- Povratna vrijednost `validate_lines()` (`results` lista) — mora ostati identična za sve
  postojeće pozivaoce (`scripts/agent_tariff_eval_report.py`, `chat_intent_handler.py`).

## Konflikti

Nema poznatih.
