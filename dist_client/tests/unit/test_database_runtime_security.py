from unittest.mock import MagicMock

import pytest

from database.db import _assert_connection_security


def _connection(state):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = state
    return conn


def _safe_state(**overrides):
    state = {
        "ssl": True,
        "rolsuper": False,
        "rolcreaterole": False,
        "rolcreatedb": False,
        "rolreplication": False,
        "rolbypassrls": False,
    }
    state.update(overrides)
    return state


def test_sigurna_runtime_konekcija_prolazi():
    _assert_connection_security(_connection(_safe_state()))


def test_konekcija_bez_tls_se_odbija():
    with pytest.raises(RuntimeError, match="TLS"):
        _assert_connection_security(_connection(_safe_state(ssl=False)))


@pytest.mark.parametrize(
    "privilege",
    ["rolsuper", "rolcreaterole", "rolcreatedb", "rolreplication", "rolbypassrls"],
)
def test_administratorske_privilegije_se_odbijaju(privilege):
    with pytest.raises(RuntimeError, match="administratorske"):
        _assert_connection_security(
            _connection(_safe_state(**{privilege: True}))
        )
