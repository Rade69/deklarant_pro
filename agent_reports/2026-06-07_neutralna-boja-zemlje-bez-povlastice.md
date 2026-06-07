# Izvještaj: Vizuelno razdvajanje zemalja bez potvrđene povlastice u koloni Zemlja porijekla

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
3. **Ovaj fix**: `country_confidence` (pouzdanost IDENTIFIKACIJE zemlje)
   vizuelno izgledao identično kao potvrda POVLASTICE — i u prvom pokušaju
   identično kao "zemlja je TEORIJSKI podobna za povlasticu", što je i dalje
   bilo različito od "povlastica je STVARNO potvrđena za ovu stavku"

Dva kruga korekcije pokazuju da "podobnost" (eligibility) i "potvrda"
(confirmation) izgledaju slično ali su suštinski različiti — podobnost je
osobina ZEMLJE (statična, ista za sve stavke iz te zemlje), dok je potvrda
osobina KONKRETNE STAVKE (zavisi od dokumentacije te konkretne pošiljke).
Vizuelni signal "sve je u redu" (zelena, ✅) smije pratiti samo potvrdu na
nivou stavke — inače korisnik dobija lažni utisak da je povlastica
osigurana za robu koja je tek "kandidat" za nju.

## Tabela commitova

| Hash | Poruka | Status |
|------|--------|--------|
| `6afa1ad` | fix(faktura): vizuelno razdvoji zemlje bez mogucnosti povlastice od ostalih u koloni Zemlja porijekla | ⛔ odbačeno (nova ikonica 🌍 zbunjujuća) |
| `89245c2` | fix(faktura): znak za povlasticu prikazi samo kad je STVARNO potvrdjena, ne kad je zemlja samo "podobna" | ✅ finalno |

## Memorija

- `2026-06-07_neutralna-boja-zemlje-bez-povlastice.md` (ažurirana da odražava finalnu logiku i oba kruga korekcije)
