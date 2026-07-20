# Agent Report — 2026-07-20: Review Pi-jevog autosave rada + fix closeEvent bug-a

## Datum
2026-07-20

## Agent
Claude Sonnet 5

## Scope
- Review: `services/draft_autosave_service.py`, `gui/main_window.py`, `run.py` (Pi-jev rad,
  commit `cfdbe98` na grani `feature/draft-autosave-nacrt`)
- Fix: `gui/main_window.py` + dist_client mirror (`closeEvent`, `_on_exit_clicked`)

## Status izvora

- `project_rooms/2026-07-20_autosave-nacrt-brief-za-pi-agenta.md` — brief koji sam napisao,
  aktivan, korišten kao referentni okvir za review.
- `agent_reports/2026-07-20_pi-autosave-nacrt.md` — Pi-jev izvještaj, aktivan, tačan osim
  jedne kozmetičke netačnosti (putanja opisana kao `~/.autosave/autosave.xml`, stvarna je
  `~/Documents/Deklarant Pro/Nacrti/.autosave/autosave.xml`) — nije funkcionalni bug, samo
  netačan opis u izvještaju.

## GitNexus impact

Prije fix-a: `MainWindow.closeEvent`/`_on_exit_clicked` — LOW rizik (metode UI-events, nema
downstream zavisnika osim Qt frameworka). Nakon commita `366d5db`:
`gitnexus_detect_changes(scope="all")` → **risk_level: low**, 16 promijenjenih simbola
(root+dist_client parovi `MainWindow`, `closeEvent`, `_on_exit_clicked`, lokalna varijabla
`screen`), **0 affected_processes**.

## Šta je urađeno

### 1. Review Pi-jevog rada (grana `feature/draft-autosave-nacrt`, commit `cfdbe98`)

Provjereno: dist_client mirror identičan (bez BOM razlike), `py_compile` čist, 14/14 novih
testova (`tests/unit/test_draft_autosave_service.py`) prolazi, `gitnexus_detect_changes()`
nakon Pi-jevog commita — low risk, 0 affected processes.

**Pozitivno**: Pi je iskoristio postojeći `FakturaView.naimenovanja_created` signal umjesto
direktnog diranja `_on_create_naimenovanja` u `faktura_view.py` — potpuno poštovan scope lock
iz brief-a bez ijednog kompromisa na funkcionalnosti.

### 2. Otkriven bug: `closeEvent` ne briše autosave

`clear_autosave()` je pozivan SAMO iz `_on_exit_clicked()` (custom "Izlaz" dugme u tab traci).
`MainWindow.closeEvent()` (okida se i pri zatvaranju preko **standardnog Windows X dugmeta**
u naslovnoj traci — najčešći način zatvaranja aplikacije) je čuvao samo geometriju prozora,
ne i brisao autosave. Posljedica: svaki uredan izlazak preko X dugmeta bi ostavio
`autosave.xml`, pa bi sljedeći start UVIJEK lažno prijavio "Pronađen je nesačuvan rad" —
iako nije bilo nikakvog pada. Ovo poništava cijelu svrhu recovery dijaloga (treba se javiti
samo nakon stvarnog prekida).

### 3. Fix

`clear_autosave()` premješten u `closeEvent()` (pokriva OBA puta zatvaranja — Izlaz dugme
poziva `self.close()` na kraju, što svakako okida `closeEvent`). Duplirani poziv uklonjen iz
`_on_exit_clicked()` da ne postoje dva izvora iste logike.

## Zašto je urađeno

Korisnik je eksplicitno tražio review prije merge-a. Bug je nađen čitanjem svih puteva
zatvaranja aplikacije (`_on_exit_clicked`, `closeEvent`, `_confirm_safe_to_exit`) prije nego
što je potvrđeno da je autosave-brisanje ispravno pokriveno — standardna disciplina "pročitaj
sve povratne/izlazne putanje prije izmjene" primijenjena i na review tuđeg koda.

## Kako je urađeno

