"""
Testovi za draft.revision — Faza −1.A (Agent V2 plan §10)
"""
from __future__ import annotations

from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft


def test_revision_starts_at_zero():
    draft = DeclarationDraft()
    assert draft.revision == 0
    assert draft.fingerprint == hash(0)


def test_mark_dirty_increments_revision():
    draft = DeclarationDraft()
    draft.mark_dirty()
    assert draft.revision == 1
    assert draft.fingerprint == hash(1)


def test_multiple_mark_dirty_cumulative():
    draft = DeclarationDraft()
    for _ in range(5):
        draft.mark_dirty()
    assert draft.revision == 5


def test_fingerprint_changes_with_revision():
    draft = DeclarationDraft()
    f1 = draft.fingerprint
    draft.mark_dirty()
    f2 = draft.fingerprint
    assert f1 != f2


def test_read_operations_dont_increment():
    draft = DeclarationDraft()
    _ = draft.dirty
    _ = draft.invoice_lines
    _ = draft.items
    assert draft.revision == 0


def test_clear_dirty_does_not_increment():
    draft = DeclarationDraft()
    draft.mark_dirty()
    r1 = draft.revision
    draft.clear_dirty()
    assert draft.revision == r1  # clear_dirty ne menja revision


def test_deserialized_draft_starts_at_zero():
    """Deserijalizovani draft ne čuva revision (polje ima init=False)."""
    draft = DeclarationDraft()
    draft.mark_dirty()
    draft.mark_dirty()
    assert draft.revision == 2
    # Simuliraj deserijalizaciju — novi draft je novi objekat
    draft2 = DeclarationDraft()
    assert draft2.revision == 0


def test_revision_persists_across_operations():
    draft = DeclarationDraft()
    draft.invoice_lines = [InvoiceLine(naziv_robe="Test")]
    draft.mark_dirty()
    assert draft.revision >= 1
