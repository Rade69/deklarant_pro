# Izvještaj: Vizuelno razdvajanje zemalja bez mogućnosti povlastice u koloni Zemlja porijekla

**Datum:** 2026-06-07
**Prijavio:** Radovan (screenshot niza "CN" ćelija, sve identično zelene)

## Šta je urađeno

Ćelije u koloni "Zemlja porijekla" (kolona 9) za zemlje koje fundamentalno
nemaju mogućnost povlastice (npr. Kina — CN) sad dobijaju **neutralnu
sivo-plavu nijansu** (`#dfe4ea`) i ikonicu 🌍, umjesto standardne zelene ✅
("HIGH" pouzdanost) koja se koristi i za zemlje kod kojih povlastica jeste
moguća/potvrđena.

## Kako je urađeno

`_apply_country_confidence_color` boji ćeliju isključivo na osnovu
`item.country_confidence` (HIGH/MEDIUM/LOW/CONFLICT — koliko je pouzdan
PODATAK o zemlji porijekla). Kina ima HIGH pouzdanost (podatak dolazi
direktno iz dokumenta), pa je dobijala istu zelenu `#d4edda` boju kao npr.
Italija sa potvrđenom EUP povlasticom — vizuelno neraspoznatljivo.

Dodata je provjera podobnosti za povlasticu preko već postojeće funkcije
`_suggest_preference_by_country(country_code)` (vraća `'EUP'/'CEFTAP'/'TRP'/'IRP'`
za podobne zemlje, `''` za sve ostale). Kad je `country_confidence == "HIGH"`
ALI zemlja NIJE podobna ni za jednu povlasticu:
- boja ćelije se prebacuje na `_NEUTRAL_COUNTRY_COLOR = "#dfe4ea"` (nova
  klasna konstanta, vizuelno jasno različita od zelene/žute/narandžaste/crvene)
- ikonica se mijenja iz ✅ u 🌍 ("globus" — neutralan simbol "informativno,
  ne potvrda")
- tooltip dobija dodatno objašnjenje: "Ova zemlja (van EU/CEFTA/Turske/Irana)
  nema mogućnost povlastice u ovom sistemu — kolona Povlastica ostaje prazna."

Izmjena je napravljena u oba mjesta:
- `gui/tabs/faktura_view.py:1044` (`_apply_country_confidence_color`)
- `dist_client/gui/tabs/faktura_view.py:1084` (ista funkcija, ima dodatnu
  `has_preferential_doc`/`icon` logiku specifičnu za dist_client — neutralni
  override je dodat NAKON te logike, pa je override uvijek finalna riječ za
  ne-podobne zemlje)

## Zašto

Ovo je treći fix u istom lancu otkrivenom preko istog korisničkog screenshot-a
(faktura sa dominantno kineskom robom):
1. Žuto upozorenje za povlasticu na CN redovima (`bd619d9`)
2. Top-5 limit sakrivao Španiju iz statusne trake (`1518af9`)
3. **Ovaj fix**: zelena boja na CN redovima izgledala identično kao kod
   zemalja sa potvrđenom povlasticom

Sva tri imaju isti korijenski uzrok obrasca: UI komponenta prikazuje
informaciju o JEDNOJ dimenziji podatka (pouzdanost prepoznavanja zemlje,
top-N filter, prisustvo vrijednosti) na način koji korisnik tumači kao
potvrdu DRUGE, povezane ali nezavisne dimenzije (da li ta zemlja ima pravo
na povlasticu, da li su sve zemlje prikazane, da li treba ručna provjera).
Rješenje u sva tri slučaja je isto — koristiti već postojeću funkciju
`_suggest_preference_by_country` kao "izvor istine" za podobnost zemlje, i
dosljedno je primijeniti svuda gdje se ta informacija (direktno ili
indirektno) prikazuje korisniku.

Alternativa (npr. potpuno gašenje boje za nepodobne zemlje, ili poseban
tooltip bez promjene boje) bi i dalje ostavila vizuelnu sličnost koja je i
dovela do zabune — eksplicitna promjena boje + ikonice je transparentnija.

## Tabela commitova

| Hash | Poruka |
|------|--------|
| `6afa1ad` | fix(faktura): vizuelno razdvoji zemlje bez mogucnosti povlastice od ostalih u koloni Zemlja porijekla |

## Memorija

- `2026-06-07_neutralna-boja-zemlje-bez-povlastice.md`
