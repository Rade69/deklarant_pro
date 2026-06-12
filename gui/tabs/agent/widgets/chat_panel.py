"""
Chat panel sa Carinski Agent brandingom i tabovima (Agent, Aktivnosti, Pitanja).
Botanički Sage Green dizajn.

ENHANCED: Dodato pamćenje chat konteksta (ChatMemoryService).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTextEdit, QApplication,
    QLineEdit, QPushButton, QHBoxLayout, QLabel, QFrame, QMenuBar
)
from PySide6.QtCore import Qt, Signal, QDateTime, QTimer
from PySide6.QtGui import QTextCursor, QFont, QAction, QKeyEvent, QTextDocument


class _ChatInput(QTextEdit):
    """QTextEdit koji šalje poruku na Enter, a Shift+Enter dodaje novi red."""
    send_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.send_requested.emit()
        else:
            super().keyPressEvent(event)
import qtawesome as qta
from ..constants import *

# ENHANCED: Import memory service
from services.agent.chat_memory_service import ChatMemoryService


class ChatPanel(QWidget):
    """Desni panel — Carinski Agent branding + chat."""

    message_sent = Signal(str)
    proposal_confirmed = Signal(dict)   # {key: value}
    proposal_rejected = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # ENHANCED: Inicijalizuj memory service
        self._memory_service = ChatMemoryService(project="deklarant_pro")
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

        # ENHANCED: Memory status bar
        layout.addWidget(self._create_memory_status_bar())

        # ── Proposal card area (sakrivena dok nema prijedloga) ────────────────
        self._proposal_card = None
        self._proposal_area = QWidget()
        self._proposal_area.setVisible(False)
        self._proposal_layout = QVBoxLayout(self._proposal_area)
        self._proposal_layout.setContentsMargins(0, 0, 0, 0)
        self._proposal_layout.setSpacing(0)
        layout.addWidget(self._proposal_area)

        # ── Action buttons area (akcioni dugmići nakon analize) ───────────────
        self._action_area = QWidget()
        self._action_area.setVisible(False)
        self._action_area.setAttribute(Qt.WA_StyledBackground, True)
        self._action_area.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_SAGE_BG};
                border-top: 1px solid {COLOR_SAGE_PALE};
            }}
        """)
        self._action_layout = QHBoxLayout(self._action_area)
        self._action_layout.setContentsMargins(12, 8, 12, 8)
        self._action_layout.setSpacing(8)
        layout.addWidget(self._action_area)

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

        # Reset dugme
        self._reset_btn = QPushButton(qta.icon('fa5s.redo-alt', color=COLOR_TEXT_MUTED), " Reset")
        self._reset_btn.setFixedHeight(30)
        self._reset_btn.setToolTip("Resetuj agenta — obriši fajlove i akcije, kreni ispočetka")
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #5a4e8a;
            }}
        """)
        layout.addWidget(self._reset_btn)

        return header

    def connect_reset(self, callback):
        """Poveži Reset dugme sa callback-om iz controller-a."""
        self._reset_btn.clicked.connect(callback)

    def _create_memory_status_bar(self) -> QWidget:
        """ENHANCED: Status bar za prikaz memorije."""
        bar = QFrame()
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_SAGE_BG};
                border-bottom: 1px solid {COLOR_SAGE_PALE};
                padding: 4px 12px;
            }}
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(8)
        
        # Memory ikon
        memory_icon = QLabel()
        memory_icon.setPixmap(qta.icon('fa5s.memory', color=COLOR_SAGE).pixmap(14, 14))
        memory_icon.setStyleSheet("background: transparent;")
        
        # Status tekst
        self.memory_status_label = QLabel("💬 Nova sesija")
        self.memory_status_label.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 11px;
            background: transparent;
        """)
        
        # Dugme za kopiranje izvještaja (posljednja poruka agenta)
        self.copy_report_btn = QPushButton(qta.icon('fa5s.copy', color=COLOR_TEXT_MUTED), "")
        self.copy_report_btn.setFixedSize(24, 24)
        self.copy_report_btn.setToolTip("Kopiraj posljednji odgovor agenta")
        self.copy_report_btn.clicked.connect(self._copy_last_agent_message)
        self.copy_report_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SAGE_PALE};
            }}
        """)

        # Dugme za brisanje memorije
        self.clear_memory_btn = QPushButton(qta.icon('fa5s.trash-alt', color=COLOR_TEXT_MUTED), "")
        self.clear_memory_btn.setFixedSize(24, 24)
        self.clear_memory_btn.setToolTip("Obriši chat istoriju")
        self.clear_memory_btn.clicked.connect(self._clear_memory)
        self.clear_memory_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SAGE_PALE};
            }}
        """)

        layout.addWidget(memory_icon)
        layout.addWidget(self.memory_status_label)
        layout.addStretch()
        layout.addWidget(self.copy_report_btn)
        layout.addWidget(self.clear_memory_btn)

        return bar

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
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.input_field = _ChatInput()
        self.input_field.setPlaceholderText("Postavi pitanje... (Enter = pošalji, Shift+Enter = novi red)")
        self.input_field.setFixedHeight(80)
        self.input_field.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input_field.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.input_field.send_requested.connect(self._send_message)
        self.input_field.setStyleSheet(f"""
            QTextEdit {{
                padding: 8px 14px;
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 12px;
                font-size: 13px;
                background-color: {COLOR_SAGE_BG};
                color: {COLOR_TEXT};
            }}
            QTextEdit:focus {{
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
        layout.addWidget(send_btn, 0, Qt.AlignBottom)

        return widget

    # ── Bubble HTML ───────────────────────────────────────────────────────────

    def _agent_bubble(self, body: str, timestamp: str) -> str:
        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 6px 0;">
          <tr>
            <td width="5%" valign="top" style="padding-top:4px;">
              <span style="font-size:18px;">🌿</span>
            </td>
            <td width="84%" style="background-color:#ffffff;
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
            <td width="11%"></td>
          </tr>
        </table>"""

    def _user_bubble(self, body: str, timestamp: str) -> str:
        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 6px 0;">
          <tr>
            <td width="19%"></td>
            <td width="76%" align="right"
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

    # ── Typing indicator ──────────────────────────────────────────────────────

    def show_typing_indicator(self):
        """Prikaži 'Razmišljam...' bubble dok AI obrađuje upit."""
        if hasattr(self, '_typing_cursor_pos'):
            return
        cursor = self.agent_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._typing_cursor_pos = cursor.position()
        timestamp = QDateTime.currentDateTime().toString("HH:mm")
        self.agent_view.append(self._typing_bubble(timestamp))
        self._scroll_to_bottom()
        self.input_field.setEnabled(False)

    def hide_typing_indicator(self):
        """Ukloni 'Razmišljam...' bubble i vrati input."""
        if not hasattr(self, '_typing_cursor_pos'):
            return
        cursor = self.agent_view.textCursor()
        cursor.setPosition(self._typing_cursor_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        del self._typing_cursor_pos
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

    # ── Streaming ──────────────────────────────────────────────────────────────

    def start_streaming(self):
        """Ukloni typing indicator i otvori streaming bubble. Timer osvježava UI svakih 50ms."""
        self.hide_typing_indicator()
        cursor = self.agent_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._stream_start_pos = cursor.position()
        self._stream_buffer = ""
        self._stream_timestamp = QDateTime.currentDateTime().toString("HH:mm")
        self.agent_view.append(self._agent_bubble("▌", self._stream_timestamp))
        self._scroll_to_bottom()

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(50)
        self._stream_timer.timeout.connect(self._refresh_stream_bubble)
        self._stream_timer.start()

    def append_stream_token(self, token: str):
        """Akumuliraj token u buffer — timer se brine za osvježavanje."""
        self._stream_buffer += token

    def _refresh_stream_bubble(self):
        if not hasattr(self, '_stream_start_pos'):
            return
        cursor = self.agent_view.textCursor()
        cursor.setPosition(self._stream_start_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        body = self._stream_buffer.replace("\n", "<br>") + " ▌"
        self.agent_view.insertHtml(self._agent_bubble(body, self._stream_timestamp))
        self._scroll_to_bottom()

    def finalize_streaming(self):
        """Zatvori streaming bubble (prikaži finalni tekst bez kursora)."""
        if not hasattr(self, '_stream_start_pos'):
            return
        if hasattr(self, '_stream_timer'):
            self._stream_timer.stop()
            self._stream_timer.deleteLater()
            del self._stream_timer
        cursor = self.agent_view.textCursor()
        cursor.setPosition(self._stream_start_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        if hasattr(self, '_stream_buffer') and self._stream_buffer:
            body = self._stream_buffer.strip().replace("\n", "<br>")
            self._last_agent_message_html = body
            self.agent_view.insertHtml(self._agent_bubble(body, self._stream_timestamp))
        for attr in ('_stream_start_pos', '_stream_buffer', '_stream_timestamp'):
            if hasattr(self, attr):
                delattr(self, attr)
        self._scroll_to_bottom()
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self._update_memory_status()

    def cancel_streaming(self):
        """Ukloni streaming bubble bez prikaza sadržaja (npr. pri grešci)."""
        if not hasattr(self, '_stream_start_pos'):
            return
        if hasattr(self, '_stream_timer'):
            self._stream_timer.stop()
            self._stream_timer.deleteLater()
            del self._stream_timer
        cursor = self.agent_view.textCursor()
        cursor.setPosition(self._stream_start_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        for attr in ('_stream_start_pos', '_stream_buffer', '_stream_timestamp'):
            if hasattr(self, attr):
                delattr(self, attr)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

    def _typing_bubble(self, timestamp: str) -> str:
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
              <div style="color:{COLOR_TEXT_MUTED}; font-size:13px; font-style:italic;">
                ⏳ Razmišljam...
              </div>
            </td>
            <td width="23%"></td>
          </tr>
        </table>"""

    def add_agent_message(self, text: str):
        timestamp = QDateTime.currentDateTime().toString("HH:mm")
        body = text.replace("\n", "<br>")
        self._last_agent_message_html = body
        self.agent_view.append(self._agent_bubble(body, timestamp))
        self._scroll_to_bottom()
        # ENHANCED: Ažuriraj memory status
        self._update_memory_status()

    def _copy_last_agent_message(self):
        """Kopiraj posljednju poruku agenta (bez HTML oznaka) u clipboard — kratki izvještaj odluke."""
        html = getattr(self, "_last_agent_message_html", "")
        if not html:
            self.add_activity("ℹ️ Nema poruke agenta za kopiranje.")
            return
        doc = QTextDocument()
        doc.setHtml(html)
        plain = doc.toPlainText().strip()
        QApplication.clipboard().setText(plain)
        self.add_activity("📋 Izvještaj kopiran u clipboard.")

    def add_user_message(self, text: str):
        timestamp = QDateTime.currentDateTime().toString("HH:mm")
        body = text.replace("<", "&lt;").replace(">", "&gt;")
        self.agent_view.append(self._user_bubble(body, timestamp))
        self._scroll_to_bottom()
        # ENHANCED: Ažuriraj memory status
        self._update_memory_status()

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
        message = self.input_field.toPlainText().strip()
        if not message:
            return
        self.add_user_message(message)
        self.input_field.clear()
        self.message_sent.emit(message)

    def _update_memory_status(self):
        """ENHANCED: Ažuriraj status memorije."""
        msg_count = len(self._memory_service)
        if msg_count == 0:
            self.memory_status_label.setText("💬 Nova sesija")
        elif msg_count <= 4:
            self.memory_status_label.setText(f"💬 {msg_count} poruka u sesiji")
        else:
            self.memory_status_label.setText(f"💬 {msg_count} poruka — pamti kontekst")

    def _clear_memory(self):
        """ENHANCED: Obriši chat memoriju."""
        self._memory_service.clear()
        self._update_memory_status()
        self.add_activity("🗑️ Chat memorija obrisana")

    # ENHANCED: Getter za memory service
    def get_memory_service(self) -> ChatMemoryService:
        """Vrati memory service za korištenje u ChatWorker."""
        return self._memory_service

    def trigger_message(self, message: str):
        """Programski pošalji poruku — kao da je korisnik upisao i pritisnuo Enter."""
        self.input_field.setPlainText(message)
        self._send_message()

    def get_input_field(self) -> _ChatInput:
        return self.input_field

    # ── Proposal Card API ─────────────────────────────────────────────────────

    def show_proposal_card(self, proposal: dict):
        """
        Prikaži editabilnu karticu prijedloga između chata i input polja.

        proposal format: vidi ProposalCardWidget docstring
        """
        from .proposal_card import ProposalCardWidget

        # Ukloni prethodnu karticu ako postoji
        self.hide_proposal_card()

        card = ProposalCardWidget(proposal)
        card.confirmed.connect(self._on_proposal_confirmed)
        card.rejected.connect(self._on_proposal_rejected)

        self._proposal_card = card
        self._proposal_layout.addWidget(card)
        self._proposal_area.setVisible(True)

        # Prebaci na Agent tab da korisnik vidi karticu
        self.tabs.setCurrentIndex(0)
        self.add_activity("📋 Prijedlog spreman — provjeri i potvrdi u kartici ispod.")

    def hide_proposal_card(self):
        """Sakrij i ukloni aktivnu karticu prijedloga."""
        if self._proposal_card is not None:
            self._proposal_layout.removeWidget(self._proposal_card)
            self._proposal_card.deleteLater()
            self._proposal_card = None
        self._proposal_area.setVisible(False)

    def _on_proposal_confirmed(self, values: dict):
        self.hide_proposal_card()
        self.proposal_confirmed.emit(values)

    def _on_proposal_rejected(self):
        self.hide_proposal_card()
        self.add_agent_message("❌ Prijedlog odbačen.")
        self.proposal_rejected.emit()

    def show_action_buttons(self, actions: list):
        """
        Prikaži akcione dugmiće iznad input polja.
        actions = [(label, callback), ...]
        Dugmići nestaju čim korisnik klikne bilo koji.
        """
        self.hide_action_buttons()

        label = QLabel("Šta dalje?")
        label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px; background: transparent;")
        self._action_layout.addWidget(label)

        for btn_label, callback in actions:
            btn = QPushButton(btn_label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_SECONDARY};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #5a4e8a;
                }}
            """)
            def make_handler(cb):
                def handler():
                    self.hide_action_buttons()
                    cb()
                return handler
            btn.clicked.connect(make_handler(callback))
            self._action_layout.addWidget(btn)

        # Dugme za odustajanje
        cancel_btn = QPushButton("✕ Odustani")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #5a4e8a;
            }}
        """)
        cancel_btn.clicked.connect(self.hide_action_buttons)
        self._action_layout.addWidget(cancel_btn)
        self._action_layout.addStretch()

        self._action_area.setVisible(True)
        self.tabs.setCurrentIndex(0)

    def hide_action_buttons(self):
        """Sakrij i očisti akcione dugmiće."""
        while self._action_layout.count():
            item = self._action_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._action_area.setVisible(False)

    def get_tabs(self) -> QTabWidget:
        return self.tabs

    def get_agent_view(self) -> QTextEdit:
        return self.agent_view

    def get_activity_view(self) -> QTextEdit:
        return self.activity_view
