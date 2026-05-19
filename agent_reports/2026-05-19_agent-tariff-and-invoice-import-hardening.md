# Agent report: tariff intelligence and invoice import hardening

**Datum**: 2026-05-19  
**Grana**: dev  
**Zadatak**: Poboljsati agentovu analizu tarifa, popraviti Rub.44 PE konflikt, sprijeciti Blagic-Loren duplikate i sortirati fakture po broju

---

## Sta je uradjeno

1. **Agent analiza tarifa**
   - `analiziraj_tarifne` sada koristi `product_tariff_mapping`, `user_feedback`, `zvanicna_tarifa` i SQLite `tariff_doc_history`.
   - Rezultat vise nije samo frekvencija tarife, nego status po stavci: `OK`, `PROVJERI`, `RIZIK`.
   - Ranije prihvaceni ili odbijeni feedback korisnika ima prioritet nad slabijim historijskim kandidatima.

2. **Rub.44 PE konzistentnost**
   - Ako master polje Rub.44.4 ima npr. `PE2 266VP-2026`, pomocna polja vise ne smiju zadrzati stale `PE1`.
   - `Rb.44 P.D.` vise ne prikazuje pogresan `PE1` iz zaglavlja za stavku koja ima `PE2`.
   - Sinhronizacija zaglavlja daje prednost `attached_document4` nad starim pomocnim PE poljima.

3. **Blagic-Loren agent import**
   - `ProcessingWorker` prenosi `consumed_paths` u `FileItem`.
   - `AgentController` prije upisa u draft izbacuje Excel-only rezultat ako postoji kombinovani PDF+Excel rezultat za isti broj fakture.
   - Sprijecen scenario gdje Excel-only redovi bez iznosa udju zajedno sa kombinovanim PDF redovima.

4. **Sortiranje faktura**
   - Agentski uvoz sada koristi prirodni redoslijed brojeva faktura: `99VP` prije `100VP`, `262VP` prije `268VP`.
   - `ProcessingWorker` emituje rezultate u sortiranom redoslijedu.
   - `AgentController` dodatno sortira finalne `Completed` fakture prije dijaloga i prije punjenja `draft.invoice_lines`.
   - Rucni grupni uvoz u Faktura tabu sortira finalne zapise po stvarnom broju fakture koji parser izvuce.

---

## Ključne izmjene

- `services/agent/chat/tariff_history_analysis_service.py`
  - dodata per-stavka analiza tarifa, kandidati iz PG baze, feedback signal i HTML izvjestaj.

- `gui/tabs/agent/widgets/processing_worker.py`
  - prirodni sort faktura i prenos `consumed_paths`.

- `gui/tabs/agent/agent_controller.py`
  - dedupe kombinovanih faktura i sortiranje finalnog uvoza.

- `gui/tabs/faktura_view.py`
  - rucni grupni uvoz sortira `final_records` prije upisa u tabelu.

- `gui/tabs/naimenovanja_view.py`
  - ciscenje stale PE dokumenata iz pomocnih rub.44 polja.

- `gui/tabs/zaglavlje_controller.py`
  - PE sinhronizacija ignorise pomocna PE polja kad postoji master PE dokument.

---

## Testovi

Pokrenuto:

```bash
python -m pytest tests/ -q
```

Rezultat:

```text
465 passed, 6 skipped
```

Dodatne ciljane provjere:

- Blagic-Loren 268 par: Excel ostaje `Skipped`, PDF combined ulazi sa 21 stavkom i ukupnim iznosom `5270.60`.
- Sortiranje fajlova: `262VP-2026.xlsx`, `262VP-2026.pdf`, `268VP-2026.xlsx`, `268VP-2026.pdf`.
- Rucni sort finalnih zapisa: `99VP-2026`, `100VP-2026`, `262VP-2026`, `268VP-2026`.

---

## Rizik

GitNexus `detect_changes` prijavljuje visok agregatni rizik jer radno stablo sadrzi vise izmjena u agent import toku, Rub.44 logici i tariff analysis servisu. Pojedinacni impact prije izmjena za glavne simbole bio je LOW ili MEDIUM, a kompletan test paket prolazi.

Nevezane izmjene u `AGENTS.md` i `CLAUDE.md` nisu dio ovog commita.
