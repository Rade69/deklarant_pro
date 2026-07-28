"""
Settings Service - Configuration management.

TASK 7: Implementirano čitanje/pisanje sa validacijom i backup-om
"""

from typing import Dict, Any, Optional
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class SettingsService:
    """
    Service za upravljanje settings-ima.
    
    TASK 7: Čitanje/Pisanje settings-a sa validacijom i backup-om
    """

    # Validne vrijednosti za svaki setting
    VALID_THEMES = ['light', 'dark']
    VALID_LANGUAGES = ['sr', 'en']
    VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    
    # Default vrijednosti
    DEFAULT_SETTINGS = {
        'theme': 'light',
        'language': 'sr',
        'auto_backup': True,
        'backup_interval_days': 7,
        'log_level': 'INFO',
        'plugins_auto_load': True,
        'completion_sound_enabled': True,
    }

    def __init__(self):
        """Inicijalizacija."""
        self.settings_dir = Path.home() / ".deklarant_pro"
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings_file = self.settings_dir / "settings.json"
        self.backup_dir = self.settings_dir / "settings_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def get_settings(self) -> Dict[str, Any]:
        """
        Vrati trenutne settings.
        
        Ako settings fajl ne postoji ili je nevalidan, vraća default.

        Returns:
            Dict sa settings-ima
        """
        if not self.settings_file.exists():
            logger.debug(f"Settings fajl ne postoji, koriste se defaulti: {self.settings_file}")
            return self.get_default_settings()

        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            # Validiraj i popuni missing vrijednosti
            settings = self._validate_and_merge(settings)
            
            return settings
        except Exception as e:
            logger.error(f"❌ Error loading settings: {e}")
            return self.get_default_settings()

    def save_settings(self, settings: Dict[str, Any], create_backup: bool = True) -> bool:
        """
        Sačuvaj settings.

        Args:
            settings: Dict sa settings-ima
            create_backup: Da li kreirati backup prije čuvanja

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            # 1. Validiraj settings
            if not self.validate_settings(settings):
                logger.error("❌ Validacija settings-a nije uspjela")
                return False

            # 2. Kreiraj backup (opciono)
            if create_backup and self.settings_file.exists():
                self._create_backup()

            # 3. Sačuvaj settings
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Settings sačuvani: {self.settings_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving settings: {e}")
            return False

    def get_default_settings(self) -> Dict[str, Any]:
        """
        Vrati default settings.

        Returns:
            Dict sa default settings-ima
        """
        return self.DEFAULT_SETTINGS.copy()

    def reset_to_defaults(self) -> bool:
        """
        Resetuj settings na fabrička podešavanja.

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            # Kreiraj backup trenutnih settings
            if self.settings_file.exists():
                self._create_backup()

            # Resetuj na default
            default_settings = self.get_default_settings()
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Settings resetovani na default")
            return True
        except Exception as e:
            logger.error(f"❌ Error resetting settings: {e}")
            return False

    def validate_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Validiraj settings.

        Args:
            settings: Dict sa settings-ima

        Returns:
            True ako su validni, False ako nisu
        """
        try:
            # Theme
            if 'theme' in settings:
                if settings['theme'] not in self.VALID_THEMES:
                    logger.error(f"❌ Invalid theme: {settings['theme']}")
                    return False

            # Language
            if 'language' in settings:
                if settings['language'] not in self.VALID_LANGUAGES:
                    logger.error(f"❌ Invalid language: {settings['language']}")
                    return False

            # Log level
            if 'log_level' in settings:
                if settings['log_level'] not in self.VALID_LOG_LEVELS:
                    logger.error(f"❌ Invalid log level: {settings['log_level']}")
                    return False

            # Auto backup (boolean)
            if 'auto_backup' in settings:
                if not isinstance(settings['auto_backup'], bool):
                    logger.error(f"❌ Invalid auto_backup type: {type(settings['auto_backup'])}")
                    return False

            # Backup interval (integer, 1-365)
            if 'backup_interval_days' in settings:
                interval = settings['backup_interval_days']
                if not isinstance(interval, int) or interval < 1 or interval > 365:
                    logger.error(f"❌ Invalid backup_interval_days: {interval}")
                    return False

            # Plugins auto load (boolean)
            if 'plugins_auto_load' in settings:
                if not isinstance(settings['plugins_auto_load'], bool):
                    logger.error(f"❌ Invalid plugins_auto_load type")
                    return False

            if 'completion_sound_enabled' in settings:
                if not isinstance(settings['completion_sound_enabled'], bool):
                    logger.error("❌ Invalid completion_sound_enabled type")
                    return False

            return True
        except Exception as e:
            logger.error(f"❌ Validation error: {e}")
            return False

    def get_setting(self, key: str, default: Any = None) -> Optional[Any]:
        """
        Vrati vrijednost specifičnog setting-a.

        Args:
            key: Ključ setting-a
            default: Default vrijednost ako key ne postoji

        Returns:
            Vrijednost setting-a ili None
        """
        settings = self.get_settings()
        return settings.get(key, default)

    def set_setting(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Postavi vrijednost specifičnog setting-a.

        Args:
            key: Ključ setting-a
            value: Vrijednost setting-a
            save: Da li odmah sačuvati

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            settings = self.get_settings()
            settings[key] = value
            
            if save:
                return self.save_settings(settings)
            return True
        except Exception as e:
            logger.error(f"❌ Error setting {key}: {e}")
            return False

    def _validate_and_merge(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validiraj settings i popuni missing vrijednosti sa default-ima.

        Args:
            settings: Dict sa settings-ima

        Returns:
            Validirani i kompletni settings
        """
        merged = self.DEFAULT_SETTINGS.copy()
        merged.update(settings)
        
        # Validiraj
        if not self.validate_settings(merged):
            logger.warning("⚠️  Settings nisu validni, vraćam default")
            return self.DEFAULT_SETTINGS.copy()
        
        return merged

    def _create_backup(self) -> Optional[Path]:
        """
        Kreiraj backup trenutnih settings.

        Returns:
            Putanja do backup fajla ili None
        """
        try:
            if not self.settings_file.exists():
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"settings_backup_{timestamp}.json"

            shutil.copy2(self.settings_file, backup_path)
            logger.info(f"✅ Backup kreiran: {backup_path}")
            
            # Zadrži samo zadnjih 5 backup-a
            self._cleanup_old_backups()
            
            return backup_path
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            return None

    def _cleanup_old_backups(self, keep_count: int = 5):
        """
        Obriši stare backup-e, zadrži samo zadnjih N.

        Args:
            keep_count: Broj backup-a za zadržati
        """
        try:
            backups = sorted(self.backup_dir.glob("settings_backup_*.json"))
            
            if len(backups) > keep_count:
                # Obriši najstarije
                for backup in backups[:-keep_count]:
                    backup.unlink()
                    logger.debug(f"🗑️  Obrisan stari backup: {backup.name}")
        except Exception as e:
            logger.error(f"❌ Error cleaning up backups: {e}")

    def get_available_backups(self) -> list:
        """
        Vrati listu dostupnih backup-a.

        Returns:
            Lista dict-ova sa backup informacijama
        """
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob("settings_backup_*.json")):
            stat = backup_file.stat()
            backups.append({
                'filename': backup_file.name,
                'filepath': str(backup_file),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
        
        # Sortiraj od najnovijeg ka najstarijem
        backups.reverse()
        return backups

    def restore_from_backup(self, backup_path: str) -> bool:
        """
        Restore settings iz backup-a.

        Args:
            backup_path: Putanja do backup fajla

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            backup_file = Path(backup_path)
            
            if not backup_file.exists():
                logger.error(f"❌ Backup fajl ne postoji: {backup_path}")
                return False

            # Kreiraj backup trenutnih settings prije restore-a
            self._create_backup()

            # Kopiraj backup na settings file
            shutil.copy2(backup_file, self.settings_file)
            logger.info(f"✅ Settings restore-ovani iz: {backup_path}")

            return True
        except Exception as e:
            logger.error(f"❌ Error restoring from backup: {e}")
            return False
