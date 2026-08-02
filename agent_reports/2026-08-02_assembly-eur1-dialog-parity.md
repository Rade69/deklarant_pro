## Datum
2026-08-02

## Agent
Claude Sonnet 5 (Claude Code)

## Scope
`gui/tabs/faktura_view.py` (`_finish_import_legacy_path`, `_process_batch_records_legacy`), `services/naimenovanja/declaration_assembly.py` (`AssemblyItem.update_from_invoice`), + dist_client mirror. Novi testovi: `tests/unit/test_assembly_origin_evidence_priority.py`, `tests/unit/test_batch_assembly_matching_wiring.py`.

## Status izvora
Nastavak Faze 6 iz `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` (aktivan, Faza 6 DONE). Novi zaseban plan: `project_rooms/2026-08-02_assembly-eur1-dialog-parity.md` (aktivan, sadrži sva tri "Dodatka" — svaki nalaz otkriven TEK nakon prethodne popravke, kroz korisnikovo stvarno GUI testiranje).

## GitNexus impact
`_finish_import_legacy_path`: LOW, 1 pozivalac. `_process_batch_records_legacy`: LOW, 2 pozivaoca (`_process_batch_records`, `_on_batch_done`). `AssemblyItem.update_from_invoice`: GitNexus prijavljuje 0 upstream (dinamički poziv iz `add_invoice()`, poznato ograničenje indeksa — potvrđeno ručnim čitanjem koda, ima 1 stvaran pozivalac unutar iste klase). `gitnexus_detect_changes()` nakon svake od tri popravke: risk LOW, 0 affected_processes.

## Reprodukcija prije izmjene
Sve tri popravke su reagovale na KONKRETAN korisnički GUI test (screenshot dokaz), ne apstraktnu sumnju:
1. Popravka 1: korisnik pokazao screenshot Agent moda sa ispravnim EUR.1 dijalogom za identičan Excel+fakture koje Assembly ručni put nije tražio.
2. Popravka 2: korisnik prijavio da se status "0% (0 faktura)" ne mijenja kod grupnog uvoza, iako radi kod pojedinačnog.
3. Popravka 3: korisnik pokazao screenshot sa popunjenom "EUPR"/"EFTA1R" povlasticom ali bez ✅ kvačice na koloni Zemlja.

## Šta je urađeno
Tri sekvencijalne popravke istog dana, svaka otkrivena tek nakon što je prethodna verifikovana i korisnik nastavio testirati u pravoj aplikaciji:
1. `_finish_import_legacy_path` (Assembly grana) sad zove `determine_origin_dialog()` + `_collect_manual_origin_response()` + `_apply_origin_decision()` PRIJE `assembly.add_invoice()` — isti tok kao Agent mod. `update_from_invoice()` dodaje pravilo "potvrđen dokaz uvijek nadjačava master-liste predlog" za `povlastica`/`eur1_number`/`has_origin_statement`/`is_authorized_exporter`.
2. `_process_batch_records_legacy` (grupni uvoz): kad je master lista već učitana, batch petlja sad zove `add_invoice()` PO FAKTURI (sa istim EUR.1 tokom kao Popravka 1) umjesto `draft.invoice_lines.clear()+extend()` koje je brisalo prethodno matchovane stavke.
3. `update_from_invoice()` dopunjeno da kopira i `country_confidence`/`country_source`/`country_conflict_details` — bez toga Faza 5 UI pravilo (`ValidationService.country_confidence_style()`) nikad ne prikazuje kvačicu, bez obzira što je povlastica stvarno potvrđena.

## Zašto je urađeno
Korisnička eksplicitna odluka: "Ovo mora raditi identično kao agentski mod, nema druge opcije." Assembly/master-list ručni uvoz je bio jedini od tri aktivna uvoz-toka koji NIJE tražio EUR.1/PE2/PE3 potvrdu — carinski rizik (povlastica bez dokaza u zvaničnoj deklaraciji).

## Kako je urađeno
Za svaku od tri popravke: (1) pročitan tačan trenutni kod prije bilo kakve izmjene, (2) karakterizacioni test napisan PRIJE popravke i potvrđeno da namjerno PADA na starom kodu (dokaz da je bug stvaran, ne pretpostavka), (3) minimalna, ciljana izmjena, (4) test ponovo pokrenut da prođe, (5) pun test suite + dist_client sync + `gitnexus_detect_changes()`. Popravka 3 je otkrivena zahvaljujući `PreferenceValidator` "X bez EUR1" status-bar indikatoru u GUI-ju — brojka (1 od 88) je pokazala da JE povlastica potvrđena za skoro sve stavke, što je isključilo hipotezu "dijalog se ne poziva" i usmjerilo istragu na "podatak se gubi pri spajanju".

