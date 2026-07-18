# Faza 5 dist_client runtime import fix

## Kontekst

Pi agent je završio Fazu 5 u razvojnom kodu i rebuildao `dist_client/services/tariff_mapping_service.cp314-win_amd64.pyd`, ali runtime provjera je pokazala da dio aplikacije i dalje importuje stari put:

```python
from services.tariff.tariff_mapping_service import TariffMappingService
```

Pošto u `dist_client` nije postojao fizički paket `services/tariff/`, Python je taj put rješavao kroz stari Nuitka loader i dobijao staru implementaciju bez `confirmed_only=True`.

## Šta je urađeno

- Dodan je fizički mirror paket `dist_client/services/tariff/`.
- `dist_client/services/tariff/tariff_mapping_service.py` je namjerni shim na novi flat runtime modul:

```python
from services.tariff_mapping_service import *  # noqa: F401, F403
```

- U paket su dodani prateći moduli koje `services.tariff.__init__` očekuje:
  - `country_origin_validator.py`
  - `origin_statement_detector.py`
  - `product_master_list.py`
  - `tarifa_service.py`
  - `tariff_tree_service.py`

## Zašto ovako

Ovo je najmanji runtime-safe zahvat: ne mijenja poslovnu logiku, ne dira razvojni `services/tariff_mapping_service.py`, nego samo osigurava da oba import puta u `dist_client` završavaju na istoj novoj implementaciji. Time se čuva pravilo Faze 5: baza znanja uči tarifu samo kada postoji eksplicitna potvrda deklaranta.

## Verifikacija

Runtime provjera u `dist_client` je potvrdila:

```text
services.tariff.tariff_mapping_service.TariffMappingService
  == services.tariff_mapping_service.TariffMappingService
learn_from_draft(..., confirmed_only=True)
kandidat bez potvrde -> rezultat 0, save_mapping 0 poziva
```

Pokrenuto:

```text
dist_client\.venv\Scripts\python.exe -m py_compile dist_client\services\tariff\*.py
dist_client\.venv\Scripts\python.exe -m pytest tests\unit\test_decision_controlled_learning.py tests\unit\test_declaration_decision_service.py tests\unit\test_declaration_decision_model.py tests\unit\test_decision_tariff_policy.py tests\unit\test_evidence_model.py tests\integration -q --basetemp .pytest_tmp
```

Rezultat:

```text
152 passed, 1 skipped
```

## Napomena

U worktree-u su ostale druge nepovezane izmjene i fajlovi koje nisam dirao niti stagovao.
