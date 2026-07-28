# Naimenovanja refaktor — popravke nakon code reviewa

## Datum

2026-07-28

## Agent

Codex

## Scope

Naimenovanja View/Controller/Service wiring, DI composition root, karakterizacioni
testovi i odgovarajuće `dist_client` kopije.

## Status izvora

- `project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md` — aktivan.
- Commitovi Faza 0–8 do `16be92a` — aktivna osnova.
- `docs/CONTEXT.md` pravila za multi-draft, Rb.31 i tipove polja — aktivna.

## GitNexus impact

- `delete_item`: LOW, bez statički detektovanih pozivalaca.
- `normalize_field_value`: LOW, jedan direktni potrošač.
- `_create_naimenovanja_tab`: LOW, četiri zavisna mjesta.
- `_format_trading_names`: LOW, dva direktna poziva.
- `_compute_statistical_value` i `_compute_pd_codes`: LOW, po jedan direktni poziv.
- Završni `detect_changes`: LOW; Qt dinamički signali dodatno su provjereni testovima.

## Šta je urađeno

- View save/navigacija/add/delete radnje emituju signale prema Controlleru.
- Controller snima aktivni draft kroz getter, orkestrira navigaciju i mutacije.
- Brisanje više ne snima staru formu nakon uklanjanja stavke.
- Normalizacija čuva `int`/`float` tipove i čisti tarifni broj.
- `TabFactory` prosljeđuje registrovani singleton `NaimenovanjaService`.
- Izdvojene PD, statističke i trgovačke kalkulacije koriste se u produkcijskom toku.
- GUI trgovački naziv više se ne skraćuje na XML limit od 280 znakova.
- Šest runtime fajlova preslikano je u `dist_client` uz SHA-256 paritet.
- Karakterizacioni testovi prošireni stvarnim widget/controller operacijama.

## Zašto je urađeno

Prethodni testovi potvrđivali su uglavnom početno stanje objekata, ali nisu izvršavali
roundtrip, navigaciju ili klikove. Posebno je potvrđena korupcija: brisanje srednje
stavke, pa save-before-navigation, prepisivalo je sljedeće naimenovanje podacima
obrisane forme.

## Kako je urađeno

UI zadržava dijaloge i prikaz, a korisničke CRUD namjere emituje signalima.
Controller primjenjuje formu kroz servis, šalje tačno jednu dirty/data promjenu i
renderuje validan indeks. Servis vraća informaciju da li je model stvarno promijenjen.

## Šta nije dirano

- Tarifni prijedlozi, XML import, PE sinhronizacija i ASYCUDA builder.
- Četiri ranije izmijenjena generisana UI Python fajla.
- Korisnički `.env`.
- Nepovezani padovi DB i penetration testova.

## Verifikacija

- Ciljani paket: `35 passed`.
- Puna suite: `1346 passed, 72 skipped, 5 xfailed, 11 failed`.
- Deset padova zahtijeva nedostupan PostgreSQL/circuit breaker.
- Jedan pad je postojeći `.env` problem: `DEBUG=release` nije validan boolean.
- `py_compile` prolazi za svih šest root i šest `dist_client` runtime fajlova.
- SHA-256 sadržajni paritet root/`dist_client`: potvrđen za svih šest parova.
- `git diff --check`: prolazi.

## Pronađeni problemi

Puna suite zavisi od dostupnog PostgreSQL servera. Takođe, lokalni `.env` sadrži
`DEBUG=release`, zbog čega `AppSettings` penetration test pada prije izvođenja
same provjere.

## Konflikti / kontradiktorni izvori

Plan nalaže puni test gate, ali trenutna infrastruktura ne omogućava zelenu punu
suite bez dostupne baze i validnog lokalnog `DEBUG` podešavanja. Ciljani refaktorski
testovi i sve nepovezane test grupe prolaze. Korisnička potvrda nije potrebna za kod.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `2e145c3` | `fix(naimenovanja): zatvori controller wiring i zastiti draft` |

## Rizici / ograničenja

Qt signalne veze su dinamičke i GitNexus ih ne vidi u potpunosti; zato su pokrivene
offscreen klik i controller testovima. Ručni Windows smoke test još nije izvršen.

## Potreban follow-up

- Pokrenuti punu suite kada PostgreSQL bude dostupan.
- Ispraviti lokalni `DEBUG` u `.env` na validnu boolean vrijednost prije security testa.

## Potrebna korisnička potvrda

Ručno provjeriti u Windows aplikaciji: izmijeni stavku → Sljedeće/Prethodno, dodaj
stavku, obriši srednju stavku i potvrdi da susjedna stavka ostaje nepromijenjena.
