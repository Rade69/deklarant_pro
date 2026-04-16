# FormValidator

## Svrha
Generička validacija za forme — provjerava obavezna polja, dužinu i sanitizuje input.
Izvučena iz SifarniciView da bi bila dostupna svim tabovima (Faktura, Zaglavlje, Admin).

## Zavisnosti i pretpostavke
- Čist Python — nema Qt dependency
- Može se koristiti u servisima, CLI alatima i testovima
- `ValidationRule` je dataclass koji definiše pravila po polju

## Pravila i granice
- `validate_required_fields()` vraća listu praznih polja — ne baca exception
- `validate_with_rules()` vraća dict sa greškama po polju — caller odlučuje šta radi
- `sanitize_input()` samo trimuje whitespace — ne radi SQL injection protection
- Za SQL sigurnost koristiti parametrizovane upite (SifarniciService to radi)

## Zašto ovako
Validacija je bila inline u View-u (80 linija). Izdvajanjem je postala testabilna
i dostupna drugim tabovima.
Alternativa: inline validacija u svakom View-u — odbijeno jer duplicira logiku.
Provjera: `FormValidator.validate_required_fields({"JIB": "", "Naziv": "Test"})` → `["JIB"]`.
