"""
Plugin Service - Plugin operations.

TASK 2: Implementirano učitavanje parsera iz plugins/parsers/ foldera
"""

from typing import List, Dict, Any, Optional, Type
from pathlib import Path
import sys
import logging
import shutil
import importlib.util
import inspect
from importers.plugin_loader import PluginLoader
from importers.strategy_registry import get_registry
from importers.base_strategy import ImportStrategy

logger = logging.getLogger(__name__)


class PluginService:
    """
    Service za plugin operacije.
    
    TASK 2: Učitavanje parsera iz plugins/parsers/ foldera
    """

    def __init__(self):
        """Inicijalizacija."""
        self.plugin_loader = PluginLoader()

    def get_installed_plugins(self) -> List[Dict[str, Any]]:
        """
        Vrati listu instaliranih plugin-a.
        
        Prolazi kroz sve .py fajlove u plugins/parsers/ folderu,
        učitava parser klase i vraća njihove metapodatke.

        Returns:
            Lista dict-ova sa plugin info-m:
            [
                {
                    'name': 'Parser Name',
                    'priority': 20,
                    'filename': 'parser.py',
                    'filepath': '/full/path/to/parser.py',
                    'client': 'Client Name',
                    'firma': 'Firma Name',
                    'version': '1.0',
                    'author': 'Author'
                }
            ]
        """
        plugins = []
        parsers_dir = self.plugin_loader.parsers_dir

        if not parsers_dir.exists():
            logger.warning(f"⚠️  Parsers directory ne postoji: {parsers_dir}")
            return plugins

        # Prođi kroz sve .py fajlove
        for filepath in parsers_dir.glob("*.py"):
            # Preskoči _template, __init__.py i slično
            if filepath.name.startswith("_"):
                continue

            try:
                # Učitaj parser klasu koristeći PluginLoader
                parser_class = self.plugin_loader._load_parser_from_file(filepath)

                if parser_class:
                    # Kreiraj instancu da izvučemo metapodatke
                    instance = parser_class()

                    # Izvuci metapodatke
                    plugins.append({
                        'name': instance.strategy_name,
                        'priority': instance.priority,
                        'filename': filepath.name,
                        'filepath': str(filepath),
                        'client': instance.metadata.get('client', 'Nepoznato'),
                        'firma': instance.metadata.get('firma', 'Nepoznato'),
                        'version': instance.metadata.get('version', '1.0'),
                        'author': instance.metadata.get('author', 'Nepoznato'),
                    })
            except Exception as e:
                logger.error(f"❌ Error loading {filepath.name}: {e}")
                continue

        if plugins:
            logger.info(f"✅ Pronađeno {len(plugins)} parser-a u plugins/parsers/")
        
        return plugins

    def install_plugin(self, filepath: str) -> bool:
        """
        Instaliraj plugin kopiranjem fajla u plugins/parsers/.

        Args:
            filepath: Put do .py fajla

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            source = Path(filepath)

            # 1. Validacija: fajl mora postojati
            if not source.exists():
                logger.error(f"❌ Fajl ne postoji: {filepath}")
                return False

            # 2. Validacija: mora biti .py ekstenzija
            if source.suffix != '.py':
                logger.error(f"❌ Nije Python fajl: {filepath}")
                return False

            # 3. Validacija: mora sadržati validnu parser klasu (opciono)
            try:
                parser_class = self._load_parser_from_file(source)
                if not parser_class:
                    logger.warning(f"⚠️  Warning: Fajl ne sadrži validnu parser klasu: {filepath}")
                    logger.debug(f"   Nastavljam sa instalacijom ali parser možda neće raditi.")
            except Exception as e:
                logger.warning(f"⚠️  Warning pri validaciji parsera: {e}")
                logger.debug(f"   Nastavljam sa instalacijom ali parser možda neće raditi.")

            # 4. Kopiraj fajl u plugins/parsers/
            destination = self.plugin_loader.parsers_dir / source.name

            # Provjeri da fajl sa istim imenom već ne postoji
            if destination.exists():
                logger.warning(f"⚠️  Parser sa imenom '{source.name}' već postoji! Biće overwrite-ovan.")
                # Napravi backup starog fajla
                backup_path = destination.with_suffix('.py.backup')
                shutil.copy2(destination, backup_path)
                logger.debug(f"   Backup kreiran: {backup_path}")

            # Kopiraj
            shutil.copy2(source, destination)
            logger.info(f"✅ Plugin instaliran: {destination}")
            return True

        except Exception as e:
            logger.error(f"❌ Plugin install failed: {e}")
            return False

    def remove_plugin(self, plugin_name: str) -> bool:
        """
        Ukloni plugin brisanjem fajla iz plugins/parsers/.

        Args:
            plugin_name: Ime plugin-a (strategy_name)

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            # 1. Pronađi parser u listi
            plugins = self.get_installed_plugins()

            for plugin in plugins:
                if plugin['name'] == plugin_name:
                    filepath = Path(plugin['filepath'])

                    # 2. Provjeri da fajl postoji
                    if not filepath.exists():
                        logger.error(f"❌ Fajl ne postoji: {filepath}")
                        return False

                    # 3. Obriši fajl
                    filepath.unlink()
                    logger.info(f"✅ Plugin uklonjen: {filepath.name}")
                    return True

            logger.error(f"❌ Parser '{plugin_name}' nije pronađen")
            return False

        except Exception as e:
            logger.error(f"❌ Plugin remove failed: {e}")
            return False

    def reload_plugins(self) -> bool:
        """
        Reload svih plugin-a iz registry-ja.

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            registry = get_registry()

            # Provjeri da li registry ima reload metodu
            if hasattr(registry, 'reload_plugins'):
                registry.reload_plugins()
                logger.info("✅ Plugins reloaded from registry")
            else:
                # Alternativa: kreiraj novi PluginLoader
                self.plugin_loader = PluginLoader()
                logger.info("✅ PluginLoader reloaded")

            return True
        except Exception as e:
            logger.error(f"❌ Plugin reload failed: {e}")
            return False

    def _load_parser_from_file(self, filepath: Path) -> Optional[Type[ImportStrategy]]:
        """
        Dinamički učitaj parser klasu iz Python fajla.
        
        Pomoćna metoda za validaciju parsera prije instalacije.

        Args:
            filepath: Put do .py fajla

        Returns:
            ImportStrategy klasa ili None
        """
        try:
            # Kreiraj module name
            module_name = f"temp_parser_{filepath.stem}"

            # Učitaj modul
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Pronađi ImportStrategy klasu u modulu
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # Da li je klasa koja nasljeđuje ImportStrategy?
                if (isinstance(attr, type) and
                        issubclass(attr, ImportStrategy) and
                        attr != ImportStrategy):
                    return attr

            return None

        except Exception as e:
            logger.debug(f"Error loading parser from {filepath}: {e}")
            return None

    def get_parser_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Vrati detaljne informacije o specifičnom parseru.

        Args:
            plugin_name: Ime parser-a

        Returns:
            Dict sa informacijama ili None
        """
        plugins = self.get_installed_plugins()

        for plugin in plugins:
            if plugin['name'] == plugin_name:
                return plugin

        return None

    def is_parser_installed(self, plugin_name: str) -> bool:
        """
        Provjeri da li je parser instaliran.

        Args:
            plugin_name: Ime parser-a

        Returns:
            True ako je instaliran, False ako nije
        """
        plugins = self.get_installed_plugins()
        return any(p['name'] == plugin_name for p in plugins)
