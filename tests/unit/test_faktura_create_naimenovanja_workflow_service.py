from unittest.mock import MagicMock
from types import SimpleNamespace

from core.draft import DeclarationDraft, InvoiceLine
from services.faktura.models import (
    CreateNaimenovanjaDraftResult,
    CreateNaimenovanjaWorkflowResult,
)
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


def test_build_post_action_plan_cuva_legacy_korake_kao_default():
    plan = CreateNaimenovanjaWorkflowService().build_post_action_plan()

    assert plan.mark_dirty is True
    assert plan.emit_data_changed is True
    assert plan.sync_pe_docs is True
    assert plan.sync_inspection_docs is True
    assert plan.reload_faktura_table is True
    assert plan.reload_related_tabs is True
    assert plan.emit_naimenovanja_created is True
    assert plan.clear_import_memory is True


def test_prepare_trazi_split_samo_u_interaktivnom_single_draft_toku(monkeypatch):
    draft = _draft()

    monkeypatch.setattr(
        "services.faktura.declaration_split_service.count_declaration_groups",
        lambda lines: 2,
    )

    result = CreateNaimenovanjaWorkflowService().prepare(draft, [], auto=False)

    assert result.should_offer_split is True
    assert result.drafts_to_process == [draft]
    assert result.all_lines == draft.invoice_lines


def test_prepare_ne_trazi_split_u_auto_toku(monkeypatch):
    draft = _draft()

    monkeypatch.setattr(
        "services.faktura.declaration_split_service.count_declaration_groups",
        lambda lines: 2,
    )

    result = CreateNaimenovanjaWorkflowService().prepare(draft, [], auto=True)

    assert result.should_offer_split is False


def test_prepare_multi_drafts_obradjuje_sve_draftove(monkeypatch):
    draft_1 = _draft("uid-1")
    draft_2 = _draft("uid-2")

    monkeypatch.setattr(
        "services.faktura.declaration_split_service.count_declaration_groups",
        lambda lines: 99,
    )

    result = CreateNaimenovanjaWorkflowService().prepare(draft_1, [draft_1, draft_2])

    assert result.should_offer_split is False
    assert result.drafts_to_process == [draft_1, draft_2]
    assert result.all_lines == draft_1.invoice_lines + draft_2.invoice_lines


def test_build_success_message_single_draft_cuva_legacy_tekst():
    draft = _draft()
    result = CreateNaimenovanjaWorkflowResult(
        draft_results=[CreateNaimenovanjaDraftResult(draft=draft, count=3)]
    )

    message = CreateNaimenovanjaWorkflowService().build_success_message(result, all_lines_count=5)

    assert message.level == "information"
    assert message.title == "Uspjeh!"
    assert "Kreirano 3 naimenovanja iz 5 stavki" in message.message


def test_build_success_message_overflow_ima_prioritet():
    draft = _draft()
    split_info = SimpleNamespace(total_count=120, current_count=99, overflow_count=21)
    result = CreateNaimenovanjaWorkflowResult(
        draft_results=[
            CreateNaimenovanjaDraftResult(draft=draft, count=99, split_info=split_info)
        ]
    )

    message = CreateNaimenovanjaWorkflowService().build_success_message(result, all_lines_count=100)

    assert message.level == "warning"
    assert message.title == "ASYCUDA limit — 99 naimenovanja"
    assert "Preostalih 21 naimenovanja" in message.message
