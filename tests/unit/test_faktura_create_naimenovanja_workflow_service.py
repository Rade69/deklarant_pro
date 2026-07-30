from unittest.mock import MagicMock

from core.draft import DeclarationDraft, InvoiceLine
from services.faktura.create_naimenovanja_workflow_service import (
    CreateNaimenovanjaWorkflowService,
)


def _draft(uid="draft-1"):
    draft = DeclarationDraft()
    draft.draft_uid = uid
    draft.invoice_lines = [InvoiceLine(naziv_robe="Test", tarifni_broj="08052190")]
    return draft


def test_create_for_drafts_poziva_create_smart_group_i_ucenje_sa_draft_uid(monkeypatch):
    draft = _draft("uid-123")

    class FakeCreateService:
        def __init__(self, received_draft):
            self.received_draft = received_draft
            self.last_split_info = MagicMock(overflow_count=0)

        def create_smart_group(self):
            return 3

    class FakeFacade:
        calls = []

        @classmethod
        def get_instance(cls):
            return cls()

        def learn_from_draft(self, lines, **kwargs):
            self.calls.append((lines, kwargs))
            return 2

    monkeypatch.setattr(
        "services.naimenovanja.create_naimenovanja_service.CreateNaimenovanjaService",
        FakeCreateService,
    )
    monkeypatch.setattr("services.tariff_facade.TariffFacade", FakeFacade)

    result = CreateNaimenovanjaWorkflowService().create_for_drafts([draft])

    assert result.error is None
    assert result.total_count == 3
    assert result.draft_results[0].learning_count == 2
    assert FakeFacade.calls == [(draft.invoice_lines, {"draft_uid": "uid-123"})]


def test_learning_error_ne_blokira_kreiranje(monkeypatch):
    draft = _draft("uid-err")

    class FakeCreateService:
        last_split_info = None

        def __init__(self, received_draft):
            self.received_draft = received_draft

        def create_smart_group(self):
            return 1

    class FakeFacade:
        @classmethod
        def get_instance(cls):
            return cls()

        def learn_from_draft(self, lines, **kwargs):
            raise RuntimeError("ledger down")

    monkeypatch.setattr(
        "services.naimenovanja.create_naimenovanja_service.CreateNaimenovanjaService",
        FakeCreateService,
    )
    monkeypatch.setattr("services.tariff_facade.TariffFacade", FakeFacade)

    result = CreateNaimenovanjaWorkflowService().create_for_drafts([draft])

    assert result.error is None
    assert result.draft_results[0].count == 1
    assert "ledger down" in result.draft_results[0].learning_error


def test_create_error_vraca_strukturisanu_gresku(monkeypatch):
    draft = _draft()

    class BrokenCreateService:
        def __init__(self, received_draft):
            self.received_draft = received_draft

        def create_smart_group(self):
            raise RuntimeError("create failed")

    monkeypatch.setattr(
        "services.naimenovanja.create_naimenovanja_service.CreateNaimenovanjaService",
        BrokenCreateService,
    )

    result = CreateNaimenovanjaWorkflowService().create_for_drafts([draft])

    assert result.error is not None
    assert "create failed" in str(result.error)
