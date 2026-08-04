"""
Admin panel - centralizovane boje i zajednički stylesheet-ovi.

Sve boje se mijenjaju na jednom mjestu.
"""

# ── Boje ──────────────────────────────────────────────────────────────────────
PRIMARY        = "#3477a5"
PRIMARY_HOVER  = "#2b648c"
SUCCESS        = "#2f7d5b"
SUCCESS_HOVER  = "#286a4e"
DANGER         = "#ad3e3e"
DANGER_HOVER   = "#943535"
SECONDARY      = "#4f6779"
SECONDARY_HOVER = "#425868"
INFO           = "#2f7773"
INFO_HOVER     = "#286662"

TEXT_PRIMARY   = "#17324a"
TEXT_SECONDARY = "#52697b"
TEXT_MUTED     = "#8798a5"

BORDER         = "#bfd0dc"
BORDER_FOCUS   = "#7f9db2"
BG_WHITE       = "#ffffff"
BG_LIGHT       = "#eef3f6"
BG_HOVER       = "#e1ebf1"
BG_PRESSED     = "#d3e0e8"

# Log boje (tamna tema terminala)
LOG_ERROR     = "#ff6b6b"
LOG_WARNING   = "#ffa94d"
LOG_INFO      = "#74c0fc"
LOG_DEBUG     = "#8798a5"
LOG_DEFAULT   = "#d4d4d4"
LOG_TIMESTAMP = "#52697b"

# ── Bazni stil panela (override globalnog QLabel font-size: 9px) ───────────────
# Primjenjuje se na self (panel widget) da pokrije sve QLabel/QCheckBox/QGroupBox
# unutar panela, bez potrebe da se svaki widget stilizuje posebno.
PANEL_BASE_STYLE = """
    QLabel {
        font-size: 13px;
        color: #17324a;
    }
    QCheckBox {
        font-size: 13px;
        color: #17324a;
    }
    QGroupBox {
        font-size: 14px;
        font-weight: bold;
        color: #17324a;
    }
    QGroupBox::title {
        font-size: 13px;
        font-weight: bold;
        color: #17324a;
    }
"""

# ── Zajednički stylesheet-ovi ──────────────────────────────────────────────────
GROUPBOX_STYLE = f"""
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 6px;
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
