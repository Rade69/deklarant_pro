# Agent Report — 2026-07-22: "Provjeri" automatski nakon uvoza fakture

## Datum
2026-07-22

## Agent
Claude Sonnet 5

## Scope
- `gui/tabs/faktura_view.py` + `dist_client` kopija
- `tests/unit/test_faktura_view_provjeri_nakon_uvoza.py` (novo)
- `docs/CONTEXT.md` (§30, nastavak §29)

## Status izvora

Direktan nastavak `agent_reports/2026-07-22_sussina-supplier-filter-fix.md`. Nakon što je
supplier-filter bug popravljen, korisnik je postavio produktno pitanje: kako trajno riješiti
da se pogrešno tarifirana roba (SUSSINA tip greške i "niz drugih na fakturama") uhvati odmah
pri uvozu, umjesto da zavisi od naknadnog ručnog klika "Provjeri". Razmotrio sam dvije opcije
(tiha notifikacija vs. automatsko pokretanje postojećeg modala) — korisnik je eksplicitno
potvrdio drugu opciju nakon što sam iskreno rekao da je to bolje rješenje jer ne zahtijeva
novi kod, samo raniji poziv postojećeg.

## GitNexus impact

`_on_import_finished` — LOW (0 direktnih pozivalaca u grafu jer je Qt signal/slot handler,
ne direktan poziv; 0 affected_processes). `_process_batch_records` — LOW (1 direktan
pozivalac `_on_batch_done`, 0 affected_processes). `gitnexus_detect_changes()` nakon izmjene:
`risk_level: low`, `affected_count: 0`.

Napomena: iako je GitNexus-ov graph-based impact LOW (malo direktnih pozivalaca), ovo je
**funkcionalno** značajna promjena ponašanja jer se `_on_import_finished` izvršava na SVAKI
uspješan uvoz fakture — najčešći put u aplikaciji. Testiranje je zato bilo pažljivije nego
što bi LOW risk sam po sebi sugerisao.

## Šta je urađeno

`_on_import_finished` (pojedinačni/kombinovani uvoz) i `_process_batch_records` (grupni
uvoz) sad, u svom završnom dijelu (nakon `_update_status_bar()` / nakon "Grupni uvoz"
QMessageBox-a), pozivaju `self._run_historical_tariff_validation(auto=False)` — potpuno
identičan kod koji se izvršava kad korisnik ručno klikne "Provjeri" u toolbaru. Dijalog sa
prijedlozima se prikazuje SAMO kad postoji istorijski dokaz da je trenutna tarifa upitna
(postojeća `if not matches: return` logika ostaje netaknuta) — čista faktura bez problema ne
prikazuje ništa, ne prekida korisnika.

Poziv je uslovljen sa `if not self._agent_mode:` — kad je agent mod aktivan (puna
automatizacija preko chat-a), poziv se PRESKAČE jer `import_pipeline_service.
_puna_auto_pipeline()` već zove `_on_validate_all(auto=True)` kasnije u svom sopstvenom,
kontrolisanom redoslijedu koraka (mase → auto-popuna tarifa → validacija). Automatski poziv
ovdje bi u tom slučaju ili duplirao provjeru ili prekinuo agent chat tok neočekivanim
modalom prije nego agent stigne do svog koraka.

## Zašto je urađeno

Korisnikov uvid: čekanje na ručni klik "Provjeri" je tačno razlog zašto se SUSSINA-tip
greška (i slične) provuku — korisnik uveze fakturu, pređe na sljedeći korak, i ne stigne
(ili zaboravi) kliknuti "Provjeri" prije nego što deklaracija ode dalje. Pomjeranje provjere
na trenutak odmah nakon uvoza — kad je greška najjeftinija za ispraviti — direktno zatvara
tu rupu, bez potrebe za bilo kakvom novom logikom (samo raniji poziv postojećeg, već
testiranog koda).

## Kako je urađeno

