from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard, QGuiApplication


class ComplianceReportDialog(QDialog):
    """
    Ne-modalni dijaloški prozor sa rezultatima provjere deklaracije.
    Otvara se kao poseban prozor pored aplikacije.
    """

    def __init__(self, result, context: str = "", parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Provjera deklaracije")
        self.setMinimumSize(560, 480)
        self.resize(640, 540)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(False)

        self._result = result
        self._setup_ui(context)

    def _setup_ui(self, context: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # --- Header ---
        layout.addWidget(self._make_header(context))

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #d0d5dd;")
        layout.addWidget(sep)

        # --- Sadržaj ---
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        browser.setStyleSheet("""
            QTextBrowser {
                background: #ffffff;
                border: 1px solid #e0e4ea;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }
        """)
        browser.setHtml(self._build_html())
        layout.addWidget(browser)

        # --- Dugmad ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        copy_btn = QPushButton("Kopiraj izvještaj")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(self._btn_style(secondary=True))
        copy_btn.clicked.connect(self._copy_to_clipboard)

        close_btn = QPushButton("Zatvori")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setDefault(True)
        close_btn.setStyleSheet(self._btn_style(secondary=False))
        close_btn.clicked.connect(self.close)

        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _make_header(self, context: str) -> QWidget:
        from PySide6.QtWidgets import QWidget
        container = QWidget()
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setStyleSheet("""
            QWidget {
                background: #F0F4FA;
                border-radius: 8px;
            }
        """)
        row = QHBoxLayout(container)
        row.setContentsMargins(12, 10, 12, 10)

        n_err  = len(self._result.errors)
        n_warn = len(self._result.warnings)
        n_info = sum(1 for i in self._result.issues if i.severity == 'info')

        title = QLabel(f"<b>📋 Provjera deklaracije</b>")
        title.setStyleSheet("font-size: 14px; background: transparent;")

        if context:
            ctx_lbl = QLabel(context)
            ctx_lbl.setStyleSheet("color: #6b7280; font-size: 12px; background: transparent;")
        else:
            ctx_lbl = None

        if self._result.is_ok:
            badge_html = "<span style='color:#2d6a30; font-weight:600;'>✅ Sve uredu</span>"
        else:
            parts = []
            if n_err:
                parts.append(f"<span style='color:#b05050; font-weight:600;'>❌ {n_err} greška</span>")
            if n_warn:
                parts.append(f"<span style='color:#b8963a; font-weight:600;'>⚠️ {n_warn} upozorenja</span>")
            badge_html = " &nbsp; ".join(parts)

        badge = QLabel(badge_html)
        badge.setTextFormat(Qt.RichText)
        badge.setStyleSheet("background: transparent;")

        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(title)
        if ctx_lbl:
            left.addWidget(ctx_lbl)

        row.addLayout(left)
        row.addStretch()
        row.addWidget(badge)
        return container

    def _build_html(self) -> str:
        errors   = self._result.errors
        warnings = self._result.warnings
        infos    = [i for i in self._result.issues if i.severity == 'info']

        parts = []

        def section(icon, title, color, issues):
            rows = "".join(
                f"<tr><td style='padding:5px 8px; vertical-align:top; color:{color};'>{icon}</td>"
                f"<td style='padding:5px 0; color:#1a1a2e; line-height:1.5;'>{i.message}"
                + (f" <span style='color:#888; font-size:11px;'>[stavka {i.item_index}]</span>" if i.item_index >= 0 else "")
                + "</td></tr>"
                for i in issues
            )
            return (
                f"<p style='margin:12px 0 4px; font-weight:600; color:{color}; font-size:13px;'>"
                f"{icon} {title} ({len(issues)})</p>"
                f"<table width='100%' cellspacing='0' cellpadding='0' "
                f"style='background:#fafafa; border:1px solid #e8eaed; border-radius:5px;'>"
                f"{rows}</table>"
            )

        if not errors and not warnings and not infos:
            parts.append("<p style='color:#2d6a30; font-size:14px; margin-top:20px;'>✅ Sve provjere su prošle bez problema.</p>")
        else:
            if errors:
                parts.append(section("❌", "Greške", "#b05050", errors))
            if warnings:
                parts.append(section("⚠️", "Upozorenja", "#b8963a", warnings))
            if infos:
                parts.append(section("ℹ️", "Napomene", "#4a7890", infos))

        return "<html><body style='font-family: sans-serif; font-size:13px; margin:4px;'>" + "".join(parts) + "</body></html>"

    def _copy_to_clipboard(self) -> None:
        lines = []
        for issue in self._result.issues:
            prefix = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
            loc = f" [stavka {issue.item_index}]" if issue.item_index >= 0 else ""
            lines.append(f"{prefix} {issue.message}{loc}")
        text = "\n".join(lines) if lines else "Sve provjere prošle bez grešaka."
        QGuiApplication.clipboard().setText(text)

    @staticmethod
    def _btn_style(secondary: bool) -> str:
        if secondary:
            return """
                QPushButton {
                    background: #ffffff; color: #374151;
                    border: 1px solid #d1d5db; border-radius: 6px;
                    padding: 6px 16px; font-size: 13px;
                }
                QPushButton:hover { background: #f3f4f6; }
            """
        return """
            QPushButton {
                background: #1E3A5F; color: #ffffff;
                border: none; border-radius: 6px;
                padding: 6px 20px; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #2D5A8E; }
        """
