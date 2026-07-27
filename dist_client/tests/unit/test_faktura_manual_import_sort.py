from gui.tabs.faktura_view import _manual_invoice_record_sort_key


def test_manual_group_import_sorts_records_by_invoice_number():
    records = [
        {"invoice_name": "268VP-2026", "filepath": "/tmp/268VP-2026.pdf"},
        {"invoice_name": "262VP-2026", "filepath": "/tmp/262VP-2026.pdf"},
        {"invoice_name": "100VP-2026", "filepath": "/tmp/100VP-2026.pdf"},
        {"invoice_name": "99VP-2026", "filepath": "/tmp/99VP-2026.pdf"},
    ]

    ordered = sorted(records, key=_manual_invoice_record_sort_key)

    assert [record["invoice_name"] for record in ordered] == [
        "99VP-2026",
        "100VP-2026",
        "262VP-2026",
        "268VP-2026",
    ]
