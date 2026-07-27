import logging
import os
import re
from collections.abc import Iterable


_PATTERNS = (
    (re.compile(r"(?i)\b(DB_PASSWORD|GROQ_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY)\s*=\s*[^\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)postgres(?:ql)?://([^:/@\s]+):([^@\s]+)@"), r"postgresql://\1:[REDACTED]@"),
    (re.compile(r"\b(?:gsk_|sk-|AIza)[A-Za-z0-9_.-]{8,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?<!\d)\d{13}(?!\d)"), "[REDACTED_JIB]"),
    (re.compile(r"(?i)\bC:\\Users\\[^\\\s]+"), r"%USERPROFILE%"),
)


def redact_text(value: object) -> str:
    text = str(value)
    for env_name in (
        "DB_PASSWORD", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
    ):
        secret = os.getenv(env_name, "")
        if len(secret) >= 6:
            text = text.replace(secret, "[REDACTED]")
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.getMessage())
            record.args = ()
        except Exception:
            record.msg = "[REDACTED_LOG_RECORD]"
            record.args = ()
        return True


def install_redaction_filter(handlers: Iterable[logging.Handler]) -> None:
    for handler in handlers:
        if not any(isinstance(item, SensitiveDataFilter) for item in handler.filters):
            handler.addFilter(SensitiveDataFilter())
