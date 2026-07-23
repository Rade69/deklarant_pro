# services/tariff_tree_service.py

"""
TariffTreeService — hijerarhijski prikaz carinske tarife (drill-down).

Pruža mogućnost:
  - get_tree(prefix) — vraća sve nivoe ispod datog prefiksa
  - get_node(kod)    — vraća detalje jednog čvora
  - get_children(prefix) — vraća direktne potomke prefiksa

Nivoi hijerarhije:
  2 cifre → Poglavlje (npr. "85")
  4 cifre → Glava (npr. "8516")
  6 cifara → Podglava (npr. "851660")
  8 cifara → Tarifni broj (npr. "85166090")
  10 cifara → Podbroj (npr. "8516609000")
"""

import sqlite3
import sys
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("deklarant_pro.tariff_tree")


def _resolve_db_path() -> str:
    """
    Pronađi deklarant_sistem.db: probaj više lokacija.

    Prvobitni obrazac (samo jedan '..') je pogrešan i za dev mod — ovaj fajl
    je u services/tariff/, pa treba DVA nivoa gore do korijena projekta, ne
    jedan. Dodat i frozen-build fallback (vidi services/tariff/
    tarifa_service.py::_resolve_db_path() i gui/tabs/sifarnici/
    tariff_hierarchy.py::_resolve_db_path() za isti obrazac/objašnjenje).
    """
    candidates = [
        os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'deklarant_sistem.db')),
    ]
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'database', 'deklarant_sistem.db'))
    candidates.append(os.path.join('database', 'deklarant_sistem.db'))

    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


DB_PATH = _resolve_db_path()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row) -> Dict:
    return {
        'kod': row['kod'],
        'poglavlje': row['poglavlje'],
        'naziv': row['naziv'],
        'dopunska_jm': row['dopunska_jm'],
        'stopa_uvozna': row['stopa_uvozna'],
        'stopa_eu': row['stopa_eu'],
        'stopa_cefta': row['stopa_cefta'],
        'nivo': row['nivo'],
    }


def _nivo_label(nivo: str) -> str:
    """Oznaka nivoa za prikaz."""
    labels = {
        'glava': '📂',
        'podglava': '📁',
        'tarifni_broj': '📋',
        'podbroj': '📄',
    }
    return labels.get(nivo, '📌')


def _nivo_name(nivo: str) -> str:
    """Ime nivoa na srpskom."""
    names = {
        'glava': 'Glava',
        'podglava': 'Podglava',
        'tarifni_broj': 'Tarifni broj',
        'podbroj': 'Podbroj',
    }
    return names.get(nivo, nivo)


def get_node(kod: str) -> Optional[Dict]:
    """
    Vrati detalje jednog čvora po tačnom kodu.

    Returns:
        Dict sa svim poljima ili None.
    """
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM tarifa_2026 WHERE kod = ?", (kod,)
        ).fetchone()
        conn.close()
        return _row_to_dict(row) if row else None
    except Exception as e:
        logger.error(f"Greška pri čitanju čvora {kod}: {e}")
        return None


def get_children(prefix: str, limit: int = 100) -> List[Dict]:
    """
    Vrati DIREKTNE potomke datog prefiksa.

    Npr. za prefix "8516" vraća sve 6-cifrene podglave ispod njega.
    Za prefix "851660" vraća sve 8-cifrene tarifne brojeve.

    Returns:
        Lista dict sortiranih po kodu.
    """
    prefix = prefix.replace(' ', '').replace('.', '')
    if not prefix.isdigit():
        return []

    prefix_len = len(prefix)

    # Odredi dužinu direktnih potomaka:
    # 2 cifre → tražimo 4-cifrene glave
    # 4 cifre → tražimo 6-cifrene podglave
    # 6 cifara → tražimo 8-cifrene tarifne brojeve
    # 8 cifara → tražimo 10-cifrene podbrojeve
    child_lengths = {
        2: 4,   # poglavlje → glava
        4: 6,   # glava → podglava
        6: 8,   # podglava → tarifni broj
        8: 10,  # tarifni broj → podbroj
    }

    target_len = child_lengths.get(prefix_len)
    if not target_len:
        return []

    try:
        conn = _get_conn()
        rows = conn.execute("""
            SELECT kod, poglavlje, naziv, dopunska_jm,
                   stopa_uvozna, stopa_eu, stopa_cefta, nivo
            FROM tarifa_2026
            WHERE kod LIKE ? AND LENGTH(kod) = ?
            ORDER BY kod
            LIMIT ?
        """, (prefix + '%', target_len, limit)).fetchall()
        conn.close()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Greška pri čitanju potomaka za {prefix}: {e}")
        return []


