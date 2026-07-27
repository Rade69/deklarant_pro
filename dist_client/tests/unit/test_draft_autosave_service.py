"""
Unit tests for draft_autosave_service.py

Covers:
- autosave save/load/has/clear/timestamp
- autosave does NOT modify _persistent_draft_path or drafts/lastDirectory
- recovery detection (exists/not exists)
- Multiple save/load cycles (file overwrite)
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from datetime import datetime

from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft, Party
from services.draft_autosave_service import (
    autosave_path,
    save_autosave,
    has_autosave,
    autosave_timestamp,
    load_autosave,
    clear_autosave,
    AUTOSAVE_DIR,
    AUTOSAVE_FILENAME,
)


@pytest.fixture
def sample_draft():
    """Create a minimal draft with one invoice line."""
    draft = DeclarationDraft()
    draft.ref_br = "TEST-AUTOSAVE-001"
    draft.invoice_lines = [
        InvoiceLine(
            tarifni_broj="08052190",
            naziv_robe="Test proizvod",
            zemlja_porijekla="DE",
            povlastica="",
            bruto_kg=100.0,
            neto_kg=90.0,
            iznos=500.0,
            kolicina=10,
            jm="kom",
            eur1_number="",
            exporter=Party(name="Exporter d.o.o.", address="Export str 1", country="DE"),
            importer=Party(name="Importer d.o.o.", address="Import str 1", country="BA"),
        )
    ]
    return draft


@pytest.fixture
def clean_autosave_dir():
    """Ensure autosave directory is clean before and after each test."""
    path = autosave_path()
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


def test_autosave_path_returns_fixed_path():
    """Autosave path should be fixed, not dependent on draft content."""
    p = autosave_path()
    assert isinstance(p, Path)
    assert p.name == AUTOSAVE_FILENAME
    assert AUTOSAVE_DIR in str(p)


def test_save_and_has_autosave(sample_draft, clean_autosave_dir):
    """After save, has_autosave() should return True."""
    assert not has_autosave()
    result = save_autosave(sample_draft)
    assert result is not None
    assert result.exists()
    assert has_autosave()


def test_load_autosave_returns_draft(sample_draft, clean_autosave_dir):
    """Loaded draft should match saved draft."""
    save_autosave(sample_draft)
    loaded = load_autosave()
    assert loaded is not None
    assert loaded.ref_br == sample_draft.ref_br
    assert len(loaded.invoice_lines) == 1
    assert loaded.invoice_lines[0].tarifni_broj == "08052190"
    assert loaded.invoice_lines[0].naziv_robe == "Test proizvod"


def test_clear_autosave(sample_draft, clean_autosave_dir):
    """After clear, has_autosave() should return False."""
    save_autosave(sample_draft)
    assert has_autosave()
    clear_autosave()
    assert not has_autosave()


def test_clear_autosave_no_file():
    """clear_autosave() should not raise if file does not exist."""
    clear_autosave()  # Should not raise


def test_autosave_timestamp(sample_draft, clean_autosave_dir):
    """autosave_timestamp() should return a datetime after save."""
    assert autosave_timestamp() is None
    save_autosave(sample_draft)
    ts = autosave_timestamp()
    assert ts is not None
    assert isinstance(ts, datetime)
    # Should be recent (within last 10 seconds)
    delta = (datetime.now() - ts).total_seconds()
    assert delta < 10


def test_autosave_does_not_set_persistent_path(sample_draft, clean_autosave_dir):
    """Autosave must NOT set _persistent_draft_path (only manual save/load does)."""
    # _persistent_draft_path is a dynamic attribute set by DeclarationDraftService.load()
    # Autosave uses save() internally which does NOT set this attribute
    assert not hasattr(sample_draft, '_persistent_draft_path')
    save_autosave(sample_draft)
    assert not hasattr(sample_draft, '_persistent_draft_path')


def test_autosave_does_not_set_dirty(sample_draft, clean_autosave_dir):
    """Autosave should not mark the draft as clean (dirty is a UI concept)."""
    sample_draft.dirty = True
    save_autosave(sample_draft)
    # save_autosave uses DeclarationDraftService.save() which does NOT set dirty = False
    # (only load() does that). The draft object should remain dirty.
    assert sample_draft.dirty is True


def test_multiple_save_load_cycles(sample_draft, clean_autosave_dir):
    """Multiple save/load cycles should work (file overwrite)."""
    # First save
    save_autosave(sample_draft)

    # Modify draft
    sample_draft.ref_br = "TEST-AUTOSAVE-002"
    sample_draft.invoice_lines[0].naziv_robe = "Drugi proizvod"

    # Second save
    save_autosave(sample_draft)

    # Load should return the second version
    loaded = load_autosave()
    assert loaded.ref_br == "TEST-AUTOSAVE-002"
    assert loaded.invoice_lines[0].naziv_robe == "Drugi proizvod"


def test_has_autosave_no_file(clean_autosave_dir):
    """has_autosave() should return False when no autosave file exists."""
    assert not has_autosave()


def test_load_autosave_no_file(clean_autosave_dir):
    """load_autosave() should return None when no autosave file exists."""
    assert load_autosave() is None


def test_autosave_saves_valid_xml(sample_draft, clean_autosave_dir):
    """Autosave file should be valid XML with DeklarantProDraft root tag."""
    import xml.etree.ElementTree as ET
    save_autosave(sample_draft)
    root = ET.parse(autosave_path()).getroot()
    assert root.tag == "DeklarantProDraft"
    assert root.get("version") == "1"


def test_autosave_does_not_remove_naimenovanja(sample_draft, clean_autosave_dir):
    """Autosave should preserve naimenovanja if they exist."""
    sample_draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=1,
            tariff_code="08052190",
            goods_description="Test naimenovanje",
            origin_country_code="DE",
        )
    ]
    save_autosave(sample_draft)
    loaded = load_autosave()
    assert loaded is not None
    assert len(loaded.items) == 1
    assert loaded.items[0].tariff_code == "08052190"


def test_autosave_path_under_drafts_dir():
    """Autosave directory should be under default_drafts_directory()."""
    from services.declaration_draft_service import default_drafts_directory
    p = autosave_path()
    assert str(p).startswith(str(default_drafts_directory()))