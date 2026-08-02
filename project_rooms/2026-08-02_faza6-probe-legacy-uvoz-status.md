# PROBE — Faza 6: da li legacy uvoz put treba ukloniti/zamijeniti ili samo izdvojiti?

## Pitanje
Da li se `_finish_import_legacy_path`/`_process_batch_records_legacy` mogu
zamijeniti proširenjem unified import puta (`ImportWorkflowService`/
`prepare_import()`/`apply_import_plan()`), ili treba samo izdvojiti postojeću
logiku u zaseban servis bez promjene arhitekture?

## Pretpostavka
Iz faznog plana (2026-08-01): pretpostavljeno da je ovo otvoreno pitanje koje
zahtijeva mjerenje stvarnog omjera legacy/unified uvoza prije odluke.

## Način provjere
Dokumentaciona arheologija umjesto mjerenja u produkciji: pretraga
`docs/context/history.md` i `project_rooms/` za prethodni rad na istoj temi,
prije nego što se PROBE radi ispočetka.

## Rezultat
**Pitanje je već riješeno u ranijoj sesiji (2026-07-24/25, Codex/Pi) — nije
otvoreno pitanje, nego dovršena arhitektonska odluka.**

Postoji kompletan master plan `docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_
IMPLEMENTATION_PLAN.md` (odobren 2026-07-24, scope: ručni pojedinačni +
ručni grupni + Agent uvoz). Faze 0-8 tog plana su IZVRŠENE (`docs/context/
history.md` #49-53, #57 — uklj. e2e test na 4 stvarna vendor formata:
Master Frigo, PIP Food, SRECKO, Medicopharm):

- Ručni pojedinačni uvoz → unified tok (Faza 6, `history.md` #51)
- Agent uvoz → unified tok (Faza 7, `history.md` #52)
- Ručni grupni uvoz → unified tok (`history.md` #53)

Legacy putevi (`_on_import_finished_legacy` → kasnije preimenovan u
`_finish_import_legacy_path`, `_process_batch_records_legacy`) su OSTALI
**namjerno i eksplicitno**, ne kao nedovršena migracija:

> "Legacy batch tok ostaje namjerno kao `_process_batch_records_legacy()`
> samo kada je `assembly.master_list_loaded=True`, jer Assembly/Master-list
> režim i dalje ima posebnu logiku koja nije dio neutralnog draft apply
> servisa. **Ne brisati ove fallback-e dok poseban Assembly tok ne bude
> eksplicitno pokriven servisom i testovima.**" (`history.md` #53)

Test matrica master plana (§17) eksplicitno navodi Assembly/master-lista kao
red sa očekivanim rezultatom "**Postojeći podržani tok ostaje funkcionalan**"
— tj. NIJE u scope-u unifikacije, po dizajnu, ne slučajno zaboravljeno.

## Dokaz
- `docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md` (cio pročitan)
- `docs/context/history.md` #49-53, #57 (cio odjeljak pročitan)
- `project_rooms/2026-07-24_faza0-sigurnosna-analiza-import-workflow.md` (cio pročitan)
- `tests/integration/test_real_invoice_import_e2e.py` postoji i pokriva unified tok na realnim fakturama

## Ograničenja rezultata
Nisam mjerio stvarni % legacy vs unified uvoza u produkciji (npr. koliko
često korisnik stvarno koristi "Učitaj glavnu listu" dugme) — ali to
mjerenje više nije potrebno jer odluka ne zavisi od tog omjera: Assembly
tok ostaje bez obzira na učestalost, sve dok ne dobije sopstveni servis.

## Preporuka
Preformulisati Fazu 6 mog plana (2026-08-01) iz "odluči da li legacy umire
ili se unified proširuje" u: **izdvoji Assembly/master-list logiku iz
`_finish_import_legacy_path`/`_process_batch_records_legacy` u zaseban
servis** (isti obrazac kao Faze 1-5, ne dublja arhitektonska promjena).
Ovo je niži rizik nego što je originalni plan pretpostavljao — arhitektonska
odluka je već donesena, ostaje samo mehanička ekstrakcija + testovi koje
`history.md` #53 eksplicitno traži kao uslov ("dok ne bude pokriven servisom
i testovima").

## Odluka koju sada možemo donijeti
Faza 6 se može raditi kao redovna ekstrakciona faza (kao Faze 1-5), NE kao
posebno rizičan arhitektonski zadatak. Ne treba korisnička odluka o
"unified vs legacy" — ta odluka je već donesena. Jedina preostala odluka za
korisnika: da li se Faza 6 radi sada (ekstrakcija Assembly logike u servis)
ili se ostavlja za kasnije jer trenutni fallback već radi ispravno
(potvrđeno testovima i e2e).
