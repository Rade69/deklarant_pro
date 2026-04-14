# PartnerFormStrip

## Svrha
Izdvojena UI komponenta za unos podataka o partnerima (Pošiljaoci / Uvoznici).
Umjesto 150 linija inline koda u SifarniciView, ovo je self-contained widget
koji se može testirati i razumjeti nezavisno.

## Zavisnosti i pretpostavke
- PySide6.QtWidgets — standardni Qt widgeti
- Nema poslovne logike — samo UI layout
- Polja su dostupna kroz property-je (jib_field, naziv_field, itd.)

## Pravila i granice
- `pdv_field` zapravo sadrži JIB (13 cifara), a label kaže "PDV" — historijsko ime
- `jib_field` sadrži PDV (12 cifara) — suprotno od očekivanog
- Ova konfuzija namjerno nije ispravljena jer se oslanja na postojeći
  kod u View-u koji računa `jib = "4" + pdv`
- Ne mijenjati imena property-ja bez ažuriranja svih referenci u View-u

## Zašto ovako
PartnerFormStrip je izdvojen jer je bio najveći single UI blok u View-u (~150 linija).
Alternativa je bila ostaviti ga inline — odbijeno jer je otežavao razumijevanje
_setup_posiljaoci i _setup_uvoznici metoda.
Provjera: vizuelni izgled mora biti identičan prije i poslije ekstrakcije.
