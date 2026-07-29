## Cilj

Faza 3 treba uskladiti Faktura validacioni servis sa stvarnim View ponašanjem i prebaciti čistu odluku o osnovnoj boji/tooltipu u Service, bez premještanja Qt operacija.

## Pogođeno

GitNexus impact:

- `ValidationService.validate_and_get_color` — LOW, 2 direktna poziva iz FakturaController-a.
- `FakturaView._validate_and_color_row` — MEDIUM, 10 direktnih i 35 ukupno pogođenih simbola.

## Plan

1. Dodati neutralan result model u `services/faktura/validation_service.py` koji sadrži:
   - validation result,
   - row color,
   - row tooltip,
   - per-cell overrides.
2. `ValidationService` mora reprodukovati osnovni dio `_validate_and_color_row` ponašanja:
   - fuzzy tariff žuta samo na koloni tarife;
   - unmatched stavka bijeli red + override kolona tarife/zemlje;
   - nedostaje tarifa/zemlja kao per-cell override;
   - postojeća paleta `#F9E4E3`, `#FFF4D6`, `#EAF4EE`, `#E6F0F8`.
3. `FakturaView._validate_and_color_row` delegira samo tu odluku servisu, ali i dalje:
   - upisuje `validation_cache`;
   - primjenjuje Qt `ValidationColorRole`;
   - poziva `_apply_country_confidence_color`;
   - poziva `_apply_preference_confidence_color`.
4. Ogledati root izmjene u `dist_client`.

## Šta NE dirati

- Ne mijenjati `FakturaController` signalni model osim ako test pokaže da mora.
- Ne mijenjati `QTimer` chunkovanje.
- Ne mijenjati validaciona pravila `FakturaItemValidator`.
- Ne premještati country/preference confidence bojenje u ovoj fazi.
- Ne aktivirati nove signale.

## Konflikti

Postojeći `ValidationService.validate_and_get_color()` nije paritetan sa View-om. View ponašanje je važeći izvor; servis se usklađuje sa njim.
