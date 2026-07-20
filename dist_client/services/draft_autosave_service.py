"""
Autosave service for declaration drafts.

Saves drafts automatically in the background (periodic timer + after naimenovanja
creation) and provides recovery detection on startup.

See agent_reports/2026-07-20_pi-autosave-nacrt.md for design decisions.
"""

import logging
from datetime import datetime
from pathlib import Path

from core.draft import DeclarationDraft
from services.declaration_draft_service import (
    DeclarationDraftService,
    default_drafts_directory,
)

logger = logging.getLogger("deklarant_pro.autosave")


AUTOSAVE_DIR = ".autosave"
AUTOSAVE_FILENAME = "autosave.xml"


def _autosave_dir() -> Path:
    return default_drafts_directory() / AUTOSAVE_DIR


def autosave_path() -> Path:
    """Return the fixed autosave file path (does not depend on draft content)."""
    return _autosave_dir() / AUTOSAVE_FILENAME


def save_autosave(draft: DeclarationDraft) -> Path | None:
    """Save draft to the autosave location. Returns path on success, None on failure."""
    try:
        dst = _autosave_dir()
        dst.mkdir(parents=True, exist_ok=True)
        service = DeclarationDraftService()
        result = service.save(draft, autosave_path())
        logger.info("✅ Autosave saved: %s", result)
        return result
    except Exception as e:
        logger.warning("⚠️ Autosave failed: %s", e)
        return None


def has_autosave() -> bool:
    """Check if an autosave file exists."""
    return autosave_path().is_file()


def autosave_timestamp() -> datetime | None:
    """Return the modification time of the autosave file, or None."""
    try:
        mtime = autosave_path().stat().st_mtime
        return datetime.fromtimestamp(mtime)
    except (OSError, FileNotFoundError):
        return None


def load_autosave() -> DeclarationDraft | None:
    """Load draft from autosave file. Returns None on failure."""
    try:
        service = DeclarationDraftService()
        draft = service.load(autosave_path())
        logger.info("📂 Autosave loaded: %s", autosave_path())
        return draft
    except Exception as e:
        logger.warning("⚠️ Autosave load failed: %s", e)
        return None


def clear_autosave() -> None:
    """Delete the autosave file. Safe to call even if it does not exist."""
    try:
        path = autosave_path()
        if path.exists():
            path.unlink()
            logger.info("🗑️ Autosave cleared")
    except Exception as e:
        logger.warning("⚠️ Autosave clear failed: %s", e)