## Šta nije dirano
Unified import put (`services/import_workflow/*`) — samo pozivan, logika unutra nepromijenjena. Non-Assembly (`else`) grana `_finish_import_legacy_path`-a i `_process_batch_records_legacy`-a kad master lista NIJE učitana prije batcha — stari mehanizmi (`_show_eur1_dialog`, `load_master_list_from_lines`) netaknuti. Sam Excel format master liste — i dalje popunjava početni predlog povlastice, samo više nije neopoziv.

## Verifikacija
Deterministički testovi (najjači nivo po AGENTS.md hijerarhiji): 9 testova u `test_assembly_origin_evidence_priority.py` (6 iz Popravke 1 + 3 iz Popravke 3), 3 u `test_batch_assembly_matching_wiring.py` (Popravka 2) — svi PRVO potvrđeno da padaju na starom kodu. Pun test suite nakon svake popravke: 1461 passed / 1 poznat nepovezan DB nalaz (`product_tariff_mapping` "Test proizvod", nepromijenjeno ovim radom). Postojeći e2e test (`test_assembly_master_list_import_e2e.py`, 5 testova sa stvarnom fakturom Master Frigo) i dalje prolazi bez izmjene ponašanja. GUI vizuelna potvrda: korisnik je nakon svake popravke ponovo testirao uživo i pokazao screenshot — treći screenshot (nakon Popravke 3) nije još dostavljen u trenutku pisanja ovog izvještaja.

## Nezavisna provjera
- Checker korišćen: DA (pokrenut paralelno sa pisanjem ovog izvještaja, general-purpose agent, u pozadini)
- Checker agent/model: Claude Code general-purpose subagent
- Šta je checker provjerio nezavisno: zadatak — pokušati oboriti hipotezu da su sve tri popravke ispravne/kompletne; provjeriti da li postoji JOŠ neko polje iz `_apply_grouped_origin_data()` koje se gubi (isti class buga kao Popravka 3); provjeriti "flat" (non-grouped) granu `_apply_origin_decision`-a odvojeno; provjeriti tipsku sigurnost `has_origin_statement`/`is_authorized_exporter` izvučenih iz `record.get("_import_result")` u batch petlji; provjeriti edge case otkazivanja EUR.1 dijaloga usred Assembly uvoza; provjeriti da testovi stvarno testiraju tvrđeno ponašanje.
- Koje pretpostavke je pokušao oboriti: da li postoji propušteno polje iz `_apply_grouped_origin_data()` (isti class buga kao Popravka 3); da li "flat" (non-grouped) grana `_apply_origin_decision`-a zahtijeva isto; tipska sigurnost `has_origin_statement`/`is_authorized_exporter` iz `record.get("_import_result")`; edge case otkazivanja dijaloga; da li testovi stvarno testiraju tvrđeno ponašanje.
- Šta je potvrđeno: sve tri popravke rade ispravno, pun skup relevantnih polja iz `_apply_grouped_origin_data()` je pokriven (nema dodatnog propusta te vrste), `record.get("_import_result")` je tipski siguran (`getattr(None, ..., False)`), 17 ciljanih + 106 širih povezanih testova prolazi bez regresije, `unmatched` stavke ne prolaze kroz `update_from_invoice()` pa merge-prioritet nije ni relevantan za taj slučaj.
- Šta nije potvrđeno: stvaran GUI klik-test scenarija otkazivanja dijaloga (nalaz izveden iz čitanja koda, ne izvršenog uživo scenarija); nije mapiran pun obim importera koji per-line `has_origin_statement` pre-postavljaju (potvrđeno samo za `proton_system_importer.py`, dovoljno da dokaže da rizik postoji).
- Novi nalazi: (1) otkazivanje EUR.1/PE2/PE3 dijaloga ne čisti per-line `has_origin_statement` koje neki parseri postavljaju direktno iz PDF teksta — DIJELJENA infrastruktura sa Agent modom, van scope-a, NIJE popravljeno, zahtijeva korisničku odluku; (2) `is_authorized_exporter` asimetrično kopiranje — POPRAVLJENO (commit `7c753ae`); (3) netačan komentar u testu — POPRAVLJENO (isti commit).
- Da li je promjena spremna za prihvatanje: DA za sve popravljeno (kod-nivo dokazano testovima + GUI potvrda korisnika za popravke 1-3, nezavisno provjereno za sve tri + dodatna dva nalaza). Nalaz #1 (otkazivanje dijaloga) ostaje otvoren — nije "spreman za prihvatanje" jer nije ni pokušan, čeka korisničku odluku o obimu (dira 3 uvoz-toka).

