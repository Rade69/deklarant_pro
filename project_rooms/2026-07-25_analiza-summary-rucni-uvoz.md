# Analiza summary (podjela po zemljama) nedostaje kod ručnog uvoza

## Cilj
`FakturaView` status bar ima segment `lbl_analysis` (🌍 DE:54 | FR:24 | ...) koji
se prikazuje SAMO ako je `self._analysis_summary_auto == True`. Taj flag se
postavlja isključivo iz `AgentController._proactive_analysis()`
(`gui/tabs/agent/agent_controller.py:743`, `fw.set_analysis_summary(...)`) —
poziva se SAMO nakon Agent uvoza. Ručni uvoz (`_on_import_finished`,
`_process_batch_records` i legacy varijante) nikad ne postavlja ovaj flag,
pa `_refresh_analysis_summary_from_draft()` uvijek rano izlazi
(`if not self._analysis_summary_auto: return`) i segment ostaje skriven.
Korisnik je ovo prijavio uz screenshot ("Assembly: N/A" — nepovezano, drugi
segment za master-list feature; stvarni nedostatak je 🌍 linija).

## Pogođeno (GitNexus impact na `_update_status_bar`)
- **Risk: HIGH**, impactedCount 30, 21 direktan pozivalac (skoro sve akcije
  u Faktura tabu: add/delete/undo/redo/import/export/validate/auto-fill...)
- Razlog HIGH ocjene: `_update_status_bar()` je čvorna funkcija koju poziva
  skoro sav Faktura tab kod — GitNexus mjeri "ko poziva ovu funkciju", ne
  "šta moja konkretna izmjena mijenja".
- Stvarna izmjena je ADITIVNA i lokalna: jedan-smjerni latch
  (`self._analysis_summary_auto = True` čim `item_count > 0`, samo jednom)
  ubačen NA POČETKU postojeće grane za `item_count > 0`, prije bilo kakvog
  drugog label-a. Ne mijenja povratnu vrijednost, ne mijenja logiku
  postojećih labela (item_count, total_amount, validation, assembly), ne
  mijenja signaturu, ne dodaje nove pozive.

## Plan
1. U `_update_status_bar()` (gui/tabs/faktura_view.py, dist_client mirror),
   odmah nakon `if item_count == 0: ... return` bloka, dodati:
   ```python
   if not self._analysis_summary_auto:
       self._analysis_summary_auto = True
   ```
2. `_refresh_analysis_summary_from_draft()` (već pozvan na kraju funkcije,
   nepromijenjen) će od tog trenutka stvarno izračunati i prikazati 🌍 liniju
   — identičnu logiku kao za Agent uvoz, ali čitanu iz TRENUTNOG stanja
   draft/tabele (`_build_analysis_summary_from_draft`), ne iz agent-ovog
   `lines` parametra — što je ionako ISPRAVNIJE (uvijek prikazuje CIJELI
   draft, ne samo zadnji uvezeni batch).
3. Mirror u dist_client, novi regresioni test, pun test suite, GitNexus
   detect_changes, commit.

## Šta NE dirati
- `AgentController._proactive_analysis()` — ostaje nepromijenjen (i dalje
  zove `set_analysis_summary()` eksplicitno; nije štetno, samo sad
  redundantno postavlja flag koji će već biti True).
- `lbl_assembly` / "Assembly: N/A" logika (`self.assembly.master_list_loaded`)
  — potpuno odvojen feature (master-list učitavanje), korisnikov screenshot
  ga prikazuje ali NIJE predmet ovog zadatka.
- Sve OSTALE grane/labeli unutar `_update_status_bar()` — netaknuto.

## Konflikti
Nema — nema ranijeg agent_report/memory zapisa o ovom ponašanju kao
namjernom. Docstring `set_analysis_summary()` ("Poziva se iz AgentController-a
nakon uvoza") opisuje TRENUTNI poziv-obrazac, ne eksplicitnu namjeru da ručni
uvoz bude isključen — tretiram kao previd/gap, ne kao namjerni dizajn.
Korisnička potvrda: NIJE potrebna (jasan bug report sa screenshotom,
minimalan aditivan fix).
