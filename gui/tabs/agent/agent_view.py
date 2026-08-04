"""
Main Agent View — botanički sage green layout.
Split: DocumentPanel (lijevo 70%) | ChatPanel (desno 30%).
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor
from .widgets.header_bar import HeaderBar
from .widgets.document_panel import DocumentPanel
from .widgets.chat_panel import ChatPanel
from .constants import COLOR_SAGE_BG, COLOR_SAGE_LIGHT, COLOR_SAGE_MID, COLOR_SAGE_PALE


class AgentView(QWidget):
    """Main Agent View sa botaničkim dizajnom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"AgentView {{ background-color: {COLOR_SAGE_BG}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        self.header = HeaderBar()
        layout.addWidget(self.header)

        # Splitter: DocumentPanel | ChatPanel
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLOR_SAGE_MID};
                width: 3px;
            }}
        """)

        self.document_panel = DocumentPanel()
        self.document_panel.setMinimumWidth(700)
        self.splitter.addWidget(self.document_panel)

        self.chat_panel = ChatPanel()
        self.chat_panel.setMinimumWidth(430)
        self.splitter.addWidget(self.chat_panel)

        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 68)
        self.splitter.setStretchFactor(1, 32)
        self.splitter.setSizes([1180, 560])

        layout.addWidget(self.splitter, 1)

    def paintEvent(self, event):
        """Crta botaničke dekorativne elemente u uglovima."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Donji desni ugao — botanički krug
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLOR_SAGE_PALE))
        painter.setOpacity(0.5)
        painter.drawEllipse(w - 180, h - 180, 220, 220)

        painter.setBrush(QColor(COLOR_SAGE_LIGHT))
        painter.setOpacity(0.3)
        painter.drawEllipse(w - 120, h - 120, 160, 160)

        # Donji lijevi ugao
        painter.setBrush(QColor(COLOR_SAGE_PALE))
        painter.setOpacity(0.4)
        painter.drawEllipse(-60, h - 140, 180, 180)

        painter.setBrush(QColor(COLOR_SAGE_LIGHT))
        painter.setOpacity(0.25)
        painter.drawEllipse(-30, h - 90, 120, 120)

        painter.end()

    # Public API
    def get_document_panel(self) -> DocumentPanel:
        return self.document_panel

    def get_chat_panel(self) -> ChatPanel:
        return self.chat_panel

    def get_header(self) -> HeaderBar:
        return self.header
