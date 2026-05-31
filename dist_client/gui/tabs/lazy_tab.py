# gui/tabs/lazy_tab.py

"""
LazyTab — wrapper koji kreira pravi tab widget tek pri prvom showEvent.

Koristi se za kartica koje su teške za inicijalizaciju (QUiLoader, DB upiti)
ali nisu vidljive pri pokretanju aplikacije.

Nepostojeći atributi se proslijeđuju na unutrašnji widget kad je kreiran,
ili vraćaju _noop dok nije kreiran — štiti pozivaoce od grešaka.

Dokumentacija: scripts/perf_and_stability_2026-04-26.md#1-lazy-tab-loading
"""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QSizePolicy, QWidget, QVBoxLayout


def _noop(*args, **kwargs):
    pass


# Minimalna veličina LazyTab placeholder-a dok unutrašnji widget nije kreiran.
# Sprječava Qt da skupi prozor pri prvom kliku na lazy karticu.
_PLACEHOLDER_MIN = QSize(800, 600)


class LazyTab(QWidget):
    """
    Placeholder koji kreira pravi tab widget tek kad korisnik prvi put klikne karticu.

    Atributi se proslijeđuju na unutrašnji widget (ensure_initialized().attr).
    Dok unutrašnji widget nije kreiran, nepostojeći atributi vraćaju _noop.
    """

    def __init__(self, factory_fn, parent=None):
        super().__init__(parent)
        self._factory_fn = factory_fn
        self._inner = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._layout = layout
        # Expanding policy osigurava da LazyTab uvijek zauzme cijeli raspoloživi prostor
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def sizeHint(self) -> QSize:
        if self._inner is not None:
            return self._inner.sizeHint()
        return _PLACEHOLDER_MIN

    def minimumSizeHint(self) -> QSize:
        if self._inner is not None:
            return self._inner.minimumSizeHint()
        return _PLACEHOLDER_MIN

    @property
    def is_initialized(self):
        return self._inner is not None

    def ensure_initialized(self):
        """Kreira unutrašnji widget ako još nije kreiran. Vraća unutrašnji widget."""
        if self._inner is None:
            self._inner = self._factory_fn()
            self._layout.addWidget(self._inner)
        return self._inner

    def showEvent(self, event):
        self.ensure_initialized()
        super().showEvent(event)

    def __getattr__(self, name):
        inner = self.__dict__.get('_inner')
        if inner is not None:
            return getattr(inner, name)
        return _noop
