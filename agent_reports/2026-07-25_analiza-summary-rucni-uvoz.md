# Podjela po zemljama u status baru — nedostajala kod ručnog uvoza

## Datum
2026-07-25

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/faktura_view.py` + `dist_client/` mirror (`_update_status_bar`)
- `tests/unit/test_faktura_view_status_bar.py` (3 nova testa)
- `project_rooms/2026-07-25_analiza-summary-rucni-uvoz.md` (HIGH-risk plan)
- `docs/CONTEXT.md` (§60)

## Status izvora
Korisnička prijava putem dva screenshot-a statusne trake ("Neprovjereno" +
"Assembly: N/A" + "🌍 DE:54 | FR:24 | AT:5 | IT:5 | GB:2"), sa tvrdnjom:
"Prilikom ručnog uvoza faktura nema podjele po zemljama, kao kod agentskog
uvoza faktura." Nije bilo ranijeg agent_report/memory zapisa o ovom
ponašanju — istraženo od nule čitanjem koda.

## GitNexus impact
- `_update_status_bar` (upstream): **HIGH** rizik, impactedCount 30, 21
  direktan pozivalac (skoro sve akcije u Faktura tabu — add/delete/undo/
  redo/import/export/validate/auto-fill...).
- Prije izmjene napisan `project_rooms/2026-07-25_analiza-summary-rucni-
  uvoz.md` (AGENTS.md HIGH-risk protokol) — eksplicitno navedeno da je
  visoka ocjena posljedica GitNexus-ove mjere "ko poziva ovu funkciju", ne
  stvarnog rizika same izmjene (aditivan dvolinijski latch, bez dirat
  postojeću logiku bilo kojeg drugog labela).
- `detect_changes(scope=all)` POSLIJE izmjene: risk_level **LOW**, 26
  promijenjenih simbola, 3 fajla, 0 affected_processes — potvrđuje da je
  stvarni blast radius mali, kako je predviđeno u planu.

## Šta je urađeno
`FakturaView._update_status_bar()` sad postavlja `self._analysis_summary_
auto = True` (jednosmjerni latch, samo ako je trenutno False) čim
`item_count > 0`, PRIJE nego što se pozove `_refresh_analysis_summary_
from_draft()` na kraju iste funkcije. Time se segment "🌍 DE:54 | FR:24 |
..." počinje prikazivati bez obzira na to da li su stavke stigle ručnim ili
Agent uvozom (ili čak ručnim unosom reda po reda).

## Zašto je urađeno
`lbl_analysis` segment je bio uslovljen flagom koji je postavljala
ISKLJUČIVO `AgentController._proactive_analysis()` nakon Agent uvoza
(`fw.set_analysis_summary(...)`, `gui/tabs/agent/agent_controller.py:743`).
Ručni uvoz (`_on_import_finished`, `_process_batch_records` i legacy
varijante) nikad nije pozivao tu metodu, pa je `_refresh_analysis_summary_
from_draft()` uvijek rano izlazila (`if not self._analysis_summary_auto:
return`) — segment nikad nije prikazan za ručni tok. Ovo je čitano kao
previd/gap u dizajnu (docstring `set_analysis_summary()` opisuje TRENUTNI
poziv-obrazac, ne eksplicitnu namjeru isključenja ručnog uvoza), ne kao
namjerno ograničenje — informacija (podjela po zemljama) je izvedena
isključivo iz `draft.invoice_lines`, nema ničeg agent-specifičnog u njoj.

## Kako je urađeno
- Locirano preko grep-a na tačan tekst sa screenshot-a ("Assembly: N/A",
  "Neprovjereno") u `gui/tabs/faktura_view.py`.
- Pročitan cijeli `_update_status_bar()` i `_refresh_analysis_summary_from_
  draft()`/`_build_analysis_summary_from_draft()` da se razumije TAČAN
  gate-mehanizam prije bilo kakve izmjene.
- Pronađen JEDINI poziv `set_analysis_summary()` (grep), potvrđeno da je
  isključivo iz `AgentController._proactive_analysis()`.
- Upoređena agent-ova inline `_proactive_analysis()` logika (koristi
  batch `lines` parametar, bez normalizacije zemlje) sa `FakturaView`-ovom
  `_build_analysis_summary_from_draft()` (čita CIJELI trenutni draft/
  tabelu, normalizuje zemlju na 2-slovni kod regex-om) — potvrđeno da je
  potonja ISPRAVNIJA i da latch-pristup (umjesto pozivanja `set_analysis_
  summary()` sa 4 nova mjesta u ručnom toku) postiže isti efekat sa manje
  koda i bez duplikacije agent-ove manje precizne logike.
- GitNexus impact provjeren PRIJE izmjene (HIGH), plan file napisan po
  AGENTS.md HIGH-risk protokolu, rizik eksplicitno prijavljen prije
  nastavka.

## Šta nije dirano
- `AgentController._proactive_analysis()` — netaknuto, i dalje zove
  `set_analysis_summary()` (sad redundantno, ali bezopasno).
- `lbl_assembly` / "Assembly: N/A" (`self.assembly.master_list_loaded`) —
  potpuno odvojen master-list feature, vidljiv na korisnikovom screenshot-u
  ali NIJE bio predmet prijave (korisnik je eksplicitno naveo "podjela po
  zemljama", ne Assembly status).
- Sve ostale grane/labeli unutar `_update_status_bar()`.

## Verifikacija
- `python -m py_compile` na oba (root + dist_client) — OK.
- 3 nova testa u `tests/unit/test_faktura_view_status_bar.py`:
  latch se uključuje kad ima stavki, NE uključuje se za prazan draft,
  jednosmjeran je (ne gasi već uključen flag).
- Pun test suite: 1138 passed (bilo 1135, +3 nova), isti pre-postojeći 1
  fail/1 error (nepovezani).
- `gitnexus_detect_changes(scope=all)`: risk_level LOW, 0 affected_processes.
- Root vs dist_client diff nakon mirroringa: prazan (bit-identični).

## Pronađeni problemi
Nema novih.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `bf99ef2` | fix(faktura): prikazi podjelu po zemljama i kod rucnog uvoza |

## Rizici / ograničenja
- Latch je permanentan po instanci `FakturaView` (nikad se ne gasi nazad
  na False) — ovo je namjerno (jednom prikazana informacija ostaje
  ažurna/vidljiva), ali znači da nakon "Očisti sve" (prazan draft) segment
  se sakriva (jer `_build_analysis_summary_from_draft` vraća `("", "")` za
  prazan draft) a NE zato što se flag gasi — ako se draft ponovo napuni,
  segment se odmah vraća (flag je i dalje True). Ponašanje provjereno
  logikom, ne dodatno testirano za taj specifičan uzastopni scenario.

## Potreban follow-up
Nema — nalaz je zatvoren.

## Potrebna korisnička potvrda
- Da potvrdi da je "Assembly: N/A" segment (drugi, nepovezani indikator sa
  screenshot-a) namjerno izvan scope-a ove prijave, ili treba li i taj
  segment razjasniti/popraviti u posebnom zadatku.
