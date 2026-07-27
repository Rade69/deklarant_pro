"""
Test za FakturaView._apply_import_result_to_header — paritet isporuke
(Rb.20 "Uslovi isporuke", 2026-07-26).

Korisnički zahtjev: paritet isporuke (Incoterms) prepoznat na fakturi mora
automatski popuniti draft.uslovi_kod, po istom pravilu kao izvoznik/
uvoznik/valuta — samo ako je polje već prazno (ne prepisuje ručni unos).

Isti MagicMock "self" obrazac kao test_import_workflow_parity.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from core.draft.draft import DeclarationDraft
from gui.tabs.faktura_view import FakturaView
from importers.import_result import ImportResult


def _mock_self(draft: DeclarationDraft) -> MagicMock:
    mock_self = MagicMock()
    mock_self.draft = draft
    return mock_self


def test_popunjava_uslovi_kod_kad_je_prazan():
    draft = DeclarationDraft()
    result = ImportResult(incoterm_code="CPT")

    FakturaView._apply_import_result_to_header(_mock_self(draft), result)

    assert draft.uslovi_kod == "CPT"


def test_ne_prepisuje_rucno_unesen_uslovi_kod():
    draft = DeclarationDraft(uslovi_kod="FCA")
    result = ImportResult(incoterm_code="CPT")

    FakturaView._apply_import_result_to_header(_mock_self(draft), result)

    assert draft.uslovi_kod == "FCA"


def test_prazan_incoterm_code_ne_dira_draft():
    draft = DeclarationDraft()
    result = ImportResult(incoterm_code="")

    FakturaView._apply_import_result_to_header(_mock_self(draft), result)

    assert draft.uslovi_kod == ""
