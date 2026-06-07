# Izvještaj: Vizuelno razdvajanje zemalja bez potvrđene povlastice u koloni Zemlja porijekla (3 kruga korekcije)

**Datum:** 2026-06-07
**Prijavio:** Radovan (screenshot niza "CN" ćelija, sve identično zelene kao zemlje sa povlasticom)

## Šta je urađeno

Ćelije u koloni "Zemlja porijekla" sada dobijaju zelenu boju (`#d4edda`) i
znak ✅ ISKLJUČIVO kada je povlastica STVARNO POTVRĐENA za tu konkretnu
stavku. Sve ostalo — i zemlje koje fundamentalno nemaju mogućnost povlastice
(Kina), i zemlje koje JESU podobne ali povlastica za tu stavku (još) nije
potvrđena (npr. Srbija bez CEFTAP) — dobija jedinstvenu neutralnu sivo-plavu
boju (`#dfe4ea`, nova klasna konstanta `_NEUTRAL_COUNTRY_COLOR`) bez ikakvog
znaka.

Ovaj fix je prošao kroz **dva kruga korekcije** od korisnika prije nego što
je dostigao ispravnu logiku — oba su dokumentovana ispod jer opisuju važnu
distinkciju (podobnost vs. potvrda) koja nije bila očigledna iz prve.

## Kako je urađeno

### Početno stanje (bug)
`_apply_country_confidence_color` je bojila ćeliju isključivo na osnovu
`item.country_confidence` (HIGH/MEDIUM/LOW/CONFLICT — koliko je pouzdan
PODATAK o zemlji porijekla, potpuno nezavisno od toga da li ta zemlja
uopšte može imati povlasticu ili da li je povlastica za tu stavku
potvrđena). Kina ima HIGH pouzdanost (podatak dolazi direktno iz
dokumenta), pa je dobijala identičnu zelenu kao npr. Italija sa potvrđenom
EUP povlasticom.

### Krug 1 — odbačen pokušaj (commit `6afa1ad`)
Dodao sam `_NEUTRAL_COUNTRY_COLOR = "#dfe4ea"` i mijenjao ikonicu iz ✅ u 🌍
za zemlje koje `_suggest_preference_by_country(country_code)` vraća kao
nepodobne (vraća `''` za sve osim EU/CEFTA/TR/IR). Korisnik je ovo odbio:
nove ikonice unose dodatnu zabunu — treba SAMO promijeniti boju pozadine,
bez ikakvih novih znakova; znak ✅ mora ostati rezervisan isključivo za
zemlje sa povlasticom.

### Krug 2 — dopunska korekcija
Sljedeća verzija je i dalje bila netačna jer je provjera bila "da li je
zemlja TEORIJSKI podobna" (`_suggest_preference_by_country(...) != ''`).
Korisnik je pojasnio da to nije dovoljno: roba MOŽE doći iz Srbije (CEFTA-
podobne zemlje) BEZ potvrđene povlastice za tu konkretnu pošiljku — u tom
slučaju ćelija ne smije dobiti zelenu/✅ kao da je "sve u redu", jer
povlastica zapravo nije potvrđena.

### Konačna implementacija (commit `89245c2`)
Uslov za zelenu+✅ promijenjen sa "zemlja je podobna" na "povlastica je
STVARNO potvrđena za ovu stavku":

- **`gui/tabs/faktura_view.py:1044`**:
  ```python
  has_confirmed_pref = bool(item.povlastica)
  neutral_country = item.country_confidence == "HIGH" and not has_confirmed_pref
  if neutral_country:
      color_hex = self._NEUTRAL_COUNTRY_COLOR
      icon = ""
  ```
- **`dist_client/gui/tabs/faktura_view.py:1084`**: koristi već postojeću
  stržu provjeru `has_preferential_doc` (povlastica + prateći dokument:
  PE-šifra / EUR.1 broj / izjava o porijeklu) koja već kontroliše ikonicu;
  `neutral_country = country_confidence == "HIGH" and not has_preferential_doc`
  prebacuje samo boju (icon je već `""` u tom slučaju).
- Tooltip dobija DVA odvojena objašnjenja za neutralni slučaj:
  - zemlja MOŽE imati povlasticu, ali za ovu stavku (još) nije potvrđena
    (npr. Srbija)
  - zemlja (van EU/CEFTA/Turske/Irana) fundamentalno nema tu mogućnost
    (npr. Kina)

### Krug 3 — finalno pojednostavljenje (commit `7acee3a`)

I `89245c2` je i dalje bio nedosljedan. Korisnik je poslao novi screenshot:
neke CN stavke su i dalje "zelene kao pozadina cijele tabele", druge sive.
Uzrok: uslov `neutral_country = country_confidence == "HIGH" and not
has_confirmed_pref` je neutralnu boju primjenjivao SAMO za stavke sa
`country_confidence == "HIGH"`. Stavke sa `MEDIUM`/`LOW`/`CONFLICT`
pouzdanošću su zadržavale svoju "confidence" boju (`_CONFIDENCE_COLORS`)
nezavisno od toga da li je povlastica potvrđena — opet nedosljedno.

