import logging
logger = logging.getLogger(__name__)
"""
Plugin Service - Business logic za plugin management.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from importers.plugin_loader import PluginLoader
from importers.strategy_registry import get_registry


class PluginServiceError(Exception):
    """Greška u plugin servisu."""
    pass


class PluginService:
    """Service za upravljanje plugin parserima."""

    def __init__(self):
        self.plugin_loader = PluginLoader()

    def get_all_plugins(self) -> List[Dict[str, Any]]:
        """
        Dohvati sve instalirane pluginove.

        Returns:
            Lista dict-ova sa informacijama o pluginovima
        """
        return self.plugin_loader.list_installed_parsers()

    def get_plugin_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Dohvati informacije o specifičnom pluginu.

        Args:
            filename: Ime fajla parsera (npr. 'firma_parser.py')

        Returns:
            Dict sa informacijama ili None
        """
        filepath = self.plugin_loader.parsers_dir / filename
        if not filepath.exists():
            return None

        return self.plugin_loader.get_parser_info(filepath)

    def install_plugin(self, source_path: str) -> Tuple[bool, str]:
        """
        Instaliraj novi plugin.

        Args:
            source_path: Put do .py fajla

        Returns:
            (success, message) tuple
        """
        try:
            source = Path(source_path)

            if not source.exists():
                return False, f"Fajl ne postoji: {source_path}"

            if not source.suffix == '.py':
                return False, "Fajl mora biti Python (.py) fajl"

            # Provjeri da li parser već postoji
            existing = self.plugin_loader.parsers_dir / source.name
            if existing.exists():
                return False, f"Parser '{source.name}' već postoji!"

            # Instaliraj
            success = self.plugin_loader.install_plugin(source)

            if success:
                # Reload registry da se učita novi parser
                try:
                    registry = get_registry()
                    registry.reload_plugins()
                except Exception as e:
                    logger.warning(f"⚠️  Registry reload failed: {e}")

                return True, f"Parser '{source.name}' uspješno instaliran!"
            else:
                return False, "Greška prilikom kopiranja fajla"

        except Exception as e:
            return False, f"Greška: {str(e)}"

    def uninstall_plugin(self, filename: str) -> Tuple[bool, str]:
        """
        Deinstaliraj plugin.

        Args:
            filename: Ime fajla parsera (npr. 'firma_parser.py')

        Returns:
            (success, message) tuple
        """
        try:
            if not filename.endswith('.py'):
                filename = f"{filename}.py"

            # Provjeri da li postoji
            filepath = self.plugin_loader.parsers_dir / filename
            if not filepath.exists():
                return False, f"Parser '{filename}' ne postoji!"

            # Deinstaliraj
            success = self.plugin_loader.uninstall_plugin(filename)

            if success:
                # Reload registry da se ukloni parser
                try:
                    registry = get_registry()
                    registry.reload_plugins()
                except Exception as e:
                    logger.warning(f"⚠️  Registry reload failed: {e}")

                return True, f"Parser '{filename}' uspješno uklonjen!"
            else:
                return False, "Greška prilikom brisanja fajla"

        except Exception as e:
            return False, f"Greška: {str(e)}"

    def reload_plugins(self) -> Tuple[bool, str]:
        """
        Ponovo učitaj sve pluginove (hot-reload).

        Returns:
            (success, message) tuple
        """
        try:
            registry = get_registry()
            registry.reload_plugins()
            return True, "Svi parseri uspješno reload-ovani!"
        except Exception as e:
            return False, f"Greška prilikom reload-a: {str(e)}"

    def validate_parser_file(self, filepath: str) -> Tuple[bool, str]:
        """
        Validiraj parser fajl prije instalacije.

        Args:
            filepath: Put do .py fajla

        Returns:
            (is_valid, message) tuple
        """
        try:
            path = Path(filepath)

            if not path.exists():
                return False, "Fajl ne postoji"

            if not path.suffix == '.py':
                return False, "Fajl mora biti Python (.py) fajl"

            # Probaj učitati parser
            parser_class = self.plugin_loader._load_parser_from_file(path)

            if parser_class is None:
                return False, "Fajl ne sadrži validnu ImportStrategy klasu"

            # Kreiraj instancu i provjeri required atribute
            instance = parser_class()

            if not hasattr(instance, 'strategy_name'):
                return False, "Parser mora imati 'strategy_name' property"

            if not hasattr(instance, 'priority'):
                return False, "Parser mora imati 'priority' property"

            if not hasattr(instance, 'can_handle'):
                return False, "Parser mora imati 'can_handle' metodu"

            if not hasattr(instance, 'import_file'):
                return False, "Parser mora imati 'import_file' metodu"

            return True, f"Validan parser: {instance.strategy_name}"

        except Exception as e:
            return False, f"Greška pri validaciji: {str(e)}"

    def get_plugins_statistics(self) -> Dict[str, Any]:
        """
        Dohvati statistiku o pluginovima.

        Returns:
            Dict sa statistikom
        """
        plugins = self.get_all_plugins()

        # Grupiši po formatu
        by_format = {}
        for plugin in plugins:
            metadata = plugin.get('metadata', {})
            file_format = metadata.get('file_format', 'unknown')
            if file_format not in by_format:
                by_format[file_format] = 0
            by_format[file_format] += 1

        return {
            'total_count': len(plugins),
            'active_count': len([p for p in plugins if p.get('metadata', {}).get('active', True)]),
            'by_format': by_format,
            'parsers_dir': str(self.plugin_loader.parsers_dir)
        }
