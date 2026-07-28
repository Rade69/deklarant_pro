## Datum
2026-07-27/28 (sesija se protegla preko ponoći, prekinuta zbog nedostupnog servera)

## Agent
Claude (Opus 5)

## Scope
- `services/agent/workflow/declaration_workflow_state.py` — `items_created` kapija
- `tests/unit/test_agent_v2_wiring_fixes.py` — fixture + novi test
- (usput, prethodni fixevi iste istrage): `gui/tabs/agent/services/import_pipeline_service.py`
  (`_wait_for_historical_validation`), `gui/tabs/agent/agent_controller.py`
  (povratak fokusa na Agent tab)

## Status izvora
- §75/76/77 `docs/CONTEXT.md` — svi aktivni, ali §77 fix (async čekanje) NIJE
  bio dovoljan; ovaj izvještaj dokumentuje ŠTA je stvarno bio uzrok.
- Korisnička uživo testiranja (višestruka, preko dvije sesije) — primarni
  izvor dokaza, uključujući "Aktivnosti" tab log koji nikad ranije nije
  pregledan.

## GitNexus impact
`DeclarationWorkflowState.from_draft` — `target_uid:
Method:services/agent/workflow/declaration_workflow_state.py:DeclarationWorkflowState.from_draft#1`,
rizik **LOW** (5 impacted, samo unutar workflow lanca:
`compute_state_from_draft` → `_run` → `run_declaration_workflow`, nema
drugih pozivaoca).

## Šta je urađeno
Popravljen stvaran uzrok bug-a koji je uzrokovao da "Puna automatizacija"
prijavljuje potpuno prazno "naimenovanje 1" (nedostaje naziv/tarifa/zemlja/
masa) i stane na `items_validated` kapiji, iako je Faktura tab jasno
pokazivao ispravno popunjenih 94 stavki.

## Zašto je urađeno
Korisnik je uporno insistirao (kroz nekoliko rundi testiranja) da automatski
put "ne pokreće aktivnost koju pokreće klik na Provjeri/Kreiraj Naimenovanja"
— ispostavilo se da je bio potpuno u pravu, doslovno: `create_smart_group()`
(logika iza dugmeta "Kreiraj Naimenovanja") **nikad nije bila pozvana** u
automatskom režimu.

## Kako je urađeno — istraga
1. Prethodni fix (§77, `_wait_for_historical_validation`) je bio realan i
   ostaje u kodu (rješava stvaran, ali drugi async gap), ali NIJE riješio
   glavni simptom — potvrđeno ponovljenim testom nakon rebuild-a.
2. Privremena dijagnostika (`logger.warning("🔬 [DIJAG]...")`) dodana u
   `create_smart_group()`, `_on_create_naimenovanja`, `_on_validate_all`,
   `_on_historical_validation_finished` — koristi `.warning` jer je runtime
   log level `WARNING` (`run.py:37`), pa `.debug`/`.info` nikad ne stižu u
   `~/.deklarant_pro/logs/deklarant_pro.log`.
3. Ručni test (korisnik klikne "Provjeri" pa "Kreiraj Naimenovanja" na 94
   stavki fakture 1476/26) → log pokazuje **26 ispravno popunjenih
   naimenovanja**. Ovo je isključilo `create_smart_group()`/field-mapping
   kao uzrok.
4. Automatski test ("Puna automatizacija") → log NIKAD nije pokazao
   `auto=True` poziv nijedne od dijagnostikovanih funkcija — dokaz da
   `_puna_auto_pipeline` nikad nije ni pokrenuta.
5. Otkriveno da korisnik jedan test slučajno pokrenuo na POGREŠNOM,
   zastarjelom EXE-u (`.worktrees/agent-v2/dist/`, 12:31, prije svih
   popravki) — ispravljeno provjerom `Get-Process DeklarantPro | Path`.
6. Korisnik otkrio "Aktivnosti" tab (treći tab pored "Agent"/"Pitanja") u
   Agent panelu — `chat.add_activity()` ide tamo, ne u glavni chat. Taj log
   je pokazao: `"⚠️ Prethodna sesija prekinuta u fazi: analyzing"` (Blagić
   fakture — DRUGA sesija/faktura) na samom početku, i tok se zaustavlja na
   `"🔄 Faza: Završeno"` odmah nakon uvoznog EUR1 dijaloga — bez ijedne
   poruke iz `_puna_auto_pipeline`.
7. Zaključak: session restore mehanizam je vratio draft sa BAREM JEDNIM
   zastarjelim naimenovanjem iz DRUGE sesije. `items_created` kapija
   (`bool(draft.items)`) je to lažno prihvatila kao "kreirano za trenutnu
   fakturu", `_puna_auto_pipeline` se nikad nije pozvala (jer
   `pre_item_gates` provjera u `run_declaration_workflow._run()` je vidjela
   sve kapije prije `items_created` uključujući i nju kao već prošle), a
   `items_validated` je onda ispravno prijavila da TO staro naimenovanje
   nema popunjena polja.

