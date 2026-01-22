#!/usr/bin/env python3
"""
Test script za proveru da li aplikacija može da se pokrene
"""
import sys
import os

# Dodaj parent direktorij u sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def test_imports():
    """Test da li se svi moduli mogu importovati"""
    print("Testiram importove...")

    try:
        from asycuda_pro.core.draft import DeclarationDraft, NaimenovanjeDraft
        print("  ✓ Draft modeli")
    except ImportError as e:
        print(f"  ✗ Draft modeli: {e}")
        return False

    try:
        from asycuda_pro.gui.main_window import MainWindow
        print("  ✓ Main Window")
    except ImportError as e:
        print(f"  ✗ Main Window: {e}")
        return False

    try:
        from asycuda_pro.gui.tabs.naimenovanja_tab import NaimenovanjaTab
        print("  ✓ Naimenovanja Tab")
    except ImportError as e:
        print(f"  ✗ Naimenovanja Tab: {e}")
        return False

    return True

def test_draft_creation():
    """Test kreiranje draft objekta"""
    print("\nTestiram kreiranje draft objekta...")

    try:
        from asycuda_pro.core.draft import DeclarationDraft

        draft = DeclarationDraft()
        draft.ensure_min_items(1)

        assert len(draft.items) == 1, "Draft treba da ima 1 item"
        assert draft.items[0].ordinal_no == 1, "Ordinal broj treba da bude 1"

        print(f"  ✓ Draft kreiran sa {len(draft.items)} item(a)")
        print(f"  ✓ Item ID: {draft.items[0].item_id}")
        print(f"  ✓ Ordinal No: {draft.items[0].ordinal_no}")

        return True
    except Exception as e:
        print(f"  ✗ Greška: {e}")
        return False

def test_ui_file():
    """Test da li UI fajl postoji"""
    print("\nTestiram UI fajl...")

    ui_file = os.path.join(
        os.path.dirname(__file__),
        "ui", "naimenovanja_tab_OPTIMIZED.ui"
    )

    if os.path.exists(ui_file):
        print(f"  ✓ UI fajl pronađen: {ui_file}")
        return True
    else:
        print(f"  ✗ UI fajl ne postoji: {ui_file}")
        return False

def main():
    """Pokreni sve testove"""
    print("=" * 50)
    print("ASYCUDA Pro - Test aplikacije")
    print("=" * 50)

    results = []

    results.append(("Importi", test_imports()))
    results.append(("Draft kreiranje", test_draft_creation()))
    results.append(("UI fajl", test_ui_file()))

    print("\n" + "=" * 50)
    print("REZULTATI")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("\n✓ Svi testovi su prošli! Aplikacija je spremna za pokretanje.")
        print("\nPokrenite aplikaciju sa:")
        print("  python3 __main__.py")
        print("  ili")
        print("  ./run_app.sh")
        return 0
    else:
        print("\n✗ Neki testovi nisu prošli. Molim vas proverite greške.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
