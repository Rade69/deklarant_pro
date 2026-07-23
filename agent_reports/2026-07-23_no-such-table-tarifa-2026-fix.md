## Datum
2026-07-23

## Agent
Claude Code (Sonnet 5)

## Scope
- `gui/tabs/sifarnici/tariff_hierarchy.py` + `dist_client/` kopija
- `tests/unit/test_tariff_hierarchy_db_path.py` (novo)
- `docs/CONTEXT.md` §44

## Status izvora
Nema ranijeg agent_reporta za ovaj konkretan bug. Referentni izvor za rješenje:
`services/tariff/tarifa_service.py::_resolve_db_path()` — isti obrazac buga (compiled/frozen
build resolving pogrešnu putanju) već ranije riješen tamo i u `dist_client/services/
tarifa_service.py` (DB_PATH runtime patch, vidi `2026-05-31_windows-deploy-fixes-2.md`).

## GitNexus impact
`gitnexus_impact` na `populate_tariff_hierarchy` prije izmjene: LOW risk, 0 direktnih poziva
u grafu (funkcija se poziva iz `sifarnici_view.py` ali GitNexus graf to nije uhvatio —
potvrđeno ručno preko `grep`). Nakon izmjene `gitnexus_detect_changes`: risk_level LOW,
affected_count 0.

## Šta je urađeno
Korisnik je prijavio grešku "Greška pri pretrazi trgovačkih naziva: no such table: tarifa_2026"
u Šifarnici tabu, uz sumnju da je Codex-ov paralelni redizajn tog taba nešto pokvario.

1. Provjereno PRVO da li je Codex uzrok — `diff` `tariff_hierarchy.py` između root-a,
   `dist_client/` i `.worktrees/codex-faktura-toolbar/` pokazao je BIT-ZA-BIT identičan
   fajl u sva tri mjesta. Codex NIJE uzrok.
2. Pronađen pravi uzrok: `_DB_PATH` računat fiksnom `__file__`-relativnom putanjom bez
   `sys.frozen` svijesti — u kompajliranom `.exe`-u `__file__` pokazuje unutar `_internal/`
   bundle-a, a `deklarant_sistem.db` (read-write, lokalna) NIJE u `deklarant_pro.spec`
   `datas` listi (bundluju se samo `zvanicna_tarifa.db`/`inspection_rules.db`).
   `sqlite3.connect()` na nepostojećoj putanji tiho pravi praznu bazu → "no such table".
3. Primijenjen isti robustan fallback obrazac kao u `tarifa_service.py::_resolve_db_path()`
   (lista kandidata: standardna dev putanja → frozen exe-folder putanja → CWD-relativna).
4. Napisana 3 nova testa (`monkeypatch` na `__file__`/`sys.frozen`/`sys.executable`).

## Zašto je urađeno
Korisnik je aktivno naišao na grešku u živoj aplikaciji i eksplicitno pitao da li je Codex
uzrok — bilo je bitno prvo dati definitivan, provjeren odgovor (nije), a zatim popraviti
stvarni uzrok umjesto nagađanja.

## Kako je urađeno
`_resolve_db_path()` funkcija (kopirana filozofija iz `tarifa_service.py`, ne doslovno isti
kod jer je putanja jedan nivo dublja — `gui/tabs/sifarnici/` vs `services/tariff/`): lista
kandidata koja uključuje frozen-svjestan fallback (`os.path.dirname(sys.executable)`) samo
kad je `getattr(sys, 'frozen', False)` istinito, plus CWD-relativni fallback za edge case.

## Šta nije dirano
- `.worktrees/codex-faktura-toolbar/` — nije dirano jer je to Codex-ova aktivna radna grana;
  isti bug tamo će se riješiti kad se ta grana spoji/rebase-uje na ovaj fix, ili ga Codex/
  korisnik mogu ručno povući.
- `deklarant_pro.spec` (datas lista) — nije dirano; alternativno rješenje bi bilo dodati
  `deklarant_sistem.db` u bundle, ali to bi značilo da se lokalno naučeni podaci brišu pri
  svakom rebuild-u (baza mora ostati read-write van bundle-a).
- `services/tariff/tarifa_service.py` sam — već ispravan, korišten kao referenca.

## Verifikacija
- Potvrđeno uživo (lokalno) da `database/deklarant_sistem.db` postoji i ima `tarifa_2026`
  tabelu — bug se NE reprodukuje u dev modu (python run), samo u frozen `.exe`-u, što
  objašnjava zašto korisnik nije ranije primijetio problem u razvojnom okruženju.
- 3 nova testa prolaze (`test_resolve_db_path_koristi_standardnu_putanju_kad_postoji`,
  `test_resolve_db_path_frozen_fallback_na_exe_folder`,
  `test_resolve_db_path_vraca_prvi_kandidat_kad_nista_ne_postoji`)
- Pun test suite: 918 passed (915+3 novih), isti pre-postojeći 3 fail/1 error nepovezani
- `py_compile` čist na oba fajla (root + dist_client), `diff` potvrđuje identičnost

## Pronađeni problemi
Prvi test (`test_resolve_db_path_vraca_prvi_kandidat_kad_nista_ne_postoji`) je inicijalno
pao zbog greške u SAMOM TESTU (CWD-relativni kandidat je slučajno postojao jer pytest radi
iz root-a projekta gdje `database/deklarant_sistem.db` stvarno postoji) — ispravljeno
dodavanjem `monkeypatch.chdir(tmp_path)`.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
|---|---|
| 29f3015 | fix(sifarnici): "no such table: tarifa_2026" u pretrazi trgovačkih naziva |

## Rizici / ograničenja
- Nisam mogao direktno reprodukovati bug u stvarnom PyInstaller `.exe`-u (zahtijeva pun
  rebuild) — hipoteza je potvrđena posrednim dokazima (identičan poznat obrazac buga već
  riješen na drugom mjestu u istom kodu, `deklarant_sistem.db` potvrđeno odsutan iz spec
  `datas` liste, `sqlite3.connect()`-ovo poznato ponašanje tihog kreiranja fajla) i
  jediničnim testovima koji simuliraju frozen okruženje preko `monkeypatch`.

## Potreban follow-up
- Nakon sljedećeg rebuild-a `.exe`-a, ručno provjeriti da numerička pretraga u "Trgovački
  nazivi" (Šifarnici tab) radi ispravno u stvarnom kompajliranom okruženju.
- Razmisliti da li postoje DRUGI moduli u `gui/` sa istim `__file__`-relativnim DB_PATH
  obrascem bez frozen-svijesti (nisam radio širi grep za sve slične slučajeve — ovaj put
  je fix bio reaktivan na konkretnu korisničku prijavu).

## Potrebna korisnička potvrda
- Potvrda nakon sljedećeg rebuild-a i testiranja stvarnog `.exe`-a da je pretraga tarifnog
  koda u Šifarnicima sad ispravna.
