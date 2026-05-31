"""
Naimenovanja Intent Service — upisivanje i brisanje vrijednosti u kolone.

Business logika za:
- Parsiranje "upiši X u kolonu Y" poruka
- Mapiranje sinonima kolona na atribute (80+ sinonima)
- Upisivanje vrijednosti u Faktura ili Naimenovanja stavke
- Brisanje vrijednosti iz kolona
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────
# KOLONA MAP — 80+ sinonima → (atribut, tab)
# ─────────────────────────────────────────────────────────────────────

KOLONA_MAP: Dict[str, Tuple[str, str]] = {
    # ═══════════════════════════════════════════════════════
    # FAKTURA TAB (InvoiceLine)
    # ═══════════════════════════════════════════════════════
    'tarifni broj':       ('tarifni_broj',      'faktura'),
    'tarifni':            ('tarifni_broj',      'faktura'),
    'tarif':              ('tarifni_broj',      'faktura'),
    'hs kod':             ('tarifni_broj',      'faktura'),
    'hs':                 ('tarifni_broj',      'faktura'),
    'zemlja porijekla':   ('zemlja_porijekla',  'faktura'),
    'zemlja':             ('zemlja_porijekla',  'faktura'),
    'porijeklo':          ('zemlja_porijekla',  'faktura'),
    'porijekla':          ('zemlja_porijekla',  'faktura'),
    'origin':             ('zemlja_porijekla',  'faktura'),
    'povlastica':         ('povlastica',        'faktura'),
    'povlastice':         ('povlastica',        'faktura'),
    'pref':               ('povlastica',        'faktura'),
    'preference':         ('povlastica',        'faktura'),
    'eur1':               ('eur1_number',       'faktura'),
    'eur.1':              ('eur1_number',       'faktura'),
    'eur 1':              ('eur1_number',       'faktura'),
    'valuta':             ('valuta',            'faktura'),
    'currency':           ('valuta',            'faktura'),
    'naziv robe':         ('naziv_robe',        'faktura'),
    'naziv':              ('naziv_robe',        'faktura'),
    'opis':               ('naziv_robe',        'faktura'),
    'kolicina':           ('kolicina',          'faktura'),
    'količina':           ('kolicina',          'faktura'),
    'qty':                ('kolicina',          'faktura'),
    'jm':                 ('jm',               'faktura'),
    'jedinica mjere':     ('jm',               'faktura'),
    'jedinica':           ('jm',               'faktura'),

    # ═══════════════════════════════════════════════════════
    # NAIM TAB (NaimenovanjeDraft)
    # ═══════════════════════════════════════════════════════
    'oznake':             ('package_marks',      'naim'),
    'oznake i broj':      ('package_marks',      'naim'),
    'marks':              ('package_marks',      'naim'),
    'pakovanje':          ('package_code',       'naim'),
    'package':            ('package_code',       'naim'),
    'kod pakovanja':      ('package_code',       'naim'),
    'broj paketa':        ('package_qty',        'naim'),
    'opis robe':          ('goods_description',  'naim'),
    'goods description':  ('goods_description',  'naim'),
    'trgovački naziv':    ('goods_trade_name',   'naim'),
    'trade name':         ('goods_trade_name',   'naim'),
    'trg naziv':          ('goods_trade_name',   'naim'),
    'tarifni broj naim':  ('tariff_code',        'naim'),
    'tariff code':        ('tariff_code',        'naim'),
    'zemlja naim':        ('origin_country_code', 'naim'),
    'origin code':        ('origin_country_code', 'naim'),
    'povlastica naim':    ('preference_code',    'naim'),
    'preference code':    ('preference_code',    'naim'),
    'procedura':          ('procedure_code',     'naim'),
    'proceduru':          ('procedure_code',     'naim'),
    'procedure':          ('procedure_code',     'naim'),
    'postupak':           ('procedure_code',     'naim'),
    'postupku':           ('procedure_code',     'naim'),
    'rub37':              ('procedure_code',     'naim'),
    'rubrika 37':         ('procedure_code',     'naim'),
    'prethodni postupak': ('procedure_prev_code', 'naim'),
    'prev procedure':     ('procedure_prev_code', 'naim'),
    'rub40':              ('previous_document',  'naim'),
    'rubrika 40':         ('previous_document',  'naim'),
    'prethodni dokument': ('previous_document',  'naim'),
    'rub40 2':            ('previous_document2', 'naim'),
    'rub40 3':            ('previous_document3', 'naim'),
    'rub44':              ('attached_document4', 'naim'),
    'rub 44':             ('attached_document4', 'naim'),
    'rubrika 44':         ('attached_document4', 'naim'),
    'rub44.1':            ('attached_document1', 'naim'),
    'rub44.2':            ('attached_document2', 'naim'),
    'rub44.3':            ('attached_document3', 'naim'),
    'rub44.4':            ('attached_document4', 'naim'),
    'rub44.5':            ('attached_document5', 'naim'),
    'priložena isprava':  ('attached_document1', 'naim'),
    'prilozen':           ('attached_document1', 'naim'),
    'eur.1 broj':         ('attached_document4', 'naim'),
    'statisticka':        ('statistical_value',  'naim'),
    'statistička':        ('statistical_value',  'naim'),
    'rub46':              ('statistical_value',  'naim'),
    'rubrika 46':         ('statistical_value',  'naim'),
    'vrijednost':         ('item_value',         'naim'),
    'iznos':              ('item_value',         'naim'),
    'item value':         ('item_value',         'naim'),
    'valuta naim':        ('currency',           'naim'),
    'napomena':           ('notes',              'naim'),
    'notes':              ('notes',              'naim'),
}

# Nazivi kolona za display
_NAZIV_KOLONE: Dict[str, str] = {
    'tarifni_broj': 'Tarifni broj', 'zemlja_porijekla': 'Zemlja porijekla',
    'povlastica': 'Povlastica', 'eur1_number': 'EUR.1', 'valuta': 'Valuta',
    'naziv_robe': 'Naziv robe', 'kolicina': 'Količina', 'jm': 'JM',
    'tariff_code': 'Tarifni broj', 'origin_country_code': 'Zemlja porijekla',
    'preference_code': 'Povlastica', 'procedure_code': 'Rub.37 Procedura',
    'procedure_prev_code': 'Prethodni postupak', 'currency': 'Valuta',
    'package_code': 'Pakovanje (kod)', 'package_marks': 'Oznake i broj',
    'package_qty': 'Broj paketa', 'goods_description': 'Opis robe',
    'goods_trade_name': 'Trgovački naziv',
    'previous_document': 'Rub.40', 'previous_document2': 'Rub.40.2',
    'previous_document3': 'Rub.40.3', 'attached_document1': 'Rub.44.1',
    'attached_document2': 'Rub.44.2', 'attached_document3': 'Rub.44.3',
    'attached_document4': 'Rub.44.4', 'attached_document5': 'Rub.44.5',
    'statistical_value': 'Statistička vrijednost (Rub.46)',
    'item_value': 'Vrijednost (Rub.42)', 'notes': 'Napomena',
}

_FLOAT_ATTRS = {
    'kolicina', 'bruto_kg', 'neto_kg', 'iznos',
    'gross_mass_kg', 'net_mass_kg', 'item_value', 'statistical_value',
    'package_qty', 'supplementary_unit_qty',
}


@dataclass
class KolonaParseResult:
    """Rezultat parsiranja 'upiši X u kolonu Y'."""
    atribut: str
    vrijednost: str
    tab: str  # 'faktura' | 'naim'


class NaimenovanjaIntentService:
    """
    Service za upisivanje/brisanje vrijednosti u kolone.
    """

    def __init__(self, draft):
        self.draft = draft
        self.on_agent_message: Optional[Callable[[str], None]] = None
        self.on_activity: Optional[Callable[[str], None]] = None
        self.on_refresh_faktura: Optional[Callable[[], None]] = None
        self.on_refresh_naim: Optional[Callable[[], None]] = None

    def parse(self, message: str, brisanje: bool = False) -> Optional[KolonaParseResult]:
        """
        Parsira poruku u (atribut, vrijednost, tab).
        """
        msg_lower = message.lower().strip()

        # Detektuj eksplicitni tab hint
        tab_hint = None
        if any(k in msg_lower for k in ['naim', 'naimenovanj', 'rubrik']):
            tab_hint = 'naim'
        elif any(k in msg_lower for k in ['faktur', 'invoice']):
            tab_hint = 'faktura'

        if brisanje:
            m = re.search(
                r'(?:izbri|obri|ukloni|ocisti|prazni|brisi)[a-zšđčćž]*\s+(?:kolonu?|polje|rubrik[ua]?)?\s*(.+)',
                msg_lower
            )
            if m:
                kolona_raw = m.group(1).strip().rstrip('.')
                for hint in ['u naim', 'u faktur', 'naim', 'faktur']:
                    kolona_raw = kolona_raw.replace(hint, '').strip()
                atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
                if atribut:
                    return KolonaParseResult(atribut=atribut, vrijednost='', tab=tab)
            return None

        def _strip_tab_hints(s):
            for hint in [' u naim', ' u faktur', ' naim', ' faktur']:
                s = s.replace(hint, '')
            return s.strip().rstrip('.')

        # Format 1: "upiši/unesi/stavi VRIJEDNOST u [kolonu/polje/rubriku] KOLONA"
        m = re.search(
            r'(?:upi[sš][a-zšđčćž]*|unesi[a-z]*|stavi[a-z]*|set)\s+(.+?)\s+u\s+(?:kolonu?|polje|rubriku?)?\s*(.+)',
            msg_lower
        )
        if m:
            vrijednost = m.group(1).strip().upper()
            kolona_raw = _strip_tab_hints(m.group(2))
            atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
            if atribut:
                return KolonaParseResult(atribut=atribut, vrijednost=vrijednost, tab=tab)

        # Format 2: "postavi KOLONA na VRIJEDNOST"
        m = re.search(r'postavi\s+(.+?)\s+na\s+(\S+)', msg_lower)
        if m:
            kolona_raw = _strip_tab_hints(m.group(1))
            vrijednost = m.group(2).strip().upper()
            kolona_raw = re.sub(r'[uaie]$', 'a', kolona_raw)
            atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
            if atribut:
                return KolonaParseResult(atribut=atribut, vrijednost=vrijednost, tab=tab)

        # Format 3: "VRIJEDNOST u kolonu/rubriku KOLONA"
        m = re.search(r'(\S+)\s+u\s+(?:kolonu?|polje|rubriku?)\s+(.+)', msg_lower)
        if m:
            vrijednost = m.group(1).strip().upper()
            kolona_raw = _strip_tab_hints(m.group(2))
            atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
            if atribut:
                return KolonaParseResult(atribut=atribut, vrijednost=vrijednost, tab=tab)

        return None

    def execute(self, atribut: str, vrijednost: str, tab: str = 'faktura'):
        """Upiši vrijednost u zadani atribut svih stavki."""
        from PySide6.QtWidgets import QApplication

        naziv_kolone = _NAZIV_KOLONE.get(atribut, atribut)

        typed_value: Any = vrijednost
        if atribut in _FLOAT_ATTRS:
            try:
                typed_value = float(vrijednost.replace(',', '.')) if vrijednost else 0.0
            except (ValueError, AttributeError):
                self._msg(f"⚠️ '{vrijednost}' nije broj. Upotrijebite numeričku vrijednost.")
                return

        if tab == 'faktura':
            if not self.draft or not self.draft.invoice_lines:
                self._msg("⚠️ Nema učitanih stavki u Faktura tabu.")
                return
            upisano = sum(
                1 for line in self.draft.invoice_lines
                if hasattr(line, atribut) and not setattr(line, atribut, typed_value)
            )
            if self.on_refresh_faktura:
                QApplication.processEvents()
                self.on_refresh_faktura()
        else:  # naim
            if not self.draft or not self.draft.items:
                self._msg("⚠️ Nema kreiranih naimenovanja.")
                return
            upisano = sum(
                1 for item in self.draft.items
                if hasattr(item, atribut) and not setattr(item, atribut, typed_value)
            )
            if self.on_refresh_naim:
                QApplication.processEvents()
                self.on_refresh_naim()

        tab_naziv = "Faktura" if tab == 'faktura' else "Naimenovanja"
        akcija = "Obrisano iz" if vrijednost == '' else f"Upisano <b>{vrijednost}</b> u"
        self._msg(
            f"✅ {akcija} kolone <b>{naziv_kolone}</b> ({tab_naziv} tab) "
            f"— {upisano} stavki."
        )

    def _resolve_kolona(self, kolona_raw: str, tab_hint=None) -> Tuple[str, str]:
        """Pretvori slobodan naziv kolone u (atribut, tab)."""
        k = kolona_raw.lower().strip()
        if k in KOLONA_MAP:
            atrib, tab = KOLONA_MAP[k]
            return atrib, tab_hint or tab
        for kw, (atrib, tab) in KOLONA_MAP.items():
            if kw in k or k in kw:
                return atrib, tab_hint or tab
        return '', tab_hint or 'faktura'

    def _msg(self, text: str):
        if self.on_agent_message:
            self.on_agent_message(text)

    def _activity(self, text: str):
        if self.on_activity:
            self.on_activity(text)
