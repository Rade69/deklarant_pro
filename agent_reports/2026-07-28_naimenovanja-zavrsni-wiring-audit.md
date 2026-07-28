# Završni wiring audit Naimenovanja refaktora

## Datum

2026-07-28

## Agent

Codex

## Scope

`services/naimenovanja/models.py`, Phase 4 View API, ručni izbor tarife,
samostalni `dist_client` runtime i karakterizacioni testovi Naimenovanja taba.
Glavna/windows grana nije mijenjana niti spojena.

## Status izvora

- `docs/CONTEXT.md` — aktivan, autoritativan.
- Claude pregled 19 commitova iz korisničke poruke — aktivan za dva potvrđena
  nalaza; tvrdnja o duplim brojevima CONTEXT sekcija je zastarjela.
- Kod grane `refactor/naimenovanja-3layer` — konačni izvor istine.
- `project_rooms/2026-07-26_naimenovanja-3layer-refaktor-plan.md` — aktivan kao
  plan, ali stvarno ponašanje je potvrđivano kodom i testovima.

## GitNexus impact

- `NaimenovanjeRenderContext`: LOW, četiri direktna importera, bez procesa.
- mrtvi Phase 4 `render_current_item`: LOW, nula pozivalaca.
- aktivni `NaimenovanjaView.render_current_item`: LOW u grafu, uz ručno
  potvrđene Controller i test pozive.
- `_load_current_item`: MEDIUM, pet direktnih pozivalaca; nije mijenjan.
- `_on_manual_tariff_search`: LOW, bez grafom pronađenih upstream pozivalaca.
- završni `detect_changes`: LOW za izmjene agenta; korisnički UI fajlovi su
  prepoznati kao postojeće, nepovezane izmjene i nisu stageovani.

## Šta je urađeno

- Dodat je nedostajući `dist_client/services/naimenovanja/models.py`.
- Uklonjen je mrtvi i nepotpuni render scaffold iz root i dist kopije.
- Zadržan je jedan kanonski, prethodno karakterizovan render put.
- Ručni izbor tarife preusmjeren je kroz View signal i Controller.
- Dodat je regresioni test koji dokazuje da View emituje tačno jedan zahtjev,
  ažurira prikaz i ne mutira draft.
- Potvrđen je potpuni Python paritet ključnih Naimenovanja root/dist fajlova.

## Zašto je urađeno

Samostalni dist runtime nije mogao uvesti Naimenovanja servis jer models modul
nije postojao. Alternativni render nije bio nova implementacija nego mrtav,
nepotpun put koji bi pri uključivanju pogrešno obrađivao combobox/QTextEdit
vrijednosti i izostavio više polja. Uklanjanje scaffolda je sigurnije od
aktiviranja neprovjerenog drugog renderer-a.

Ručna pretraga tarife je direktno mijenjala draft u View sloju i zaobilazila
Controller tarifni tok, uključujući centralno dodavanje dokumenata,
sinhronizaciju faktura stavki i dirty obavještavanje.

## Kako je urađeno

Root modeli su preslikani u dist runtime. Phase 4 modul sada sadrži samo aktivni
`read_current_form()` API. Nakon izbora u `TariffSearchDialog`, View postavlja
vrijednost widgeta uz `is_loading` guard i emituje
`tariff_lookup_requested`; postojeći Controller obavlja mutaciju.

## Šta nije dirano

- `_load_current_item()` i njegovo provjereno Rub.31/280 ponašanje.
- Kreiranje i grupisanje naimenovanja.
- Faktura, Zaglavlje, puna automatizacija i ASYCUDA XML builder.
- Četiri korisnička UI fajla i korisnikov Faktura refaktor plan.
- `.env` i sve tajne u njemu.
- Glavna/windows grana i merge istorija.

## Verifikacija

- `py_compile` svih izmijenjenih root/dist Python fajlova: prolazi.
- Samostalni import iz `dist_client` root-a: `DIST_IMPORT_OK`.
- Ciljani Naimenovanja paket: 41/41 prolazi.
- Novi i povezani karakterizacioni paket: 26/26 prolazi.
- Puna svita sa validnim procesnim `DEBUG=false`: 1366 passed, 72 skipped,
  5 xfailed.
- Puna automatizacija, ASYCUDA Rub.31/XML, penetration i sigurnosni testovi
  obuhvaćeni su punom svitom i prolaze.
- `git diff --check`: prolazi.

## Pronađeni problemi

Prvi puni test bez procesnog override-a imao je jedan pad prije izvršenja
kill-switch asercije: lokalna `.env` vrijednost `DEBUG=release` nije validan
boolean za Pydantic. Kod nije mijenjan jer je `AppSettings` CRITICAL simbol sa
368 pogođenih simbola, a problem je lokalna konfiguracija. Ponovljena puna
svita sa `DEBUG=false`, bez izmjene `.env`, prolazi u cijelosti.

Statički audit je pokazao da veliki legacy View još sadrži ranije postojeće
mutacije za pakovanja, dokumente, reload i apply-to-all. To nije nov wiring
regresijski nalaz i potpuna migracija bi bila zaseban MEDIUM/HIGH refaktor;
ovdje nisu dirane jer je korisnik već potvrdio živi tok, a `_load_current_item`
ima pet direktnih zavisnosti.

## Konflikti / kontradiktorni izvori

Claude navod o nedostajućem dist modelu i mrtvom render scaffold-u je potvrđen.
Navod da CONTEXT sekcije treba prenumerisati nije potvrđen: nema duplikata;
nedostaju samo istorijski brojevi 66–68. Korisnička potvrda nije potrebna.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `ef5cb3c` | `fix(naimenovanja): zatvori dist i render wiring gapove` |

## Rizici / ograničenja

Aktivni legacy render ostaje kompleksan i nije čist View po novom 3-layer
standardu. Njegovo kompletno razdvajanje nije bezbjedna mala popravka i treba
poseban scope-lock plan sa render karakterizacionim testovima.

## Potreban follow-up

- U aktivnom lokalnom `.env` postaviti `DEBUG=false` ili `DEBUG=true`; vrijednost
  `release` nije validna.
- Ako se želi potpuno čist 3-layer View, otvoriti poseban zadatak za migraciju
  `_load_current_item`, pakovanja i apply-to-all operacija.

## Potrebna korisnička potvrda

Na buildovanom EXE-u ručno provjeriti: Puna automatizacija → otvaranje
Naimenovanja → ručni izbor tarife → navigacija → XML izvoz.
