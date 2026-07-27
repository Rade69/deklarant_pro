import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("Test 1: core.draft import")
try:
    from core.draft import DeclarationDraft
    print("✓ core.draft.DeclarationDraft")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nTest 2: TabFactory import")
try:
    from gui.tabs.tab_factory import get_tab_factory
    print("✓ gui.tabs.tab_factory.get_tab_factory")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nTest 3: MainWindow import")
try:
    from gui.main_window import MainWindow
    print("✓ gui.main_window.MainWindow")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()