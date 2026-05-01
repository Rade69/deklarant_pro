# XML Learning Admin Panel

## Svrha

Admin panel "Učenje iz XML-ova" služi za uvoz i reindeksiranje historijskih
ASYCUDA XML deklaracija. Primarni rezultat prve verzije je indeks:

```text
(exporter_normalized, consignee_jib/consignee_normalized) -> xml_filepath
```

Indeks koristi agent i MCP fallback za pronalazak prethodno korištenog XML
templatea po paru izvoznik-primalac.

## Glavni fajlovi

- `gui/tabs/admin/panels/learning_panel.py` — GUI za dodavanje XML fajlova,
  pokretanje reindeksiranja i pregled statistike.
- `services/agent/learning/exporter_xml_indexer.py` — parsiranje XML-ova,
  normalizacija naziva, izbor najnovijeg XML-a i upis u PostgreSQL indeks.
- `gui/tabs/admin/admin_view.py` — registracija panela u Admin navigaciji.

## Sigurnosna pravila

- `create_table_if_not_exists()` ne smije brisati postojeće podatke.
- Reindex prvo skenira XML folder, pa tek onda u jednoj transakciji mijenja
  indeks. Ako upis padne, radi se rollback.
- Ako scan ne pronađe nijedan validan par, postojeći indeks se ne briše.
- DB konekcija ide preko `config.settings.get_db_settings()`.
- Fuzzy matching prag za XML lookup je `0.92`.
- XML fajlovi se prije kopiranja validiraju i duplikati se preskaču po SHA-256
  hash-u.

## Trenutno ograničenje

Panel prikazuje i broj tarifnih veza iz `catalogs.product_tariff_mapping`, ali
reindex trenutno puni samo `catalogs.exporter_xml_index`. Ako se kasnije dodaje
učenje roba -> tarifa, to treba implementirati eksplicitno i pokriti testovima.

## Provjera

Fokusirani testovi:

```bash
python -m pytest tests/unit/test_exporter_xml_indexer.py mcp_server/tests/test_tools.py tests/test_origin_intent_routing.py -q
```

Očekivani rezultat poslije zadnje izmjene: `43 passed`.
