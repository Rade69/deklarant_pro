# config/settings.py

"""
ASYCUDA Pro - Centralizovani sistem za konfiguraciju

Ovaj modul pruža jedinstvenu tačku za upravljanje svim konfiguracijskim
postavkama aplikacije koristeći Pydantic Settings v2.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Eksplicitno učitaj .env iz root-a
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)


# ============================================================
# DATABASE SETTINGS
# ============================================================

class DatabaseSettings(BaseSettings):
    """
    Konfiguracija za PostgreSQL bazu podataka.
    
    Sve vrijednosti se učitavaju iz .env fajla sa DB_ prefiksom.
    """
    
    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=5432, alias="DB_PORT")
    database: str = Field(default="asycuda_pro", alias="DB_NAME")
    user: str = Field(default="postgres", alias="DB_USER")
    password: str = Field(..., alias="DB_PASSWORD")  # REQUIRED iz env
    
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )
    
    @property
    def connection_string(self) -> str:
        """
        Generiše PostgreSQL connection string.
        
        Returns:
            str: Connection string u formatu postgresql://user:password@host:port/database
        """
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


# ============================================================
# PATH SETTINGS
# ============================================================

class PathSettings(BaseSettings):
    """
    Konfiguracija putanja do direktorijuma.
    
    Automatski kreira potrebne direktorijume pri inicijalizaciji.
    """
    
    project_root: Path = PROJECT_ROOT
    imports_dir: Path = PROJECT_ROOT / "imports"
    exports_dir: Path = PROJECT_ROOT / "exports"
    temp_dir: Path = PROJECT_ROOT / "temp"
    logs_dir: Path = PROJECT_ROOT / "logs"
    styles_dir: Path = PROJECT_ROOT / "styles"
    ui_dir: Path = PROJECT_ROOT / "ui"
    sifrarnici_dir: Path = PROJECT_ROOT / "sifrarnici"
    
    model_config = SettingsConfigDict(
        extra="ignore",
    )
    
    def model_post_init(self, __context) -> None:
        """
        Kreira direktorijume ako ne postoje.
        
        Kreiraju se: temp, logs (ne diraju se imports/exports - korisnički podaci)
        """
        dirs_to_create = [self.temp_dir, self.logs_dir]
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)


# ============================================================
# APP SETTINGS
# ============================================================

class AppSettings(BaseSettings):
    """
    Opšte postavke aplikacije.
    
    Sadrži osnovne informacije o aplikaciji i opcione konfiguracije.
    """
    
    app_name: str = Field(default="ASYCUDA Pro", alias="APP_NAME")
    version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    max_import_workers: int = Field(default=4, alias="MAX_IMPORT_WORKERS")
    strict_validation: bool = Field(default=True, alias="STRICT_VALIDATION")
    
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


# ============================================================
# SINGLETON GETTERS
# ============================================================

# Globalne instance za singleton pattern
_db_settings: Optional[DatabaseSettings] = None
_path_settings: Optional[PathSettings] = None
_app_settings: Optional[AppSettings] = None


def get_db_settings() -> DatabaseSettings:
    """
    Dohvata singleton instancu DatabaseSettings.
    
    Returns:
        DatabaseSettings: Konfiguracija baze podataka
    """
    global _db_settings
    if _db_settings is None:
        _db_settings = DatabaseSettings()
    return _db_settings


def get_path_settings() -> PathSettings:
    """
    Dohvata singleton instancu PathSettings.
    
    Returns:
        PathSettings: Konfiguracija putanja
    """
    global _path_settings
    if _path_settings is None:
        _path_settings = PathSettings()
    return _path_settings


def get_app_settings() -> AppSettings:
    """
    Dohvata singleton instancu AppSettings.
    
    Returns:
        AppSettings: Konfiguracija aplikacije
    """
    global _app_settings
    if _app_settings is None:
        _app_settings = AppSettings()
    return _app_settings
