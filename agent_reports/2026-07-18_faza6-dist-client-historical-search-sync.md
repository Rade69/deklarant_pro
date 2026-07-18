# Faza 6 dist_client historical search sync

## Kontekst

Nakon Pi Faza 6 izmjena, `dist_client` je ostao bez fajla:

```text
dist_client/services/agent/validation/historical_tariff_search_service.py
```

GUI i agent runtime ga i dalje importuju iz:

- `dist_client/gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/agent/widgets/tariff_validation_dialog.py`
- `dist_client/gui/tabs/agent/services/chat_intent_handler.py`

Bez tog fajla `dist_client` puca sa:

```text
ModuleNotFoundError: No module named 'services.agent.validation.historical_tariff_search_service'
```

## Šta je urađeno

`dist_client/services/agent/validation/historical_tariff_search_service.py` je sinhronizovan iz root verzije:

```text
services/agent/validation/historical_tariff_search_service.py
```

Root i `dist_client` fajl su provjereni byte poređenjem i nemaju razlika.

## Zašto ovako

Faza 6 pravilo traži da root i `dist_client` runtime kopije budu usklađene. Ovo nije nova poslovna logika, nego vraćanje runtime kompatibilnosti za postojeće import putanje.

## Verifikacija

Pokrenuto:

```text
dist_client\.venv\Scripts\python.exe tmp_verify_dist_phase6_import.py
dist_client\.venv\Scripts\python.exe -m py_compile dist_client\services\agent\validation\historical_tariff_search_service.py
dist_client\.venv\Scripts\python.exe -m pytest tests\unit\test_historical_tariff_validation.py tests\unit\test_declaration_decision_service.py tests\integration\test_manual_agent_decision_parity.py -q --basetemp .pytest_tmp
fc /b services\agent\validation\historical_tariff_search_service.py dist_client\services\agent\validation\historical_tariff_search_service.py
```

Rezultat:

```text
HistoricalTariffSearchService import OK
59 passed
FC: no differences encountered
```

## GitNexus

- `HistoricalTariffSearchService` impact za `dist_client` verziju: LOW.
- `detect_changes(scope=all)`: LOW, 1 fajl.

## Napomena

Nepovezane untracked fajlove (`client.log.lck`, eksportovani `.xlsx`, `nul`, drugi reporti) nisam dirao.
