import logging
logger = logging.getLogger(__name__)
"""
Tariff Suggestion Dialog

Custom dialog za prijedlog tarifnog broja sa top 3 match-a.
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QCheckBox, QFrame, QButtonGroup, QWidget,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent

from services.tariff.tariff_mapping_service import TariffMapping
from core.draft import NaimenovanjeDraft


def _tariff_digits(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _clamp_similarity(value: float | None) -> float:
    try:
        similarity = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(similarity, 1.0))


def _format_similarity(value: float | None) -> str:
    return f"{_clamp_similarity(value):.0%}"


def _tariff_change_profile(current_code: str | None, suggested_code: str | None) -> dict:
    current = _tariff_digits(current_code)
    suggested = _tariff_digits(suggested_code)

    if not suggested:
        return {
            "level": "high",
            "label": "Rizik: visok - prijedlog nema tarifni broj",
            "apply_default": False,
            "border": "#D32F2F",
            "background": "#FFEBEE",
            "hover": "#FFCDD2",
            "text_color": "#B71C1C",
        }

    if not current:
        return {
            "level": "medium",
            "label": "Rizik: srednji - nema trenutne tarife za poređenje",
            "apply_default": False,
            "border": "#FFB300",
            "background": "#FFF8E1",
            "hover": "#FFECB3",
            "text_color": "#8A5A00",
        }

    if current == suggested:
        return {
            "level": "same",
            "label": "Rizik: nema promjene tarifnog broja",
            "apply_default": False,
            "border": "#90A4AE",
            "background": "#ECEFF1",
            "hover": "#CFD8DC",
            "text_color": "#455A64",
        }

    if current[:4] == suggested[:4]:
        return {
            "level": "low",
            "label": "Rizik: nizak - ista tarifna glava",
            "apply_default": True,
            "border": "#00BCD4",
            "background": "#E0F7FA",
            "hover": "#B2EBF2",
            "text_color": "#00838F",
        }

    if current[:2] == suggested[:2]:
        return {
            "level": "medium",
            "label": "Rizik: srednji - isto poglavlje, druga tarifna glava",
            "apply_default": False,
            "border": "#FFB300",
            "background": "#FFF8E1",
            "hover": "#FFECB3",
            "text_color": "#8A5A00",
        }

    return {
        "level": "high",
        "label": "Rizik: visok - drugo tarifno poglavlje",
        "apply_default": False,
        "border": "#D32F2F",
        "background": "#FFEBEE",
        "hover": "#FFCDD2",
        "text_color": "#B71C1C",
    }


class ClickableFrame(QFrame):
    """QFrame koji emituje click event kada se klikne na njega."""

    def __init__(self, index: int, parent_dialog):
        super().__init__()
        self.index = index
        self.parent_dialog = parent_dialog
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        """Klik na karticu - selektuj taj radio button."""
        if event.button() == Qt.LeftButton:
            # Selektuj odgovarajući radio button
            button = self.parent_dialog.radio_group.button(self.index)
            if button:
                button.setChecked(True)
                logger.debug(f"📌 Kartica #{self.index + 1} kliknuta - radio button selektovan")
        super().mousePressEvent(event)


class TariffSuggestionDialog(QDialog):
    """
    Dialog za prijedlog tarifnog broja.

    Features:
    - Prikazuje top 3 prijedloga sa match %
    - Radio buttons za odabir
    - Checkboxes za šta primijeniti
    - 3 dugmeta: Primijeni/Odbij/Ručna pretraga
    """

    suggestion_accepted = Signal(dict)  # {tariff, zemlja, povlastica}
    manual_search_requested = Signal()

    def __init__(
        self,
        mappings: List[TariffMapping],
        current_item: NaimenovanjeDraft,
        parent=None
    ):
        super().__init__(parent)
        self.mappings = mappings
        self.current_item = current_item
        self.selected_mapping: Optional[TariffMapping] = None

        # 🔍 DEBUG: Provjeri primljene mappings
        logger.debug(f"\n🔍 TariffSuggestionDialog.__init__")
        logger.debug(f"   Broj mappings: {len(mappings)}")
        for i, m in enumerate(mappings, 1):
            logger.debug(f"   {i}. {m.tarifni_broj} | {m.similarity:.0%} | {m.usage_count}× | {m.naziv_robe[:50]}")

        self.setWindowTitle("💡 Prijedlog tarifnog broja")
        self.setMinimumWidth(900)  # Povećano sa 700
        self.setMinimumHeight(650)  # Povećano sa 500
        self.resize(950, 700)  # Default size

        # Bolji font rendering
        from PySide6.QtGui import QFont
        font = QFont()
        font.setHintingPreference(QFont.PreferFullHinting)
        self.setFont(font)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup kompletnog UI-a."""
        # Global stylesheet za bolji rendering
        self.setStyleSheet("""
            QDialog {
                background-color: #FAFAFA;
            }
            QLabel {
                color: #212121;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header sekcija
        header_widget = self._create_header()
        layout.addWidget(header_widget)

        # Separator
        layout.addWidget(self._create_separator())

        # Prijedlozi sekcija
        suggestions_widget = self._create_suggestions_section()
        layout.addWidget(suggestions_widget)

        # Separator
        layout.addWidget(self._create_separator())

        # Upozorenje za postojeći tarifni broj (ako postoji)
        if self.current_item.tariff_code:
            warning_widget = self._create_warning_section()
            layout.addWidget(warning_widget)
            layout.addWidget(self._create_separator())

        # Akcije sekcija (checkboxes)
        actions_widget = self._create_actions_section()
        layout.addWidget(actions_widget)

        # Buttons sekcija
        buttons_widget = self._create_buttons_section()
        layout.addWidget(buttons_widget)

    def _create_header(self) -> QWidget:
        """Kreira header sa informacijama o proizvodu."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # Proizvod naziv
        naziv = self.current_item.goods_trade_name or "N/A"
        if len(naziv) > 100:
            naziv = naziv[:100] + "..."

        lbl_proizvod = QLabel(f'<b>Proizvod:</b> "{naziv}"')
        lbl_proizvod.setWordWrap(True)
        lbl_proizvod.setStyleSheet("font-size: 12pt;")
        lbl_proizvod.setMinimumWidth(300)
        layout.addWidget(lbl_proizvod)

        # Zemlja porijekla
        zemlja = self.current_item.origin_country_code or "N/A"
        lbl_zemlja = QLabel(f"<b>Zemlja porijekla:</b> {zemlja}")
        lbl_zemlja.setStyleSheet("font-size: 12pt;")
        lbl_zemlja.setMinimumWidth(200)
        layout.addWidget(lbl_zemlja)

        return widget

    def _create_suggestions_section(self) -> QWidget:
        """Kreira sekciju sa prijedlozima."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Naslov
        title = QLabel("🔍 Pronađeni prijedlozi:")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(13)  # Povećano sa 10
        title.setFont(title_font)
        title.setMinimumWidth(200)
        layout.addWidget(title)

        # Radio button group
        self.radio_group = QButtonGroup(self)

        # Kreiraj karticu za svaki mapping
        for i, mapping in enumerate(self.mappings):
            card = self._create_suggestion_card(i, mapping)
            layout.addWidget(card)

            # Automatski selektuj prvi (najbolji)
            if i == 0:
                self.radio_group.button(0).setChecked(True)
                self.selected_mapping = mapping

        return widget

    def _create_suggestion_card(self, index: int, mapping: TariffMapping) -> QWidget:
        """Kreira karticu za jedan prijedlog."""
        # 🔍 DEBUG: Provjeri mapping podatke
        logger.debug(f"\n🔍 _create_suggestion_card #{index + 1}")
        logger.debug(f"   tarifni_broj: '{mapping.tarifni_broj}' (type: {type(mapping.tarifni_broj)})")
        logger.debug(f"   similarity: {mapping.similarity:.2%}")
        logger.debug(f"   usage_count: {mapping.usage_count}")
        logger.debug(f"   naziv_robe: {mapping.naziv_robe[:80]}")

        # Wrapper widget sa click event
        card = ClickableFrame(index, self)
        card.setFrameShape(QFrame.NoFrame)

        profile = self._mapping_profile(mapping)
        border_width = 2 if index == 0 else 1
        card.setStyleSheet(
            f"ClickableFrame {{ background-color: {profile['background']}; border: {border_width}px solid {profile['border']}; border-radius: 8px; }}"
            f"ClickableFrame:hover {{ background-color: {profile['hover']}; border: 2px solid {profile['border']}; }}"
            "QLabel { background: transparent; border: none; }"
        )

        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 10)

        # Prva linija: Radio button + broj + tarifni broj + match %
        first_row = QHBoxLayout()

        # Radio button - povećaj clickable area
        radio = QRadioButton()
        radio.setStyleSheet("""
            QRadioButton {
                spacing: 8px;
                min-width: 20px;
                min-height: 20px;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
            }
        """)
        radio.setCursor(Qt.PointingHandCursor)  # Pointer cursor
        self.radio_group.addButton(radio, index)
        first_row.addWidget(radio)

        # Badge broj (1, 2, 3)
        badge_colors = ["#FF9800", "#9E9E9E", "#795548"]
        badge = QLabel(str(index + 1))
        # Direct style without QLabel selector
        badge.setStyleSheet(f"background-color: {badge_colors[index]}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11pt;")
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumWidth(30)
        badge.setMaximumWidth(40)
        badge.setMinimumHeight(25)
        first_row.addWidget(badge)

        # Tarifni broj (bold, large)
        lbl_tariff = QLabel(mapping.tarifni_broj)
        # Direct style - NO QLabel selector!
        lbl_tariff.setStyleSheet("font-size: 18pt; font-weight: bold; color: #1976D2;")
        lbl_tariff.setMinimumWidth(150)  # Povećano sa 120
        lbl_tariff.setMinimumHeight(30)
        first_row.addWidget(lbl_tariff)

        first_row.addSpacing(30)  # Povećano sa 20

        # Match procenat
        match_color = self._get_match_color(mapping.similarity)
        lbl_match = QLabel(f"Match: {_format_similarity(mapping.similarity)}")
        lbl_match.setStyleSheet(f"color: {match_color}; font-weight: bold; font-size: 12pt;")
        lbl_match.setMinimumWidth(120)  # Povećano sa 100
        lbl_match.setMinimumHeight(25)
        first_row.addWidget(lbl_match)

        first_row.addSpacing(15)  # Dodato spacing prije progress bar-a

        # Progress bar za match
        progress_bar = self._create_progress_bar(mapping.similarity)
        first_row.addWidget(progress_bar)

        first_row.addSpacing(20)  # Povećano sa 10

        # Usage count
        lbl_usage = QLabel(f"Korišćeno: {mapping.usage_count}×")
        lbl_usage.setStyleSheet("color: #666; font-size: 11pt;")
        lbl_usage.setMinimumWidth(130)  # Povećano sa 110
        lbl_usage.setMinimumHeight(25)
        first_row.addWidget(lbl_usage)

        first_row.addStretch()

        layout.addLayout(first_row)

        # Druga linija: Checkmarks (zašto je dobar match)
        second_row = QHBoxLayout()
        second_row.addSpacing(40)  # Indent za align sa radio button-om

        # ✓ Sličan naziv (uvijek true jer je pronađen)
        lbl_naziv = QLabel("✓ Sličan naziv")
        lbl_naziv.setStyleSheet("color: #4CAF50; font-size: 11pt;")
        lbl_naziv.setMinimumWidth(120)
        lbl_naziv.setMinimumHeight(25)
        second_row.addWidget(lbl_naziv)

        second_row.addSpacing(20)

        # ✓ Ista zemlja (ako match-uje)
        if mapping.zemlja_porijekla and self.current_item.origin_country_code:
            if mapping.zemlja_porijekla.upper() == self.current_item.origin_country_code.upper():
                lbl_zemlja = QLabel(f"✓ Ista zemlja ({mapping.zemlja_porijekla})")
                lbl_zemlja.setStyleSheet("color: #4CAF50; font-size: 11pt;")
                lbl_zemlja.setMinimumWidth(150)
                lbl_zemlja.setMinimumHeight(25)
                second_row.addWidget(lbl_zemlja)
                second_row.addSpacing(20)

        # ✓ Ista povlastica (ako postoji i match-uje)
        if mapping.povlastica and self.current_item.preference_code:
            if mapping.povlastica == self.current_item.preference_code:
                lbl_povlastica = QLabel(f"✓ Ista povlastica ({mapping.povlastica})")
                lbl_povlastica.setStyleSheet("color: #4CAF50; font-size: 11pt;")
                lbl_povlastica.setMinimumWidth(180)
                lbl_povlastica.setMinimumHeight(25)
                second_row.addWidget(lbl_povlastica)

        second_row.addStretch()

        layout.addLayout(second_row)

        risk_row = QHBoxLayout()
        risk_row.addSpacing(40)
        lbl_risk = QLabel(profile["label"])
        lbl_risk.setStyleSheet(f"color: {profile['text_color']}; font-weight: bold; font-size: 10pt;")
        lbl_risk.setMinimumHeight(22)
        risk_row.addWidget(lbl_risk)
        risk_row.addStretch()
        layout.addLayout(risk_row)

        # Edge Case 5: Sličan kvalitet matcha
        if index > 0:
            diff = self.mappings[0].similarity - mapping.similarity
            if diff < 0.05:  # < 5% razlika
                warning = QLabel(f"≈ Sličan kvalitet matcha (razlika {diff:.1%})")
                warning.setStyleSheet("color: #FFA500; font-style: italic; font-size: 10pt;")
                warning.setMinimumWidth(250)
                warning.setMinimumHeight(25)
                warning_layout = QHBoxLayout()
                warning_layout.addSpacing(40)
                warning_layout.addWidget(warning)
                warning_layout.addStretch()
                layout.addLayout(warning_layout)

        return card

    def _mapping_profile(self, mapping: TariffMapping) -> dict:
        return _tariff_change_profile(
            self.current_item.tariff_code,
            mapping.tarifni_broj,
        )

    def _create_progress_bar(self, similarity: float) -> QWidget:
        """Kreira progress bar za match %."""
        from PySide6.QtWidgets import QProgressBar

        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setValue(int(_clamp_similarity(similarity) * 100))
        progress.setTextVisible(False)
        progress.setMaximumWidth(100)
        progress.setMaximumHeight(12)

        # Boja prema kvalitetu matcha
        similarity = _clamp_similarity(similarity)
        if similarity >= 0.9:
            color = "#4CAF50"  # Zelena
        elif similarity >= 0.75:
            color = "#FFC107"  # Žuta
        else:
            color = "#FF9800"  # Narandžasta

        progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #CCC;
                border-radius: 3px;
                background-color: #F0F0F0;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)

        return progress

    def _get_match_color(self, similarity: float) -> str:
        """Vraća boju prema kvalitetu matcha."""
        similarity = _clamp_similarity(similarity)
        if similarity >= 0.9:
            return "#4CAF50"  # Zelena
        elif similarity >= 0.75:
            return "#FFC107"  # Žuta
        else:
            return "#FF9800"  # Narandžasta

    def _create_warning_section(self) -> QWidget:
        """Kreira upozorenje za postojeći tarifni broj."""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: #FFF3CD;
                border: 1px solid #FFE082;
                border-radius: 6px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Tekst sa ugrađenom warning oznakom
        text = QLabel(
            f"<b>!</b>&nbsp;&nbsp;"
            f"<b>Trenutni tarifni broj:</b> {self.current_item.tariff_code}&nbsp;&nbsp;"
            f"<i>(Biće zamijenjen ako prihvatite novi prijedlog)</i>"
        )
        text.setStyleSheet("font-size: 11pt; color: #7B5B00;")
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch()

        return widget

    def _create_actions_section(self) -> QWidget:
        """Kreira sekciju sa akcijama (checkboxes)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # Naslov
        title = QLabel("<b>Akcija:</b>")
        title.setStyleSheet("font-size: 12pt; font-weight: bold;")
        title.setMinimumWidth(100)
        layout.addWidget(title)

        apply_tariff_default = False
        if self.selected_mapping:
            apply_tariff_default = self._mapping_profile(self.selected_mapping)["apply_default"]

        # Checkbox: Primijeni tarifni broj
        self.chk_apply_tariff = QCheckBox("Primijeni tarifni broj")
        self.chk_apply_tariff.setChecked(apply_tariff_default)
        self.chk_apply_tariff.setStyleSheet("font-size: 11pt;")
        self.chk_apply_tariff.setMinimumWidth(220)
        layout.addWidget(self.chk_apply_tariff)

        # Checkbox: Primijeni povlasticu
        self.chk_apply_povlastica = QCheckBox("Primijeni povlasticu")
        self.chk_apply_povlastica.setChecked(False)
        self.chk_apply_povlastica.setStyleSheet("font-size: 11pt;")
        self.chk_apply_povlastica.setMinimumWidth(200)
        layout.addWidget(self.chk_apply_povlastica)

        # Checkbox: Primijeni zemlju porijekla
        self.chk_apply_zemlja = QCheckBox("Primijeni zemlju porijekla")
        self.chk_apply_zemlja.setChecked(False)
        self.chk_apply_zemlja.setStyleSheet("font-size: 11pt;")
        self.chk_apply_zemlja.setMinimumWidth(230)
        layout.addWidget(self.chk_apply_zemlja)

        return widget

    def _create_buttons_section(self) -> QWidget:
        """Kreira buttons sa akcijama."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # PRIMIJENI ODABRANI (zeleno)
        self.btn_apply = QPushButton("PRIMIJENI ODABRANI")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 13pt;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
            QPushButton:pressed {
                background-color: #3D8B40;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #F5F5F5;
            }
        """)
        self.btn_apply.setMinimumWidth(200)
        layout.addWidget(self.btn_apply)

        # ODBIJ (sivo)
        self.btn_reject = QPushButton("ODBIJ")
        self.btn_reject.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 13pt;
            }
            QPushButton:hover {
                background-color: #757575;
            }
            QPushButton:pressed {
                background-color: #616161;
            }
        """)
        self.btn_reject.setMinimumWidth(120)
        layout.addWidget(self.btn_reject)

        # RUČNA PRETRAGA (plavo)
        self.btn_manual = QPushButton("RUČNA PRETRAGA")
        self.btn_manual.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 13pt;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        self.btn_manual.setMinimumWidth(180)
        layout.addWidget(self.btn_manual)

        layout.addStretch()

        return widget

    def _create_separator(self) -> QFrame:
        """Kreira separator liniju."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #E0E0E0;")
        return line

    def _connect_signals(self):
        """Poveži signale."""
        # Radio button promjena
        self.radio_group.buttonClicked.connect(self._on_radio_changed)

        # Buttons
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_reject.clicked.connect(self._on_reject_clicked)
        self.btn_manual.clicked.connect(self._on_manual_clicked)

        self.chk_apply_tariff.stateChanged.connect(self._on_checkbox_changed)
        self.chk_apply_povlastica.stateChanged.connect(self._on_checkbox_changed)
        self.chk_apply_zemlja.stateChanged.connect(self._on_checkbox_changed)
        if self.selected_mapping:
            self._apply_selected_profile()

    def _on_radio_changed(self, button):
        """Radio button promijenjen - update selected mapping."""
        index = self.radio_group.id(button)
        self.selected_mapping = self.mappings[index]

        logger.debug(f"\n🔘 Radio button promijenjen!")
        logger.debug(f"   Index: {index}")
        logger.debug(f"   Tarifni broj: {self.selected_mapping.tarifni_broj}")
        logger.debug(f"   Match: {self.selected_mapping.similarity:.0%}")

        self._apply_selected_profile()

        if self.selected_mapping.povlastica:
            self.chk_apply_povlastica.setText(
                f"Primijeni povlasticu ({self.selected_mapping.povlastica})"
            )
            self.chk_apply_povlastica.setEnabled(True)
        else:
            self.chk_apply_povlastica.setText("Primijeni povlasticu (N/A)")
            self.chk_apply_povlastica.setEnabled(False)
            self.chk_apply_povlastica.setChecked(False)

        if self.selected_mapping.zemlja_porijekla:
            self.chk_apply_zemlja.setText(
                f"Primijeni zemlju porijekla ({self.selected_mapping.zemlja_porijekla})"
            )
            self.chk_apply_zemlja.setEnabled(True)
        else:
            self.chk_apply_zemlja.setText("Primijeni zemlju porijekla (N/A)")
            self.chk_apply_zemlja.setEnabled(False)
            self.chk_apply_zemlja.setChecked(False)

    def _apply_selected_profile(self):
        if not self.selected_mapping:
            return

        profile = self._mapping_profile(self.selected_mapping)
        self.chk_apply_tariff.setText(
            f"Primijeni tarifni broj ({self.selected_mapping.tarifni_broj}) - {profile['label']}"
        )
        self.chk_apply_tariff.setChecked(profile["apply_default"])
        self._update_apply_button_state()

    def _on_checkbox_changed(self):
        """Ažuriraj dostupnost primjene prema izabranim poljima."""
        self._update_apply_button_state()

    def _update_apply_button_state(self):
        if not hasattr(self, "btn_apply"):
            return
        has_action = (
            self.chk_apply_tariff.isChecked()
            or self.chk_apply_povlastica.isChecked()
            or self.chk_apply_zemlja.isChecked()
        )
        self.btn_apply.setEnabled(has_action)

    def _on_apply_clicked(self):
        """Korisnik prihvatio prijedlog."""
        if not self.selected_mapping:
            return

        # Pripremi rezultat
        result = {
            'tarifni_broj': self.selected_mapping.tarifni_broj if self.chk_apply_tariff.isChecked() else None,
            'povlastica': self.selected_mapping.povlastica if self.chk_apply_povlastica.isChecked() else None,
            'zemlja_porijekla': self.selected_mapping.zemlja_porijekla if self.chk_apply_zemlja.isChecked() else None,
            'similarity': self.selected_mapping.similarity,
            'usage_count': self.selected_mapping.usage_count
        }

        self.suggestion_accepted.emit(result)
        self.accept()

    def _on_reject_clicked(self):
        """Korisnik odbio prijedlog."""
        self.reject()

    def _on_manual_clicked(self):
        """Korisnik traži ručnu pretragu."""
        self.manual_search_requested.emit()
        self.reject()

    def get_result(self) -> Optional[dict]:
        """Vraća rezultat (nakon što je dialog zatvoren)."""
        if self.result() == QDialog.Accepted and self.selected_mapping:
            return {
                'tarifni_broj': self.selected_mapping.tarifni_broj if self.chk_apply_tariff.isChecked() else None,
                'povlastica': self.selected_mapping.povlastica if self.chk_apply_povlastica.isChecked() else None,
                'zemlja_porijekla': self.selected_mapping.zemlja_porijekla if self.chk_apply_zemlja.isChecked() else None,
                'similarity': self.selected_mapping.similarity,
                'usage_count': self.selected_mapping.usage_count
            }
        return None
