# gui/tabs/sifarnici/tariff_hierarchy.py

"""
Hijerarhijski prikaz carinskih tarifa iz SQLite baze.

Kad korisnik unese brojčani prefiks (2+ cifre) u polje Pretraga,
ova komponenta prikazuje cijelo poglavlje sa svim nasljednicima
u tabelarnom prikazu sa indentacijom i QtAwesome ikonicama.

Izvor podataka: database/deklarant_sistem.db → tarifa_2026
"""

import os
import sqlite3
from typing import List, Tuple, Any, Optional, Callable

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
from PySide6.QtGui import QFont

try:
    import qtawesome as qta
    QTAWESOME_AVAILABLE = True
except ImportError:
    QTAWESOME_AVAILABLE = False


# ============================================================
# SECTION: tariff-hierarchy-display
# PURPOSE: Renders hierarchical tariff view from SQLite DB
# DOC: docs/sections/tariff-hierarchy-display.md
# ============================================================

_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'database', 'deklarant_sistem.db')
)

_NIVO_EMOJI = {
    'glava':        '📂',
    'podglava':     '📁',
    'tarifni_broj': '📋',
    'podbroj':      '📄',
}

_NIVO_QTA = {
    'glava':        'fa5s.folder',
    'podglava':     'fa5s.folder-open',
    'tarifni_broj': 'fa5s.file-alt',
    'podbroj':      'fa5s.file',
}


def is_code_search(text: str) -> bool:
    """Provjeri da li je tekst brojčani prefiks (2+ cifre)."""
    import re
    return bool(re.match(r'^\d{2,}$', text)) if text else False


def populate_tariff_hierarchy(
    table: QTableWidget,
    prefix: str,
    clean_opis_fn: Optional[Callable[[Any], str]] = None,
) -> int:
    """Popuni tabelu hijerarhijskim prikazom tarifa za dati prefiks.

    Args:
        table: QTableWidget sa 2 kolone (tarifni_kod, opis)
        prefix: Brojčani prefiks (npr. '8516')
        clean_opis_fn: Optional funkcija za čišćenje opisa

    Returns:
        Broj prikazanih redova
    """
    prefix = prefix.replace(' ', '').replace('.', '')

    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row

    root_row = conn.execute(
        "SELECT kod, naziv, stopa_uvozna, nivo FROM tarifa_2026 WHERE kod = ?",
        (prefix,)
    ).fetchone()

    desc_rows = conn.execute(
        "SELECT kod, naziv, stopa_uvozna, nivo FROM tarifa_2026 "
        "WHERE kod LIKE ? AND kod != ? ORDER BY kod LIMIT 300",
        (prefix + '%', prefix)
    ).fetchall()
    conn.close()

    prefix_len = len(prefix)

    def _indent(kod: str) -> str:
        extra = len(kod) - prefix_len
        return '  ' * max(0, extra // 2)

    rows_to_show: List[Tuple] = []
    if root_row:
        rows_to_show.append((root_row['kod'], root_row['naziv'],
                             root_row['stopa_uvozna'], root_row['nivo'], True))
    for r in desc_rows:
        rows_to_show.append((r['kod'], r['naziv'],
                             r['stopa_uvozna'], r['nivo'], False))

    # Ako nema tačnog podudaranja, bolduj prvi red (najširi roditeljski)
    if not root_row and rows_to_show:
        kod, naziv, stopa, nivo, _ = rows_to_show[0]
        rows_to_show[0] = (kod, naziv, stopa, nivo, True)

    table.setRowCount(len(rows_to_show))
    for i, (kod, naziv, stopa, nivo, is_root) in enumerate(rows_to_show):
        emoji = _NIVO_EMOJI.get(nivo, '•')
        indent = '' if is_root else _indent(kod)
        stopa_str = ''
        if stopa:
            stopa_str = stopa if str(stopa).endswith('%') else str(stopa) + '%'

        # QtAwesome ikonica ili emoji fallback
        if QTAWESOME_AVAILABLE and nivo in _NIVO_QTA:
            try:
                qta_icon = qta.icon(_NIVO_QTA[nivo], scale_factor=0.9)
                item_kod = QTableWidgetItem()
                item_kod.setIcon(qta_icon)
                item_kod.setText(indent + ' ' + kod)
            except Exception:
                item_kod = QTableWidgetItem(indent + emoji + ' ' + kod)
        else:
            item_kod = QTableWidgetItem(indent + emoji + ' ' + kod)

        opis_val = clean_opis_fn(naziv) if clean_opis_fn else (naziv or '')
        item_naziv = QTableWidgetItem(opis_val or '')
        if stopa_str:
            item_naziv.setToolTip(f"Stopa uvozna: {stopa_str}")

        if is_root:
            # Uzmi font TABELE (ne itema) da naslijedimo tačnu veličinu (14pt)
            font = table.font()
            font.setBold(True)
            item_kod.setFont(font)
            item_naziv.setFont(font)

        table.setItem(i, 0, item_kod)
        table.setItem(i, 1, item_naziv)

    table.setColumnWidth(0, 200)

    # Selektuj i skroluj na prvi red (root / najspecifičniji pogodak)
    if rows_to_show:
        table.setCurrentCell(0, 0)
        table.scrollToTop()

    return len(rows_to_show)
