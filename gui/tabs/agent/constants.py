"""
Konstante za Agent Tab — Botanička Sage Green Paleta.
"""

# ─── BOTANIČKA SAGE GREEN PALETA ──────────────────────────────────────────────
COLOR_SAGE_DARKEST = "#17324a"
COLOR_SAGE_DARK    = "#244866"
COLOR_SAGE         = "#3477a5"
COLOR_SAGE_MID     = "#7897ad"
COLOR_SAGE_LIGHT   = "#b8cbd8"
COLOR_SAGE_PALE    = "#c7d6df"
COLOR_SAGE_BG      = "#f3f6f8"
COLOR_SAGE_PANEL   = "#eef3f6"
COLOR_SAGE_UPLOAD  = "#f8fafb"
COLOR_SAGE_CARD    = "#ffffff"

# ─── AKCENT BOJE ─────────────────────────────────────────────────────────────
COLOR_PRIMARY   = "#3477a5"
COLOR_SECONDARY = "#6b4aa2"
COLOR_SUCCESS   = "#2f7d5b"
COLOR_WARNING   = "#b1842d"
COLOR_DANGER    = "#ad3e3e"
COLOR_INFO      = "#4f6779"

# ─── TEKST ────────────────────────────────────────────────────────────────────
COLOR_TEXT       = "#17324a"
COLOR_TEXT_LIGHT = "#52697b"
COLOR_TEXT_MUTED = "#7f919f"

# ─── BACKWARDS COMPATIBILITY ──────────────────────────────────────────────────
COLOR_BACKGROUND = COLOR_SAGE_BG
COLOR_BORDER     = COLOR_SAGE_PALE

# ─── IKONE (Font Awesome 5 Solid) ─────────────────────────────────────────────
ICON_ROBOT      = "fa5s.robot"
ICON_UPLOAD     = "fa5s.cloud-upload-alt"
ICON_FILE_PDF   = "fa5s.file-pdf"
ICON_FILE_EXCEL = "fa5s.file-excel"
ICON_FILE_XML   = "fa5s.file-code"
ICON_PLAY       = "fa5s.play-circle"
ICON_STOP       = "fa5s.stop-circle"
ICON_TRASH      = "fa5s.trash-alt"
ICON_COG        = "fa5s.cog"
ICON_CHAT       = "fa5s.comments"
ICON_SEND       = "fa5s.paper-plane"
ICON_CHECK      = "fa5s.check-circle"
ICON_WARNING    = "fa5s.exclamation-triangle"
ICON_QUESTION   = "fa5s.question-circle"
ICON_SEARCH     = "fa5s.search"
ICON_IMPORT     = "fa5s.file-import"
ICON_MAGIC      = "fa5s.magic"
ICON_BELL       = "fa5s.bell"

# ─── STATUS ───────────────────────────────────────────────────────────────────
STATUS_READY      = "Spreman"
STATUS_PROCESSING = "Procesiranje"
STATUS_COMPLETED  = "Završeno"
STATUS_ERROR      = "Greška"
STATUS_PAUSED     = "Pauzirano"

# ─── PODRŽANI FORMATI ─────────────────────────────────────────────────────────
SUPPORTED_FORMATS = {
    '.pdf':  ('PDF Dokument', ICON_FILE_PDF,   COLOR_DANGER),
    '.xlsx': ('Excel Tabela', ICON_FILE_EXCEL, COLOR_SUCCESS),
    '.xls':  ('Excel Tabela', ICON_FILE_EXCEL, COLOR_SUCCESS),
    '.xml':  ('XML Dokument', ICON_FILE_XML,   COLOR_INFO),
}

# ─── CHAT TAB INDEKSI ─────────────────────────────────────────────────────────
TAB_AGENT      = 0
TAB_AKTIVNOSTI = 1
TAB_PITANJA    = 2