Korisnik je dao jasnu, finalnu instrukciju: "sve što nema eksplicitnu
potvrdu da ima povlasticu oboji u drugu boju... nema aplikacija potrebu da
bilo šta predviđa ili pretpostavlja" — eksplicitno zabranjujući bilo kakvo
uslovljavanje preko `country_confidence` ili `eligible_for_pref`.

**Finalna implementacija — čisto binarna, bez ijednog dodatnog uslova:**
```python
has_confirmed_pref = bool(item.povlastica)            # gui/
has_preferential_doc = bool(preference and (...))     # dist_client/
if has_confirmed_pref:          # / has_preferential_doc
    color_hex = _CONFIDENCE_COLORS[country_confidence]
    icon = "✅"
else:
    color_hex = _NEUTRAL_COUNTRY_COLOR
    icon = ""
```
`country_confidence` se sada koristi ISKLJUČIVO za sadržaj tooltip-a
(objašnjenje pouzdanosti podatka o zemlji porijekla), nikad za odluku o
boji ili ikonici — ta odluka prati isključivo eksplicitnu potvrdu povlastice
na nivou stavke. Tooltip pojednostavljen na jednu zajedničku poruku za
neutralni slučaj ("Povlastica za ovu stavku nije eksplicitno potvrđena."),
umjesto ranijeg razlikovanja "podobna/nepodobna zemlja".

## Zašto

Ovo je treći fix u lancu otkrivenom preko istog korisničkog screenshot-a
(faktura sa dominantno kineskom robom), i svi dijele isti korijenski
obrazac: UI prikazuje informaciju o JEDNOJ dimenziji podatka na način koji
korisnik (opravdano) tumači kao potvrdu DRUGE, povezane ali nezavisne
dimenzije:

1. Žuto upozorenje za povlasticu na CN redovima — `country_confidence`
   protumačen kao "treba provjeriti povlasticu" (`bd619d9`)
2. Top-5 limit sakrivao Španiju iz statusne trake — broj prikazanih zemalja
   protumačen kao "sve zemlje u deklaraciji" (`1518af9`)
3. **Ovaj fix (3 kruga)**: `country_confidence` (pouzdanost IDENTIFIKACIJE
   zemlje) vizuelno izgledao identično kao potvrda POVLASTICE — krug 1
   pokušao da to riješi novom ikonicom (odbačeno), krug 2 vezao boju za
   "zemlja je TEORIJSKI podobna" (i dalje pogrešno za Srbiju bez potvrde),
   krug 3 vezao neutralnu boju samo za `country_confidence == "HIGH"` (i
   dalje nedosljedno za MEDIUM/LOW/CONFLICT stavke). Tek čisto binarna
   logika — boja/znak prati ISKLJUČIVO `item.povlastica`/`has_preferential_doc`,
   bez ijednog dodatnog `and`-uslova — daje dosljedan rezultat.

Tri kruga korekcije pokazuju da "podobnost" (eligibility), "pouzdanost
podatka" (`country_confidence`) i "potvrda" (`item.povlastica`) izgledaju
slično ali su tri suštinski različite dimenzije — podobnost je osobina
ZEMLJE (statična), pouzdanost je osobina KVALITETA PODATKA, a potvrda je
osobina KONKRETNE STAVKE (zavisi od dokumentacije te pošiljke). Vizuelni
signal "sve je u redu" (zelena, ✅) smije pratiti SAMO potvrdu na nivou
stavke — svaki dodatni uslov ("ali samo ako je i zemlja podobna", "ali samo
ako je i pouzdanost visoka") ponovo otvara isti nesporazum, čak i kad
djeluje logično. Korisnikova lekcija — "nema aplikacija potrebu da bilo šta
predviđa ili pretpostavlja" — znači: kad je u pitanju binarni status
("potvrđeno / nije potvrđeno"), ne kombinuj ga sa drugim signalima u istoj
vizuelnoj odluci.

## Tabela commitova

| Hash | Poruka | Status |
|------|--------|--------|
| `6afa1ad` | fix(faktura): vizuelno razdvoji zemlje bez mogucnosti povlastice od ostalih u koloni Zemlja porijekla | ⛔ odbačeno (nova ikonica 🌍 zbunjujuća) |
| `89245c2` | fix(faktura): znak za povlasticu prikazi samo kad je STVARNO potvrdjena, ne kad je zemlja samo "podobna" | ⚠️ djelimično (i dalje uslovljeno sa country_confidence == "HIGH") |
| `7acee3a` | fix(faktura): pojednostavi bojenje zemlje porijekla - samo eksplicitna potvrda povlastice | ✅ finalno (čisto binarno) |

## Memorija

- `2026-06-07_neutralna-boja-zemlje-bez-povlastice.md` (ažurirana da odražava finalnu binarnu logiku i sva tri kruga korekcije)
