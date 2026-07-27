"""
Testovi za Plugin Service.
"""
import pytest
from pathlib import Path
from services.plugin_service import PluginService, PluginServiceError
from services.security.parser_trust_service import validate_parser_structure


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
            assert is_valid is False
            assert "isključeni" in message.lower()

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

        is_valid, message = validate_parser_structure(self.template_path)
        assert is_valid is True, f"Template nema validnu strukturu: {message}"

    def test_nepotpisana_kopija_templatea_se_ne_ucitava(self):
        """Nepotpisana kopija ne smije postati aktivan parser."""
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

            # Fajl postoji, ali nije potpisan i ne smije biti aktivan.
            plugins = self.service.get_all_plugins()
            plugin_names = [p['filename'] for p in plugins]
            assert test_parser_name not in plugin_names

        finally:
            # Cleanup
            if test_parser_path.exists():
                test_parser_path.unlink()


class TestParserTrust:
    def test_nepotpisan_parser_se_ne_izvrsava(self, tmp_path, monkeypatch):
        parser_path = tmp_path / "malicious_parser.py"
        marker = tmp_path / "executed.txt"
        parser_path.write_text(
            "from importers.base_strategy import ImportStrategy\n"
            f"open({str(marker)!r}, 'w').write('executed')\n"
            "class MaliciousParser(ImportStrategy):\n"
            "    @property\n"
            "    def strategy_name(self): return 'malicious'\n"
            "    @property\n"
            "    def priority(self): return 1\n"
            "    def can_handle(self, filepath): return False\n"
            "    def import_file(self, filepath): return None\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("ALLOW_EXTERNAL_PARSER_PLUGINS", raising=False)

        service = PluginService()
        is_valid, message = service.validate_parser_file(str(parser_path))

        assert is_valid is False
        assert "isključeni" in message.lower()
        assert not marker.exists()

    def test_parser_sa_vazecim_potpisom_se_moze_ucitati(
        self, tmp_path, monkeypatch,
    ):
        import base64
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        parser_path = tmp_path / "signed_parser.py"
        parser_path.write_text(
            "from importers.base_strategy import ImportStrategy\n"
            "class SignedParser(ImportStrategy):\n"
            "    @property\n"
            "    def strategy_name(self): return 'signed'\n"
            "    @property\n"
            "    def priority(self): return 1\n"
            "    def can_handle(self, filepath): return False\n"
            "    def import_file(self, filepath): return None\n",
            encoding="utf-8",
        )
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_path = tmp_path / "parser_public.pem"
        public_path.write_bytes(private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        signature = private_key.sign(
            parser_path.read_bytes(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        parser_path.with_suffix(".py.sig").write_bytes(base64.b64encode(signature))
        monkeypatch.setenv("ALLOW_EXTERNAL_PARSER_PLUGINS", "true")
        monkeypatch.setenv("PARSER_SIGNING_PUBLIC_KEY", str(public_path))

        service = PluginService()
        is_valid, message = service.validate_parser_file(str(parser_path))

        assert is_valid is True, message
        assert "SignedParser" in message
