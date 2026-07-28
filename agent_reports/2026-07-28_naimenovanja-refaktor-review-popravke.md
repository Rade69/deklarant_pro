# Naimenovanja refaktor — popravke nakon code reviewa

## Datum

2026-07-28

## Agent

Codex

## Scope

Naimenovanja View/Controller/Service wiring za svih osam faza, DI composition
root, tarifni/PE/XML tokovi, karakterizacioni testovi i `dist_client` kopije.

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
- Faze 5–8 (`on_tariff_changed`, XML, PE i suggestion handleri): LOW, bez
  statičkih pozivalaca; stvarni pozivaoci su Qt signali.

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
- Tarifni debounce sada emituje namjeru Controlleru; lookup, dopunska JM,
  povezane faktura-stavke i dokumenti obrađuju se kroz Service.
- Kontrolisano KB učenje koristi sve linije povezane preko
  `assigned_naimenovanje_ordinal` i radi samo nakon korisničke potvrde.
- Prihvatanje prijedloga mijenja samo tarifni broj, ne zemlju ni povlasticu.
- PE dokumenti se normalizuju, uklanjaju bez povlastice, čiste iz sekundarnih
  polja i deduplikuju u zaglavlju.
- XML import više nije dvostruk: View bira/potvrđuje fajl, Service mutira isti
  draft i čuva aktuelna transportna polja, Controller osvježava oba taba.
- Root i `dist_client` Python kopije imaju potvrđen SHA-256 paritet.
- Naknadnom Windows smoke provjerom otkrivena je regresija Rub.31: refaktor je
  promijenio podrazumijevani GUI limit sa 280 na neograničeno. Vraćen je
  provjereni Windows algoritam koji čuva faktura referencu pri skraćivanju.

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

- ASYCUDA XML builder i XML export pravila.
- Četiri ranije izmijenjena generisana UI Python fajla.
- Novi, nevezani Faktura refaktor plan u radnom stablu.

## Verifikacija

- Prvi rez ciljano: `35 passed`; faze 5–8 ciljano: `52 passed`.
- Rub.31 ciljano: `44 passed` (uključuje kompletan ASYCUDA Rub.31 paket).
- Puna suite sa dostupnim serverom: `1361 passed, 72 skipped, 5 xfailed`.
- Server `192.168.0.25:5432`: TCP dostupnost potvrđena.
- Procesna varijabla `DEBUG=release` privremeno je pregažena sa `false`;
  `.env` već sadrži validno `DEBUG=False`.
- `py_compile` prolazi za svih šest root i šest `dist_client` runtime fajlova.
- SHA-256 sadržajni paritet root/`dist_client`: potvrđen za svih šest parova.
- `git diff --check`: prolazi.

## Pronađeni problemi

Procesno okruženje IDE-a ima `DEBUG=release`, što nadjačava ispravni `.env`.
Testovi su zeleni kada se proces pokrene sa `DEBUG=false`. To nije kodna
regresija, ali IDE/runtime environment treba trajno očistiti.

## Konflikti / kontradiktorni izvori

Raniji izvještaj navodio je nedostupan server i 11 padova. Korisnik je dao novu
adresu `192.168.0.25`; nakon promjene aktivnog `.env` hosta puna suite je zelena.
Korisnička potvrda nije potrebna za kod.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `2e145c3` | `fix(naimenovanja): zatvori controller wiring i zastiti draft` |
| `24fb7af` | `docs(report): evidentiraj popravke naimenovanja refaktora` |
| `7d9d6e2` | `refactor(naimenovanja): zavrsi tarifni dokument i xml tok` |
| `4e391eb` | `fix(naimenovanja): vrati rub31 limit iz windows grane` |

## Rizici / ograničenja

Qt signalne veze su dinamičke i GitNexus ih ne vidi u potpunosti; zato su
pokrivene offscreen i controller/service testovima. Ručni Windows smoke test
tarifnog dijaloga i XML izbora fajla još nije izvršen.

## Potreban follow-up

- U IDE/terminal okruženju ukloniti sistemsku/procesnu varijablu
  `DEBUG=release`, jer nadjačava `.env`.

## Potrebna korisnička potvrda

Ručno provjeriti u Windows aplikaciji: izmijeni stavku → Sljedeće/Prethodno, dodaj
stavku, obriši srednju stavku i potvrdi da susjedna stavka ostaje nepromijenjena.
