import logging

from services.security.log_redaction import SensitiveDataFilter, redact_text


def test_redactuje_jib_i_api_kljuc():
    text = redact_text("JIB 4401234567890 ključ gsk_abcdefghijklmnop")

    assert "4401234567890" not in text
    assert "gsk_abcdefghijklmnop" not in text


def test_redactuje_db_url_i_user_putanju():
    text = redact_text(
        "postgresql://radovan:secret123@server/db C:\\Users\\radovan\\dok.xml"
    )

    assert "secret123" not in text
    assert "C:\\Users\\radovan" not in text


def test_filter_obradjuje_formatirane_argumente():
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "Partner JIB=%s", ("4401234567890",),
        None,
    )

    assert SensitiveDataFilter().filter(record)
    assert "4401234567890" not in record.getMessage()
