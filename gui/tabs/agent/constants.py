"""
Konstante za Agent Tab — Botanička Sage Green Paleta.
"""

# ─── BOTANIČKA SAGE GREEN PALETA ──────────────────────────────────────────────
COLOR_SAGE_DARKEST = "#2d4a30"   # Najdublji zeleni (naslovi, header)
COLOR_SAGE_DARK    = "#3d6040"   # Tamni sage (dugmad, ikone)
COLOR_SAGE         = "#5a8060"   # Glavni sage (primarna boja)
COLOR_SAGE_MID     = "#7aa080"   # Srednji sage
COLOR_SAGE_LIGHT   = "#a0c4a0"   # Svjetliji sage (hover)
COLOR_SAGE_PALE    = "#c8dcc8"   # Borderi, rubovi
COLOR_SAGE_BG      = "#f0f7f0"   # Glavna pozadina taba
COLOR_SAGE_PANEL   = "#e8f2e8"   # Panel pozadina
COLOR_SAGE_UPLOAD  = "#eef6ec"   # Upload area pozadina
COLOR_SAGE_CARD    = "#f7faf7"   # Kartica pozadina

# ─── AKCENT BOJE ─────────────────────────────────────────────────────────────
COLOR_PRIMARY   = "#5a8060"   # Sage Green — primarna akcija (Odaberi fajlove)
COLOR_SECONDARY = "#7264a0"   # Muted Purple — AI/sekundarna (Pokreni analizu)
COLOR_SUCCESS   = "#4a9060"   # Uspjeh
COLOR_WARNING   = "#b8963a"   # Upozorenje
COLOR_DANGER    = "#b05050"   # Greška
COLOR_INFO      = "#4a7890"   # Info

# ─── TEKST ────────────────────────────────────────────────────────────────────
COLOR_TEXT       = "#1e3820"   # Primarni tekst
COLOR_TEXT_LIGHT = "#4a6a4a"   # Sekundarni tekst
COLOR_TEXT_MUTED = "#8a9a8a"   # Blijedi tekst

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

# ─── PARSERI ──────────────────────────────────────────────────────────────────
PARSER_AUTO         = "Auto-detect"
PARSER_MASTER_FRIGO = "Master Frigo"
PARSER_BLAGIC       = "Blagić"
PARSER_SUMAPROM     = "ŠUMAPROM"
PARSER_IMAMOGLU     = "IMAMOGLU"
PARSER_GENERIC      = "Generic"

# ─── PODRŽANI FORMATI ─────────────────────────────────────────────────────────
SUPPORTED_FORMATS = {
    '.pdf':  ('PDF Dokument', ICON_FILE_PDF,   '#b05050'),
    '.xlsx': ('Excel Tabela', ICON_FILE_EXCEL, '#3d6040'),
    '.xls':  ('Excel Tabela', ICON_FILE_EXCEL, '#3d6040'),
    '.xml':  ('XML Dokument', ICON_FILE_XML,   '#4a7890'),
}

# ─── CHAT TAB INDEKSI ─────────────────────────────────────────────────────────
TAB_AGENT      = 0
TAB_AKTIVNOSTI = 1
TAB_PITANJA    = 2