def get_tree(prefix: str, depth: int = 2) -> Dict:
    """
    Vrati hijerarhijsko stablo počevši od prefiksa.

    Args:
        prefix: Početni kod (npr. "85", "8516", "851660")
        depth: Koliko nivoa duboko ići (default 2)

    Returns:
        Dict: {
            'node': {...},           # Trenutni čvor
            'children': [            # Direktni potomci
                {
                    'node': {...},
                    'children': [...],
                    'has_more': bool,
                },
                ...
            ],
            'has_more': bool,
        }
    """
    prefix = prefix.replace(' ', '').replace('.', '')

    # Pronađi trenutni čvor
    node = None
    if prefix:
        node = get_node(prefix)
        if not node:
            # Pokušaj prefix match — uzmi najduži koji odgovara
            try:
                conn = _get_conn()
                row = conn.execute("""
                    SELECT * FROM tarifa_2026
                    WHERE kod LIKE ?
                    ORDER BY LENGTH(kod) ASC
                    LIMIT 1
                """, (prefix + '%',)).fetchone()
                conn.close()
                node = _row_to_dict(row) if row else None
            except Exception:
                pass

    # Pronađi djecu
    children_data = get_children(prefix, limit=50)
    has_more = len(children_data) >= 50

    result = {
        'node': _row_to_dict(node) if node else None,
        'children': [],
        'has_more': has_more,
    }

    # Rekurzivno uđi dublje ako treba
    if depth > 1 and children_data:
        for child in children_data:
            child_result = {
                'node': child,
                'children': [],
                'has_more': False,
            }
            # Za dublje nivoe, samo prikaži da ima potomaka
            grandchildren = get_children(child['kod'], limit=2)
            if grandchildren:
                child_result['children'] = [
                    {'node': gc, 'children': [], 'has_more': False}
                    for gc in grandchildren
                ]
                if len(get_children(child['kod'], limit=3)) > 2:
                    child_result['has_more'] = True
            result['children'].append(child_result)

    return result


def format_tree_html(tree: Dict, indent: int = 0) -> str:
    """
    Formatiraj hijerarhijsko stablo u HTML za prikaz.
    """
    if not tree or not tree.get('node'):
        return "<i>Nije pronađeno.</i>"

    lines = []
    node = tree['node']
    emoji = _nivo_label(node['nivo'])
    level_name = _nivo_name(node['nivo'])

    stopa = node['stopa_uvozna'] or '—'
    if stopa != '—' and not str(stopa).endswith('%'):
        stopa = str(stopa) + '%'

    lines.append(
        f"<b>{emoji} {node['kod']}</b> <small>({level_name})</small><br>"
        f"&nbsp;&nbsp;{node['naziv']}<br>"
        f"&nbsp;&nbsp;Stopa: <b>{stopa}</b>"
        + (f" | EU: {node['stopa_eu'] or '—'}" if node['stopa_eu'] else "")
    )

    if tree.get('children'):
        for child_tree in tree['children']:
            child_node = child_tree.get('node')
            if not child_node:
                continue
            c_emoji = _nivo_label(child_node['nivo'])
            c_stopa = child_node['stopa_uvozna'] or '—'
            if c_stopa != '—' and not str(c_stopa).endswith('%'):
                c_stopa = str(c_stopa) + '%'

            indent_html = "&nbsp;&nbsp;&nbsp;&nbsp;"
            lines.append(
                f"{indent_html}{c_emoji} <b>{child_node['kod']}</b> — "
                f"{child_node['naziv']}<br>"
                f"{indent_html}&nbsp;&nbsp;Stopa: {c_stopa}"
            )

            # Prikaži unuke ako postoje
            if child_tree.get('children'):
                for gc_tree in child_tree['children']:
                    gc_node = gc_tree.get('node')
                    if not gc_node:
                        continue
                    gc_indent = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                    gc_stopa = gc_node['stopa_uvozna'] or '—'
                    if gc_stopa != '—' and not str(gc_stopa).endswith('%'):
                        gc_stopa = str(gc_stopa) + '%'
                    lines.append(
                        f"{gc_indent}📄 <b>{gc_node['kod']}</b> — "
                        f"{gc_node['naziv']}<br>"
                        f"{gc_indent}&nbsp;&nbsp;Stopa: {gc_stopa}"
                    )
                if child_tree.get('has_more'):
                    lines.append(f"{indent_html}&nbsp;&nbsp;<i>... i još</i>")

    if tree.get('has_more'):
        lines.append("<br><i>... više stavki. Unesi duži kod za precizniji prikaz.</i>")

    return "<br>".join(lines)


def get_full_path(kod: str) -> List[Dict]:
    """
    Vrati puni put od korijena do datog koda.

    Npr. za "8516609000":
      85 → 8516 → 851660 → 85166090 → 8516609000
    """
    path = []
    current = kod
    while current:
        node = get_node(current)
        if node:
            path.insert(0, node)
        if len(current) <= 2:
            break
        # Idi na roditelja (2 cifre manje, ili na početak)
        if len(current) > 4:
            current = current[:-2]
        else:
            current = current[:2]
    return path


# Klasa-omotac za kompatibilnost sa starim importima
class TariffTreeService:
    get_node        = staticmethod(get_node)
    get_children    = staticmethod(get_children)
    get_tree        = staticmethod(get_tree)
    format_tree_html = staticmethod(format_tree_html)
    get_full_path   = staticmethod(get_full_path)
