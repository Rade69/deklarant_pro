# Brief za Pi agenta — Autosave / recovery nacrta deklaracije

## Kontekst

Korisnik (Radovan) je primijetio da dugme "Sačuvaj nacrt" (`FakturaView`/`NaimenovanjaView`,
prije preimenovano iz "Sačuvaj" u commit `3665f4d`) čuva nacrt **isključivo ručno** — nema
zaštite od gubitka rada pri padu aplikacije, strujnom udaru ili slučajnom zatvaranju.
Cilj ove faze: dodati automatsko čuvanje u pozadini + ponudu za oporavak pri sljedećem
pokretanju, bez ometanja korisnika dijalozima usred rada.

Ovo NIJE dio `docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md` (Faze A–F) —
zaseban, nezavisan zadatak koji Radovan želi da se radi **paralelno** sa Fazom D tog plana
(koju radi Claude na `windows` grani).

## Grana — OBAVEZNO

Radi isključivo na grani `feature/draft-autosave-nacrt` (već kreirana od `windows @ 3665f4d`).
**Ne commitovati direktno na `windows`** dok Claude paralelno radi Fazu D — dva agenta bez
međusobne komunikacije na istoj grani je siguran recept za sudar (naročito oko
`docs/CONTEXT.md` i GitNexus brojeva u `AGENTS.md`/`CLAUDE.md`, koje oba agenta dodiruju).
Kad završiš, javi korisniku — on odlučuje kad i kako spaja granu nazad u `windows`.

## Cilj (2 konkretne stvari)

1. **Periodični autosave u pozadini** — na fiksni interval (predlog: 5 min, ali provjeri
   ima li već QTimer infrastrukturu u aplikaciji za slično ponavljajuće poslove pa se
   nadoveži na nju umjesto nove) čuva trenutni nacrt na fiksnu, skrivenu putanju — **bez
   dijaloga, bez prekidanja korisnika**. Ne mijenja `_persistent_draft_path` ručno sačuvanog
   nacrta niti "last directory" podešavanje (`drafts/lastDirectory`) — to ostaje isključivo
   za eksplicitno "Sačuvaj nacrt".
2. **Autosave odmah nakon uspješnog kreiranja naimenovanja** — hook na kraj uspješne putanje
   `FakturaView._on_create_naimenovanja` (`gui/tabs/faktura_view.py`, vraća `True` na uspjeh —
   vidi Faza C izmjenu, commit `994785e`). To je trenutak kad je upravo završen najviše
   vrijedan rad u sesiji.
3. **Ponuda za oporavak pri startu aplikacije** — ako autosave fajl postoji i noviji je od
   posljednjeg čistog gašenja (ili jednostavnije: ako postoji uopšte), pri sljedećem
   pokretanju ponuditi dijalog "Pronađen je nesačuvan rad iz [vrijeme] — učitati?".
   Pogledaj `_check_license_on_startup` u `run.py` (poziva se odmah nakon `window.show()`,
   ne blokira aplikaciju) kao gotov obrazac za ovakvu "provjeri i upozori bez blokiranja" logiku.

## Predložena tehnička rješenja (provjeri/prilagodi — nisu propisana)

- `services/declaration_draft_service.py` već ima `save()`, `load()`, `suggested_filename()`,
  `default_drafts_directory()`, `is_draft_file()` — logično mjesto za dodati
  `autosave_path(draft)` (fiksna putanja, npr. `default_drafts_directory() / ".autosave" /
  "<ref_br ili session-id>.xml"`) i eventualno `AutosaveService` klasu, ili novi zaseban
  fajl `services/draft_autosave_service.py` ako se čini čišće. `DeclarationDraftService.save()`
  se može direktno reuse-ovati za sam zapis (već piše ispravan XML format).
- Timer + trigger na "kreirana naimenovanja" najvjerovatnije treba živjeti tamo gdje postoji
  pristup trenutnom `draft`-u i gdje se `FakturaView` inicijalizuje (npr. `MainWindow` ili
  `agent_controller.py`) — **istraži GitNexus kontekst prije nego odlučiš gdje**, ne pretpostavljaj
  strukturu koju nisam ovdje naveo jer je nisam ovom sesijom čitao.
