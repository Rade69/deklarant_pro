"""
Chat panel sa Carinski Agent brandingom i tabovima (Agent, Aktivnosti, Pitanja).
Botanički Sage Green dizajn.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTextEdit,
    QLineEdit, QPushButton, QHBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtGui import QTextCursor, QFont
import qtawesome as qta
from ..constants import *


class ChatPanel(QWidget):
    """Desni panel — Carinski Agent branding + chat."""

    message_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"ChatPanel {{ background-color: {COLOR_SAGE_PANEL}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Carinski Agent branding ───────────────────────────────────────────
        layout.addWidget(self._create_agent_header())

        # ── Tab widget ────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {COLOR_SAGE_PANEL};
            }}
            QTabBar::tab {{
                background-color: {COLOR_SAGE_BG};
                padding: 8px 16px;
                margin-right: 2px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 13px;
                font-weight: bold;
                color: {COLOR_TEXT_LIGHT};
                min-width: 70px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLOR_SAGE_PANEL};
                color: {COLOR_SAGE_DARK};
                border-bottom: 2px solid {COLOR_SAGE};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLOR_SAGE_BG};
                color: {COLOR_TEXT};
            }}
            QTabBar::scroller {{ width: 0px; }}
        """)

        self.agent_view = self._create_chat_view()
        self.tabs.addTab(self.agent_view, qta.icon(ICON_ROBOT, color=COLOR_SAGE_DARK), " Agent")

        self.activity_view = self._create_activity_view()
        self.tabs.addTab(self.activity_view, qta.icon('fa5s.list', color=COLOR_SAGE_DARK), " Aktivnosti")

        self.faq_view = self._create_faq_view()
        self.tabs.addTab(self.faq_view, qta.icon(ICON_QUESTION, color=COLOR_SAGE_DARK), " Pitanja")

        layout.addWidget(self.tabs, 1)

        # ── Input area ────────────────────────────────────────────────────────
        layout.addWidget(self._create_input_area())

        # Welcome message
        self._add_welcome_message()

    def _create_agent_header(self) -> QWidget:
        """Carinski Agent branding sekcija."""
        header = QFrame()
        header.setAttribute(Qt.WA_StyledBackground, True)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-bottom: 1px solid {COLOR_SAGE_PALE};
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Avatar
        avatar = QLabel()
        avatar.setPixmap(qta.icon(ICON_ROBOT, color=COLOR_SECONDARY).pixmap(42, 42))
        avatar.setFixedSize(48, 48)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_SAGE_PANEL};
                border: 2px solid {COLOR_SAGE_PALE};
                border-radius: 24px;
                padding: 4px;
            }}
        """)

        # Tekst
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title = QLabel("Carinski Agent")
        title.setStyleSheet(f"""
            font-size: 15px;
            font-weight: bold;
            color: {COLOR_TEXT};
            background: transparent;
        """)

        subtitle = QLabel("AI pomočnik za parsiranje i tarifiranje")
        subtitle.setStyleSheet(f"""
            font-size: 11px;
            color: {COLOR_TEXT_MUTED};
            background: transparent;
        """)

        text_col.addWidget(title)
        text_col.addWidget(subtitle)

        layout.addWidget(avatar)
        layout.addLayout(text_col)
        layout.addStretch()

        # Online indikator
        dot = QLabel("● Online")
        dot.setStyleSheet(f"""
            color: {COLOR_SUCCESS};
            font-size: 11px;
            font-weight: bold;
            background: transparent;
        """)
        layout.addWidget(dot)

        return header

    def _create_chat_view(self) -> QTextEdit:
        view = QTextEdit()
        view.setReadOnly(True)
        view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLOR_SAGE_PANEL};
                border: none;
                padding: 10px;
                font-size: 13px;
            }}
        """)
        return view

    def _create_activity_view(self) -> QTextEdit:
        view = QTextEdit()
        view.setReadOnly(True)
        view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLOR_SAGE_DARKEST};
                color: {COLOR_SAGE_LIGHT};
                border: none;
                padding: 10px;
                font-family: monospace;
                font-size: 12px;
            }}
        """)
        return view

    def _create_faq_view(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {COLOR_SAGE_PANEL};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)

        faq_text = QLabel("""
        <h3 style="color: #3d6040;">Često postavljana pitanja</h3>

        <p><b>Q: Koliko fajlova mogu uploadovati odjednom?</b><br>
        A: Možete uploadovati do 50 faktura u jednom batch-u.</p>

        <p><b>Q: Koje formate podržava agent?</b><br>
        A: PDF, Excel (.xlsx, .xls) i XML dokumente.</p>

        <p><b>Q: Šta znači "Potrebna potvrda"?</b><br>
        A: Agent nije dovoljno siguran u tarifni broj (&lt; 80% confidence).</p>

        <p><b>Q: Kako radi auto-detect parser?</b><br>
        A: Agent automatski prepoznaje format fakture i bira odgovarajući parser.</p>
        """)
        faq_text.setWordWrap(True)
        faq_text.setTextFormat(Qt.RichText)
        faq_text.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px; background: transparent;")

        layout.addWidget(faq_text)
        layout.addStretch()
        return widget

    def _create_input_area(self) -> QWidget:
        widget = QWidget()
        widget.setAttribute(Qt.WA_StyledBackground, True)
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: white;
                border-top: 1px solid {COLOR_SAGE_PALE};
            }}
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Postavi pitanje...")
        self.input_field.returnPressed.connect(self._send_message)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 14px;
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 18px;
                font-size: 13px;
                background-color: {COLOR_SAGE_BG};
                color: {COLOR_TEXT};
            }}
            QLineEdit:focus {{
                border-color: {COLOR_SAGE};
                background-color: white;
            }}
        """)

        send_btn = QPushButton(qta.icon(ICON_SEND, color='white'), "")
        send_btn.setFixedSize(36, 36)
        send_btn.clicked.connect(self._send_message)
        send_btn.setToolTip("Pošalji (Enter)")
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                border: none;
                border-radius: 18px;
            }}
            QPushButton:hover {{ background-color: #5a4e8a; }}
        """)

        layout.addWidget(self.input_field)
        layout.addWidget(send_btn)

        return widget

    # ── Bubble HTML ───────────────────────────────────────────────────────────

    def _agent_bubble(self, body: str, timestamp: str) -> str:
        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 6px 0;">
          <tr>
            <td width="5%" valign="top" style="padding-top:4px;">
              <span style="font-size:18px;">🌿</span>
            </td>
            <td width="72%" style="background-color:#ffffff;
                    border-radius:4px 16px 16px 16px;
                    padding: 10px 14px;
                    border: 1px solid {COLOR_SAGE_PALE};">
              <div style="font-size:11px; color:{COLOR_TEXT_MUTED}; margin-bottom:5px;">
                <b style="color:{COLOR_SAGE_DARK};">Carinski Agent</b> &nbsp;·&nbsp; {timestamp}
              </div>
              <div style="color:{COLOR_TEXT}; font-size:13px; line-height:1.5;">
                {body}
              </div>
            </td>
            <td width="23%"></td>
          </tr>
        </table>"""

    def _user_bubble(self, body: str, timestamp: str) -> str:
        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 6px 0;">
          <tr>
            <td width="23%"></td>
            <td width="72%" align="right"
                style="background-color:{COLOR_SECONDARY};
                       border-radius:16px 4px 16px 16px;
                       padding: 10px 14px;">
              <div style="font-size:11px; color:rgba(255,255,255,0.75);
                          margin-bottom:5px; text-align:right;">
                <b style="color:white;">Vi</b> &nbsp;·&nbsp; {timestamp}
              </div>
              <div style="color:white; font-size:13px; line-height:1.5;">
                {body}
              </div>
            </td>
            <td width="5%" valign="top" style="padding-top:4px; text-align:center;">
              <span style="font-size:18px;">👤</span>
            </td>
          </tr>
        </table>"""

    # ── Public API ────────────────────────────────────────────────────────────

    def _add_welcome_message(self):
        timestamp = QDateTime.currentDateTime().toString("HH:mm")
        body = (
            "Zdravo! Ja sam <b>Carinski Agent</b> — AI asistent za carinsko posredovanje.<br><br>"
            "Mogu ti pomoći sa:<br>"
            f"<span style='color:{COLOR_SAGE_DARK};'>•</span> Automatskim popunjavanjem tarifnih brojeva<br>"
            f"<span style='color:{COLOR_SAGE_DARK};'>•</span> Identifikacijom proizvoda<br>"
            f"<span style='color:{COLOR_SAGE_DARK};'>•</span> Validacijom podataka<br><br>"
            "Prevuci fakture u upload panel ili postavi pitanje."
        )
        self.agent_view.append(self._agent_bubble(body, timestamp))

    def add_agent_message(self, text: str):
        timestamp = QDateTime.currentDateTime().toString("HH:mm")
        body = text.replace("\n", "<br>")
        self.agent_view.append(self._agent_bubble(body, timestamp))
        self._scroll_to_bottom()

    def add_user_message(self, text: str):
        timestamp = QDateTime.currentDateTime().toString("HH:mm")
        body = text.replace("<", "&lt;").replace(">", "&gt;")
        self.agent_view.append(self._user_bubble(body, timestamp))
        self._scroll_to_bottom()

    def add_activity(self, text: str):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.activity_view.append(f"[{timestamp}] {text}")
        cursor = self.activity_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.activity_view.setTextCursor(cursor)

    def _scroll_to_bottom(self):
        cursor = self.agent_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.agent_view.setTextCursor(cursor)
        self.agent_view.ensureCursorVisible()

    def _send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return
        self.add_user_message(message)
        self.input_field.clear()
        self.message_sent.emit(message)

    def get_input_field(self) -> QLineEdit:
        return self.input_field

    def get_tabs(self) -> QTabWidget:
        return self.tabs

    def get_agent_view(self) -> QTextEdit:
        return self.agent_view

    def get_activity_view(self) -> QTextEdit:
        return self.activity_view
