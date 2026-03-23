#!/usr/bin/env python3
"""
Cleanup skripta za uklanjanje duplikata, backupova i privremenih fajlova.
"""

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Kategorije fajlova za brisanje
TO_DELETE = {
    # Backup i original fajlovi
    "backup_fajlovi": [
        "gui/tabs/naimenovanja_tab_original.py",
        "gui/tabs/sifarnici_tab_original.py",
        "gui/tabs/faktura_tab_v2.py",
        "services/zaglavlje_service_original.py",
    ],
    
    # Refactored verzije (zadržavamo samo one bez sufiksa)
    "refactored_fajlovi": [
        "gui/tabs/faktura_controller_refactored.py",
        "gui/tabs/faktura_tab_refactored.py",
        "gui/tabs/naimenovanja_controller_refactored.py",
        "gui/tabs/naimenovanja_tab_refactored.py",
        "gui/tabs/sifarnici_controller_refactored.py",
        "gui/tabs/sifarnici_tab_refactored.py",
        "gui/tabs/zaglavlje_controller_refactored.py",
        "gui/tabs/zaglavlje_tab_refactored.py",
        "services/faktura_service_refactored.py",
        "services/naimenovanja_service_refactored.py",
        "services/sifarnici_service_refactored.py",
        "services/zaglavlje_service_refactored.py",
    ],
    
    # Test fajlovi za refactored code
    "test_fajlovi": [
        "test_refactored_services.py",
        "test_zaglavlje_tab_refactored.py",
        "test_refactored_controllers.py",
    ],
    
    # Stari UI fajlovi (zadržavamo samo zaglavlje_tab.ui i naimenovanja_tab_OPTIMIZED.ui)
    "ui_fajlovi": [
        "ui/naimenovanja_tab_from_json.ui",
    ],
    
    # QSS duplikati
    "qss_fajlovi": [
        "styles/faktura_tab_v2.qss",
    ],
    
    # Dokumentacija - duplikati
    "docs_fajlovi": [
        "docs/AGENT_TAB_CORRECTION_PROMPT.md",
        "docs/AGENT_TAB_FINAL_IMPLEMENTATION_PROMPT -novi.md",
    ],
    
    # Database verzije
    "db_fajlovi": [
        "database/sifre_vrste_carinske_deklaracije_polje1_v2.json",
        "memory/sifre_vrste_carinske_deklaracije_polje1_v2.json",
    ],
}


def cleanup():
    """Izbriši sve backup i duplicate fajlove."""
    deleted = []
    errors = []
    
    for category, files in TO_DELETE.items():
        print(f"\n📁 Kategorija: {category}")
        for file_path in files:
            full_path = ROOT / file_path
            if full_path.exists():
                try:
                    full_path.unlink()
                    deleted.append(file_path)
                    print(f"  ✅ Obrisan: {file_path}")
                except Exception as e:
                    errors.append((file_path, str(e)))
                    print(f"  ❌ Greška: {file_path} - {e}")
            else:
                print(f"  ⚠️  Ne postoji: {file_path}")
    
    # Obriši __pycache__ direktorije (osim .venv i venv)
    print("\n🗑️  Čišćenje __pycache__ direktorija...")
    for pycache in ROOT.rglob("__pycache__"):
        if ".git" not in str(pycache) and "venv" not in str(pycache) and ".venv" not in str(pycache):
            try:
                shutil.rmtree(pycache)
                print(f"  ✅ Obrisan: {pycache}")
            except Exception as e:
                print(f"  ❌ Greška: {pycache} - {e}")
    
    print("\n" + "="*60)
    print(f"✅ UKUPNO OBRISANO: {len(deleted)} fajlova")
    if errors:
        print(f"❌ GREŠKE: {len(errors)}")
    
    return deleted, errors


if __name__ == "__main__":
    print("🧹 ASYCUDA PRO - CLEANUP DUPLIKATA")
    print("="*60)
    deleted, errors = cleanup()
