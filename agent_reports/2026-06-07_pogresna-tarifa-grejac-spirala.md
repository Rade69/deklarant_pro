# Agent Report: Ispravka pogrešne tarife "GREJAC SPIRALA 600W" (Blagić Loren)

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je pokazao screenshot iz uvezene fakture za **Blagić Loren** gdje je
stavka "GREJAC SPIRALA 600W" (šifra `417UN079`) auto-popunjena tarifom
`19023010` — službeni opis "Tjestenina, kuhana ili nekuhana ili punjena
(mesom ili drugim materijama)..." — i rekao da je to nemoguće jer se ta firma
bavi potpuno drugačijim robama (elektro-uređaji/grejači).

Pronađen je uzrok: **loš zapis u bazi znanja `catalogs.product_tariff_mapping`**
(`product_code='417UN079', naziv_robe='GREJAC SPIRALA 600W', commodity_code=
'19023010'`) koji je preko prioritetnog exact-match-a po `product_code`
nadjačao ispravnu fuzzy/majority-vote logiku. Korisnik je odabrao opciju
"UPDATE na 85168080" (tačna tarifa za električne grejne elemente, ista kao svi
ostali "GREJAC ..." proizvodi u bazi).

**Rezultat**: jedan red u `catalogs.product_tariff_mapping` ažuriran —
`commodity_code` promijenjen sa `19023010` na ispravan `85168080`.

## Kako je urađeno

1. **Reprodukcija problema preko `TariffMappingService.find_mapping()`**:
   - Pozivom BEZ `product_code` (samo `naziv_robe='GREJAC SPIRALA 600W'`):
     majority-vote logika je ispravno predložila `85168080` sa **81% glasova**
     (510/632), na osnovu svih ostalih "GREJAC ..." zapisa u bazi (svi mapirani
     na `85168080`, `usage_count=13`, `RS`/`CEFTAR`).
   - Pozivom SA `product_code='417UN079'`: vraćen je odmah pogrešan `19023010`
     sa `similarity=1.0` — exact-match po šifri ima apsolutni prioritet u
     `find_mapping()` (`tariff_mapping_service.py:346-372`) i fuzzy/vote logika
     se uopšte ne pokreće kad postoji exact match.

2. **Provjera baze**: pretragom `product_tariff_mapping` po `product_code =
   '417UN079'` pronađen je tačno jedan zapis sa pogrešnom tarifom,
   `usage_count=7`, `last_used` = isti dan ujutru (2026-06-07 06:07) — dakle
   greška je već postojala u bazi i samo se ojačavala kroz `_increment_usage`
   pri svakom uspješnom (pogrešnom) matchu.

3. **Predlog korisniku** kroz `AskUserQuestion` (3 opcije: UPDATE na
   `85168080`, brisanje zapisa, ili ručna ispravka samo na fakturi bez diranja
   baze) — **korisnik izabrao "UPDATE na 85168080"**.

4. **Skripta `scripts/popravka_pogresne_tarife_grejac_417un079.py`**
   (dry-run/`--execute`/CSV-backup pattern, isti kao u prethodnim popravkama):
   - Pronalazi tačno taj jedan zapis (po `product_code` + `naziv_robe` +
     pogrešnom `commodity_code`)
   - Pravi CSV backup stanja prije izmjene
     (`scripts/_tariff_mapping_fix_backup_20260607_092204.csv`, gitignore-ovan)
   - `UPDATE commodity_code = '85168080' WHERE ...` — `precision_1`,
     `zemlja_porijekla`, `povlastica`, `usage_count` ostaju nepromijenjeni
     (jer su ispravni — odgovaraju stvarnim podacima sa fakture: CN, bez
     povlastice)

5. **Verifikacija**: ponovni poziv `find_mapping(product_code='417UN079',
   naziv_robe='GREJAC SPIRALA 600W', ...)` sada vraća ispravno
   `tarifni_broj='85168080'` sa `similarity=1.0`.

## Zašto

**Uzrok**: u `find_mapping()` exact match po `product_code` ima apsolutni
prioritet (vraća se odmah, prije fuzzy/vote provjere). Ovo je dizajn-odluka
koja daje brzinu i preciznost KADA je naučen mapping ispravan — ali ako se
JEDNOM upiše pogrešna tarifa za neku šifru (npr. ručna greška korisnika u
ranijoj deklaraciji, koju je `learn_from_draft`/`save_mapping` "naučio"),
sistem se trajno "zaglavi" na tom pogrešnom rezultatu. Greška se sama
ojačava — svaki uspješan (pogrešan) match povećava `usage_count` preko
`_increment_usage`, čineći je sve "pouzdanijom" iz perspektive sistema.

Ovo NIJE bug u logici uvoza ili parsiranju — `naziv_robe` i `product_code`
u zapisu su bili tačni, samo je `commodity_code` (tarifa) bila pogrešno
naučena. Vjerovatni izvor: ranija deklaracija gdje je korisnik (ili neko
drugi) ručno potvrdio/upisao pogrešnu tarifu za tu stavku.

**Signal za prepoznavanje sličnih budućih slučajeva**: ako auto-popunjena
tarifa "ne pripada" poslovnom profilu dobavljača (npr. tjestenina za
elektro-firmu), prvo provjeriti exact `product_code` zapis u
`product_tariff_mapping` i uporediti sa "porodičnim" zapisima istog naziva
(npr. svi "GREJAC ..." zapisi → trebalo bi da imaju isti `commodity_code`).

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `d570411` | fix | Ispravka pogrešnog naučenog mappinga GREJAC SPIRALA 600W (417UN079): 19023010 → 85168080 |

---

## Napomena za buduće sesije

Korisnik treba **ručno ispraviti tarifu i na već kreiranim naimenovanjima**
koja koriste ovu stavku — ispravka mappinga u bazi utiče samo na BUDUĆE
auto-popunjavanje, ne mijenja postojeće drafove/deklaracije koje su već
kreirane sa pogrešnom tarifom `19023010`.

Ako se ovakav obrazac ponovi (jedna pogrešna tarifa "zaglavljena" kao exact
match po šifri), isti dijagnostički put je brz: provjeriti `find_mapping()`
sa i bez `product_code` — razlika u rezultatu odmah otkriva da li je problem
u exact-match zapisu ili u fuzzy/vote logici. Vidi
[[pogresna-tarifa-grejac-spirala]] za pun kontekst i template skriptu.