- Recovery dijalog na startu: `run.py`, blizu `_check_license_on_startup` (linija ~89-107,
  ~162-163) — isti obrazac (non-blocking upozorenje nakon `window.show()`).

## Šta NE dirati (scope lock — Faza D teritorija, van tvog zadatka)

- `gui/tabs/agent/services/*` (uključujući `chat_intent_handler.py`, `tool_policy.py`,
  `import_pipeline_service.py`, `pipeline_stage_result.py`)
- `services/agent/chat/*` (`tool_dispatcher.py`, `intent_classifier.py`, `tool_definitions.py`)
- `gui/tabs/agent/widgets/llm_provider.py`
- `gui/tabs/agent/agent_controller.py` — osim ako je stvarno jedino mjesto gdje autosave
  timer može dobiti pristup draftu; ako je tako, ograniči izmjenu na dodavanje jednog poziva/
  hooka, ne diraj postojeću pipeline logiku
- Unutar `gui/tabs/faktura_view.py::_on_create_naimenovanja` — smiješ dodati SAMO poziv
  autosave hooka na kraju uspješne putanje (poslije `return True` pripreme, prije samog
  return-a), ne mijenjaj ništa drugo u toj metodi ili fajlu (Claude je upravo završio Fazu C tu)

## Obavezna procedura (AGENTS.md, važi za sve agente)

- Srpski, latinica, u svim porukama/komentarima/commit porukama
- `gitnexus_impact` prije izmjene svakog simbola koji već postoji (npr. prije diranja
  `_on_create_naimenovanja`, `run.py::main`); ako HIGH/CRITICAL, prijaviti korisniku PRIJE
  izmjene i napisati kratak `project_rooms/YYYY-MM-DD_*.md` fajl
- `dist_client/` mirror za svaki izmijenjeni/novi fajl (provjeri BOM: root ima `﻿`,
  dist_client nema — `encoding='utf-8-sig'` pri čitanju, `'utf-8'` pri pisanju)
- `python -m py_compile` na sve izmijenjene/nove fajlove (root + dist_client) prije commita
- Testovi: novi `tests/unit/test_*autosave*.py`, pokriti: periodični trigger, hook nakon
  naimenovanja, recovery detekciju (postoji/ne postoji autosave, stariji/noviji), da autosave
  NE mijenja `drafts/lastDirectory` niti `_persistent_draft_path`
- `mcp__gitnexus__detect_changes()` prije commita — provjeri scope
- `agent_reports/2026-07-20_pi-autosave-nacrt.md` (ili sličan naziv) po standardnom formatu
  (Datum/Agent/Scope/GitNexus impact/Šta je urađeno/Zašto/Kako/Šta nije dirano/Verifikacija/
  Commitovi/Rizici/Follow-up)
- `docs/CONTEXT.md` — dodaj NOVU numerisanu sekciju na kraj fajla (trenutno zadnja je §22).
  **Napomena**: Claude paralelno možda dodaje §23 za Fazu D na `windows` grani — kad se grane
  budu spajale, moguć je trivijalan git konflikt na kraju `CONTEXT.md` (obje sekcije treba
  zadržati, samo prenumerisati ako želite urednost — nije blokirajuće, samo napomena unaprijed)

## Prihvatljiv ishod (definition of done)

- Autosave se dešava tiho, ne prekida korisnika dijalozima, ne mijenja postojeće ručno
  "Sačuvaj nacrt" ponašanje
- Nakon simuliranog "pada" (npr. ubiti proces dok je autosave fajl svjež) i ponovnog starta,
  korisnik dobija jasnu ponudu za oporavak sa tačnim vremenom zadnjeg autosave-a
- Svi testovi prolaze, `py_compile` čist, dist_client identičan (bez BOM razlike)
- `gitnexus_detect_changes()` prijavljuje očekivan, uzak scope (samo fajlovi iz ovog zadatka)
