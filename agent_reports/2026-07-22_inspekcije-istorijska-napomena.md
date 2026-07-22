## Datum
2026-07-22

## Agent
Claude Code (Sonnet 5)

## Scope
- `services/inspection_service.py` + `dist_client/` kopija
- `gui/dialogs/inspection_dialog.py` + `dist_client/` kopija
- `database/migrate_inspection_document_history.py` (nov fajl)
- `project_rooms/2026-07-22_istorijska-napomena-inspekcije.md` (plan)
- `tests/unit/test_inspection_service_historical_hint.py`,
  `tests/unit/test_migrate_inspection_document_history.py`,
  `tests/unit/test_inspection_dialog_historical_note.py` (novi testovi)
- `docs/CONTEXT.md` §42

## Status izvora
Nema ranijih agent_reports/memorije za ovu funkcionalnost — prvi put se dodaje. Statični
izvor (`catalogs.inspection_rules`, "BiH UIO Objedinjen spisak... mart 2015") ostaje aktivan
i netaknut; ovaj rad dodaje NOVI, potpuno odvojen informativni sloj.

## GitNexus impact
`gitnexus_detect_changes(scope=all, repo=deklarant_pro)` prije commita: `risk_level: low`,
`affected_count: 0`, `affected_processes: []`. Sve izmjene su aditivne (nove metode/klase,
novi fajlovi) — nijedan postojeći poziv nije mijenjan, pa je rizik nizak i pored toga što
`InspectionDialog`/`InspectionService` imaju širu povezanost u grafu.

## Šta je urađeno
1. Istražena arhiva stvarnih ASYCUDA XML deklaracija na `H:\New folder\NOVA ASIKUDA`
   (5706 fajlova) da se provjeri izvodljivost prije pisanja koda.
2. Napravljen `database/migrate_inspection_document_history.py` — skenira XML arhivu,
   agregira `(tarifni_broj, inspection_type) → usage_count`, gradi/puni PostgreSQL tabelu
   `catalogs.inspection_document_history` (idempotentno, drop+rebuild pri svakom pokretanju).
3. Dodana `HistoricalDocumentHint` dataklasa i `InspectionService.historical_hint()` metoda
   (`services/inspection_service.py`) — čita novu tabelu po tačnom (8-cifrenom) tarifnom broju.
4. Dodana `InspectionDialog._build_historical_note()` (`gui/dialogs/inspection_dialog.py`) —
   prikazuje sivu informativnu napomenu po sekciji (tipu inspekcije), ispod postojeće
   tabele/uslovnog upozorenja.
5. Napisano 14 novih testova (bez mokovanja PostgreSQL konekcije — testirane samo putanje
   koje ne dotiču bazu + čisto XML parsiranje sa pravim privremenim fajlovima).
6. `docs/CONTEXT.md` §42 i ovaj izvještaj.

## Zašto je urađeno
Korisnik je primijetio da je statični spisak inspekcijskih pravila zastario i pitao da li
istorija stvarnih deklaracija može poslužiti kao dokaz. Nakon rasprave (vidi project_room
plan) odlučeno je da se NE gradi zamjenski/samostalni sistem — jer objedinjen entitetski
spisak ne postoji i sličan "frekvencija ≠ ispravnost" rizik (GREJAC SPIRALA/Plamenik bug)
bi ovdje bio opasniji (zakonska/sigurnosna oblast) — nego čisto informativni sloj koji
korisnik sam tumači.

## Kako je urađeno
XML parsing preko `xml.etree.ElementTree`, navigacija `item.findall(".//Attached_documents")`
po `<Item>` bloku, mapiranje starog/novog koda dokumenta (SAN/N852, VET/N853, FIT/N851,
UVK/N003, AGL) na `inspection_type` ključeve iz `services/inspection_service.py`. Novi
DB poziv je potpuno odvojen od `TariffMappingService.import_from_xml_files` (namjerno —
taj servis je CRITICAL/`.pyd`-zaključan, nije dirano).

## Šta nije dirano
- `catalogs.inspection_rules` i `InspectionService.check()` — pravno pravilo ostaje isto
- `TariffMappingService.import_from_xml_files` — CRITICAL, `.pyd`-zaključan
- Boje/status postojećih redova u `InspectionDialog` tabelama

## Verifikacija
- `python -m py_compile` čisto na svih 8 izmijenjenih/novih `.py` fajlova
- 14 novih testova prolazi (`pytest tests/unit/test_inspection_*　test_migrate_inspection_*`)
- Pun test suite: 905 passed, 58 skipped, 5 xfailed, 13 failed — svih 13 failova nepovezano
  sa ovim radom (DB circuit breaker jer je PostgreSQL server nedostupan do sutra + 2
  postojeća nepovezana problema sa PDF/XML parserom, pre-postojeća prije ove sesije)
- `scan_xml_archive()` testiran i protiv stvarne H: arhive (639 parova, sadržajno smisleno)
- `diff` root vs `dist_client` za oba izmijenjena fajla: identično nakon kopiranja
- `gitnexus_detect_changes`: risk_level low, affected_count 0

## Pronađeni problemi
Nema (ovaj put nije bilo lažno-pozitivnih zaključaka niti otkrivenih bugova van scope-a).

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
|---|---|
| (TBD) | feat(inspekcije): istorijska informativna napomena iz stvarnih ASYCUDA deklaracija |
| (TBD) | docs(inspekcije): dokumentuj istorijsku napomenu u CONTEXT.md |

## Rizici / ograničenja
- Podatak je informativan, može biti pogrešno protumačen kao "obavezno" ako korisnik ne
  pročita napomenu pažljivo — labela eksplicitno kaže "ne zamjenjuje pravno pravilo"
- `historical_hint()` se poziva po jedinstvenom tarifnom broju unutar sekcije — kod
  dijaloga sa mnogo naimenovanja to znači dodatni DB poziv po tarifnom broju (isti obrazac
  kao postojeći `check()` poziv po naimenovanju — nije nova vrsta performansnog problema)

## Potreban follow-up
- Pokrenuti `python database/migrate_inspection_document_history.py --xml-dir "H:\New folder\NOVA ASIKUDA"`
  kad PostgreSQL server bude dostupan (najavljeno za sutra, 2026-07-23)
- Vizuelno provjeriti izgled napomene u živoj aplikaciji nakon što tabela postoji (offscreen
  Qt testovi ne mogu zamijeniti vizuelnu provjeru)
- Razmisliti o bulk verziji `historical_hint()` ako broj DB poziva po otvaranju dijaloga
  postane primjetno spor sa velikim brojem naimenovanja

## Potrebna korisnička potvrda
- Da li je format/tekst napomene ("📊 Istorijski podatak (informativno...)") zadovoljavajući,
  ili korisnik želi drugačiju formulaciju/boju nakon što je vidi uživo
- Potvrda da se migracija pokrene sutra kad server bude dostupan
