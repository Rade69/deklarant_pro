import pytest
from pydantic import ValidationError

from config.settings import DatabaseSettings


def _settings(**overrides):
    values = {
        "DB_HOST": "db.internal",
        "DB_NAME": "deklarant_pro",
        "DB_USER": "deklarant_app",
        "DB_PASSWORD": "test-only-password",
    }
    values.update(overrides)
    return DatabaseSettings(**values)


def test_tls_je_obavezan_po_defaultu():
    assert _settings().sslmode == "require"


@pytest.mark.parametrize("unsafe_mode", ["disable", "allow", "prefer"])
def test_nesiguran_sslmode_se_odbija(unsafe_mode):
    with pytest.raises(ValidationError):
        _settings(DB_SSLMODE=unsafe_mode)


@pytest.mark.parametrize("safe_mode", ["require", "verify-ca", "verify-full"])
def test_sigurni_sslmode_se_prihvata(safe_mode):
    assert _settings(DB_SSLMODE=safe_mode).sslmode == safe_mode
