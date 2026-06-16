"""
Unit testovi za MassCalculator — proporcionalna raspodjela masa na stavke.

Čista logika bez DB i bez fajlova.
"""
import pytest
from services.faktura.mass_calculator import MassCalculator
from core.draft.draft import InvoiceLine


def make_item(kolicina=1.0, bruto_kg=0.0, neto_kg=0.0, iznos=0.0) -> InvoiceLine:
    return InvoiceLine(
        naziv_robe="Test stavka",
        product_code="TEST",
        kolicina=kolicina,
        bruto_kg=bruto_kg or 0.0,
        neto_kg=neto_kg or 0.0,
        iznos=iznos,
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

    def test_rounding_remainder_keeps_invoice_total(self):
        items = [make_item(1.0), make_item(1.0), make_item(1.0)]

        MassCalculator.calculate_masses(items, bruto_total=1.0, neto_total=0.8)

        assert sum(item.bruto_kg for item in items) == pytest.approx(1.0, abs=0.001)
        assert sum(item.neto_kg for item in items) == pytest.approx(0.8, abs=0.001)
        assert items[-1].bruto_kg == pytest.approx(0.34, abs=0.001)

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


class TestMassCalculatorValueDistribution:
    """Distribucija po vrijednosti (iznos) — ima prioritet nad količinom."""

    def test_value_distribution_preferred_over_qty(self):
        # Dvije stavke: ista količina ali različita vrijednost
        # Po količini: 50/50. Po vrijednosti: 75/25.
        items = [
            make_item(kolicina=100.0, iznos=300.0),
            make_item(kolicina=100.0, iznos=100.0),
        ]
        MassCalculator.calculate_masses(items, bruto_total=400.0, neto_total=380.0)
        assert items[0].bruto_kg == pytest.approx(300.0, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(100.0, abs=0.01)

    def test_value_distribution_kg_fashion_scenario(self):
        # Turska (cipele 100€) vs Kina (torbe 50€) — ista količina, različita vrijednost
        items = [
            make_item(kolicina=12.0, iznos=1200.0),   # cipele
            make_item(kolicina=12.0, iznos=600.0),    # torbe
        ]
        MassCalculator.calculate_masses(items, bruto_total=90.0, neto_total=85.0)
        # 1200/(1200+600) = 2/3 → cipele 60kg, torbe 30kg
        assert items[0].bruto_kg == pytest.approx(60.0, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(30.0, abs=0.01)

    def test_fallback_to_qty_when_no_iznos(self):
        # Ako iznos nije postavljen (=0), padamo na kolicina
        items = [
            make_item(kolicina=300.0, iznos=0.0),
            make_item(kolicina=100.0, iznos=0.0),
        ]
        MassCalculator.calculate_masses(items, bruto_total=400.0, neto_total=380.0)
        assert items[0].bruto_kg == pytest.approx(300.0, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(100.0, abs=0.01)

    def test_value_sum_preserved(self):
        items = [
            make_item(kolicina=10.0, iznos=250.0),
            make_item(kolicina=20.0, iznos=500.0),
            make_item(kolicina=5.0, iznos=750.0),
        ]
        MassCalculator.calculate_masses(items, bruto_total=150.0, neto_total=142.0)
        assert sum(i.bruto_kg for i in items) == pytest.approx(150.0, abs=0.01)
        assert sum(i.neto_kg for i in items) == pytest.approx(142.0, abs=0.01)


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

    def test_rounding_remainder_not_applied_to_partial_updates(self):
        items = [
            make_item(kolicina=100.0, bruto_kg=10.0, neto_kg=9.5),
            make_item(kolicina=100.0),
            make_item(kolicina=100.0),
        ]

        MassCalculator.calculate_masses(items, bruto_total=20.0, neto_total=19.0)

        assert sum(item.bruto_kg for item in items) == pytest.approx(20.0, abs=0.001)
        assert sum(item.neto_kg for item in items) == pytest.approx(19.0, abs=0.001)

    def test_suspicious_existing_neto_total_is_redistributed_with_empty_items(self):
        items = [
            make_item(kolicina=1.0, neto_kg=154.91),
            make_item(kolicina=10.0),
            make_item(kolicina=20.0),
        ]

        MassCalculator.calculate_masses(items, bruto_total=170.0, neto_total=154.91)

        assert items[0].bruto_kg == pytest.approx(5.48, abs=0.01)
        assert items[0].neto_kg == pytest.approx(5.00, abs=0.01)
        assert items[1].bruto_kg == pytest.approx(54.84, abs=0.01)
        assert items[1].neto_kg == pytest.approx(49.97, abs=0.01)
        assert items[2].bruto_kg == pytest.approx(109.68, abs=0.01)
        assert items[2].neto_kg == pytest.approx(99.94, abs=0.01)
        assert sum(item.bruto_kg for item in items) == pytest.approx(170.0, abs=0.001)
        assert sum(item.neto_kg for item in items) == pytest.approx(154.91, abs=0.001)
