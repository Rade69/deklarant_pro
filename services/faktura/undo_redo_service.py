"""
Undo/Redo Service — upravljanje historijom izmjena draft-a
"""

import copy
from typing import List
from core.draft import InvoiceLine


class UndoRedoService:
    """Upravlja undo/redo stackovima za invoice_lines"""

    def __init__(self, max_undo: int = 30):
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._max_undo = max_undo

    def push_snapshot(self, invoice_lines: List[InvoiceLine]) -> None:
        snapshot = copy.deepcopy(invoice_lines)
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self, invoice_lines: List[InvoiceLine]) -> List[InvoiceLine] | None:
        if not self._undo_stack:
            return None
        self._redo_stack.append(copy.deepcopy(invoice_lines))
        return self._undo_stack.pop()

    def redo(self, invoice_lines: List[InvoiceLine]) -> List[InvoiceLine] | None:
        if not self._redo_stack:
            return None
        self._undo_stack.append(copy.deepcopy(invoice_lines))
        return self._redo_stack.pop()

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
