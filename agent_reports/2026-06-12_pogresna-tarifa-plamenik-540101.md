# Agent report — Ispravka pogrešne tarife "Plamenik fi 75mm" (540 101)

## Datum
2026-06-12

## Agent
Claude Sonnet 4.6 (Claude Code, grana `windows`)

## Scope
- `catalogs.product_tariff_mapping` (PostgreSQL, `database.db`) — jedan red, `id=62850`
- Novi fajl: `scripts/popravka_pogresne_tarife_plamenik_540101.py`
- Bez izmjena u aplikativnom kodu (GUI/servisi/importeri)

## GitNexus impact
Nije pokretan `gitnexus_impact` — zadatak ne mijenja nijedan kod-simbol
(funkciju/klasu/metodu), već jedan red u bazi znanja kroz novu skriptu
(isti pattern kao prethodna ispravka GREJAC SPIRALA, `scripts/popravka_pogresne_tarife_grejac_417un079.py`).
Nakon commitova pokrenut `npx gitnexus analyze` (Korak 5) — indeks ažuriran
na 39.136 nodes / 61.530 edges, bez upozorenja o riziku.

## Šta je urađeno
Korisnik je u GUI prikazu fakture 2420/2026 (ATOS preko Blagić Loren) primijetio
da su dvije "sestrinske" stavke istog proizvoda — "Plamenik fi 75mm" (red 54,
`product_code='540 101'`) i "Plamenik fi 100mm" (red 55, `product_code='540 103'`)
— iste zemlje porijekla (RS), dobile potpuno različite auto-popunjene tarifne
brojeve: `72254090` (čelični lim / "TV TABLA") za fi 75mm, `85169000` (dijelovi
el. grejnih uređaja) za fi 100mm.

Dijagnosticiran je pogrešan zapis u `catalogs.product_tariff_mapping`
(`id=62850`, `product_code='540 101'`) i ispravljen preko nove skripte
`scripts/popravka_pogresne_tarife_plamenik_540101.py`:
`commodity_code` `72254090 → 85169000`.

## Zašto je urađeno
**Uzrok**: zapisi `id=62850` (`540 101`) i `id=62851` (`540 103`) su kreirani
u ISTOJ SEKUNDI — 2026-04-14 15:51:18 — u nekoj ranijoj deklaraciji. `540 103`
je tada ispravno naučio `85169000` (kao i svi ostali "PLAMENIK"/"GRIJAČ ..."
zapisi dobavljača ATOS u bazi), ali `540 101` je naučio `72254090` — istu
tarifu kao potpuno nepovezana stavka "...TV TABLA 3,00X1500X3000"
(`supplier='HISTORIJA'`, `source='ptm_backup'`, `usage_count=17`). Vjerovatno
copy-paste/ručna greška u toj ranijoj deklaraciji, koju je `learn_from_draft()`
zapamtio i `_increment_usage()` ojačavao do `usage_count=13`.

**Mehanizam nadjačavanja**: `find_mapping()` (`services/tariff/tariff_mapping_service.py:402-428`)
ima exact-match po `product_code` kao apsolutni prioritet (vraća se odmah,
`similarity=1.0`, prije fuzzy/majority-vote provjere). Ovo je TREĆI put isti
obrazac kao [[pogresna-tarifa-grejac-spirala]] (2026-06-07,
`417UN079`/`19023010 → 85168080`) — jedan loš naučen zapis se trajno
"zaglavi" kao tačan rezultat i sam se ojačava.

**Alternativa razmatrana, odbačena**: izmjena `find_mapping()` da exact-match
prvo provjeri "porodičnu" konzistentnost (npr. uporedi sa sličnim
`naziv_robe` zapisima prije nego vrati exact match) — odbačeno kao van scope-a
ovog zadatka (veći refaktor matching logike, rizik regresije na svim ostalim
exact-match slučajevima koji su ISPRAVNI). Zabilježeno kao mogući follow-up.

## Kako je urađeno
1. Upit `catalogs.product_tariff_mapping` (`naziv_robe ILIKE '%lamenik%' OR
   commodity_code IN ('72254090','85169000')`) — pronađena oba "Plamenik"
   zapisa i nepovezani "TV TABLA" zapis sa istom (pogrešnom) tarifom.
2. Upit po `id`/`created_at`/`last_used` za `540 101`/`540 103` — potvrđeno
   da su kreirani u istoj sekundi (2026-04-14 15:51:18), oba `last_used`
   danas (auto-popuni za fakturu 2420).
