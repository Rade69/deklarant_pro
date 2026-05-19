from datetime import datetime
from types import SimpleNamespace

from gui.tabs.agent.agent_controller import AgentController
from gui.tabs.agent.models.file_item import FileItem


class FakeFileTable:
    def __init__(self):
        self.calls = []

    def update_file_status(self, filepath, status, confidence, parser=None):
        self.calls.append((filepath, status, confidence, parser))


def _file_item(status, lines):
    return FileItem(
        filepath="/tmp/invoice.pdf",
        filename="invoice.pdf",
        file_type="PDF",
        size_bytes=1,
        parser="auto",
        status=status,
        confidence=0.0,
        added_at=datetime.now(),
        invoice_lines=lines,
    )


def test_all_completed_normalizes_processing_file_with_lines():
    table = FakeFileTable()
    ctrl = SimpleNamespace(
        view=SimpleNamespace(
            get_document_panel=lambda: SimpleNamespace(file_table=table)
        )
    )
    item = _file_item("Processing", [object()])

    AgentController._normalize_finished_file_statuses(ctrl, [item])

    assert item.status == "Completed"
    assert item.confidence == 1.0
    assert table.calls == [("/tmp/invoice.pdf", "Completed", 1.0, "auto")]


def test_all_completed_does_not_complete_processing_file_without_lines():
    table = FakeFileTable()
    ctrl = SimpleNamespace(
        view=SimpleNamespace(
            get_document_panel=lambda: SimpleNamespace(file_table=table)
        )
    )
    item = _file_item("Processing", [])

    AgentController._normalize_finished_file_statuses(ctrl, [item])

    assert item.status == "Processing"
    assert table.calls == []