## Fix
`items_created` kapija sad provjerava da SVAKA `invoice_lines` stavka ima
`assigned_naimenovanje_id` koji pokazuje na POSTOJEĆI `item_id` u
`draft.items` (polje koje `create_smart_group()` uvijek postavlja po
liniji) — ne samo `bool(items)`. Ako ijedna stavka nije povezana (zastarjelo
ili nedostaje), kapija ispravno javlja "nije kreirano", i
`run_declaration_workflow` onda ISPRAVNO poziva `_puna_auto_pipeline`, koja
(preko `create_smart_group()`) prvo briše stara items i kreira nova iz
TRENUTNIH `invoice_lines`.

## Šta nije dirano
- `_puna_auto_pipeline` sama (osim §77 async wait, ranije u istoj istrazi)
- Session restore mehanizam (namjerna resilience funkcija — nije bug sam
  po sebi, samo otkrio slabost u items_created provjeri)
- `create_smart_group()`/field-mapping logika — dokazano ispravna

## Verifikacija
- Dijagnostički logovi (privremeni) uklonjeni nakon što je uzrok pronađen —
  ne ostaju u kodu.
- Test fixture `_minimal_ready_draft()` ažuriran da postavi
  `assigned_naimenovanje_id` (odražava stvarno stanje nakon
  `create_smart_group()`) — bez toga bi 2 postojeća testa pukla nakon fixa
  (potvrđeno, pa ispravljeno).
- Novi test `test_zastarjelo_naimenovanje_iz_prethodne_sesije_ne_prolazi_items_created`
  direktno reprodukuje scenario (item sa `item_id` koji NE odgovara nijednoj
  liniji) i dokazuje da kapija sad ispravno blokira.
- Puna svita: `python -m pytest tests/ -q` → 1416 passed, 85 skipped,
  5 xfailed, 0 failed (isti 3 pre-postojeća nepovezana pada, dokumentovana
  u §71 CONTEXT.md).
- `scripts/sync_dist_client.py --apply` pa dry-run → 0 stvarnih razlika.

## Pronađeni problemi
- Dvije "lažne trage" prije pravog nalaza (spec.datas pretpostavka, pogrešan
  EXE) — dokumentovano u §78 CONTEXT.md kao pouka za buduće agente.
- `id(self.draft)` u dijagnostičkim logovima se prikazivao kao
  `[REDACTED_JIB]` — `SensitiveDataFilter` (ranija sigurnosna popravka ove
  sesije) pogrešno prepoznaje veliki memorijski id() broj kao 13-cifreni
  JIB i redaguje ga. Ovo je onemogućilo direktno poređenje draft identiteta
  preko log fajla tokom istrage — nije popravljeno (dijagnostika je
  uklonjena), ali vrijedi zapamtiti za buduću dijagnostiku sličnog tipa.

## Konflikti / kontradiktorni izvori
§77 fix (async wait) nije bio pogrešan — ostaje validan, rješava stvaran
(drugi) problem. Ovaj izvještaj NE poništava §77, dopunjuje ga.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `9dd95e0` | `fix(agent): items_created kapija ne smije prihvatiti zastarjela naimenovanja` |

## Rizici / ograničenja
- Ako `assigned_naimenovanje_id`/`item_id` veza ikad postane nekonzistentna
  iz DRUGOG razloga (npr. ručna izmjena XML-a van aplikacije), kapija bi
  ispravno (namjerno) tražila ponovno kreiranje naimenovanja — ovo je
  namjerno konzervativno ponašanje, ne bug.
- Session restore mehanizam sam po sebi nije mijenjan — ako je poželjno da
  restore NE ostavlja "tuđa" naimenovanja u novom kontekstu, to bi bio
  poseban, širi zahvat (van scope-a ovog fixa).

## Potreban follow-up
- Rebuild EXE-a i vizuelna potvrda da "Puna automatizacija" sad stvarno
  ide do kraja (do XML izvoza) sa svježim, nekonfliktnim draft stanjem
  (očekuje se da PROĐE — sad zavisi samo od stvarnog stanja Zaglavlja koje
  je ranije bilo nepopunjeno, poseban, legitiman nalaz od 2026-07-27 19:04
  testa, van scope-a ovog fixa).
- Razmisliti (odvojeno, ne sad) da li session restore treba eksplicitno
  čistiti/upozoravati na "tuđa" naimenovanja pri učitavanju druge fakture.

## Potrebna korisnička potvrda
- Potvrditi uživo (nakon rebuild-a) da "Puna automatizacija" sad ili
  ispravno kreira naimenovanja i nastavlja dalje, ili se zaustavlja na
  kasnijoj, legitimnoj kapiji (npr. Zaglavlje) sa ispravnom porukom — ne
  više na lažno-praznom naimenovanju.
