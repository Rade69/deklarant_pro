# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec fajl za Deklarant Pro
#
# Pokretanje:
#   pyinstaller deklarant_pro.spec
#
# Napomena: Graditi NA Windows mašini (ili wine okruženju).
# Python 3.11+, PySide6, psycopg2-binary moraju biti instalirani.

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)

# ─── Hidden imports ───────────────────────────────────────────────────────────
# Moduli koje PyInstaller ne detektuje automatski (dinamički importi, plugins)

hidden_imports = [
    # Database
    'psycopg2',
    'psycopg2.extensions',
    'psycopg2.extras',
    'psycopg2._psycopg',

    # PDF
    'pdfplumber',
    'pdfminer',
    'pdfminer.high_level',
    'pdfminer.layout',
    'pdfminer.pdfinterp',
    'pdfminer.converter',

    # Excel
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',

    # Config / env
    'dotenv',
    'pydantic',
    'pydantic_settings',

    # PySide6 - Qt modules koji se koriste
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtPrintSupport',
    'PySide6.QtSvg',
    'PySide6.QtXml',

    # Utilities
    'colorama',
    'unicodedata',
    'xml.etree.ElementTree',
    'xml.etree.cElementTree',
    'sqlite3',
    'difflib',
    'rapidfuzz',

    # Svi importeri (dinamički se učitavaju)
    'importers.vendors.blagic.blagic_attos_importer',
    'importers.vendors.blagic.blagic_loren_importer',
    'importers.vendors.blagic.blagic_loren_pdf_parser',
    'importers.vendors.blagic.blagic_importer',
    'importers.vendors.imamoglu.imamoglu_pdf_parser',
    'importers.vendors.leburic.leburic_pekabesko_importer',
    'importers.smart_pdf_importer',
    'importers.generic_pdf_importer',
    'importers.packing_list_parser',
    'importers.excel_importer',
    'importers.plugin_loader',

    # QtAwesome (ikone)
    'qtawesome',
    'qtawesome.iconic_font',
]

# ─── Data fajlovi ─────────────────────────────────────────────────────────────
# (source, destination_in_bundle)

datas = [
    # Qt UI fajlovi
    (str(ROOT / 'ui'),                          'ui'),

    # QSS stilovi
    (str(ROOT / 'styles'),                      'styles'),

    # Ikone i assets
    (str(ROOT / 'assets'),                      'assets'),

    # SQLite baze koje se distribuiraju uz aplikaciju
    (str(ROOT / 'database' / 'zvanicna_tarifa.db'),    'database'),
    (str(ROOT / 'database' / 'inspection_rules.db'),   'database'),

    # Zakonska regulativa (PDF dokumenti za knowledge base agenta)
    (str(ROOT / 'data' / 'knowledge_base'),     'data/knowledge_base'),

    # Predložak .env fajla (korisnik kopira i popunjava)
    (str(ROOT / '.env.example'),                '.'),
]

# Dodaj qtawesome fontove
try:
    datas += collect_data_files('qtawesome')
except Exception:
    pass

# Dodaj PySide6 Qt plugins
try:
    datas += collect_data_files('PySide6', include_py_files=False)
except Exception:
    pass

# ─── Excludes ────────────────────────────────────────────────────────────────
excludes = [
    'tkinter',
    'matplotlib',
    'scipy',
    'numpy',
    'pandas',
    'IPython',
    'jupyter',
    'pytest',
    'unittest',
    'test',
    'tests',
    'venv',
    '.venv',
    '.gitnexus',
]

# ─── Analysis ────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / 'run.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[str(ROOT / 'build_hooks')],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# ─── PYZ ─────────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ─── EXE ─────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DeklarantPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,             # Nema konzole (GUI aplikacija)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'icons' / 'deklarant_icon.ico'),
    version='build_hooks/version_info.txt',
)

# ─── COLLECT ─────────────────────────────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DeklarantPro',
)
