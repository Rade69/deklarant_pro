# Izvještaj: Uklanjanje žutog upozorenja za povlasticu kod nepodobnih zemalja (Kina)

**Datum:** 2026-06-07
**Prijavio:** Radovan (screenshot tabele Faktura — redovi sa "CN" obojeni žuto/zeleno)

## Šta je urađeno

Uklonjeno je nepotrebno žuto "⚠️ provjerite ručno" upozorenje na koloni
Povlastica za zemlje koje fundamentalno ne mogu imati povlasticu kroz ovaj
sistem (npr. Kina — CN). Korisnik je prijavio da ga te oznake zbunjuju jer
sugerišu da postoji nešto za provjeru, iako za Kinu povlastica nikad neće
postojati.

## Kako je urađeno

`_apply_preference_confidence_color` (kolona 10 — Povlastica) je primjenjivao
žutu boju i tooltip "provjerite ručno da li roba ima pravo na povlasticu" čim
su ispunjena dva uslova:
- `country_source == "PDF_OZNAKA"` (dokument ima samo oznaku zemlje, bez izjave o porijeklu)
- `povlastica` je prazna

Bez treće, ključne provjere: da li ta zemlja uopšte MOŽE imati povlasticu.
Sistem već posjeduje funkciju `_suggest_preference_by_country(country_code)`
koja vraća `'EUP'`/`'CEFTAP'`/`'TRP'`/`'IRP'` za podobne zemlje (EU, CEFTA,
Turska, Iran), a prazan string `''` za sve ostale (uključujući Kinu).

Fix dodaje provjeru `eligible_for_pref = bool(self._suggest_preference_by_country(country_code))`
i žuto upozorenje se sada prikazuje samo kad je `eligible_for_pref == True` —
tj. kad zemlja STVARNO može imati povlasticu, ali sistem je iz nekog razloga
nije automatski postavio (nedostaje izjava o porijeklu u dokumentu).

Izmjena je napravljena u oba mjesta (glavni i dist_client mirror):
- `gui/tabs/faktura_view.py:1093` (`_apply_preference_confidence_color`)
- `dist_client/gui/tabs/faktura_view.py:1143` (`_apply_preference_confidence_color`)

Zelena oznaka ("✅ povlastica izvedena iz potvrđenog porijekla") nije
dirana — ona se prikazuje samo kad `povlastica` postoji i `country_source`
je `PDF_IZJAVA`/`MATCH`, što je već ispravno (ne pojavljuje se za Kinu jer
povlastica nikad nije postavljena za nepodobne zemlje).

## Zašto

`_suggest_preference_by_country` je već centralna i provjerena funkcija za
"da li ova zemlja uopšte može imati povlasticu" (ista funkcija koja predlaže
povlasticu pri auto-popunjavanju). Korišćenje iste provjere za prikaz
upozorenja je konzistentno i ne uvodi novu logiku — samo je nadovezuje na
postojeću tačku odluke umjesto duplog hardkodiranja seta zemalja.

Alternativa (npr. dodavanje novog flag-a na `InvoiceLine` ili posebne mape
"zemlje bez povlastice") bi bila redundantna — informacija već postoji i
koristi se na drugom mjestu u istoj klasi.

## Tabela commitova

| Hash | Poruka |
|------|--------|
| `bd619d9` | fix(faktura): ne prikazuj upozorenje za povlasticu kod zemalja bez mogucnosti povlastice |

## Memorija

- `2026-06-07_zuto-upozorenje-povlastica-nepodobne-zemlje.md`
