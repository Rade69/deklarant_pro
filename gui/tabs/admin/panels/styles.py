"""
Admin panel - centralizovane boje i zajednički stylesheet-ovi.

Sve boje se mijenjaju na jednom mjestu.
"""

# ── Boje ──────────────────────────────────────────────────────────────────────
PRIMARY        = "#0078d4"
PRIMARY_HOVER  = "#106ebe"
SUCCESS        = "#28a745"
SUCCESS_HOVER  = "#218838"
DANGER         = "#dc3545"
DANGER_HOVER   = "#c82333"
SECONDARY      = "#6c757d"
SECONDARY_HOVER = "#5a6268"
INFO           = "#17a2b8"
INFO_HOVER     = "#138496"

TEXT_PRIMARY   = "#333"
TEXT_SECONDARY = "#666"
TEXT_MUTED     = "#999"

BORDER         = "#ddd"
BORDER_FOCUS   = "#bbb"
BG_WHITE       = "white"
BG_LIGHT       = "#f5f5f5"
BG_HOVER       = "#f0f0f0"
BG_PRESSED     = "#e0e0e0"

# Log boje (tamna tema terminala)
LOG_ERROR     = "#ff6b6b"
LOG_WARNING   = "#ffa94d"
LOG_INFO      = "#74c0fc"
LOG_DEBUG     = "#999"
LOG_DEFAULT   = "#d4d4d4"
LOG_TIMESTAMP = "#666"

# ── Bazni stil panela (override globalnog QLabel font-size: 9px) ───────────────
# Primjenjuje se na self (panel widget) da pokrije sve QLabel/QCheckBox/QGroupBox
# unutar panela, bez potrebe da se svaki widget stilizuje posebno.
PANEL_BASE_STYLE = """
    QLabel {
        font-size: 13px;
        color: #333333;
    }
    QCheckBox {
        font-size: 13px;
        color: #333333;
    }
    QGroupBox {
        font-size: 14px;
        font-weight: bold;
        color: #333333;
    }
    QGroupBox::title {
        font-size: 13px;
        font-weight: bold;
        color: #333333;
    }
"""

# ── Zajednički stylesheet-ovi ──────────────────────────────────────────────────
GROUPBOX_STYLE = f"""
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 4px;
        margin-top: 12px;
        padding-top: 10px;
        font-weight: bold;
        font-size: 14px;
        background-color: {BG_WHITE};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        color: {TEXT_PRIMARY};
    }}
"""

BUTTON_BASE_STYLE = f"""
    QPushButton {{
        padding: 8px 16px;
        border: 1px solid {BORDER};
        border-radius: 4px;
        background-color: {BG_WHITE};
        font-size: 13px;
        font-weight: 500;
        min-width: 100px;
    }}
    QPushButton:hover {{
        background-color: {BG_HOVER};
        border-color: {BORDER_FOCUS};
    }}
    QPushButton:pressed {{
        background-color: {BG_PRESSED};
    }}
    QPushButton:disabled {{
        background-color: {BG_LIGHT};
        color: {TEXT_MUTED};
        border-color: {BG_PRESSED};
    }}
"""

INPUT_BASE_STYLE = f"""
    QComboBox, QLineEdit, QDateEdit, QSpinBox {{
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 6px 10px;
        background-color: {BG_WHITE};
        font-size: 13px;
    }}
    QComboBox:hover, QLineEdit:hover, QDateEdit:hover, QSpinBox:hover {{
        border-color: {BORDER_FOCUS};
    }}
    QComboBox:focus, QLineEdit:focus, QDateEdit:focus, QSpinBox:focus {{
        border-color: {PRIMARY};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 30px;
    }}
"""

LISTWIDGET_STYLE = f"""
    QListWidget {{
        background-color: {BG_LIGHT};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 5px;
        font-size: 13px;
    }}
    QListWidget::item {{
        padding: 10px;
        border-radius: 3px;
        margin-bottom: 2px;
    }}
    QListWidget::item:hover {{
        background-color: #e8e8e8;
    }}
    QListWidget::item:selected {{
        background-color: {PRIMARY};
        color: white;
    }}
"""


def log_color(level: str) -> str:
    """Vrati boju za log level."""
    return {
        "ERROR":   LOG_ERROR,
        "WARNING": LOG_WARNING,
        "INFO":    LOG_INFO,
        "DEBUG":   LOG_DEBUG,
    }.get(level, LOG_DEFAULT)


def status_color(status: str) -> str:
    """Vrati boju za declaration status."""
    return {
        "COMPLETED": SUCCESS,
        "PENDING":   "#ffc107",
        "ERROR":     DANGER,
    }.get(status, PRIMARY)
