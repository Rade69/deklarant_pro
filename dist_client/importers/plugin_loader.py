import logging
logger = logging.getLogger(__name__)
"""
Plugin Loader - Dinamičko učitavanje parsera iz plugins/ foldera.
"""
import os
import sys
import importlib.util
import shutil
from pathlib import Path
from typing import List, Type, Optional, Dict, Any
from importers.base_strategy import ImportStrategy
from services.security.parser_trust_service import assert_parser_trusted


class PluginLoader:
    """Učitava parsere iz plugins/parsers/ foldera."""

    def __init__(self):
        # Plugins folder - LOKALNI ili INSTALLATION
        self.plugins_dir = self._get_plugins_directory()
        self.parsers_dir = self.plugins_dir / "parsers"

        # Kreiraj ako ne postoji
        self.parsers_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"📂 Plugins directory: {self.plugins_dir}")

    def _get_plugins_directory(self) -> Path:
        """
        Odredi plugins directory - različito za development i production.

        Development: {project_root}/plugins/
        Production: {exe_location}/plugins/
        """
        if getattr(sys, 'frozen', False):
            # PRODUCTION - PyInstaller .exe
            # Plugins folder pored .exe fajla
            exe_dir = Path(sys.executable).parent
            return exe_dir / "plugins"
        else:
            # DEVELOPMENT - Python runtime
            # Plugins folder u projektu
            project_root = Path(__file__).parent.parent
            return project_root / "plugins"

    def discover_parsers(self) -> List[Type[ImportStrategy]]:
        """
        Pronađi sve parsere u plugins/parsers/ folderu.

        Returns:
            Lista ImportStrategy klasa
        """
        parsers = []

        if not self.parsers_dir.exists():
            logger.warning(f"⚠️  Parsers directory ne postoji: {self.parsers_dir}")
            return parsers

        # Pretraži sve .py fajlove
        for filepath in self.parsers_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue  # Skip __init__.py i slično

            try:
                parser_class = self._load_parser_from_file(filepath)
                if parser_class:
                    parsers.append(parser_class)
                    logger.info(f"✅ Loaded parser: {parser_class.__name__} from {filepath.name}")
            except Exception as e:
                logger.error(f"❌ Failed to load {filepath.name}: {e}")

        return parsers

    def _load_parser_from_file(self, filepath: Path) -> Optional[Type[ImportStrategy]]:
        """
        Dinamički učitaj parser iz Python fajla.

        Args:
            filepath: Put do .py fajla

        Returns:
            ImportStrategy klasa ili None
        """
        assert_parser_trusted(filepath)

        # Kreiraj module name
        module_name = f"plugins.parsers.{filepath.stem}"

        try:
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
                    attr is not ImportStrategy):
                    return attr

        except Exception as e:
            logger.error(f"❌ Error loading parser from {filepath}: {e}")

        return None

    def install_plugin(self, source_path: Path) -> bool:
        """
        Instaliraj novi plugin parser.

        Args:
            source_path: Put do .py fajla parsera

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            destination = self.parsers_dir / source_path.name
            shutil.copy2(source_path, destination)
            source_signature = source_path.with_suffix(source_path.suffix + ".sig")
            if source_signature.is_file():
                shutil.copy2(
                    source_signature,
                    destination.with_suffix(destination.suffix + ".sig"),
                )
            logger.info(f"✅ Plugin instaliran: {destination}")
            return True

        except Exception as e:
            logger.error(f"❌ Plugin instalacija failed: {e}")
            return False

    def uninstall_plugin(self, parser_name: str) -> bool:
        """
        Deinstaliraj plugin parser.

        Args:
            parser_name: Ime parser fajla (npr. 'firma_parser.py')

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            filepath = self.parsers_dir / parser_name
            if filepath.exists():
                filepath.unlink()
                logger.info(f"✅ Plugin deinstaliran: {parser_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Plugin deinstalacija failed: {e}")
            return False

    def get_parser_info(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """
        Dohvati informacije o parseru.

        Args:
            filepath: Put do .py fajla parsera

        Returns:
            Dict sa informacijama o parseru ili None
        """
        try:
            parser_class = self._load_parser_from_file(filepath)
            if not parser_class:
                return None

            instance = parser_class()

            return {
                'filepath': filepath,
                'filename': filepath.name,
                'strategy_name': instance.strategy_name,
                'priority': instance.priority,
                'metadata': getattr(instance, 'metadata', {}),
                'class_name': parser_class.__name__
            }
        except Exception as e:
            logger.error(f"❌ Error getting parser info: {e}")
            return None

    def list_installed_parsers(self) -> List[Dict[str, Any]]:
        """
        Lista svih instaliranih parsera sa informacijama.

        Returns:
            Lista dict-ova sa informacijama o parserima
        """
        parsers = []

        if not self.parsers_dir.exists():
            return parsers

        for filepath in self.parsers_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue

            info = self.get_parser_info(filepath)
            if info:
                parsers.append(info)

        return parsers

    def reload_parser(self, parser_name: str) -> Optional[Type[ImportStrategy]]:
        """
        Ponovo učitaj specifičan parser (hot-reload).

        Args:
            parser_name: Ime parsera (bez .py ekstenzije)

        Returns:
            Parser klasa ili None
        """
        filepath = self.parsers_dir / f"{parser_name}.py"
        if not filepath.exists():
            return None

        # Ukloni iz sys.modules ako postoji
        module_name = f"plugins.parsers.{parser_name}"
        if module_name in sys.modules:
            del sys.modules[module_name]

        return self._load_parser_from_file(filepath)
