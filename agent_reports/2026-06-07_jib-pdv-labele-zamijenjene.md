# Agent Report: Ispravka zamijenjenih labela JIB/PDV u formi partnera (Šifrarnici)

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je primijetio da se prilikom odabira firme u Šifrarnicima (Pošiljaoci/
Uvoznici) u rubrici "PDV" prikazuje neka neobična šifra poput "EX00467" i pitao
odakle to dolazi. Nakon istrage i potvrde od strane korisnika ("Popravi to"),
problem je lociran i otklonjen.

## Kako je urađeno

Prvobitna pretpostavka bila je da se radi o pogrešnoj logici u
`gui/tabs/sifarnici_view.py` koja konkateniše `"4" + jib_val` (BiH konvencija
JIB=13 cifara="4"+PDV od 12 cifara) i primjenjuje je i na strane partnere koji
nemaju BiH JIB. Daljom provjerom (`_on_uredi`, selection handler oko linije
3488-3544) utvrđeno je da je ta logika samo bezopasan privremeni fallback —
stvarna konačna vrijednost u poljima dolazi ispravno iz baze
(`db_row.get("pdv_broj")` za PDV, `jib_item.text()` za JIB).

Pravi uzrok pronađen je u `gui/tabs/sifarnici/partner_form_strip.py`
(`PartnerFormStrip`) — **tekstovi labela su bili zamijenjeni mjestima**:
- `_create_header` (red 128): `lbl_jib = QLabel("PDV:")` — labela "PDV:" je stajala
  iznad `self._jib_field` (sadrži interni katalog-kod poput "EX00467")
- `_create_right_panel` (red 227): `rf.addRow("JIB:", self._pdv_field)` — labela
  "JIB:" je stajala uz `self._pdv_field` (sadrži stvarni `pdv_broj` iz baze)

Kod je ispravno popunjavao polja (`jib_field` = JIB, `pdv_field` = PDV), ali su
korisnici gledali u "PDV" rubriku i vidjeli JIB vrijednost zbog zamijenjenih labela.

Popravka: zamijenjeni tekstovi labela na ispravna mjesta — "PDV:" → "JIB:" (red 128)
i "JIB:" → "PDV:" (red 227) — u oba `gui/` i `dist_client/` kopija identično.

`gitnexus_impact` na `PartnerFormStrip` (upstream) vratio je rizik **LOW**
(samo importi kroz `__init__.py` → `sifarnici_view.py` → `sifarnici_controller.py`/
`sifarnici_tab.py`, bez execution-flow uticaja). `gitnexus_detect_changes()`
potvrdio je da su dotaknute samo `_create_header` i `_create_right_panel`.

## Zašto

Labele i polja se kreiraju odvojeno u factory metodama (`_create_header`,
`_create_right_panel`), pa je pri pisanju/kopiranju koda lako došlo do mismatch-a
— ime promjenljive (`lbl_jib`, `_jib_field`) ne mora se poklapati sa tekstom koji
se zapravo prikazuje (`QLabel("PDV:")`). Ovo je bila čisto vizuelna greška —
podaci u bazi i logika čitanja/pisanja bili su ispravni cijelo vrijeme, samo je
displej zbunjivao korisnika prikazujući interni JIB kod pod pogrešnim nazivom.

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `88c0642` | fix | Ispravka zamijenjenih labela JIB/PDV u formi partnera (PartnerFormStrip) |

---

## Napomena za buduće sesije

Kad korisnik prijavi da se "pogrešna vrijednost" pojavljuje u nekom polju forme,
prvo provjeriti da li je LABELA pored polja možda pogrešno postavljena prije nego
što se traži greška u logici popunjavanja — naročito u `_create_*`/`_build_*_strip`
factory metodama. Vidi [[jib-pdv-labele-zamijenjene]] za detalje.