Minimalna izmjena: premještanje jednog `try/except` bloka iz jedne metode u drugu, plus
uklanjanje duplikata. Nije dirana `_confirm_safe_to_exit()` logika (agent-worker-running
upozorenje) — to je pre-postojeći, poznat gap (OS X dugme ne prolazi kroz tu provjeru uopšte)
koji NIJE u scope-u ovog zadatka, samo zabilježen ovdje radi transparentnosti.

## Šta nije dirano

- `services/draft_autosave_service.py` — netaknuto, Pi-jev kod je ispravan
- `run.py::_check_autosave_on_startup` — netaknuto (manja napomena: ručno reimplementira
  petlju za kopiranje polja drafta koja već postoji kao `MainWindow._replace_draft_contents()`
  — nije bug, samo prilika za buduće pojednostavljenje, van scope-a ovog fix-a)
- `_confirm_safe_to_exit()` — pre-postojeći gap (ne provjerava se pri zatvaranju preko X
  dugmeta), nepovezano sa autosave zadatkom, nije dirano
- Timer interval (5 min), fiksna autosave putanja — Pi-jeve odluke, nisu preispitivane

## Verifikacija

```
python -m py_compile gui/main_window.py dist_client/gui/main_window.py → OK
diff (bez BOM) root/dist_client main_window.py → IDENTIČNI
python -m pytest tests/unit/test_draft_autosave_service.py -q → 14 passed
python -m pytest tests/unit -q -k "main_window or autosave" → 14 passed (isti set,
  nema postojećih main_window-specifičnih testova)
mcp__gitnexus__detect_changes(scope="all") nakon commita → risk_level: low,
  affected_processes: []
```

## Pronađeni problemi

- Glavni: closeEvent bug opisan gore (CONFIRMED, fixed).
- Manji: `run.py::_check_autosave_on_startup` duplira `_replace_draft_contents()` logiku
  umjesto da je pozove — kozmetički, ostavljen netaknut po dogovoru (fokus na sam bug).
- Manji: Pi-jev agent_report navodi netačnu autosave putanju (`~/.autosave/...` umjesto
  stvarne `~/Documents/Deklarant Pro/Nacrti/.autosave/...`) — samo u tekstu izvještaja, kod
  je ispravan.

## Konflikti / kontradiktorni izvori

Nema. Brief i Pi-jev izvještaj su bili usklađeni; nalaz je otkriven review-om koda, ne
kontradikcijom izvora.

## Commitovi

| Hash | Poruka |
|------|--------|
| `366d5db` | fix(autosave): obriši autosave i pri zatvaranju preko OS X dugmeta |

(Prethodni Pi commitovi na istoj grani: `cfdbe98` feat, `50d4f61` docs — nisu ovog izvještaja
predmet, dokumentovani u `agent_reports/2026-07-20_pi-autosave-nacrt.md`.)

## Rizici / ograničenja

- Nije ručno testirano u pravoj GUI sesiji (simulacija pada procesa + restart) — samo
  statička verifikacija koda i unit testovi. Preporučen ručni test prije merge-a u `windows`.
- `_confirm_safe_to_exit()` gap (agent worker upozorenje se ne provjerava pri X dugmetu)
  ostaje otvoren, nepovezano sa ovim zadatkom — potencijalni budući follow-up.

## Potreban follow-up

- Ručno testiranje: zatvoriti aplikaciju preko OS X dugmeta dok postoji autosave (ili nakon
  perioda rada), restartovati — recovery dijalog se NE SMIJE pojaviti (jer je zatvaranje bilo
  uredno). Zatim simulirati stvaran pad (Task Manager → End Task) i potvrditi da SE pojavljuje.
- Grana `feature/draft-autosave-nacrt` spremna za merge u `windows` nakon ručne potvrde
  korisnika i nakon što Faza D bude završena (izbjeći merge usred aktivnog paralelnog rada).

## Potrebna korisnička potvrda

- Ručni test scenario iz "Potreban follow-up" gore.
- Odluka: merge-ovati granu odmah ili sačekati kraj Faze D?
