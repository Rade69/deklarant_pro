"""
Testovi za tarifni dedup ledger (project_rooms/
2026-07-28_tarifno-ucenje-dedup-po-deklaraciji.md).

NAPOMENA: testovi koji stvarno pišu u catalogs.tariff_learning_ledger
zahtijevaju da je migracija database/migrations/013_tariff_learning_ledger.sql
primijenjena na PostgreSQL — deklarant_app runtime nalog nema DDL privilegiju
(namjerno, sigurnosni hardening), pa migraciju mora primijeniti neko sa
admin/owner pravima. Do tada ovi testovi padaju sa "relation does not exist",
ne sa greškom u logici. NIJE mockovana DB konekcija (AGENTS.md zabrana) —
samo guard-klauzule (bez DB poziva) su izolovane bez oslanjanja na tabelu.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.draft.draft import DeclarationDraft, InvoiceLine
from services.tariff.tariff_mapping_service import TariffMappingService


@pytest.fixture
def service():
    return TariffMappingService()


@pytest.fixture
def clean_ledger_rows():
    """Ciscenje test redova iz ledgera pre i posle - integration testovi
    nisu idempotentni bez ovoga (drugo pokretanje vidi red iz proslog)."""
    draft_uids = ("test-dedup-ista-tarifa", "test-dedup-ispravka")

    def _cleanup():
        from database.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM catalogs.tariff_learning_ledger WHERE draft_uid = ANY(%s)",
                    (list(draft_uids),),
                )
                cur.execute(
                    "DELETE FROM catalogs.product_tariff_mapping WHERE naziv_robe LIKE 'TEST DEDUP PROIZVOD%'"
                )

    _cleanup()
    yield
    _cleanup()


def test_draft_uid_generisan_i_stabilan():
    """Svaki draft dobija jedinstven draft_uid, razliciti draftovi razlicit uid."""
    d1 = DeclarationDraft()
    d2 = DeclarationDraft()
    assert d1.draft_uid
    assert d1.draft_uid != d2.draft_uid


def test_draft_uid_prezivljava_save_load_roundtrip():
    """draft_uid mora ostati isti kroz nacrt XML save/load (ne generisati nov)."""
    from services.declaration_draft_service import serialize_draft, deserialize_draft

    draft = DeclarationDraft()
    original_uid = draft.draft_uid
    reloaded = deserialize_draft(serialize_draft(draft))

    assert reloaded.draft_uid == original_uid


def test_learn_with_dedup_prazan_draft_uid_ne_upisuje(service):
    """Bez draft_uid nema ledger zastite - metoda odbija upis (fail-safe)."""
    result = service.learn_with_dedup("", "kljuc", "Naziv", "", "84149000")
    assert result is False


def test_learn_with_dedup_prazan_line_key_ne_upisuje(service):
    result = service.learn_with_dedup("draft-1", "", "Naziv", "", "84149000")
    assert result is False


def test_learn_with_dedup_nevalidna_tarifa_ne_upisuje(service):
    result = service.learn_with_dedup("draft-1", "kljuc", "Naziv", "", "abc")
    assert result is False


def test_learn_from_draft_bez_draft_uid_koristi_stari_put(service):
    """Kompatibilnost: prazan draft_uid ne smije pucati, ide na save_mapping."""
    line = InvoiceLine(line_no=1, naziv_robe="SUSSINA 650 tbl.", tarifni_broj="21069098")
    line.decision_state = None

    with patch.object(service, "save_mapping", return_value=True) as mock_save:
        count = service.learn_from_draft([line], confirmed_only=False, draft_uid="")

    mock_save.assert_called_once()
    assert count == 1


def test_learn_from_draft_sa_draft_uid_ide_kroz_dedup(service):
    """Sa draft_uid, learn_from_draft mora zvati learn_with_dedup, ne save_mapping direktno."""
    line = InvoiceLine(line_no=1, naziv_robe="SUSSINA 650 tbl.", tarifni_broj="21069098")
    line.decision_state = None

    with patch.object(service, "learn_with_dedup", return_value=True) as mock_dedup, \
         patch.object(service, "save_mapping") as mock_save:
        count = service.learn_from_draft([line], confirmed_only=False, draft_uid="draft-abc")

    mock_dedup.assert_called_once()
    mock_save.assert_not_called()
    assert count == 1
    args = mock_dedup.call_args[0]
    assert args[0] == "draft-abc"


@pytest.mark.integration
def test_learn_with_dedup_ponovljena_ista_tarifa_ne_povecava_usage(service, clean_ledger_rows):
    """Prava DB provjera: ista (draft_uid, line_key, tarifa) drugi put = no-op."""
    draft_uid = "test-dedup-ista-tarifa"
    line_key = "test-dedup-proizvod-a"
    naziv = "TEST DEDUP PROIZVOD A"

    first = service.learn_with_dedup(draft_uid, line_key, naziv, "", "84149000")
    second = service.learn_with_dedup(draft_uid, line_key, naziv, "", "84149000")

    assert first is True
    assert second is False  # no-op, vec naucen isti par


@pytest.mark.integration
def test_learn_with_dedup_ispravka_skida_bod_sa_stare_tarife(service, clean_ledger_rows):
    """Prava DB provjera: promjena tarife u istoj deklaraciji skida bod sa stare."""
    from database.db import get_db_connection

    draft_uid = "test-dedup-ispravka"
    line_key = "test-dedup-proizvod-b"
    naziv = "TEST DEDUP PROIZVOD B"

    service.learn_with_dedup(draft_uid, line_key, naziv, "", "84149000")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT usage_count FROM catalogs.product_tariff_mapping "
                "WHERE naziv_robe = %s AND commodity_code = %s",
                (naziv, "84149000"),
            )
            usage_before = cur.fetchone()["usage_count"]

    service.learn_with_dedup(draft_uid, line_key, naziv, "", "85167990")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT usage_count FROM catalogs.product_tariff_mapping "
                "WHERE naziv_robe = %s AND commodity_code = %s",
                (naziv, "84149000"),
            )
            row = cur.fetchone()
            usage_after = row["usage_count"] if row else 0

    assert usage_after == usage_before - 1
