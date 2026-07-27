"""
Testovi za TariffService — opisi tarife (Faza: ujednačavanje tarifnih opisa).

Pokriva:
  - load_tariff_descriptions: vraća (full, short) iz SQLite sa cache-om
  - load_hierarchical_label: formatiran label za prikaz
  - load_tariff_description_from_postgres: PG fallback sa nivo parametrom
  - _clean_tariff_description: uklanjanje tehničkih stopa
  - cache ponašanje (sprječava N+1)
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from services.naimenovanja.tariff_service import TariffService


@pytest.fixture
def service():
    return TariffService()


# ── _clean_tariff_description ──────────────────────────────────────────────


class TestCleanTariffDescription:
    def test_prazan(self):
        assert TariffService._clean_tariff_description(None, "") == ""

    def test_bez_tehnickih_stopa(self):
        assert TariffService._clean_tariff_description(None, "Jabuke") == "Jabuke"

    def test_uklanja_km_stope(self):
        result = TariffService._clean_tariff_description(None, "Punjeni 10+3,5KM/kg 0 0")
        assert "KM/kg" not in result
        assert "10+3" not in result

    def test_uklanja_ex_podtarifu(self):
        result = TariffService._clean_tariff_description(None, "Proizvod ex 1234 56 78 90")
        assert "ex" not in result.lower()

    def test_uklanja_sufiks_brojeva(self):
        result = TariffService._clean_tariff_description(None, "Ostalo 0 0 0 0 5 5 5")
        # treba ukloniti trailing brojeve
        assert result.endswith("Ostalo") or "5 5 5" not in result


# ── load_tariff_descriptions ──────────────────────────────────────────────


class TestLoadTariffDescriptions:
    def test_prazan_kod(self, service):
        assert service.load_tariff_descriptions("") == ("", "")

    def test_bez_cifara(self, service):
        assert service.load_tariff_descriptions("ABC") == ("", "")

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_vraca_full_i_short(self, mock_trazi, service):
        mock_trazi.side_effect = lambda code: {"naziv": f"Opis za {code}"} if code == "08052190" else {"naziv": "Glava opis"}
        full, short = service.load_tariff_descriptions("08052190")
        assert "08052190" in full
        assert short == "Glava opis"

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_cache_sprecava_n1(self, mock_trazi, service):
        mock_trazi.return_value = {"naziv": "Opis"}
        # Prvi poziv
        service.load_tariff_descriptions("08052190")
        # Drugi poziv — ne treba ponovo zvati trazi_po_kodu
        service.load_tariff_descriptions("08052190")
        # trazi_po_kodu se zove samo za code8 (prvi put), code4 (prvi put)
        # drugi put vraca iz cachea
        assert mock_trazi.call_count <= 2

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_short_prazan_ako_je_code4_jednak_code8(self, mock_trazi, service):
        # 4-cifreni kod — code4 == code8 == "0805"
        mock_trazi.return_value = {"naziv": "Opis"}
        full, short = service.load_tariff_descriptions("0805")
        assert full == "Opis"
        assert short == ""  # ne radi drugi lookup jer su isti


# ── load_hierarchical_label ───────────────────────────────────────────────


class TestLoadHierarchicalLabel:
    def test_prazan(self, service):
        assert service.load_hierarchical_label("") == ""

    def test_bez_cifara(self, service):
        assert service.load_hierarchical_label("ABC") == ""

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_formatiran_label(self, mock_trazi, service):
        mock_trazi.side_effect = lambda code: {"naziv": "Glava"} if code == "0805" else {"naziv": "Podbroj"}
        result = service.load_hierarchical_label("08052190")
        assert "Glava" in result
        assert "Podbroj" in result
        assert "/" in result

    @patch("services.tariff.tarifa_service.trazi_po_kodu")
    def test_fallback_na_kod_ako_nema_opisa(self, mock_trazi, service):
        mock_trazi.return_value = None
        result = service.load_hierarchical_label("08052190")
        assert result == "08052190"


# ── load_tariff_description_from_postgres ─────────────────────────────────


class TestLoadTariffDescriptionFromPostgres:
    def test_prazan_kod(self, service):
        assert service.load_tariff_description_from_postgres("") == ""

    def test_bez_cifara(self, service):
        assert service.load_tariff_description_from_postgres("ABC") == ""

    def test_pg_nedostupan_vraca_prazno(self, service):
        # get_db_connection baca grešku — treba vratiti ""
        with patch("database.db.get_db_connection", side_effect=Exception("no PG")):
            result = service.load_tariff_description_from_postgres("08052190")
            assert result == ""

    @patch("database.db.get_db_connection")
    def test_vraca_opis_iz_postgresa(self, mock_conn, service):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"tarifni_kod": "0805219000", "opis": "Test opis 0 0 0 0"}
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        result = service.load_tariff_description_from_postgres("08052190", nivo="podbroj")
        assert "Test opis" in result

    @patch("database.db.get_db_connection")
    def test_cache_sprecava_n1(self, mock_conn, service):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"tarifni_kod": "0805219000", "opis": "Opis"}
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        # Prvi poziv
        service.load_tariff_description_from_postgres("08052190")
        # Drugi poziv — iz cachea
        service.load_tariff_description_from_postgres("08052190")
        # cursor.execute se zvao samo prvi put
        assert mock_cursor.execute.call_count > 0
        # provjeri da je fetchone pozvan samo jednom (drugi put iz cachea)
        assert mock_cursor.fetchone.call_count == 1


# ── backward compatibility ────────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_tab_argument_optionalan(self):
        # TariffService se može instancirati bez tab argumenta (testabilnost)
        svc = TariffService()
        assert svc.tab is None
        assert svc.tariff_cache == {}
        assert svc.tariff_description_cache == {}
