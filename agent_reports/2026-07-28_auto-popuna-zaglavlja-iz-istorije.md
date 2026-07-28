## Datum
2026-07-28

## Agent
Claude Code (Sonnet 5)

## Scope
`services/agent/workflow/header_autofill_service.py` (novi fajl),
`services/agent/workflow/declaration_workflow_service.py`,
`dist_client/` mirror oba, `tests/unit/test_header_autofill_service.py` (novi).

## Status izvora
- `2026-07-27_puna-automatizacija-prazno-naimenovanje-istraga-u-toku.md`
  (fajl-memorija) — aktivan, ovo je direktan follow-up dogovoren na kraju
  te sesije ("SLJEDEĆI KORAK").
- `docs/CONTEXT.md` §75-79 — aktivan, opisuje stanje na koje se ovaj
  zadatak nadovezuje (Puna automatizacija radi do Zaglavlja, zaustavlja se
  tamo ispravno ali sa nepotrebno praznom kolonom).
- Nema konflikta — ovo je čist NOV zahtjev (proširenje), ne bugfix
  postojećeg koda.

## GitNexus impact
`run_declaration_workflow` upstream: risk **LOW**, 4 direktna pozivaoca
(`AgentController._on_all_completed` × 2 kopije root/dist_client,
`chat_intent_handler._handle_message_v2` × 2 kopije), 0 affected_processes.
Izmjena ne mijenja potpis funkcije niti postojeće ponašanje van novog
"probaj auto-popunu" koraka — nije zahtijevan `project_rooms/` fajl (samo
za HIGH/CRITICAL).

`detect_changes(scope=all)` nakon izmjene: risk_level low, promijenjeni
simboli tačno `run_declaration_workflow`/`_run` u root+dist_client, 0
affected_processes.

## Šta je urađeno
1. Novi headless servis `header_autofill_service.py::
   auto_fill_header_from_history(ctrl, chat)` — nađe najbliži istorijski
   XML za trenutnog izvoznika i popuni prazna Izvoznik/Primalac/Deklarant
   (i sva ostala prazna header polja) polja drafta.
2. Povezano u `declaration_workflow_service.py::_run()`, tačno prije
   `header_ready` provjere: ako kapija ne prolazi, prvo se pokuša
   auto-popuna pa ponovo izračuna stanje; poruka o nedostajućim poljima se
   šalje samo ako i nakon toga kapija i dalje ne prolazi.
3. Isti fix portovan u `dist_client/` (bio identičan root-u prije izmjene,
   provjereno diff-om — razlika samo CRLF/LF, postojeća konvencija).
4. 6 novih unit testova.

## Zašto je urađeno
Korisnik je uživo testirao i pokazao da automatizacija ostavlja
Izvoznik/Primalac/Deklarant skoro prazne (samo naziv izvoznika iz uvoza
fakture), dok ručno dugme "Uvezi XML" u Zaglavlju popuni kompletnu kolonu.
Cilj: automatizacija treba sama da povuče te podatke kad god postoji
istorijska deklaracija za tog izvoznika, i da se zaustavi na ručni unos
SAMO kad stvarno nema odakle (prvi put za tog izvoznika, ili nepotpun
istorijski XML).

## Kako je urađeno
Istražena su dva postojeća, ranije međusobno nepovezana mehanizma:
- `exporter_xml_indexer.find_xml_for_pair()` — lookup najnovijeg XML-a po
  paru izvoznik(+primalac), iz `catalogs.exporter_xml_index`.
- `ZaglavljeService.load_from_xml()` — puni ASYCUDA XML parser (isti koji
  koristi dugme "Uvezi XML" preko `zaglavlje_controller._on_import_xml`),
  širi od `faktura_view.py::_extract_header_from_xml()` koji koristi dugme
  "Prethodna deklaracija" u Fakturi (uzak podskup polja).