## Pronađeni problemi
Svaka od tri popravke je otkrila SLEDEĆI, dublji propust u istom kodu — obrazac vrijedan pažnje: prva ispravka izgleda kompletna dok se stvarno ne testira u GUI-ju sa punim tokom (učitaj listu → uvezi → provjeri status → provjeri boju). Ovo je isti "porodični" obrazac kao stariji bugovi u "Zemlja porijekla/povlastica" memoriji (6 zapisa, Faza 5) — više odvojenih dimenzija (povlastica, completion status, vizuelna potvrda) koje izgledaju povezano ali su tehnički nezavisna polja/putevi koda, lako je popraviti jednu dimenziju i pretpostaviti da su ostale automatski riješene.

## Odbačene opcije
Nema novih (vidi `project_rooms/2026-08-02_assembly-eur1-dialog-parity.md` za odbačenu opciju iz Popravke 1 — Excel kolona kao autoritativna umjesto EUR.1 dokaza).

## Konflikti / kontradiktorni izvori
Originalni fazni plan (`project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md`) je imao "Šta NE dirati" stavku koja je izričito isključivala `_process_batch_records_legacy` iz scope-a — kontradiktorno sa Popravkom 2 koja ga JE dirala istog dana. Ispravljeno (commit `9feb782`) — tretirano kao: originalna stavka je bila procjena PRIJE nego što je korisnik otkrio grupni-uvoz bug, korisnikov naknadni izvještaj je noviji i validan izvor, nije trebala korisnička potvrda jer je jasno hronološki noviji nalaz.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `8fd2b2d` | fix(faktura): Assembly uvoz sada trazi EUR.1/PE2/PE3 potvrdu kao Agent mod |
| `3a71932` | fix(faktura): grupni Assembly uvoz vise ne brise prethodno matchovane stavke |
| `d036d5d` | fix(faktura): prenesi country_confidence pri Assembly EUR.1 potvrdi |
| `9feb782` | docs(faktura): ispravi dva zastarjela/kontradiktorna statusa u planovima |
| `feb9127` | docs(faktura): zatvori pitanje ImportService.import_multiple_files preklapanja |
| `7c753ae` | fix(faktura): simetricno kopiraj is_authorized_exporter (nalaz nezavisne provjere) |

## Rizici / ograničenja
**Otvoren rizik (nije popravljen)**: otkazivanje/reject EUR.1/PE2/PE3 dijaloga ne čisti per-line `has_origin_statement` koje neki parseri (potvrđeno: `importers/proton_system_importer.py`) postavljaju direktno iz PDF teksta prije dijaloga — flag ostaje `True` i upisuje se u draft bez obzira na otkazivanje. Dijeljena infrastruktura sa Agent modom (`_apply_origin_decision`), ne uvedeno danas, van scope-a Assembly-specifičnog rada. Vizuelna kvačica se ne pojavljuje (country_confidence ostaje prazan), ali sam flag ipak ulazi u draft — carinski relevantno ako se `has_origin_statement` koristi drugdje (npr. XML export) nezavisno od kvačice.

## Potreban follow-up
- **Fact/Decision za korisnika**: da li se popravlja nalaz #1 (otkazivanje dijaloga ne čisti parser-postavljen `has_origin_statement`) — dira `services/import_workflow/apply_service.py`, dijeljeno sa Agent modom i migriranim pojedinačnim uvozom, van scope-a ovog izvještaja dok se ne odluči.
- Faza 7 (van scope-a ovog izvještaja) ostaje neriješena — zahtijeva zasebnu odluku korisnika prije početka.

## Potrebna korisnička potvrda
Vizuelna GUI provjera da ✅ kvačica sad ispravno prati potvrđenu povlasticu (Popravka 3) — isti obrazac kao Faza 5/6, offscreen render nije dovoljan dokaz za ovu oblast.
