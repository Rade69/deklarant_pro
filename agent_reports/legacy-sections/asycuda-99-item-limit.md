# ASYCUDA limit od 99 naimenovanja

Datum: 2026-04-30

## Problem
ASYCUDA World u BiH prihvata najviše 99 naimenovanja po jednoj deklaraciji. Deklarant Pro je mogao
kreirati više od 99 naimenovanja iz fakture, posebno kada se stavke ne mogu grupisati po istom paru
tarifa + zemlja porijekla + povlastica + EUR.1.

Ako bi se samo sakrila naimenovanja preko limita, zaglavlje bi ostalo neispravno: Rb.22, bruto/neto
mase i validacija bi i dalje vidjeli sve faktura linije. Zato deklaracija mora biti stvarno podijeljena
na dva draft toka.

## Nova logika
`CreateNaimenovanjaService` ograničava trenutni draft na prvih 99 naimenovanja. Faktura linije koje
pripadaju preostalim grupama izdvajaju se u `pending_next_declaration`.

Korisnički tok:

1. Korisnik kreira naimenovanja.
2. Ako ima više od 99 grupa, trenutna deklaracija dobija prvih 99.
3. Aplikacija upozori korisnika da je ostatak pripremljen za sljedeću deklaraciju.
4. Korisnik završi i izveze prvi XML.
5. Nakon uspješnog exporta, aplikacija ponudi učitavanje sljedeće deklaracije sa ostatkom.

## Implementacija
Fajlovi:
- `services/naimenovanja/create_naimenovanja_service.py`
- `gui/tabs/faktura_view.py`
- `gui/main_window.py`
- `gui/tabs/zaglavlje_controller.py`
- `services/zaglavlje_service.py`

Ključne tačke:
- `MAX_ASYCUDA_ITEMS = 99` je centralna konstanta za servis kreiranja naimenovanja.
- `NaimenovanjaSplitInfo` opisuje koliko je grupa ukupno, koliko ostaje u trenutnom draftu i koliko ide dalje.
- `pending_next_declaration` je privremeni nastavak toka, ne trajni model.
- `MainWindow.continue_with_pending_declaration()` zamjenjuje sadržaj postojećeg draft objekta, da tabovi zadrže
  iste reference.
- Export validacija blokira XML ako `draft.items` ipak sadrži više od 99 stavki.

## Važna granica
Podjela se radi po grupama, ne po pojedinačnim faktura linijama. Jedna grupa mora ostati jedno naimenovanje,
jer se grupisanje zasniva na carinskom ključu: tarifni broj, zemlja porijekla, povlastica i EUR.1 broj.

## Provjera
Targetirani test pokriva:
- 104 različite grupe se sijeku na 99 + 5 u sljedećem draftu,
- 19 linija koje se grupišu u jednu grupu ne prave nastavak.

Test:
`python -m pytest tests/unit/asycuda_item_limit_test.py -q`
