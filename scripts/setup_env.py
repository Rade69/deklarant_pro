#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ASYCUDA Pro - .env Fajl Setup Skripta

Interaktivna skripta za kreiranje .env konfiguracijskog fajla.
Vodi korisnika kroz unos svih potrebnih postavki.

UPOTREBA:
    python scripts/setup_env.py

NAPOMENE:
    - Skripta provjerava da li .env već postoji
    - Password se unosi skriveno (getpass)
    - Opciono testira DB konekciju na kraju
"""

import os
import sys
import getpass
from pathlib import Path
from typing import Optional


# ============================================================
# KONFIGURACIJA
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
BACKUP_FILE = PROJECT_ROOT / ".env.backup"

# Default vrijednosti
DEFAULTS = {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "asycuda_pro",
    "DB_USER": "postgres",
    "DEBUG": "False",
    "MAX_IMPORT_WORKERS": "4",
    "STRICT_VALIDATION": "True",
}


# ============================================================
# POMOĆNE FUNKCIJE
# ============================================================

def print_header(text: str) -> None:
    """Ispiši zaglavlje sa dekoracijom"""
    print()
    print("=" * 60)
    print(f"  {text}")
    print("=" * 60)
    print()


def print_success(text: str) -> None:
    """Ispiši success poruku"""
    print(f"✅ {text}")


def print_error(text: str) -> None:
    """Ispiši error poruku"""
    print(f"❌ {text}")


def print_warning(text: str) -> None:
    """Ispiši warning poruku"""
    print(f"⚠️  {text}")


def get_input(prompt: str, default: Optional[str] = None) -> str:
    """
    Prikupi input od korisnika sa optional default vrijednošću.
    
    Args:
        prompt: Tekst pitanja
        default: Default vrijednost (ako postoji)
    
    Returns:
        Unesena vrijednost ili default
    """
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    value = input(full_prompt).strip()
    return value if value else default


def get_password(prompt: str = "Password") -> str:
    """
    Prikupi password skriveno (bez prikaza na ekranu).
    
    Args:
        prompt: Tekst pitanja
    
    Returns:
        Uneseni password
    """
    return getpass.getpass(f"{prompt}: ")


def confirm_password(password: str, max_attempts: int = 3) -> bool:
    """
    Potvrdi password ponovnim unosom.
    
    Args:
        password: Originalni password za poređenje
        max_attempts: Maksimalan broj pokušaja
    
    Returns:
        True ako se passwordi poklapaju
    """
    for i in range(max_attempts):
        confirm = getpass.getpass(f"Confirm Password (pokušaj {i+1}/{max_attempts}): ")
        if password == confirm:
            return True
        print_error("Passwordi se ne poklapaju!")
    return False


def backup_existing_env() -> bool:
    """
    Napravi backup postojećeg .env fajla.
    
    Returns:
        True ako je backup uspješan
    """
    if ENV_FILE.exists():
        try:
            content = ENV_FILE.read_text(encoding="utf-8")
            BACKUP_FILE.write_text(content, encoding="utf-8")
            print_success(f"Backup kreiran: {BACKUP_FILE}")
            return True
        except Exception as e:
            print_error(f"Greška pri backup-u: {e}")
            return False
    return True


def test_db_connection(host: str, port: str, name: str, user: str, password: str) -> bool:
    """
    Testiraj PostgreSQL konekciju.
    
    Args:
        host: Database host
        port: Database port
        name: Database name
        user: Database user
        password: Database password
    
    Returns:
        True ako je konekcija uspješna
    """
    try:
        import psycopg2
        
        print("\n🔌 Testiranje konekcije...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=name,
            user=user,
            password=password,
        )
        conn.close()
        print_success("Konekcija na bazu uspješna!")
        return True
        
    except ImportError:
        print_warning("psycopg2 nije instaliran - preskačem test konekcije")
        print("  Instaliraj: pip install psycopg2-binary")
        return False
        
    except Exception as e:
        print_error(f"Konekcija nije uspješna: {e}")
        print("  Provjeri da li je PostgreSQL pokrenut i da su podaci tačni")
        return False


# ============================================================
# GLAVNA FUNKCIJA
# ============================================================

def main() -> int:
    """
    Glavna funkcija - interaktivni setup .env fajla.
    
    Returns:
        Exit code (0 = success, 1 = error)
    """
    print_header("🚀 ASYCUDA Pro - .env Setup")
    
    # 1. PROVJERA DA LI .env VEĆ POSTOJI
    if ENV_FILE.exists():
        print_warning(f".env fajl već postoji: {ENV_FILE}")
        response = input("Želiš li ga overwrite? (y/n) [n]: ").strip().lower()
        if response != "y":
            print("Odustao/la od setup-a.")
            return 0
        
        # Backup
        if not backup_existing_env():
            return 1
        print()
    
    # 2. PRIKUPLJANJE PODATAKA
    print("📝 Unesi konfiguraciju baze podataka:\n")
    
    db_host = get_input("Database Host", DEFAULTS["DB_HOST"])
    db_port = get_input("Database Port", DEFAULTS["DB_PORT"])
    db_name = get_input("Database Name", DEFAULTS["DB_NAME"])
    db_user = get_input("Database User", DEFAULTS["DB_USER"])
    
    # Password sa potvrdom
    print("\n🔒 Password (unos je skriven):")
    max_password_attempts = 3
    password_set = False
    
    for attempt in range(max_password_attempts):
        db_password = get_password("Database Password")
        if not db_password:
            print_error("Password ne može biti prazan!")
            continue
        
        if confirm_password(db_password):
            password_set = True
            print_success("Password potvrđen!")
            break
        else:
            print_error(f"Neuspješna potvrda password-a ({attempt+1}/{max_password_attempts})")
    
    if not password_set:
        print_error("Prekida setup - passwordi se ne poklapaju")
        return 1
    
    # 3. KREIRANJE .env FAJLA
    env_content = f"""# ASYCUDA Pro - Environment Configuration
