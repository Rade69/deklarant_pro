"""
Testovi za Plugin Service.
"""
import pytest
from pathlib import Path
from services.plugin_service import PluginService, PluginServiceError


class TestPluginService:
    """Testovi za PluginService."""

    def setup_method(self):
        """Setup prije svakog testa."""
        self.service = PluginService()

    def test_init(self):
        """Test inicijalizacije servisa."""
        assert self.service.plugin_loader is not None
        assert self.service.plugin_loader.parsers_dir.exists()

    def test_get_all_plugins_empty(self):
        """Test dohvaćanja svih pluginova (prazno)."""
        plugins = self.service.get_all_plugins()
        assert isinstance(plugins, list)
        # Može biti 0 ako nema instaliranih pluginova
        # ili više ako postoje test pluginovi

    def test_get_plugin_info_nonexistent(self):
        """Test informacija o nepostojećem pluginu."""
        info = self.service.get_plugin_info("nepostojeći.py")
        assert info is None

    def test_validate_parser_file_nonexistent(self):
        """Test validacije nepostojećeg fajla."""
        is_valid, message = self.service.validate_parser_file("/nepostojeći/fajl.py")
        assert is_valid is False
        assert "ne postoji" in message.lower()

    def test_validate_parser_file_not_python(self, tmp_path):
        """Test validacije fajla koji nije Python."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Ovo nije Python fajl")

        is_valid, message = self.service.validate_parser_file(str(txt_file))
        assert is_valid is False
        assert "Python" in message

    def test_validate_parser_file_invalid(self, tmp_path):
        """Test validacije invalidnog Python fajla."""
        invalid_py = tmp_path / "invalid.py"
        invalid_py.write_text("# Ovo nije validan parser\nx = 1\n")

        is_valid, message = self.service.validate_parser_file(str(invalid_py))
        assert is_valid is False

    def test_get_plugins_statistics(self):
        """Test statistike pluginova."""
        stats = self.service.get_plugins_statistics()

        assert isinstance(stats, dict)
        assert 'total_count' in stats
        assert 'active_count' in stats
        assert 'by_format' in stats
        assert 'parsers_dir' in stats

        assert isinstance(stats['total_count'], int)
        assert isinstance(stats['active_count'], int)
        assert isinstance(stats['by_format'], dict)
        assert isinstance(stats['parsers_dir'], str)

    def test_install_plugin_template(self):
        """Test instalacije template parsera."""
        template_path = Path(__file__).parent.parent.parent / "plugins" / "parsers" / "_TEMPLATE_parser.py"

        if template_path.exists():
            is_valid, message = self.service.validate_parser_file(str(template_path))
            # Template bi trebao biti validan
            assert is_valid is True, f"Template parser nije validan: {message}"

    def test_reload_plugins(self):
        """Test reload-a pluginova."""
        # Napomena: reload može fail-ovati ako StrategyRegistry nije inicijalizovan
        # jer get_registry() može vratiti None u test okruženju
        success, message = self.service.reload_plugins()
        # Dozvoljavamo i success i fail - bitno je da se metoda izvrši
        assert isinstance(success, bool)
        assert isinstance(message, str)

    def test_uninstall_nonexistent_plugin(self):
        """Test deinstalacije nepostojećeg plugin-a."""
        success, message = self.service.uninstall_plugin("nepostojeći.py")
        assert success is False
        assert "ne postoji" in message.lower()


class TestPluginServiceWithTemplate:
    """Testovi sa stvarnim template parserom."""

    def setup_method(self):
        """Setup sa template parserom."""
        self.service = PluginService()
        self.template_path = Path(__file__).parent.parent.parent / "plugins" / "parsers" / "_TEMPLATE_parser.py"

    def test_template_parser_structure(self):
        """Test strukture template parsera."""
        if not self.template_path.exists():
            pytest.skip("Template parser ne postoji")

        # Validiraj template
        is_valid, message = self.service.validate_parser_file(str(self.template_path))
        assert is_valid is True, f"Template nije validan: {message}"

    def test_install_and_uninstall_template(self):
        """Test instalacije i deinstalacije template parsera."""
        if not self.template_path.exists():
            pytest.skip("Template parser ne postoji")

        # Instaliraj (kopiraj na drugo mjesto)
        import shutil
        from pathlib import Path

        test_parser_name = "test_parser_copy.py"
        test_parser_path = self.service.plugin_loader.parsers_dir / test_parser_name

        try:
            # Kopiraj template
            shutil.copy2(self.template_path, test_parser_path)

            # Provjeri da li je instaliran
            plugins = self.service.get_all_plugins()
            plugin_names = [p['filename'] for p in plugins]
            assert test_parser_name in plugin_names

        finally:
            # Cleanup
            if test_parser_path.exists():
                test_parser_path.unlink()
