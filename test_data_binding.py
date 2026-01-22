#!/usr/bin/env python3
"""
Test skript za demonstraciju data binding funkcionalnosti.
Kreira Draft sa nekoliko test items i prikazuje GUI.
"""
import sys
from pathlib import Path

# Dodaj asycuda_pro u Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from asycuda_pro.core.draft import DeclarationDraft, NaimenovanjeDraft
from asycuda_pro.gui.main_window import MainWindow


def create_test_draft() -> DeclarationDraft:
    """Kreira draft sa nekoliko test stavki"""
    draft = DeclarationDraft()
    
    # Item 1 - Čokolada
    item1 = NaimenovanjeDraft(
        item_id="test-1",
        ordinal_no=1,
        goods_description="Čokolada i ost.pr.ostalo,punjeni/\nKAKAO KREM BANANA;MINJON KOCA\n-po fak.",
        package_qty=1812.0,
        package_code="CT",
        package_name="Karton",
        tariff_code="18069031",
        tariff_suffix="000",
        origin_country_code="DE",
        preference_code="P",
        gross_mass_kg=11500.00,
        net_mass_kg=9907.80,
        procedure_code="4000",
        procedure_prev_code="000",
        item_value=27291.51,
        currency="EUR",
        supplementary_unit_qty=9907.80,
        statistical_value=53377.55,
        previous_document="SP02595798",
    )
    
    # Item 2 - Keksi
    item2 = NaimenovanjeDraft(
        item_id="test-2",
        ordinal_no=2,
        goods_description="Keksi sa čokoladom\nPakovanje 200g",
        package_qty=500.0,
        package_code="BX",
        package_name="Kutija",
        tariff_code="19053100",
        tariff_suffix="000",
        origin_country_code="IT",
        preference_code="CEFTAP",
        gross_mass_kg=120.00,
        net_mass_kg=100.00,
        procedure_code="4000",
        procedure_prev_code="000",
        item_value=1500.00,
        currency="EUR",
        supplementary_unit_qty=100.00,
        statistical_value=1500.00,
    )
    
    # Item 3 - Bombone
    item3 = NaimenovanjeDraft(
        item_id="test-3",
        ordinal_no=3,
        goods_description="Bombone razne vrste\nMješovito pakovanje",
        package_qty=200.0,
        package_code="BAG",
        package_name="Vreća",
        tariff_code="17049065",
        tariff_suffix="000",
        origin_country_code="TR",
        preference_code="",
        gross_mass_kg=55.00,
        net_mass_kg=50.00,
        procedure_code="4000",
        procedure_prev_code="000",
        item_value=750.00,
        currency="EUR",
        supplementary_unit_qty=50.00,
        statistical_value=750.00,
    )
    
    draft.items = [item1, item2, item3]
    
    return draft


def main():
    """Glavni entry point"""
    app = QApplication(sys.argv)
    
    # Kreiraj glavni prozor
    window = MainWindow()
    
    # Zamijeni prazan draft sa test draft-om
    test_draft = create_test_draft()
    window.draft = test_draft
    window.naimenovanje_tab.draft = test_draft
    
    # Učitaj prvi item
    window.naimenovanje_tab.load_item(0)
    
    window.show()
    
    print("=" * 60)
    print("TEST APLIKACIJA POKRENUTA")
    print("=" * 60)
    print()
    print("Trenutno učitano: 3 test items (Čokolada, Keksi, Bombone)")
    print()
    print("TESTIRAJ:")
    print("  1. ◀ Prethodno / Sljedeće ▶ - navigacija između items")
    print("  2. Promijeni bilo koje polje → naslov se mijenja u 'ASYCUDA Pro *'")
    print("  3. + Nova stavka → dodaje praznu 4. stavku")
    print("  4. 🗑 Obriši → briše trenutnu stavku (potvrda)")
    print()
    print("DATA BINDING:")
    print("  - Svaka promjena se automatski čuva u draft model")
    print("  - Navigacija prev/next automatski čuva prije prelaska")
    print()
    print("=" * 60)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