# Kreirano: {Path(__file__).name} setup skriptom

# Database Configuration
DB_HOST={db_host}
DB_PORT={db_port}
DB_NAME={db_name}
DB_USER={db_user}
DB_PASSWORD="{db_password}"

# Application Settings
DEBUG={DEFAULTS["DEBUG"]}
MAX_IMPORT_WORKERS={DEFAULTS["MAX_IMPORT_WORKERS"]}
STRICT_VALIDATION={DEFAULTS["STRICT_VALIDATION"]}
"""
    
    try:
        ENV_FILE.write_text(env_content, encoding="utf-8")
        print_success(".env fajl kreiran uspješno!")
        print(f"📁 Lokacija: {ENV_FILE}")
    except Exception as e:
        print_error(f"Greška pri kreiranju .env fajla: {e}")
        return 1
    
    # 4. WARNING PORUKE
    print()
    print_warning("VAŽNO:")
    print("  • Ne komituj .env u git!")
    print("  • Zadrži .env siguran (sadrži password u plain text-u)")
    print("  • .env je u .gitignore - ali budi oprezan sa backup-om")
    
    # 5. TEST KONEKCIJE (OPCIONO)
    print()
    test_response = input("🔌 Testiraj DB konekciju? (y/n) [n]: ").strip().lower()
    
    if test_response == "y":
        if not test_db_connection(db_host, db_port, db_name, db_user, db_password):
            print()
            print_warning("Konekcija nije uspješna - provjeri podatke ili da li je PostgreSQL pokrenut")
    
    # KRAJ
    print()
    print_header("✨ Setup završen!")
    print("Sada možeš pokrenuti aplikaciju: python -m asycuda_pro")
    print()
    
    return 0


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Prekinuto od strane korisnika")
        sys.exit(1)
    except Exception as e:
        print_error(f"Neočekivana greška: {e}")
        sys.exit(1)
