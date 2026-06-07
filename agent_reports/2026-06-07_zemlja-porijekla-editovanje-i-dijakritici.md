# Izvještaj: Editovanje zemlje porijekla i normalizacija dijakritika (108VP-2026)

**Datum:** 2026-06-07
**Prijavio:** Radovan (faktura 108VP-2026, Blagić-Loren, F:\najavauvoza\LOREN\fwrauni)

## Šta je urađeno

Riješena su DVA povezana bug-a koja su se manifestovala na konkretnoj fakturi:

1. **Korisnik nije mogao ručno promijeniti "Zemlja porijekla" u tabeli faktura**
   — uneseni tekst se odmah vraćao na staru vrijednost.
2. **Zemlja porijekla se prikazivala kao puno ime "Španija" umjesto ISO koda "ES"**,
   a posljedično ni povlastica (EUP) nije bila predložena za tu stavku.

## Kako je urađeno

### Bug 1 — "ne mogu da promijenim zemlju"
`gui/tabs/faktura_view.py::_on_item_changed` je za kolonu 9 (Zemlja porijekla)
čitao `item.data(Qt.UserRole)` umjesto stvarno upisanog teksta. `Qt.UserRole` je
služio kao keš PRETHODNE vrijednosti koju je upisala `_apply_country_confidence_color`
pri auto-bojenju ćelije (npr. "Spanija" prije korisnikove izmjene). Kad bi korisnik
upisao "ES", handler je odbacivao novi tekst i vraćao stari iz `Qt.UserRole`.

Fix: handler sada izvodi "čistu" vrijednost direktno iz upisanog teksta — skida se
samo eventualni ikonica-prefiks (✅/📋/⚠️/🚨), ništa se ne čita iz `UserRole`.

Bitno: ovaj bug je **PRE-EXISTING** (potiče iz `0149de9c`, prvog Windows-deploy
commita — provjereno preko `git log -S`), nije nastao mojim ranijim izmjenama.
Manifestovao se baš na ovoj fakturi jer je tu prvi put zemlja prikazana kao puno
ime umjesto ISO koda (vidi Bug 2).

### Bug 2 — "Španija" umjesto "ES" → povlastica nije upisana
`utils/country_normalizer.py::normalize_country_name` radi tačan lookup u
`COUNTRY_NAME_TO_CODE` mapi. Mapa je sadržavala `"spanija": "ES"`, ali NE i
`"španija": "ES"` (sa Š). Excel iz Blagić-Loren parsera (kolona "Poreklo", red 3,
proizvod 14506 CUBIGEL kompresor) sadrži "ŠPANIJA" velikim slovima sa dijakritikom
— lookup nije pogodio, pa je sirova vrijednost prošla nepromijenjena u
`zemlja_porijekla`.

Lančana posljedica: `_suggest_preference_by_country()` provjerava
`country_code.upper() in eu_countries` gdje `eu_countries` sadrži ISO kodove
('ES', 'DE'...). "ŠPANIJA" tu nikad ne pogađa → vraćeno `''` → povlastica ostaje
prazna. Korisnikova pritužba "ta stavka ima povlasticu i nije upisana" je dakle
**direktna posljedica** ovog istog bug-a, ne poseban problem.

Fix: dodat generički `_strip_diacritics()` helper (unicodedata NFD normalizacija +
filter combining marks) kao FALLBACK nakon tačnog lookup-a u
`normalize_country_name`. Pokriva "ŠPANIJA", "NEMAČKA", "ČEŠKA", "ŠVAJCARSKA" i sve
buduće slične slučajeve generički — bez ručnog upisivanja svih kombinacija
dijakritika/velikih slova u mapu.

Verifikovano direktnim testom:
```
ŠPANIJA      -> ES
Spanija      -> ES
ŠVAJCARSKA   -> CH
ITALIJA      -> IT
NEMAČKA      -> DE
ČEŠKA        -> CZ
KINA         -> CN
```

## Zašto

- Bug 1: `Qt.UserRole` je korišten kao izvor istine u change-handleru, iako Qt ne
  sinhronizuje tu rolu automatski sa korisnikovim direktnim izmjenama prikazanog
  teksta — klasičan "stale cached value nadjačava korisnikov unos" pattern (ista
  porodica kao GREJAC SPIRALA tarifa-bug iz iste sesije).
- Bug 2: mapa naziv→kod je punjena ručno uparenim varijantama (i "ceska" i "češka"
  postoje, ali "spanija"/"španija" par je propušten) — krhak pristup koji zahtijeva
  ručni unos za svaku novu kombinaciju. Generički diakritik-fallback je robustniji
  i sprječava cijelu klasu sličnih bugova unaprijed.

## Preporuka korisniku

Re-importovati fakturu 108VP-2026 (ili ručno upisati "ES" u postojeću stavku — sad
radi) kako bi se provjerilo da se i povlastica (EUP) ispravno predlaže za stavku
CUBIGEL kompresor.

## Tabela commitova

| Hash | Poruka |
|------|--------|
| `0948000` | fix(faktura): popravi nemogucnost rucne izmjene zemlje porijekla u tabeli |
| `523035d` | fix(import): dodaj fallback za nazive zemalja sa dijakritikom (ŠPANIJA→ES) |

## Memorija

- `2026-06-07_qt-userrole-stale-data-zemlja-porijekla.md`
- `2026-06-07_dijakritik-normalizacija-zemalja.md`
