# SECTION: Rb.23 — Auto-popunjavanje kursa iz Rb.22 valute

## Svrha
Kad korisnik upiše valutu u polje Rb.22 i napusti polje, Rb.23 (kurs) se automatski popuni:
- EUR → 1.95583 (fiksni BiH nominalni kurs, nikad se ne mijenja)
- USD, GBP, CHF i ostalo → aktuelan srednji kurs sa CBBH API-ja

## Zavisnosti i pretpostavke
- `services/agent/cbbh_exchange_service.py` → `get_cbbh_rate(currency_code)`
- CBBH API: `https://www.cbbh.ba/CurrencyExchange/GetJson?date=YYYY-MM-DD`
- Offline tolerancija: ako API nije dostupan, loguje warning i ostavlja polje prazno
- Korisnik može ručno promijeniti kurs nakon auto-popunjavanja

## Pravila i granice
- Signal `ZaglavljeView.valuta_changed` emituje se samo pri `editingFinished` (ne za svaki karakter)
- Format ispisa: `.5f` bez trailing nula (`1.95583`, ne `1.95583000`)
- Prazna valuta → ništa se ne radi
- Korisnik može slobodno editovati Rb.23 nakon auto-popune

## Zašto ovako
EUR ima zakonski fiksni kurs u BiH od uvođenja KM (konvertibilna marka), pa API poziv nije potreban.
Za sve ostale valute kurs se svakodnevno mijenja, pa se uvijek uzima svjež podatak.
`editingFinished` umjesto `textChanged` — da se ne okida API na svaki kucani karakter.

## Fajlovi
- `gui/tabs/zaglavlje_view.py` → `valuta_changed = Signal(str)`, `editingFinished` konekcija
- `gui/tabs/zaglavlje_controller.py` → `_on_valuta_changed(valuta)`
- `services/agent/cbbh_exchange_service.py` → `get_cbbh_rate`, `EUR_FIXED_RATE = 1.95583`
