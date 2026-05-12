"""
Unit testovi za MassCalculator — proporcionalna raspodjela masa na stavke.

Čista logika bez DB i bez fajlova.
"""
import pytest
from services.faktura.mass_calculator import MassCalculator
from core.draft.draft import InvoiceLine


def make_item(kolicina=1.0, bruto_kg=0.0, neto_kg=0.0) -> InvoiceLine:
    return InvoiceLine(
        naziv_robe="Test stavka",
        product_code="TEST",
        kolicina=kolicina,
        bruto_kg=bruto_kg or 0.0,
        neto_kg=neto_kg or 0.0,
    )


class TestMassCalculatorEmpty:
    def test_empty_list(self):
        result = MassCalculator.calculate_masses([], 100.0, 95.0)
        assert result == {"updated": 0, "skipped": 0}

    def test_all_items_have_masses(self):
        items = [make_item(10.0, bruto_kg=5.0, neto_kg=4.5)]
        result = MassCalculator.calculate_masses(items, 5.0, 4.5)
        assert result["updated"] == 0
        assert result["skipped"] == 1


class TestMassCalculatorScenario1:
    """Stavke bez ijedne težine — proporcionalna raspodjela po količini."""

    def test_two_items_equal_qty(self):
        items = [
            make_item(kolicina=100.0),
            make_item(kolicina=100.0),
        ]
        MassCalculator.calculate_masses(items, bruto_total=200.0, neto_total=190.0)
        assert items[0].bruto_kg == pytest.approx(100.0, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(100.0, abs=0.01)
        assert items[0].neto_kg == pytest.approx(95.0, abs=0.01)

    def test_two_items_different_qty(self):
        items = [
            make_item(kolicina=300.0),
            make_item(kolicina=100.0),
        ]
        MassCalculator.calculate_masses(items, bruto_total=400.0, neto_total=380.0)
        # 300/400 = 75% → bruto = 300, 100/400 = 25% → bruto = 100
        assert items[0].bruto_kg == pytest.approx(300.0, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(100.0, abs=0.01)

    def test_result_counts(self):
        items = [make_item(10.0), make_item(20.0)]
        result = MassCalculator.calculate_masses(items, 30.0, 28.5)
        assert result["updated"] == 2
        assert result["skipped"] == 0

    def test_zero_total_no_update(self):
        items = [make_item(kolicina=100.0)]
        MassCalculator.calculate_masses(items, bruto_total=0.0, neto_total=0.0)
        # Bez ukupnih masa ne može rasporediti — bruto ostaje 0
        assert items[0].bruto_kg == 0.0

    def test_zero_kolicina_ravnomjerna_raspodjela(self):
        # Stavke bez količine → ravnomjerna raspodjela
        items = [make_item(kolicina=0.0), make_item(kolicina=0.0)]
        MassCalculator.calculate_masses(items, bruto_total=100.0, neto_total=95.0)
        assert items[0].bruto_kg == pytest.approx(50.0, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(50.0, abs=0.01)
        assert items[0].neto_kg == pytest.approx(47.5, abs=0.01)

    def test_mixed_kolicina_nula_i_pozitivna(self):
        # Jedna stavka ima količinu, druga nema → stavka bez kolicine dobija ravnomjerni udio
        items = [make_item(kolicina=100.0), make_item(kolicina=0.0)]
        MassCalculator.calculate_masses(items, bruto_total=100.0, neto_total=95.0)
        # Ukupna qty = 100, stavka[0] dobija 100% (kolicina=100), stavka[1] dobija prosjek (1/2)
        assert items[0].bruto_kg == pytest.approx(100.0, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(50.0, abs=0.01)


class TestMassCalculatorScenario2:
    """Stavke sa bruto ali bez neto — izračunaj neto iz bruto."""

    def test_neto_calculated_from_bruto(self):
        item = make_item(kolicina=100.0, bruto_kg=10.0, neto_kg=0.0)
        MassCalculator.calculate_masses([item], bruto_total=10.0, neto_total=9.5)
        # neto_bruto_ratio = 9.5/10.0 = 0.95
        assert item.neto_kg == pytest.approx(9.5, abs=0.01)

    def test_multiple_items_bruto_only(self):
        items = [
            make_item(kolicina=100.0, bruto_kg=10.0, neto_kg=0.0),
            make_item(kolicina=50.0, bruto_kg=5.0, neto_kg=0.0),
        ]
        MassCalculator.calculate_masses(items, bruto_total=15.0, neto_total=14.25)
        ratio = 14.25 / 15.0
        assert items[0].neto_kg == pytest.approx(10.0 * ratio, abs=0.01)
        assert items[1].neto_kg == pytest.approx(5.0 * ratio, abs=0.01)


class TestMassCalculatorScenario3:
    """Stavke sa neto ali bez bruto (Leburic/Pekabesko) — izračunaj bruto iz neto."""

    def test_bruto_calculated_from_neto(self):
        item = make_item(kolicina=100.0, bruto_kg=0.0, neto_kg=9.5)
        MassCalculator.calculate_masses([item], bruto_total=10.0, neto_total=9.5)
        assert item.bruto_kg == pytest.approx(10.0, abs=0.01)

    def test_fallback_no_bruto_total(self):
        item = make_item(kolicina=100.0, bruto_kg=0.0, neto_kg=9.5)
        MassCalculator.calculate_masses([item], bruto_total=0.0, neto_total=0.0)
        # Fallback: bruto = neto / 0.95
        assert item.bruto_kg == pytest.approx(9.5 / 0.95, abs=0.01)


class TestMassCalculatorMixed:
    """Kombinovane stavke: neke imaju mase, neke nemaju."""

    def test_mixed_skipped_and_updated(self):
        items = [
            make_item(kolicina=100.0, bruto_kg=10.0, neto_kg=9.5),  # preskočena
            make_item(kolicina=100.0),                                # ažurirana
        ]
        result = MassCalculator.calculate_masses(items, bruto_total=20.0, neto_total=19.0)
        assert result["updated"] == 1
        assert result["skipped"] == 1
