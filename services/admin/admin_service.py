"""
Admin Service - Main admin business logic.

Koordinira sve admin pod-servise.
"""

import os
import platform
from typing import List, Dict, Any
from services.admin.plugin_service import PluginService
from services.admin.settings_service import SettingsService
from services.admin.backup_service import BackupService
from services.admin.log_service import LogService
from services.admin.analytics_service import AnalyticsService


def format_architecture(machine: str, processor: str = "") -> str:
    normalized = machine.strip().lower()
    processor_info = f"{processor} {os.getenv('PROCESSOR_IDENTIFIER', '')}".lower()

    if normalized in {"amd64", "x86_64"}:
        vendor = ""
        if "intel" in processor_info or "genuineintel" in processor_info:
            vendor = ", Intel"
        elif "amd" in processor_info or "authenticamd" in processor_info:
            vendor = ", AMD"
        return f"64-bit (x86-64{vendor})"
    if normalized in {"x86", "i386", "i686"}:
        return "32-bit (x86)"
    if normalized in {"arm64", "aarch64"}:
        return "64-bit (ARM)"
    return machine or "N/A"


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

    def reset_settings(self) -> bool:
        return self.settings_service.reset_to_defaults()

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

    # SYSTEM INFO

    def get_system_info(self) -> Dict[str, Any]:
        """
        Vrati kompletne system informacije.

        Returns:
            Dict sa system info-m
        """
        import sys
        from datetime import datetime
        from PySide6.QtCore import qVersion
        from PySide6 import QtCore

        # Application info
        app_info = {
            'app_name': 'Deklarant Pro',
            'app_version': '2.0.0',
            'build_date': '2026-03-12',
        }

        # System info
        system_info = {
            'platform': platform.platform(),
            'platform_system': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'architecture': format_architecture(
                platform.machine(),
                platform.processor(),
            ),
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