Direktan poziv `_on_import_xml` je odbačen jer poziva `view.show_success/
show_warning`, koji otvaraju modalni `QMessageBox` (`base_view.py`) — u
headless automatizaciji bi to blokiralo čekajući klik. Umjesto toga novi
servis radi isti posao bez GUI dijaloga i upisuje SAMO prazna polja
direktno na `draft` (isti obrazac kao već postojeći
`faktura_view.py::_apply_import_result_to_header`). Ako je Zaglavlje tab
trenutno otvoren, poziva se `zaglavlje_tab.load_from_draft(draft)` da se
osvježi prikaz (isti poziv kao postojeći `_on_load_previous_declaration`).

## Šta nije dirano
- `_on_import_xml` (GUI dugme "Uvezi XML") — nepromijenjeno, i dalje traži
  fajl ručno i prikazuje dijaloge.
- `_on_load_previous_declaration` / `_extract_header_from_xml` u
  `faktura_view.py` (dugme "Prethodna deklaracija") — odvojen, uži
  mehanizam; nije zamijenjen ni uklonjen.
- `_puna_auto_pipeline` (prva polovina automatizacije, mase→tarife→
  validacija→naimenovanja) — netaknuta, novi korak se nadovezuje tek u
  drugoj polovini (`declaration_workflow_service.py`).
- `exporter_xml_indexer.py` i `zaglavlje_service.py` — samo pozvani, bez
  izmjena unutar njih.

## Verifikacija
- `python -m py_compile` čist na sva 4 dotaknuta fajla (root+dist_client).
- 6 novih testova prolazi (`test_header_autofill_service.py`).
- Puna svita: **1424 passed** (1418 prije + 6 novih), 3 pre-postojeća
  nepovezana pada (`test_tool_use.py`/`test_tool_use_offline.py` — tool
  registry drift nepovezan sa Zaglavljem; `test_xml_parser_fix.py` —
  hardkodovana Linux putanja `/home/radovan/...`, ne postoji na ovom
  Windows PC-u) + 1 pre-postojeći error (`test_model_benchmark.py` —
  vjerovatno network/API zavisnost). Sve potvrđeno nepovezano sa ovom
  izmjenom (nijedan od ta 4 fajla nije dotaknut).

## Pronađeni problemi
Nema novih. Potvrđeno da su 3 pada + 1 error pre-postojeći (isti fajlovi
kao u §79 "3 pre-postojeća nepovezana pada", plus jedan dodatni error koji
prethodni izvještaj nije eksplicitno brojao — nije uzrokovan ovom sesijom).

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `4a3f60f` | feat(agent): auto-popuni Izvoznik/Primalac/Deklarant iz istorijskog XML-a u Puna automatizacija |

## Rizici / ograničenja
- Auto-popuna se oslanja na `catalogs.exporter_xml_index` (PostgreSQL) —
  ako server nije dostupan ili indeks nije popunjen za tog izvoznika,
  tiho se preskače (fallback na postojeće ponašanje: kapija se zaustavlja
  i traži ručni unos, što je ionako bio prethodni ishod).
  `find_xml_for_pair`/`load_from_xml` greške se hvataju i loguju kao
  warning, ne ruše workflow.
- `load_from_xml` može vratiti podatke iz DRUGOG konteksta (npr. stariji
  kurs/carinarnica koji se promijenio) — polja se popunjavaju samo ako su
  prazna, ali ne postoji validacija "da li je istorijski podatak još
  uvijek tačan" (isti rizik već postoji kod ručnog dugmeta "Uvezi XML" i
  "Prethodna deklaracija", nije nov rizik uveden ovom izmjenom).

## Potreban follow-up
Uživo testirati sa stvarnom fakturom istog izvoznika koji ima istorijski
XML u `catalogs.exporter_xml_index`, potvrditi da automatizacija sada
stiže do `cross_check_passed`/`xml_preflight_passed` kapija umjesto da
stane na `header_ready` (kao što je urađeno za §75-79 popravke).

## Potrebna korisnička potvrda
- Da li polja koja `load_from_xml` vrati (npr. Tip deklaracije, kurs) za
  NOVU deklaraciju treba uvijek preuzeti iz najnovijeg istorijskog XML-a,
  ili neka polja (kurs pogotovo) NE bi trebalo auto-popunjavati jer se
  mijenjaju po deklaraciji (trenutno se popunjavaju SAMO ako su prazna, pa
  je rizik nizak, ali vrijedi eksplicitno potvrditi za polje "kurs").
