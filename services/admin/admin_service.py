"""
Admin Service - Main admin business logic.

Koordinira sve admin pod-servise.
"""

from typing import List, Dict, Any, Optional
from services.admin.plugin_service import PluginService
from services.admin.settings_service import SettingsService
from services.admin.backup_service import BackupService
from services.admin.log_service import LogService
from services.admin.analytics_service import AnalyticsService


class AdminService:
    """
    Admin Service - main admin business logic.

    Koordinira sve admin operacije kroz pod-servise.
    """

    def __init__(self):
        """Inicijalizacija pod-servisa."""
        self.plugin_service = PluginService()
        self.settings_service = SettingsService()
        self.backup_service = BackupService()
        self.log_service = LogService()
        self.analytics_service = AnalyticsService()

    @property
    def plugin_loader(self):
        """
        Convenience property za access na plugin_loader.

        Returns:
            PluginLoader instance iz plugin_service
        """
        return self.plugin_service.plugin_loader

    def get_parser_info(self, plugin_name: str):
        """
        Vrati informacije o parseru.

        Args:
            plugin_name: Ime parsera

        Returns:
            Dict sa parser info ili None
        """
        return self.plugin_service.get_parser_info(plugin_name)

    # PLUGIN OPERATIONS (delegate to PluginService)

    def get_installed_plugins(self) -> List[Dict[str, Any]]:
        """
        Vrati listu instaliranih plugin-a.

        Returns:
            Lista dict-ova sa plugin info-m
        """
        return self.plugin_service.get_installed_plugins()

    def install_plugin(self, filepath: str) -> bool:
        """
        Instaliraj plugin.

        Args:
            filepath: Put do .py fajla

        Returns:
            True ako uspješno, False ako ne
        """
        return self.plugin_service.install_plugin(filepath)

    def remove_plugin(self, plugin_name: str) -> bool:
        """
        Ukloni plugin.

        Args:
            plugin_name: Ime plugin-a

        Returns:
            True ako uspješno, False ako ne
        """
        return self.plugin_service.remove_plugin(plugin_name)

    def reload_plugins(self) -> bool:
        """
        Reload svih plugin-a.

        Returns:
            True ako uspješno, False ako ne
        """
        return self.plugin_service.reload_plugins()

    # SETTINGS OPERATIONS (delegate to SettingsService)

    def get_settings(self) -> Dict[str, Any]:
        """
        Vrati trenutne settings.

        Returns:
            Dict sa settings-ima
        """
        return self.settings_service.get_settings()

    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Sačuvaj settings.

        Args:
            settings: Dict sa settings-ima

        Returns:
            True ako uspješno, False ako ne
        """
        return self.settings_service.save_settings(settings)

    # DATABASE OPERATIONS (delegate to BackupService)

    def create_backup(self, backup_path: str) -> bool:
        """
        Kreiraj database backup.

        Args:
            backup_path: Put gdje sačuvati backup

        Returns:
            True ako uspješno, False ako ne
        """
        return self.backup_service.create_backup(backup_path)

    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database iz backup-a.

        Args:
            backup_path: Put do backup fajla

        Returns:
            True ako uspješno, False ako ne
        """
        return self.backup_service.restore_backup(backup_path)

    def get_available_backups(self) -> List[Dict[str, Any]]:
        """
        Vrati listu dostupnih backup-a.

        Returns:
            Lista dict-ova sa backup info-m
        """
        return self.backup_service.get_available_backups()

    # LOG OPERATIONS (delegate to LogService)

    def get_recent_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Vrati nedavne log-ove.

        Args:
            count: Broj log-ova za vratiti

        Returns:
            Lista dict-ova sa log entries
        """
        return self.log_service.get_recent_logs(count)

    def filter_logs(
        self,
        level: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Filtriraj log-ove.

        Args:
            level: Log level (INFO, DEBUG, WARNING, ERROR)
            search: Search term
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            Lista filtriranih log entries
        """
        return self.log_service.filter_logs(
            level=level,
            search=search,
            start_date=start_date,
            end_date=end_date
        )

    # SYSTEM INFO

    def get_system_info(self) -> Dict[str, Any]:
        """
        Vrati kompletne system informacije.

        Returns:
            Dict sa system info-m
        """
        import sys
        import platform
        from datetime import datetime
        from PySide6.QtCore import qVersion
        from PySide6 import QtCore

        # Application info
        app_info = {
            'app_name': 'ASYCUDA Pro',
            'app_version': '2.0.0',
            'build_date': '2026-03-12',
        }

        # System info
        system_info = {
            'platform': platform.platform(),
            'platform_system': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor() or 'N/A',
            'python_version': sys.version.split()[0],
            'python_full_version': sys.version,
            'qt_version': qVersion(),
            'pyside_version': QtCore.__version__,
            'python_api': 'PySide6',
        }

        # Database & Plugins
        db_info = {
            'database_size': self.backup_service.get_database_size(),
            'plugins_count': len(self.get_installed_plugins()),
        }

        # Memory info (opciono)
        try:
            import psutil
            memory = psutil.virtual_memory()
            db_info['total_memory'] = memory.total
            db_info['available_memory'] = memory.available
            db_info['memory_percent'] = memory.percent
        except ImportError:
            # psutil nije instaliran
            db_info['total_memory'] = 0
            db_info['available_memory'] = 0
            db_info['memory_percent'] = 0

        # Disk info (opciono)
        try:
            import psutil
            disk = psutil.disk_usage('/')
            db_info['disk_total'] = disk.total
            db_info['disk_used'] = disk.used
            db_info['disk_free'] = disk.free
            db_info['disk_percent'] = disk.percent
        except ImportError:
            db_info['disk_total'] = 0
            db_info['disk_used'] = 0
            db_info['disk_free'] = 0
            db_info['disk_percent'] = 0

        # Merge all info
        all_info = {
            **app_info,
            **system_info,
            **db_info,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        return all_info

    # ANALYTICS OPERATIONS (delegate to AnalyticsService)

    def get_import_statistics(self) -> Dict[str, Any]:
        """
        Vrati import statistiku.

        Returns:
            Dict sa statistikama
        """
        return self.analytics_service.get_import_statistics()

    def get_parser_usage(self) -> List[Dict[str, Any]]:
        """
        Vrati parser usage statistiku.

        Returns:
            Lista dict-ova sa parser usage
        """
        return self.analytics_service.get_parser_usage()
