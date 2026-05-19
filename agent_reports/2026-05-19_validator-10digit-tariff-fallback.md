# Validator 10-digit tariff fallback

## Problem

U radnom stablu je ostala korisna izmjena u validatoru koja nije bila commitovana:

- za 10-cifrene tarifne brojeve validator je radio exact lookup,
- zatim bi, ako nije pronadjen, odmah pao na `False`,
- iako u praksi XML/import tokovi mogu dati 10-cifreni kod ciji 8-cifreni ASYCUDA nivo postoji u bazi.

## Rjesenje

`DeclarationValidatorService._tariff_exists_in_db()` sada radi:

1. exact lookup,
2. za 10 cifara lookup prvih 8 cifara,
3. za 8 cifara lookup prvih 6 cifara.

Time 10-cifreni kodovi iz XML/import toka ne prave laznu gresku ako postoji odgovarajuci 8-cifreni ASYCUDA nivo.

## Cleanup

Uklonjeni su preostali debug ispisi iz:

- `gui/tabs/agent/agent_controller.py`
- `gui/tabs/agent/widgets/processing_worker.py`

Ti debug ispisi nisu dio produkcionog toka i nisu commitovani.

## Verifikacija

Dodani su testovi u:

`tests/unit/test_declaration_validator_tariff_lookup.py`

Pokrenuto:

```bash
python -m pytest tests/unit/test_blagic_loren_agent_import.py tests/unit/test_import_validator.py tests/unit/test_declaration_validator_tariff_lookup.py -q
```

Rezultat:

```text
29 passed
```
