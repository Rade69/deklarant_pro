"""
PreFlightNaimenovanjaDialog — sažetak stanja faktura PRIJE kreiranja naimenovanja.

Prikazuje:
  - Predviđeni broj naimenovanja (simulacija grupisanja)
  - Stavke bez tarifnog broja
  - Stavke sa povlasticom a bez EUR1 broja
  - Stavke bez zemlje porijekla

Korisnik može nastaviti ili odustati.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


@dataclass
class PreFlightIssue:
    rb: int
    naziv: str
    problem: str


@dataclass
class PreFlightResult:
    """Izlaz analize — proslijeđuje se dijalogu i natrag pozivaocu."""
    expected_groups: int
    total_lines: int
    bez_tarife: List[PreFlightIssue]
    bez_porijekla: List[PreFlightIssue]
    povlastica_bez_eur1: List[PreFlightIssue]

    @property
    def has_blockers(self) -> bool:
        return bool(self.bez_tarife)

    @property
    def has_warnings(self) -> bool:
        return bool(self.bez_porijekla or self.povlastica_bez_eur1)

    @property
    def is_clean(self) -> bool:
        return not self.has_blockers and not self.has_warnings


def analyse_preflight(invoice_lines: list) -> PreFlightResult:
    """Analizira invoice_lines i vraća sažetak problema."""
    groups: dict = defaultdict(int)
    bez_tarife: List[PreFlightIssue] = []
    bez_porijekla: List[PreFlightIssue] = []
    povlastica_bez_eur1: List[PreFlightIssue] = []

    for i, line in enumerate(invoice_lines):
        tarifa = (getattr(line, 'tarifni_broj', '') or '').strip()
        zemlja = (getattr(line, 'zemlja_porijekla', '') or '').strip()
        povlastica = (getattr(line, 'povlastica', '') or '').strip()
        eur1 = (getattr(line, 'eur1_number', '') or '').strip()
        naziv = (getattr(line, 'naziv_robe', '') or '').strip()
        rb = i + 1

        if not tarifa:
            bez_tarife.append(PreFlightIssue(rb, naziv[:55], "Nema tarifnog broja"))
        if not zemlja:
            bez_porijekla.append(PreFlightIssue(rb, naziv[:55], "Nema zemlje porijekla"))
        if povlastica and povlastica not in ('0', '') and not eur1:
            povlastica_bez_eur1.append(
                PreFlightIssue(rb, naziv[:55], f"Povlastica '{povlastica}' bez EUR1/PE broja")
            )

        key = (tarifa, zemlja, povlastica, eur1)
        groups[key] += 1

    return PreFlightResult(
        expected_groups=len(groups),
        total_lines=len(invoice_lines),
        bez_tarife=bez_tarife,
        bez_porijekla=bez_porijekla,
        povlastica_bez_eur1=povlastica_bez_eur1,
    )


class PreFlightNaimenovanjaDialog(QDialog):
    """
    Modalni dijalog koji prikazuje pre-flight provjeru prije kreiranja naimenovanja.
    Vraća Accepted ako korisnik klikne "Nastavi", Rejected ako "Odustani".
    """

    def __init__(self, result: PreFlightResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Provjera prije kreiranja naimenovanja")
        self.setMinimumSize(640, 400)
        self.resize(720, 500)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._result = result
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        layout.addWidget(self._make_summary())

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #d0d5dd;")
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f9fafb; }")

        content = QWidget()
        content.setAttribute(Qt.WA_StyledBackground, True)
        content.setStyleSheet("QWidget { background: #f9fafb; }")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(8)

        r = self._result
        if r.bez_tarife:
            cl.addWidget(self._make_section(
                "Stavke bez tarifnog broja", r.bez_tarife,
                "#fef2f2", "#b91c1c", "Greška"
            ))
        if r.bez_porijekla:
            cl.addWidget(self._make_section(
                "Stavke bez zemlje porijekla", r.bez_porijekla,
                "#fffbeb", "#92400e", "Upozorenje"
            ))
        if r.povlastica_bez_eur1:
            cl.addWidget(self._make_section(
                "Povlastica bez EUR1/PE broja", r.povlastica_bez_eur1,
                "#fffbeb", "#92400e", "Upozorenje"
            ))
        if r.is_clean:
            ok = QLabel("<b style='color:#065f46;'>Sve provjere su prošle — nema problema.</b>")
            ok.setTextFormat(Qt.RichText)
            ok.setAlignment(Qt.AlignCenter)
            cl.addWidget(ok)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        layout.addWidget(self._make_buttons())

    def _make_summary(self) -> QWidget:
        r = self._result
        container = QWidget()
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setStyleSheet("""
            QWidget { background: #F0F4FA; border-radius: 8px; }
            QLabel  { background: transparent; }
        """)
        row = QHBoxLayout(container)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(24)

        def stat(value, label, color="#1E3A5F"):
            w = QWidget()
            w.setAttribute(Qt.WA_StyledBackground, True)
            w.setStyleSheet("QWidget { background: transparent; } QLabel { background: transparent; }")
            vl = QVBoxLayout(w)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(2)
            n = QLabel(f"<b style='font-size:22px; color:{color};'>{value}</b>")
            n.setTextFormat(Qt.RichText)
            n.setAlignment(Qt.AlignCenter)
            lbl = QLabel(f"<span style='color:#6b7280; font-size:12px;'>{label}</span>")
            lbl.setTextFormat(Qt.RichText)
            lbl.setAlignment(Qt.AlignCenter)
            vl.addWidget(n)
            vl.addWidget(lbl)
            return w

        row.addWidget(stat(r.total_lines, "stavki"))
        row.addWidget(stat(r.expected_groups, "naimenovanja"))
        err_col = "#b91c1c" if r.bez_tarife else "#065f46"
        row.addWidget(stat(len(r.bez_tarife), "bez tarife", err_col))
        warn_col = "#92400e" if (r.bez_porijekla or r.povlastica_bez_eur1) else "#065f46"
        row.addWidget(stat(
            len(r.bez_porijekla) + len(r.povlastica_bez_eur1),
            "upozorenja", warn_col
        ))
        row.addStretch()
        return container

    def _make_section(self, title: str, issues: List[PreFlightIssue],
                      bg: str, color: str, badge: str) -> QWidget:
        frame = QFrame()
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setStyleSheet(f"""
            QFrame {{ background: {bg}; border: 1px solid {color}40;
                      border-radius: 8px; }}
            QLabel {{ background: transparent; }}
        """)
        vl = QVBoxLayout(frame)
        vl.setContentsMargins(12, 10, 12, 10)
        vl.setSpacing(6)

        hdr = QLabel(
            f"<b style='color:{color}; font-size:14px;'>{title}</b>"
            f"&nbsp;&nbsp;<span style='background:{color}; color:white; font-size:11px; "
            f"padding:2px 8px; border-radius:4px;'>{badge} — {len(issues)}</span>"
        )
        hdr.setTextFormat(Qt.RichText)
        vl.addWidget(hdr)

        for issue in issues[:15]:
            lbl = QLabel(
                f"<span style='color:#374151; font-size:13px;'>"
                f"<b>Rb.{issue.rb}</b> — {issue.naziv or '(bez naziva)'}"
                f"&nbsp;&nbsp;<span style='color:{color};'>{issue.problem}</span>"
                f"</span>"
            )
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            vl.addWidget(lbl)

        if len(issues) > 15:
            more = QLabel(f"<span style='color:#6b7280; font-size:12px;'>… i još {len(issues)-15} stavki</span>")
            more.setTextFormat(Qt.RichText)
            vl.addWidget(more)

        return frame

    def _make_buttons(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        cancel_btn = QPushButton("Odustani")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton { background:#fff; color:#374151; border:1px solid #d1d5db;
                          border-radius:6px; padding:8px 20px; font-size:13px; }
            QPushButton:hover { background:#f3f4f6; }
        """)
        cancel_btn.clicked.connect(self.reject)

        label = "Nastavi svejedno" if self._result.has_blockers else "Nastavi"
        ok_btn = QPushButton(label)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton { background:#1E3A5F; color:white; border:none;
                          border-radius:6px; padding:8px 24px;
                          font-size:13px; font-weight:600; }
            QPushButton:hover { background:#2D5A8E; }
        """)
        ok_btn.clicked.connect(self.accept)

        row.addWidget(cancel_btn)
        row.addStretch()
        row.addWidget(ok_btn)
        return container