3. Nova skripta `scripts/popravka_pogresne_tarife_plamenik_540101.py` —
   kopija pattern-a iz `popravka_pogresne_tarife_grejac_417un079.py`
   (dry-run default, `--execute` pravi CSV backup pa UPDATE).
4. Pokrenuto dry-run (potvrđen target red), zatim `--execute`.
5. Verifikacija: `TariffMappingService().find_mapping(product_code='540 101',
   naziv_robe='Plamenik fi 75mm', zemlja_porijekla='RS')` → vraća
   `tarifni_broj='85169000', similarity=1.0`.

## Šta nije dirano
- Aplikativni kod (`tariff_mapping_service.py`, GUI, importeri) — nepromijenjen,
  logika `find_mapping()` ostaje ista (exact-match prioritet), samo je
  ispravljen JEDAN pogrešan podatak.
- Trenutni draft/naimenovanje za fakturu 2420 (red 54) — NE ažurira se
  automatski; korisnik treba ručno promijeniti tarifu na `85169000` na već
  kreiranoj stavci.
- Nepovezan WIP koji je u repou prisutan paralelno (drugi agent/sesija):
  `AGENTS.md`, `gui/main_window.py` + `dist_client/gui/main_window.py`,
  novi `gui/utils/display_profile.py` + `dist_client/gui/utils/display_profile.py`,
  `styles/display_profiles.qss` + `dist_client/styles/display_profiles.qss`,
  `tests/unit/test_display_profile.py` — sve ostavljeno netaknuto i
  nestaged-ovano.

## Verifikacija
- `python -m scripts.popravka_pogresne_tarife_plamenik_540101` (dry-run) —
  pronašao tačan red, ispisao plan, ništa nije izmijenjeno.
- `python -m scripts.popravka_pogresne_tarife_plamenik_540101 --execute` —
  CSV backup (`scripts/_tariff_mapping_fix_backup_20260612_172640.csv`,
  gitignore-ovan), `UPDATE` 1 red.
- `TariffMappingService().find_mapping(...)` poslije ispravke vraća
  `85169000`/`similarity=1.0` (prethodno bi vratio `72254090`).
- `npx gitnexus analyze` x2 (prije i poslije commita stats-linije) — indeks
  svjež, 39.136/61.530, bez upozorenja.

## Pronađeni problemi
- Nijedan lažno pozitivan zaključak — dijagnoza potvrđena direktnim upitom
  baze (`id`/`created_at` podudaranje) i potvrđena `find_mapping()` pozivom
  prije i poslije ispravke.
- Tokom rada otkriveno da je PARALELNA sesija/agent commitovala
  `740e7f4` (Blagić Attos dedup) i pokrenula novi nepovezani rad
  (`display_profile`/`main_window.py`) — pažljivo provjeren `git status`
  prije svakog `git add`/`commit` da se izbjegne nehotično stageovanje
  tog WIP-a.

## Commitovi
| Hash | Tip | Opis |
|------|-----|------|
| `b5c34e8` | fix | Ispravka pogrešnog naučenog mappinga Plamenik fi 75mm (540 101): 72254090 → 85169000 |
| `0d19d3c` | chore | GitNexus index statistika (39052→39136 / 61374→61530) nakon ispravke |

## Rizici / ograničenja
- Ispravka je usmjerena na JEDAN red (`id=62850`); ne mijenja generalnu
  exact-match-prvi logiku u `find_mapping()`, pa se isti obrazac (loš naučen
  exact-match koji nadjača fuzzy/vote) može ponoviti za druge šifre u budućnosti.
- `usage_count=13` na ispravljenom redu ostaje nepromijenjen — odražava
  historijsku učestalost korišćenja te šifre, ne validnost trenutnog koda.

## Potreban follow-up
- Razmotriti generalni "porodični consistency check" za exact-match po
  `product_code` (treći put isti obrazac — GREJAC SPIRALA, pa ovaj) — van
  scope-a ovog zadatka, samo zabilježeno kao ideja.
- Korisnik treba ručno provjeriti i ostale stavke fakture 2420/2026 (i
  eventualno ranijih ATOS faktura) za slične "sestrinske" nekonzistentnosti.

## Potrebna korisnička potvrda
- Korisnik treba ručno ispraviti red 54 (Plamenik fi 75mm) na trenutno
  otvorenoj fakturi/naimenovanju 2420/2026 sa `72254090` na `85169000` —
  ispravka baze utiče samo na BUDUĆE auto-popunjavanje.
