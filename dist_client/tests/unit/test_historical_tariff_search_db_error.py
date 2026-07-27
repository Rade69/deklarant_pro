"""
Testovi za razlikovanje "DB nedostupna" od "stvarno nema istorijskog
prijedloga" u HistoricalTariffSearchService (2026-07-26, SUSSINA slučaj —
korisnik prijavio da "Provjeri" pokazuje "nema boljeg prijedloga" dok je
PostgreSQL server bio nedostupan, iako 15 istorijskih zapisa postoji).

_search_one() je ranije hvatao SVAKI izuzetak (uključujući DB konekcijske
greške) i tiho vraćao [] — isto ponašanje kao "provjereno, nema prijedloga".
Sad se DB greške (psycopg2.Error) posebno hvataju i upisuju u
self.last_db_error, da pozivalac (HistoricalValidationWorker) može
razlikovati "nije provjereno" od "provjereno, nema boljeg".
"""
from __future__ import annotations

from unittest.mock import patch

import psycopg2
import pytest

from core.draft.draft import InvoiceLine
from services.agent.validation.historical_tariff_search_service import (
    HistoricalTariffSearchService,
)


def _line(naziv_robe="SUSSINA 650 tbl.", tarifni_broj="38249993"):
    return InvoiceLine(naziv_robe=naziv_robe, tarifni_broj=tarifni_broj, zemlja_porijekla="AT")


def test_search_one_postavlja_last_db_error_na_db_gresku():
    svc = HistoricalTariffSearchService()

    with patch(
        "database.db.get_db_connection",
        side_effect=psycopg2.OperationalError("connection to server failed: timeout expired"),
    ):
        matches = svc._search_one("SUSSINA 650 tbl.", "MEDIKOPHARM", "")

    assert matches == []
    assert svc.last_db_error is not None
    assert "timeout" in svc.last_db_error


def test_validate_lines_resetuje_last_db_error_svaki_poziv():
    svc = HistoricalTariffSearchService()
    svc.last_db_error = "stara greska iz proslog poziva"

    with patch(
        "database.db.get_db_connection",
        side_effect=psycopg2.OperationalError("timeout expired"),
    ):
        svc.validate_lines([_line()], izvoznik_naziv="MEDIKOPHARM")

    assert svc.last_db_error is not None
    assert "timeout" in svc.last_db_error


def test_validate_lines_last_db_error_ostaje_none_bez_greske():
    svc = HistoricalTariffSearchService()

    with patch.object(svc, "_search_one", return_value=[]):
        svc.validate_lines([_line()], izvoznik_naziv="MEDIKOPHARM")

    assert svc.last_db_error is None


def test_search_one_ne_postavlja_last_db_error_za_nepovezan_izuzetak():
    """Generički (ne-DB) izuzetak i dalje se tiho guta bez last_db_error - nepromijenjeno ponašanje."""
    svc = HistoricalTariffSearchService()

    with patch("database.db.get_db_connection", side_effect=ValueError("nepovezana greska")):
        matches = svc._search_one("SUSSINA 650 tbl.", "MEDIKOPHARM", "")

    assert matches == []
    assert svc.last_db_error is None
