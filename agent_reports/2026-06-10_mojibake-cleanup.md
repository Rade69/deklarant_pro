# Mojibake cleanup nakon Windows portovanja

Datum: 2026-06-10
Branch: `windows`

## Kontekst

Tokom ranijih Windows izmjena dio fajlova je prošao kroz bulk PowerShell skripte i dobio
mojibake artefakte (`Ä`, `Å`, `Ã`, C1 kontrolni znakovi) u komentarima, stringovima i
dokumentaciji. Problem je bio posebno rizičan jer se nalazio u širem skupu fajlova,
uključujući bazu, GUI, importere, servise i XML export.

## Šta je urađeno

- Pokrenut je kontrolisani cleanup nad pogođenim UTF-8/BOM fajlovima.
- Pomoćna skripta `scripts/fix_mojibake.py` je korištena lokalno i podešena da čuva BOM
  umjesto da slijepo prepisuje encoding.
- Očišćeni su poslovni stringovi i komentari u Python fajlovima, dokumentaciji i pravilima
  projekta.
- `docs/CONTEXT.md` je dopunjen pravilom da se za masovne tekstualne izmjene na Windowsu
  ne koristi nekontrolisani `Get-Content`/`Set-Content` tok.

## Ključne odluke

- Nije rađena ručna find/replace zamjena po cijelom projektu jer bi to lako pokvarilo
  legitimne znakove i regex klase.
- BOM fajlovi nisu masovno konvertovani u drugi format, jer dio Windows toka očekuje
  postojeći format fajlova.
- `scripts/fix_mojibake.py` nije dodat u commit jer je helper fajl iz klase `fix_*.py`
  koja je ignorisana projektom; korišten je kao jednokratni alat za sanaciju.

## Verifikacija

- `py_compile` je prošao nad svim izmijenjenim `.py` fajlovima.
- `tests/unit/test_asycuda_goods_description.py` je prošao: 35/35.
- Završni sken za mojibake indikatore ostavlja samo namjerne primjere u dokumentaciji/testu
  i legitimne `ÄÖÜ` znakove u Leburic regexu.