Dvije minimalne izmjene, obje pozivaju IDENTIČNU postojeću metodu bez izmjene njenog
potpisa ili unutrašnje logike:
- `_on_import_finished`: poziv dodat nakon `self._update_status_bar()`, prije `self.on_dirty()`.
- `_process_batch_records`: poziv dodat nakon `QMessageBox.information(self, "Grupni uvoz", ...)`,
  prije `self.data_changed.emit()`.

`dist_client` kopija bila je identična root-u u oba pogođena regiona prije izmjene
(potvrđeno pregledom) — izmjena primijenjena identično na oba mjesta.

## Šta nije dirano

- `_run_historical_tariff_validation`, `HistoricalTariffSearchService`,
  `TariffValidationDialog` — logika prijedloga/prikaza nije mijenjana, samo TRENUTAK poziva.
- `import_pipeline_service._puna_auto_pipeline` — agent-mod tok ostaje potpuno nepromijenjen,
  samo eksplicitno izuzet od NOVOG poziva (`if not self._agent_mode:`).
- Opšta validacija (`_on_validate_all`'s error/warning brojanje) — nije dirana, ovaj fix
  poziva SAMO istorijsku tarifnu podfunkciju (`_run_historical_tariff_validation`), ne cijeli
  `_on_validate_all`.

## Verifikacija

```
python -m pytest tests/unit/test_faktura_view_provjeri_nakon_uvoza.py -v
  → 4 passed (novo): pojedinačni uvoz +agent_mode/-agent_mode, grupni uvoz +/-agent_mode
python -m pytest tests/ -q --ignore=tests/unit/test_decision_characterization.py
  → 846 passed, 58 skipped, 3 failed, 1 error (identično pretpostojećim/nepovezanim
    failovima iz prethodnih izvještaja)
python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py → OK
mcp__gitnexus__detect_changes() → risk_level: low, affected_count: 0
```

## Pronađeni problemi

Nema novih.

## Konflikti / kontradiktorni izvori

Nema — direktna implementacija korisnikove eksplicitne odluke iz prethodnog razgovora u
ovoj sesiji (birao je opciju "pun modal, ništa novo graditi" nakon mog iskrenog mišljenja).

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | feat(faktura): pokreni istorijsku tarifnu provjeru automatski nakon uvoza |

## Rizici / ograničenja

- Kod grupnog uvoza VIŠE faktura odjednom, ako svaka faktura ima svoje istorijske
  prijedloge, korisnik će vidjeti JEDAN modal sa svim prijedlozima odjednom (poziv je JEDAN,
  nakon što su SVE fakture iz grupe već spojene u `self.draft.invoice_lines`) — ne po fajlu.
  Ovo je zapravo POVOLJNIJE od "jedan dijalog po fajlu" (manje prekida), ali vrijedi
  eksplicitno navesti da se ponašanje razlikuje od pojedinačnog uvoza (koji poziva provjeru
  jednom PO fakturi, jer se `_on_import_finished` poziva jednom po завршеном importu).
- Ako korisnik uzastopno uveze više pojedinačnih faktura (ne grupno), svaka će pokrenuti
  svoju provjeru — ako svaka ima nalaz, to je više modala zaredom. Isti tradeoff kao već
  postojeći EUR.1/PE2 dijalozi u istom toku — konzistentno, ali vrijedi pratiti u praksi.

## Potreban follow-up

- Ručni test u aplikaciji: uvesti fakturu sa SUSSINA (ili sličnom) pogrešno tarifiranom
  stavkom, potvrditi da se dijalog pojavljuje ODMAH nakon uvoza bez klika na "Provjeri".
- Pratiti u praksi da li je učestalost dijaloga (posebno pri uzastopnom pojedinačnom uvozu
  više faktura) prihvatljiva ili zamorna — mogući follow-up: debounce/batch prijedloga preko
  više uzastopnih uvoza u jedan dijalog ako se pokaže potrebnim.

## Potrebna korisnička potvrda

- Da li automatski dijalog nakon uvoza radi kako je očekivano i da li je učestalost u praksi
  prihvatljiva (posebno pri uvozu više pojedinačnih faktura zaredom).
