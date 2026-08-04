"""
Chat Intent Handler

Logika za obradu chat poruka u agentu: Tool Use routing (primarni),
keyword detekcija (fallback), i LLM chat.

📄 docs/decisions/001-tool-use-refactoring.md
   docs/decisions/002-tool-dispatcher-integration.md
   docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md (Faza A — sigurnosna kapija)

Premješteno iz agent_controller.py radi smanjenja veličine controllera.
"""

import json
import re
import time
import uuid
import logging
from html import escape

from services.agent.chat.tool_result import ToolResult, render_tool_result_html
from services.agent.chat.tool_policy import effect_for
from services.agent.chat.audit_log import AuditEvent, record as record_audit
from services.agent.chat.naimenovanja_intent_service import _NAZIV_KOLONE
from core.decision.decision_model import DecisionField
from services.decision.integration import sync_decision_state_after_manual_edit

logger = logging.getLogger("deklarant_pro.agent.chat_intent")

# Kolone koje su pokrivene DeclarationDecisionService-om (Faza 0-6, 2026-07-18) —
# rucna izmjena preko ovih atributa mora sinhronizovati decision_state, ne samo
# upisati sirovu vrijednost. Vidi §2/§5.1/§5.6 plana za Fazu A.
_DECISION_FIELD_BY_ATRIBUT: dict[str, DecisionField] = {
    "tarifni_broj": DecisionField.TARIFF,
    "zemlja_porijekla": DecisionField.ORIGIN_COUNTRY,
    "povlastica": DecisionField.PREFERENCE,
}

# Mapa sinonima kolona → (atribut, tab)
KOLONA_MAP = {
    # ═══════════════════════════════════════
    # FAKTURA TAB (InvoiceLine)
    # ═══════════════════════════════════════
    'tarifni broj':       ('tarifni_broj',        'faktura'),
    'tarifni':            ('tarifni_broj',        'faktura'),
    'tarif':              ('tarifni_broj',        'faktura'),
    'hs kod':             ('tarifni_broj',        'faktura'),
    'hs':                 ('tarifni_broj',        'faktura'),
    'zemlja porijekla':   ('zemlja_porijekla',    'faktura'),
    'zemlja':             ('zemlja_porijekla',    'faktura'),
    'porijeklo':          ('zemlja_porijekla',    'faktura'),
    'porijekla':          ('zemlja_porijekla',    'faktura'),
    'origin':             ('zemlja_porijekla',    'faktura'),
    'povlastica':         ('povlastica',          'faktura'),
    'povlastice':         ('povlastica',          'faktura'),
    'pref':               ('povlastica',          'faktura'),
    'preference':         ('povlastica',          'faktura'),
    'eur1':               ('eur1_number',         'faktura'),
    'eur.1':              ('eur1_number',         'faktura'),
    'eur 1':              ('eur1_number',         'faktura'),
    'valuta':             ('valuta',              'faktura'),
    'currency':           ('valuta',              'faktura'),
    'naziv robe':         ('naziv_robe',          'faktura'),
    'naziv':              ('naziv_robe',          'faktura'),
    'opis':               ('naziv_robe',          'faktura'),
    'kolicina':           ('kolicina',            'faktura'),
    'količina':           ('kolicina',            'faktura'),
    'qty':                ('kolicina',            'faktura'),
    'jm':                 ('jm',                  'faktura'),
    'jedinica mjere':     ('jm',                  'faktura'),
    'jedinica':           ('jm',                  'faktura'),
    # ═══════════════════════════════════════
    # NAIM TAB (NaimenovanjeDraft)
    # ═══════════════════════════════════════
    'oznake':             ('package_marks',       'naim'),
    'oznake i broj':      ('package_marks',       'naim'),
    'marks':              ('package_marks',       'naim'),
    'pakovanje':          ('package_code',        'naim'),
    'package':            ('package_code',        'naim'),
    'kod pakovanja':      ('package_code',        'naim'),
    'broj paketa':        ('package_qty',         'naim'),
    'opis robe':          ('goods_description',   'naim'),
    'goods description':  ('goods_description',   'naim'),
    'trgovački naziv':    ('goods_trade_name',    'naim'),
    'trade name':         ('goods_trade_name',    'naim'),
    'trg naziv':          ('goods_trade_name',    'naim'),
    'tarifni broj naim':  ('tariff_code',         'naim'),
    'tariff code':        ('tariff_code',         'naim'),
    'zemlja naim':        ('origin_country_code', 'naim'),
    'origin code':        ('origin_country_code', 'naim'),
    'povlastica naim':    ('preference_code',     'naim'),
    'preference code':    ('preference_code',     'naim'),
    'procedura':          ('procedure_code',      'naim'),
    'proceduru':          ('procedure_code',      'naim'),
    'procedure':          ('procedure_code',      'naim'),
    'postupak':           ('procedure_code',      'naim'),
    'postupku':           ('procedure_code',      'naim'),
    'rub37':              ('procedure_code',      'naim'),
    'rubrika 37':         ('procedure_code',      'naim'),
    'prethodni postupak': ('procedure_prev_code', 'naim'),
    'prev procedure':     ('procedure_prev_code', 'naim'),
    'rub40':              ('previous_document',   'naim'),
    'rubrika 40':         ('previous_document',   'naim'),
    'prethodni dokument': ('previous_document',   'naim'),
    'rub40 2':            ('previous_document2',  'naim'),
    'rub40 3':            ('previous_document3',  'naim'),
    'rub44':              ('attached_document4',  'naim'),
    'rub 44':             ('attached_document4',  'naim'),
    'rubrika 44':         ('attached_document4',  'naim'),
    'rub44.1':            ('attached_document1',  'naim'),
    'rub44.2':            ('attached_document2',  'naim'),
    'rub44.3':            ('attached_document3',  'naim'),
    'rub44.4':            ('attached_document4',  'naim'),
    'rub44.5':            ('attached_document5',  'naim'),
    'priložena isprava':  ('attached_document1',  'naim'),
    'prilozen':           ('attached_document1',  'naim'),
    'eur.1 broj':         ('attached_document4',  'naim'),
    'statisticka':        ('statistical_value',   'naim'),
    'statistička':        ('statistical_value',   'naim'),
    'rub46':              ('statistical_value',   'naim'),
    'rubrika 46':         ('statistical_value',   'naim'),
    'vrijednost':         ('item_value',          'naim'),
    'iznos':              ('item_value',          'naim'),
    'item value':         ('item_value',          'naim'),
    'valuta naim':        ('currency',            'naim'),
    'napomena':           ('notes',               'naim'),
    'notes':              ('notes',               'naim'),
}

_REDNI = {
    'prvi': 1, 'prvog': 1, 'prvo': 1, 'prva': 1,
    'drugi': 2, 'drugog': 2, 'drugo': 2, 'druga': 2,
    'treći': 3, 'trećeg': 3, 'treće': 3, 'treca': 3, 'treceg': 3,
    'četvrti': 4, 'cetvrti': 4, 'četvrtog': 4,
    'peti': 5, 'peto': 5, 'petog': 5,
    'šesti': 6, 'sesti': 6, 'šesto': 6, 'sesto': 6, 'šestog': 6, 'sestog': 6,
    'sedmi': 7, 'sedmo': 7, 'sedmog': 7,
    'osmi': 8, 'osmo': 8, 'osmog': 8,
    'deveti': 9, 'deveto': 9, 'devetog': 9,
    'deseti': 10, 'deseto': 10, 'desetog': 10,
    'posljednji': -1, 'zadnji': -1,
}


class ChatIntentHandler:
    """Upravljanje chat porukom — Tool Use routing (primarni) + keyword fallback."""

    def __init__(self, controller):
        self._ctrl = controller
        self._dispatcher_workers = []  # ToolDispatcherWorker instances

    # ═══════════════════════════════════════════════════════════════
    # region — Javni API (sve metode su [THUNK] → slobodne funkcije)
    # ═══════════════════════════════════════════════════════════════

    def handle_message(self, message: str) -> None:
        """[THUNK] → _handle_message"""
        _handle_message(self._ctrl, message)

    # ═══════════════════════════════════════════════════════════════
    # region — Tool Execution
    # ═══════════════════════════════════════════════════════════════

    def execute_tool(self, name: str, args: dict) -> None:
        """[THUNK] → _execute_tool — mapira tool call na servis."""
        _execute_tool(self._ctrl, name, args)

    # ═══════════════════════════════════════════════════════════════
    # region — Tarifno pretraživanje i porijeklo
    # ═══════════════════════════════════════════════════════════════

    def alternativni_tarifni_za_stavku(self, item_query: str = "",
                                        item_ordinal: int = None,
                                        is_alt: bool = False) -> None:
        """[THUNK] → _alternativni_tarifni_za_stavku"""
        _alternativni_tarifni_za_stavku(self._ctrl, item_query, item_ordinal, is_alt)

    # ═══════════════════════════════════════════════════════════════
    # region — Intent klasifikacija
    # ═══════════════════════════════════════════════════════════════

    def klasificiraj_i_usmjeri(self, message: str) -> None:
        """[THUNK] → _klasificiraj_i_usmjeri"""
        _klasificiraj_i_usmjeri(self._ctrl, message)

    # ═══════════════════════════════════════════════════════════════
    # region — Naimenovanja
    # ═══════════════════════════════════════════════════════════════

    def provjeri_naimenovanja(self) -> None:
        """[THUNK] → _provjeri_naimenovanja"""
        _provjeri_naimenovanja(self._ctrl)

    def pregledaj_naimenovanja(self, indeksi=None) -> None:
        """[THUNK] → _pregledaj_naimenovanja"""

    # ═══════════════════════════════════════════════════════════════
    # region — Tarifno pretraživanje (nastavak)
    # ═══════════════════════════════════════════════════════════════

    def pretrazi_tarifu(self, upit: str) -> None:
        """[THUNK] → _pretrazi_tarifu"""
        _pretrazi_tarifu(self._ctrl, upit)

    def pretrazi_porijeklo(self, upit: str) -> None:
        """[THUNK] → _pretrazi_porijeklo"""

    def pretrazi_tarifu_po_kodu(self, kod: str) -> None:
        """[THUNK] → _pretrazi_tarifu_po_kodu"""

    def pretrazi_tarifu_poglavlje(self, poglavlje: str) -> None:
        """[THUNK] → _pretrazi_tarifu_poglavlje"""

    def pretrazi_tarifu_hijerarhijski(self, kod: str) -> None:
        """[THUNK] → _pretrazi_tarifu_hijerarhijski"""

    # ═══════════════════════════════════════════════════════════════
    # region — Compliance
    # ═══════════════════════════════════════════════════════════════

    def compliance_check(self) -> None:
        """[THUNK] → _compliance_check"""
        _compliance_check(self._ctrl)

    # ═══════════════════════════════════════════════════════════════
    # region — Spajanje naimenovanja i upis u kolonu
    # ═══════════════════════════════════════════════════════════════

    def izvrsi_spajanje_naimenovanja(self, proposals, chat) -> None:
        """[THUNK] → _izvrsi_spajanje_naimenovanja"""
        _izvrsi_spajanje_naimenovanja(self._ctrl, proposals, chat)

    def propose_kolona_upis(self, atribut: str, vrijednost: str, tab: str = 'faktura') -> None:
        """[THUNK] → _propose_kolona_upis"""

    # ═══════════════════════════════════════════════════════════════
    # region — Proposal Card
    # ═══════════════════════════════════════════════════════════════

    def show_proposal_card(self, proposal: dict) -> None:
        """[THUNK] → _show_proposal_card"""
        _show_proposal_card(self._ctrl, proposal)

    def on_proposal_confirmed(self, values: dict) -> None:
        """[THUNK] → _on_proposal_confirmed"""

    def on_proposal_rejected(self) -> None:
        """[THUNK] → _on_proposal_rejected"""
        _on_proposal_rejected(self._ctrl)


# ═══════════════════════════════════════════════════════════════
# region — Implementacija: pomoćne funkcije i intent detekcija
# ═══════════════════════════════════════════════════════════════


_ORIGIN_KEYWORD_RE = r'porijek\w*|porijk\w*|porekl\w*|prijek\w*|zemlj\w*\s+por'


def _has_origin_keyword(message: str) -> bool:
    return bool(re.search(_ORIGIN_KEYWORD_RE, message or "", flags=re.IGNORECASE))


def _clean_origin_query(query: str) -> str:
    query = (query or "").strip().rstrip("?! .")
    query = re.sub(
        r'^(?:potra[žzćc]i|pretra[žz]i|prona[đd]i|na[đd]i|tra[žz]i|trazi)\s+(?:mi\s+)?(?:za\s+)?',
        '',
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        rf'\b(?:koj\w*|kakv\w*)\s+je\s+(?:{_ORIGIN_KEYWORD_RE}).*$',
        '',
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r'\b(ovog|ovaj|tog|taj|zaj|proizvoda|proizvod)\b', '', query, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', query).strip()


def _is_weak_origin_query(query: str) -> bool:
    msg = (query or "").lower().strip()
    if not msg:
        return True
    if any(part in msg for part in ("bazi znanja", "ranijim deklaracijama", "prethodnim deklaracijama")):
        return True
    weak_parts = (
        "deklaracijama", "zemlju", "zemlja", "porijekla", "porijkla", "prijekla",
    )
    if any(part in msg for part in weak_parts) and not re.search(r'[a-zšđčćž]{4,}\s+[a-z0-9]', msg, flags=re.IGNORECASE):
        return True
    return msg in {"za", "u", "iz", "ovaj", "zaj", "taj", "proizvod"}


def _is_missing_invoice_field_request(message: str) -> bool:
    msg = _normalize_naim_message(message)
    has_missing = any(kw in msg for kw in ("nema", "bez", "nedostaje", "fali", "prazn", "nepopun"))
    has_field = any(kw in msg for kw in (
        "zemlj", "porijek", "porijk", "porekl", "prijek", "tarif", "iznos", "vrijednost",
    ))
    has_table = any(kw in msg for kw in (
        "faktura", "fakture", "faktir", "tabu", "tab", "tabel", "tabela",
    ))
    return has_missing and has_field and has_table


def _extract_origin_product_query(message: str) -> str:
    # Docs: docs/sections/agent-origin-query-routing.md
    msg = (message or "").strip()
    lower = msg.lower()
    if not (_has_origin_keyword(msg) or "origin" in lower):
        return ""
    if _is_missing_invoice_field_request(msg):
        return ""
    if re.search(r'\b(upiši|upisi|upišite|upisite|postavi|unesi|unesite|stavi)\b', lower):
        return ""

    quote = re.search(r'["\']([^"\']{3,100})["\']', msg)
    if quote:
        return quote.group(1).strip()

    parts = [p.strip() for p in re.split(r'[,;\n]+', msg) if p.strip()]
    non_origin_parts = [
        p for p in parts
        if not re.search(_ORIGIN_KEYWORD_RE + r'|origin', p, flags=re.IGNORECASE)
    ]
    if non_origin_parts:
        query = _clean_origin_query(max(non_origin_parts, key=len))
        if len(query) >= 3:
            return query

    patterns = [
        rf'(?:potra[žzćc]i|pretra[žz]i|prona[đd]i|na[đd]i|tra[žz]i|trazi)\s+(?:mi\s+)?(?:{_ORIGIN_KEYWORD_RE}|origin)\s+(?:za\s+)?(.+)',
        rf'(?:{_ORIGIN_KEYWORD_RE}|origin)\s+(?:ovog\s+proizvoda\s+)?(?:za\s+)?(.+)',
        rf'(?:koja|koje|koji)\s+je\s+(?:{_ORIGIN_KEYWORD_RE}|origin)\s+(?:za\s+)?(.+)',
        rf'(.+?)\s+(?:koj\w*\s+je\s+)?(?:{_ORIGIN_KEYWORD_RE}|origin)\b.*$',
        r'odakle\s+je\s+(?:proizvod\s+)?(.+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, msg, flags=re.IGNORECASE)
        if match:
            query = _clean_origin_query(match.group(1))
            if len(query) >= 3 and not _is_weak_origin_query(query):
                return query

    return ""


def _get_conversation_context(ctrl) -> dict:
    ctx = getattr(ctrl, "_conversation_context", None)
    if ctx is None:
        ctx = {}
        ctrl._conversation_context = ctx
    return ctx


def _remember_subject(ctrl, subject: str) -> None:
    subject = (subject or "").strip()
    if subject:
        _get_conversation_context(ctrl)["last_subject"] = subject


def _clean_tariff_code(value: str) -> str:
    digits = re.sub(r'\D', '', value or "")
    return digits[:10] if len(digits) >= 8 else ""


def _remember_tariff_context(
    ctrl,
    tariff_code: str = "",
    *,
    naim_ordinal: int | None = None,
    product_name: str = "",
) -> None:
    ctx = _get_conversation_context(ctrl)
    code = _clean_tariff_code(tariff_code)
    if code:
        ctx["last_tariff_code"] = code
    if naim_ordinal:
        ctx["last_naimenovanje_ordinal"] = naim_ordinal
    product_name = (product_name or "").strip()
    if product_name:
        ctx["last_product_name"] = product_name
        ctx["last_subject"] = product_name


def _remember_naimenovanje_context(ctrl, item) -> None:
    if not item:
        return
    opis = (
        getattr(item, "goods_description", "")
        or getattr(item, "goods_trade_name", "")
        or ""
    )
    _remember_tariff_context(
        ctrl,
        getattr(item, "tariff_code", "") or "",
        naim_ordinal=getattr(item, "ordinal_no", None),
        product_name=opis,
    )


def _set_offered_action(ctrl, action: str, subject: str, label: str = "") -> None:
    ctx = _get_conversation_context(ctrl)
    ctx["last_offered_action"] = {
        "action": action,
        "subject": (subject or "").strip(),
        "label": label,
    }


def _clear_offered_action(ctrl) -> None:
    _get_conversation_context(ctrl).pop("last_offered_action", None)


def _is_followup_confirmation(message: str) -> bool:
    msg = (message or "").lower().strip()
    msg = re.sub(r'[.!?]+$', '', msg).strip()
    return msg in {
        "da", "moze", "može", "moze li", "može li", "pretrazi", "pretraži",
        "trazi", "traži", "potrazi", "potraži", "provjeri", "nastavi",
        "uradi", "kreni", "ok", "u redu",
    }


def _extract_web_search_subject(message: str) -> str:
    msg = (message or "").strip()
    lower = msg.lower()
    if not any(k in lower for k in ("internet", "internetu", "web", "online")):
        return ""

    patterns = [
        r'(?:potra[žz]i|pretra[žz]i|prona[đd]i|na[đd]i|tra[žz]i|trazi).{0,30}?(?:internet\w*|web|online)\s+(?:za\s+)?(.+)',
        r'(?:mo[žz]e[šs]\s+li|mozes\s+li).{0,50}?(?:internet\w*|web|online).{0,20}?(?:za\s+)?(.+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, msg, flags=re.IGNORECASE)
        if match:
            subject = match.group(1).strip().rstrip("?! .")
            subject = re.sub(r'\b(ga|to|ovo|ovaj|proizvod|proizvoda)\b', '', subject, flags=re.IGNORECASE)
            subject = re.sub(r'\s+', ' ', subject).strip()
            if len(subject) >= 3:
                return subject
    return ""


def _resolve_followup(ctrl, message: str) -> bool:
    chat = ctrl.view.get_chat_panel()
    ctx = _get_conversation_context(ctrl)
    offered = ctx.get("last_offered_action") or {}

    if _is_followup_confirmation(message) and offered:
        action = offered.get("action")
        subject = offered.get("subject") or ctx.get("last_subject", "")
        if action == "search_archive" and subject:
            _clear_offered_action(ctrl)
            _pretrazi_arhiv_za_proizvod(ctrl, subject)
            return True

    web_subject = _extract_web_search_subject(message) or ctx.get("last_subject", "")
    if web_subject and any(k in message.lower() for k in ("internet", "internetu", "web", "online")):
        _remember_subject(ctrl, web_subject)
        _set_offered_action(ctrl, "search_archive", web_subject, "Pretraži lokalni arhiv")
        chat.add_agent_message(
            f"Nemam direktnu web pretragu iz aplikacije, ali mogu odmah pretražiti "
            f"lokalni arhiv XML deklaracija i bazu znanja za: <b>{escape(web_subject)}</b>.<br><br>"
            f"Napiši <b>Pretraži</b> i nastaviću sa tim proizvodom."
        )
        return True

    return False


def _extract_specific_naimenovanje_request(message: str) -> int | None:
    msg = (message or "").lower()
    if not re.search(r'\b(naim|naimenovanj)\w*', msg):
        return None
    match = re.search(
        r'\b(?:naim\w*|naimenovanj\w*)\s*(?:broj|br\.?|rb\.?)?\s*(\d+)\b',
        msg,
    )
    if match:
        return int(match.group(1))
    match = re.search(
        r'\b(\d+)\.?\s*(?:naim\w*|naimenovanj\w*)\b',
        msg,
    )
    if match:
        return int(match.group(1))
    for word, ordinal in _REDNI.items():
        if ordinal > 0 and word in msg:
            return ordinal
    return None


def _extract_specific_invoice_line_request(message: str) -> int | None:
    msg = _normalize_naim_message(message)
    if not re.search(r'\b(faktur|tabu faktura|tab faktura)\w*', msg):
        return None
    if not re.search(r'\b(stavk|red|linij)\w*', msg):
        return None

    patterns = (
        r'\b(?:stavk\w*|red\w*|linij\w*)\s*(?:broj|br\.?|rb\.?)?\s*(\d+)\b',
        r'\b(\d+)\.?\s*(?:stavk\w*|red\w*|linij\w*)\b',
    )
    for pattern in patterns:
        match = re.search(pattern, msg)
        if match:
            return int(match.group(1))
    for word, ordinal in _REDNI.items():
        if ordinal > 0 and word in msg:
            return ordinal
    return None


def _find_invoice_line_by_ordinal(ctrl, ordinal: int):
    if not ordinal or not ctrl.draft:
        return None
    lines = list(getattr(ctrl.draft, "invoice_lines", []) or [])
    if 0 < ordinal <= len(lines):
        return lines[ordinal - 1]
    return None


def _invoice_line_product_name(line) -> str:
    if not line:
        return ""
    return (
        getattr(line, "naziv_robe", "")
        or getattr(line, "product_code", "")
        or ""
    ).strip()


def _find_naimenovanje_by_ordinal(ctrl, ordinal: int):
    if not ordinal or not ctrl.draft:
        return None
    for item in getattr(ctrl.draft, "items", []) or []:
        if getattr(item, "ordinal_no", None) == ordinal:
            return item
    items = list(getattr(ctrl.draft, "items", []) or [])
    if 0 < ordinal <= len(items):
        return items[ordinal - 1]
    return None


def _naimenovanje_product_name(item) -> str:
    if not item:
        return ""
    return (
        getattr(item, "goods_trade_name", "")
        or getattr(item, "goods_description", "")
        or getattr(item, "tariff_description3", "")
        or getattr(item, "tariff_description2", "")
        or getattr(item, "tariff_description1", "")
        or ""
    ).strip()


def _is_tariff_suggestion_for_naimenovanje(message: str) -> bool:
    msg = _normalize_naim_message(message)
    if not re.search(r'\b(naim|naimenovanj)\w*', msg):
        return False
    if "tarif" not in msg:
        return False
    return any(
        kw in msg for kw in (
            "predlo", "provjer", "prona", "nađi", "nadji",
            "alternativ", "ispravn", "pogrešan", "pogresan",
            "koji", "koja",
        )
    )


def _is_tariff_suggestion_for_current_item(message: str) -> bool:
    msg = _normalize_naim_message(message)
    if "tarif" not in msg:
        return False
    if not any(
        kw in msg for kw in (
            "predlo", "provjer", "prona", "nađi", "nadji",
            "alternativ", "ispravn", "koji", "koja",
        )
    ):
        return False
    return bool(
        re.search(
            r'\b(ovu|ove|ovoj|ovaj|ovog|taj|tog|tu|ta|za nju|za njega)\s+'
            r'(stavk\w*|robu|proizvod\w*)\b',
            msg,
        )
    )


def _is_current_item_reference(message: str) -> bool:
    msg = _normalize_naim_message(message)
    return bool(
        re.search(
            r'\b(ovu|ove|ovoj|ovaj|ovog|taj|tog|tu|ta|za nju|za njega)\s+'
            r'(stavk\w*|robu|proizvod\w*|broj)\b',
            msg,
        )
    )


def _is_tariff_insert_request(message: str) -> bool:
    msg = _normalize_naim_message(message)
    if not any(kw in msg for kw in ("ubac", "upiš", "upis", "unes", "postav", "stavi")):
        return False
    if not any(kw in msg for kw in ("tarif", "broj", "faktur", "faktir")):
        return False
    return True


def _should_save_tariff_mapping(message: str) -> bool:
    msg = _normalize_naim_message(message)
    return any(
        kw in msg for kw in (
            "sačuv", "sacuv", "zapam", "upam", "nauči", "nauci",
            "u bazi", "bazu podataka", "za ubuduće", "za ubuduce",
        )
    )


def _is_database_lookup_request(message: str) -> bool:
    msg = _normalize_naim_message(message)
    return any(
        kw in msg for kw in (
            "bazi podataka", "baza podataka", "u bazi", "iz baze",
            "istorij", "historij", "ranije", "sličn", "slicn",
            "korišten", "koristen", "korišćen", "koriscen",
        )
    ) and any(
        kw in msg for kw in (
            "pogled", "provjer", "pretra", "prona", "nađi", "nadji",
            "šta", "sta", "koliko",
        )
    )


def _database_lookup_from_context(ctrl, message: str) -> bool:
    if not _is_database_lookup_request(message):
        return False

    naim_ordinal = _extract_specific_naimenovanje_request(message)
    if naim_ordinal is not None:
        item = _find_naimenovanje_by_ordinal(ctrl, naim_ordinal)
        product_name = _naimenovanje_product_name(item)
        if product_name:
            _remember_naimenovanje_context(ctrl, item)
            _pronadji_slicne_proizvode(ctrl, product_name)
            return True

    ctx = _get_conversation_context(ctrl)
    product_name = (ctx.get("last_product_name") or ctx.get("last_subject") or "").strip()
    if product_name and re.search(r'\b(taj|tog|tom|taj proizvod|za njega|iz tog)\b', message.lower()):
        _pronadji_slicne_proizvode(ctrl, product_name)
        return True

    if re.search(r'\b(taj|tog|tom|proizvod|stavk|naimenovanj)\b', message.lower()):
        _set_offered_action(ctrl, "similar_product_lookup", "", "Pretraži bazu za proizvod")
        ctrl.view.get_chat_panel().add_agent_message(
            "Molim Vas, navedite redni broj naimenovanja ili naziv proizvoda "
            "(npr. <b>iz sedmog naimenovanja</b>)."
        )
        return True

    return False


def _origin_lookup_from_context(ctrl, message: str) -> bool:
    if not _has_origin_keyword(message) and "origin" not in (message or "").lower():
        return False

    query = _extract_origin_product_query(message)
    if query:
        _remember_subject(ctrl, query)
        _pretrazi_porijeklo(ctrl, query)
        return True

    ctx = _get_conversation_context(ctrl)
    product_name = (ctx.get("last_product_name") or ctx.get("last_subject") or "").strip()
    if product_name:
        _pretrazi_porijeklo(ctrl, product_name)
        return True

    invoice_ordinal = ctx.get("last_invoice_line_ordinal")
    if invoice_ordinal:
        line = _find_invoice_line_by_ordinal(ctrl, int(invoice_ordinal))
        product_name = _invoice_line_product_name(line)
        if product_name:
            _remember_tariff_context(
                ctrl,
                getattr(line, "tarifni_broj", "") or "",
                product_name=product_name,
            )
            _pretrazi_porijeklo(ctrl, product_name)
            return True

    return False


def _missing_invoice_field_from_context(ctrl, message: str) -> bool:
    msg = _normalize_naim_message(message)
    if not _is_missing_invoice_field_request(message):
        return False

    field = ""
    label = ""
    if any(kw in msg for kw in ("zemlj", "porijek", "porijk", "porekl", "prijek")):
        field = "country"
        label = "zemlje porijekla"
    elif "tarif" in msg:
        field = "tariff"
        label = "tarifnog broja"
    elif "iznos" in msg or "vrijednost" in msg:
        field = "amount"
        label = "iznosa"
    if not field:
        return False

    ctx = _get_conversation_context(ctrl)
    table_ref = any(kw in msg for kw in ("faktura", "fakture", "faktir", "tabu", "tab", "tabel", "tabela"))
    if not table_ref and ctx.get("last_app_scope") != "faktura":
        return False

    lines = list(getattr(getattr(ctrl, "draft", None), "invoice_lines", []) or [])
    missing = []
    for idx, line in enumerate(lines, start=1):
        if field == "country" and not (getattr(line, "zemlja_porijekla", "") or "").strip():
            missing.append((idx, line))
        elif field == "tariff" and not (getattr(line, "tarifni_broj", "") or "").strip():
            missing.append((idx, line))
        elif field == "amount" and (getattr(line, "iznos", 0) or 0) <= 0:
            missing.append((idx, line))

    chat = ctrl.view.get_chat_panel()
    if not missing:
        chat.add_agent_message(f"✅ U Faktura tabu nema stavki bez {escape(label)}.")
        return True

    rows = []
    for idx, line in missing[:20]:
        invoice = escape(str(getattr(line, "invoice_number", "") or "—"))
        name = escape(str(getattr(line, "naziv_robe", "") or "—")[:80])
        tariff = escape(str(getattr(line, "tarifni_broj", "") or "—"))
        rows.append(
            f"• <b>Rb.{idx}</b> — {name}<br>"
            f"<small>Faktura: {invoice}; tarifa: {tariff}</small>"
        )
    more = "" if len(missing) <= 20 else f"<br><small>... i još {len(missing) - 20} stavki.</small>"
    chat.add_agent_message(
        f"<b>Faktura tab — stavke bez {escape(label)}</b><br>"
        f"Ukupno: <b>{len(missing)}</b><br><br>"
        f"{'<br>'.join(rows)}{more}"
    )
    return True


def _is_tariff_usage_question(message: str) -> bool:
    msg = (message or "").lower()
    if "tarif" not in msg:
        return False
    usage_words = (
        "koliko puta", "korišten", "koristen", "korišćen", "koriscen",
        "upotrebljen", "usage", "istorij", "historij", "ranije",
    )
    return any(word in msg for word in usage_words)


def _normalize_naim_message(message: str) -> str:
    msg = (message or "").lower()
    msg = re.sub(r'\bn\s+aimenovanj', 'naimenovanj', msg)
    return re.sub(r'\s+', ' ', msg).strip()


def _is_naimenovanja_review_request(message: str) -> bool:
    msg = _normalize_naim_message(message)
    if not re.search(r'\b(naim|naimenovanj)\w*', msg):
        return False
    return any(
        kw in msg for kw in (
            "pregled", "pregledaj", "pogledaj", "pokaži", "pokazi",
            "prikaži", "prikazi", "detalj", "tabu naimenovanja",
            "tab naimenovanja", "u naimenovanja",
        )
    )


def _is_naimenovanja_validation_request(message: str) -> bool:
    msg = _normalize_naim_message(message)
    return any(
        kw in msg for kw in (
            "provjer", "valid", "da li su", "šta fali", "sta fali",
            "nedostaje", "prazn", "nepopunjene",
        )
    )


def _application_context_scope(message: str) -> str:
    msg = _normalize_naim_message(message)
    if not msg:
        return ""

    wants_view = any(
        kw in msg for kw in (
            "pogledaj", "pregledaj", "pokaži", "pokazi", "prikaži", "prikazi",
            "šta ima", "sta ima", "šta je učitano", "sta je ucitano",
            "stanje aplikacije", "stanje draft", "trenutno stanje",
        )
    )
    has_app_area = any(
        kw in msg for kw in (
            "tab", "tabu", "faktura", "naimenov", "naim",
            "zaglav", "učitano", "ucitano", "aplikacij", "draft",
        )
    )
    if not (wants_view and has_app_area):
        return ""

    if any(kw in msg for kw in ("faktura", "tab faktura", "tabu faktura")):
        return "faktura"
    if any(kw in msg for kw in ("naimenov", "naim")):
        return "naimenovanja"
    if "zaglav" in msg:
        return "zaglavlje"
    return "all"


def _resolve_tariff_code_from_context(ctrl, message: str) -> str:
    explicit = _clean_tariff_code(message)
    if explicit:
        return explicit
    msg = (message or "").lower()
    if re.search(r'\b(taj|tog|tom|ovaj|ovog|njemu|njega)\b', msg):
        return _get_conversation_context(ctrl).get("last_tariff_code", "")
    return ""


def _tariff_usage_stats(tariff_code: str) -> dict:
    code = _clean_tariff_code(tariff_code)
    if not code:
        return {"total_usage": 0, "rows": 0, "examples": []}

    from database.db import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(usage_count), 0) AS total_usage,
                       COUNT(*) AS rows,
                       COUNT(DISTINCT NULLIF(supplier, '')) AS suppliers
                FROM catalogs.product_tariff_mapping
                WHERE regexp_replace(COALESCE(commodity_code, ''), '\\D', '', 'g')
                      LIKE %s
                """,
                [f"{code[:8]}%"],
            )
            summary = cur.fetchone() or {}

            cur.execute(
                """
                SELECT naziv_robe, supplier, zemlja_porijekla, povlastica,
                       usage_count, source
                FROM catalogs.product_tariff_mapping
                WHERE regexp_replace(COALESCE(commodity_code, ''), '\\D', '', 'g')
                      LIKE %s
                ORDER BY usage_count DESC, naziv_robe
                LIMIT 5
                """,
                [f"{code[:8]}%"],
            )
            examples = cur.fetchall() or []

    return {
        "total_usage": int(summary.get("total_usage") or 0),
        "rows": int(summary.get("rows") or 0),
        "suppliers": int(summary.get("suppliers") or 0),
        "examples": examples,
    }


def _prikazi_statistiku_tarife(ctrl, tariff_code: str) -> None:
    chat = ctrl.view.get_chat_panel()
    code = _clean_tariff_code(tariff_code)
    if not code:
        chat.add_agent_message("Molim Vas, navedite tarifni broj.")
        return

    _remember_tariff_context(ctrl, code)
    chat.add_activity(f"📚 Provjeravam istoriju za tarifni broj {code[:8]}...")

    try:
        stats = _tariff_usage_stats(code)
        from services.tariff.tarifa_service import validiraj_tarifni_broj

        valid = validiraj_tarifni_broj(code[:8])
        opis = valid.get("naziv", "") if valid.get("valid") else ""
        status = "u zvaničnoj tarifi" if valid.get("valid") else "nije pronađen u zvaničnoj tarifi"

        examples = []
        for row in stats["examples"]:
            naziv = escape((row.get("naziv_robe") or "")[:70])
            supplier = escape(row.get("supplier") or row.get("source") or "—")
            zemlja = escape(row.get("zemlja_porijekla") or "—")
            usage = int(row.get("usage_count") or 0)
            examples.append(
                f"• {naziv} <small>({usage}x, izvor {supplier}, zemlja {zemlja})</small>"
            )

        examples_html = "<br>".join(examples) if examples else "Nema primjera u bazi znanja."
        chat.add_agent_message(
            f"<b>Istorija tarifnog broja {escape(code[:8])}</b><br>"
            f"Status: <b>{escape(status)}</b>"
            f"{('<br>Zvanični opis: ' + escape(opis[:140])) if opis else ''}<br>"
            f"Korištenje u bazi znanja: <b>{stats['total_usage']}x</b> "
            f"({stats['rows']} zapisa"
            f"{', ' + str(stats['suppliers']) + ' dobavljača' if stats['suppliers'] else ''}).<br><br>"
            f"{examples_html}"
        )
    except Exception as e:
        chat.add_agent_message(f"❌ Greška pri provjeri istorije tarife {escape(code[:8])}: {escape(str(e))}")


def _resolve_contextual_request(ctrl, message: str) -> bool:
    invoice_line_ordinal = _extract_specific_invoice_line_request(message)
    if invoice_line_ordinal is not None:
        _pregledaj_faktura_stavku(ctrl, invoice_line_ordinal)
        return True

    naim_ordinal = _extract_specific_naimenovanje_request(message)

    if _is_tariff_insert_request(message):
        explicit_code = _clean_tariff_code(message)
        ctx_code = _get_conversation_context(ctrl).get("last_tariff_code", "")
        code = explicit_code or ctx_code
        if code and _upisi_tarifu_u_trenutnu_faktura_stavku(
            ctrl,
            code,
            save_mapping=_should_save_tariff_mapping(message),
        ):
            return True

    if _is_tariff_suggestion_for_current_item(message):
        ctx = _get_conversation_context(ctrl)
        invoice_ordinal = ctx.get("last_invoice_line_ordinal")
        if invoice_ordinal:
            line = _find_invoice_line_by_ordinal(ctrl, int(invoice_ordinal))
            product_name = _invoice_line_product_name(line)
            if product_name:
                _remember_tariff_context(
                    ctrl,
                    getattr(line, "tarifni_broj", "") or "",
                    product_name=product_name,
                )
                _alternativni_tarifni_za_stavku(ctrl, item_query=product_name)
                return True

    offered = _get_conversation_context(ctrl).get("last_offered_action") or {}
    if offered.get("action") == "similar_product_lookup" and naim_ordinal is not None:
        item = _find_naimenovanje_by_ordinal(ctrl, naim_ordinal)
        product_name = _naimenovanje_product_name(item)
        if product_name:
            _clear_offered_action(ctrl)
            _remember_naimenovanje_context(ctrl, item)
            _pronadji_slicne_proizvode(ctrl, product_name)
            return True

    if naim_ordinal is not None and _is_tariff_suggestion_for_naimenovanje(message):
        item = _find_naimenovanje_by_ordinal(ctrl, naim_ordinal)
        if item:
            _remember_naimenovanje_context(ctrl, item)
        _alternativni_tarifni_za_stavku(ctrl, item_ordinal=naim_ordinal)
        return True

    if naim_ordinal is not None and _is_tariff_usage_question(message):
        item = _find_naimenovanje_by_ordinal(ctrl, naim_ordinal)
        code = _clean_tariff_code(getattr(item, "tariff_code", "") if item else "")
        if not code:
            ctrl.view.get_chat_panel().add_agent_message(
                f"⚠️ Naimenovanje broj <b>{naim_ordinal}</b> nema tarifni broj."
            )
            return True
        _remember_naimenovanje_context(ctrl, item)
        _prikazi_statistiku_tarife(ctrl, code)
        return True

    if _is_tariff_usage_question(message):
        code = _resolve_tariff_code_from_context(ctrl, message)
        if not code:
            _set_offered_action(ctrl, "tariff_usage", "", "Provjeri istoriju tarife")
            ctrl.view.get_chat_panel().add_agent_message(
                "Molim Vas, navedite tarifni broj ili prvo otvorite konkretno naimenovanje."
            )
            return True
        _prikazi_statistiku_tarife(ctrl, code)
        return True

    if _missing_invoice_field_from_context(ctrl, message):
        return True

    if _origin_lookup_from_context(ctrl, message):
        return True

    if _database_lookup_from_context(ctrl, message):
        return True

    if naim_ordinal is not None and _is_naimenovanja_validation_request(message):
        _provjeri_jedno_naimenovanje(ctrl, naim_ordinal)
        return True

    if naim_ordinal is not None:
        _pregledaj_naimenovanja(ctrl, [naim_ordinal])
        return True

    msg = (message or "").strip()
    if re.fullmatch(r'\d[\d\s\.]{7,12}', msg):
        code = _clean_tariff_code(msg)
        if code:
            offered = _get_conversation_context(ctrl).get("last_offered_action") or {}
            if offered.get("action") == "tariff_usage":
                _clear_offered_action(ctrl)
                _prikazi_statistiku_tarife(ctrl, code)
                return True
            _pretrazi_tarifu_po_kodu(ctrl, code)
            return True

    return False


def _audit_routing(routing_layer: str, **kwargs) -> None:
    """Zabilježi koji routing sloj je obradio poruku (Faza D, §8.2)."""
    record_audit(AuditEvent(routing_layer=routing_layer, **kwargs))


def _check_agent_v2_enabled(ctrl) -> bool:
    """Kill-switch za Agent V2 routing.

    Čita DEKLARANT_AGENT_V2 iz .env preko AppSettings.
    Default: False (0) — stari put, bajt-identično ponašanje.
    True (1) — V2 Intent Resolver aktivan (Faza 1+).

    Plan §10 Faza −1.C — vrijednost se auditira uz svaki routing.
    """
    try:
        from config.settings import get_app_settings
        settings = get_app_settings()
        return getattr(settings, "agent_v2_enabled", False)
    except Exception:
        return False


def _handle_message_v2(ctrl, message: str) -> None:
    """Agent V2 routing — koristi Intent Resolver umjesto keyword prečica.

    Plan §12: _application_context_scope() više ne smije presresti VALIDATE.
    Redoslijed faktura prije naimenov iz §3.3 je ispravljen.
    """
    from services.agent.chat.intent_model import IntentAction, IntentTarget
    from services.agent.chat.intent_resolver import resolve

    chat = ctrl.view.get_chat_panel()
    intent = resolve(message)
    # POPRAVKA (2026-07-27): action/target/confidence nisu polja AuditEvent-a —
    # prosljeđivanje kao top-level kwargs je bacalo TypeError na SVAKI poziv
    # _handle_message_v2 (dakle na svaku poruku kad je kill-switch uključen).
    # Vidi agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.
    _audit_routing(
        "v2_resolver",
        source=intent.source.value,
        extra={
            "action": intent.action.value,
            "target": intent.target.value,
            "confidence": intent.confidence,
        },
    )

    # ── CONFIRM / CANCEL ────────────────────────────────────────
    if intent.action == IntentAction.CONFIRM:
        if ctrl._pending_action:
            ctrl._execute_pending_action()
            _audit_routing("v2", tool="pending_action", confirmation="confirmed")
        else:
            chat.add_agent_message("Nema aktivne akcije za potvrdu.")
        return

    if intent.action == IntentAction.CANCEL:
        if ctrl._pending_action:
            ctrl._pending_action = None
            chat.add_agent_message("❌ Akcija otkazana.")
            _audit_routing("v2", tool="pending_action", confirmation="rejected")
        else:
            # Nema pending — delegiraj na standardni chat
            _start_chat_worker(ctrl, message, fallback_reason="cancel_no_pending")
        return

    # ── SHOW — prikaz stanja ─────────────────────────────────────
    if intent.action == IntentAction.SHOW:
        if intent.target == IntentTarget.INVOICE:
            _pregled_stanja_aplikacije(ctrl, "faktura")
        elif intent.target == IntentTarget.ITEMS:
            _pregledaj_naimenovanja(ctrl)
        elif intent.target == IntentTarget.HEADER:
            _pregled_stanja_aplikacije(ctrl, "zaglavlje")
        elif intent.target == IntentTarget.TARIFFS:
            _pregled_stanja_aplikacije(ctrl, "tarife")
        elif intent.target == IntentTarget.SPECIFIC_ROW and intent.ordinals:
            _pregledaj_naimenovanja(ctrl, indeksi=list(intent.ordinals))
        else:
            _pregled_stanja_aplikacije(ctrl, "all")
        return

    # ── VALIDATE — stručna provjera ──────────────────────────────
    # invoice/header su prije popravke (2026-07-27) padali na plain chat
    # ("još ne postoji") iako su invoice_review_service (Faza 3) i
    # header_review_service (Faza 5) odavno izgrađeni i testirani —
    # samo nikad povezani na ovaj ulaz. Vidi
    # agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.
    if intent.action == IntentAction.VALIDATE:
        if intent.target == IntentTarget.INVOICE:
            _dispatch_provjeri(ctrl, {"target": "invoice"}, None)
        elif intent.target == IntentTarget.ITEMS:
            _provjeri_naimenovanja(ctrl)
        elif intent.target == IntentTarget.HEADER:
            _dispatch_provjeri(ctrl, {"target": "header"}, None)
        elif intent.target == IntentTarget.TARIFFS:
            ctrl._provjeri_tarifne_za_naziv()
        elif intent.target == IntentTarget.SPECIFIC_ROW:
            _provjeri_naimenovanja(ctrl)
        else:
            # Validiramo cijelu deklaraciju
            _compliance_check(ctrl)
        return

    # ── RUN_WORKFLOW — "jedna komanda vodi cijeli proces" ────────
    # ("Pripremi deklaraciju", "nastavi", "završi") — korisnički zahtjev
    # koji je bio prioritetiziran ispred svih drugih. Prije popravke
    # nijedan kod-put nije mogao ovo izvršiti (declaration_workflow_state.py
    # je postojao ali se nigdje nije pozivao). Vidi
    # agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.
    if intent.action == IntentAction.RUN_WORKFLOW:
        from services.agent.workflow.declaration_workflow_service import (
            AgentBusyError, run_declaration_workflow,
        )
        try:
            run_declaration_workflow(ctrl, chat)
        except AgentBusyError:
            pass  # poruka je već prikazana unutar run_declaration_workflow
        return

    # ── EXPORT — "izvezi xml" bez punog workflow-a ───────────────
    # _izvezi_xml sam po sebi provjerava readiness i traži potvrdu (Faza 6) —
    # nema posebnog LLM alata za ovo (export_to_xml nije u tool_definitions),
    # pa direktan poziv umjesto Tool Use pogotka koji ne postoji.
    if intent.action == IntentAction.EXPORT:
        from gui.tabs.agent.services.xml_workflow_service import XmlWorkflowService
        XmlWorkflowService(ctrl).izvezi_xml(chat)
        return

    # ── Ostale akcije — Tool Use bira konkretan alat ─────────────
    # (ANALYZE, REQUEST_CHANGE, PROPOSE, OTHER)
    # Prije popravke ovo je išlo direktno na plain _start_chat_worker
    # (bez tools=) — LLM nije imao pristup nijednom alatu za ove namjere,
    # što je otvaralo prostor za izmišljanje odgovora.
    _audit_routing("v2", tool="tool_use_delegated", fallback_reason=f"v2_{intent.action.value}")
    _dispatch_via_tool_use(ctrl, message)


def _handle_message(ctrl, message: str) -> None:
    """
    Primarni entry point za chat poruke.
    Flow: injection → pending → Tool Use (Groq/Gemini) → regex fallback → ChatWorker.

    📄 docs/decisions/002-tool-dispatcher-integration.md
    """
    from gui.tabs.agent.widgets.chat_worker import check_injection

    chat = ctrl.view.get_chat_panel()

    blocked = check_injection(message)
    if blocked:
        chat.add_agent_message(blocked)
        return

    # ── Agent V2 kill-switch (Faza −1.C) ──────────────────────────
    agent_v2 = _check_agent_v2_enabled(ctrl)
    # Auditiraj vrijednost zastavice uz svaki routing.
    # POPRAVKA (2026-07-27): AuditEvent nema polje 'agent_v2' — prosljeđivanje
    # kao top-level kwarg je bacalo TypeError na SVAKI poziv _handle_message,
    # bez obzira na sadržaj poruke ili vrijednost kill-switcha. Nijedan
    # postojeći test nije ovo uhvatio jer nijedan ne poziva _handle_message
    # direktno (svi testiraju _handle_message_v2 ili interne funkcije).
    # Vidi agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.
    _audit_routing("switch", status="ok", extra={"agent_v2": agent_v2})
    # ── Agent V2 routing (Faza 1+) ──────────────────────────────
    if agent_v2:
        _handle_message_v2(ctrl, message)
        return
    # ── Stari routing (bajt-identičan) ──────────────────────────

    msg_lower = message.lower().strip()

    if _resolve_followup(ctrl, message):
        _audit_routing("local", tool="followup", status="ok")
        return

    if _resolve_contextual_request(ctrl, message):
        _audit_routing("contextual", status="ok")
        return

    scope = _application_context_scope(message)
    if scope:
        _pregled_stanja_aplikacije(ctrl, scope)
        _audit_routing("local", tool="pregled_stanja_aplikacije", status="ok")
        return

    if _is_naimenovanja_review_request(message):
        if _is_naimenovanja_validation_request(message):
            _provjeri_naimenovanja(ctrl)
        else:
            _pregledaj_naimenovanja(ctrl)
        _audit_routing("local", tool="naimenovanja_review", status="ok")
        return

    origin_query = _extract_origin_product_query(message)
    if origin_query:
        _remember_subject(ctrl, origin_query)
        _pretrazi_porijeklo(ctrl, origin_query)
        _audit_routing("local", tool="pretrazi_porijeklo", status="ok")
        return

    # --- POTVRDA pending akcije ---
    POTVRDE = {'da', 'odobri', 'potvrdi', 'yes', 'ok', 'u redu', 'slažem se'}
    OTKAZI = {'ne', 'odustani', 'cancel', 'no', 'storno'}

    if ctrl._pending_action:
        if msg_lower in POTVRDE or msg_lower.startswith('da ') or msg_lower.startswith('odobr'):
            ctrl._execute_pending_action()
            _audit_routing("local", tool="pending_action", confirmation="confirmed")
            return
        if msg_lower in OTKAZI:
            ctrl._pending_action = None
            chat.add_agent_message("❌ Akcija otkazana.")
            _audit_routing("local", tool="pending_action", confirmation="rejected")
            return

    similar_query = _extract_similar_product_query(message)
    if similar_query:
        _remember_subject(ctrl, similar_query)
        _pronadji_slicne_proizvode(ctrl, similar_query)
        _audit_routing("local", tool="pronadji_slicne_proizvode", status="ok")
        return

    # ═══════════════════════════════════════════════════════════════
    # Faza 2: Tool Use routing (PRIMARNI) — LLMProvider (Groq → Gemini) bira alat
    # ═══════════════════════════════════════════════════════════════
    # Vidi: docs/decisions/001-tool-use-refactoring.md
    _dispatch_via_tool_use(ctrl, message)
    # Kraj Tool Use bloka — ostatak _handle_message se NE izvršava
    return


def _dispatch_via_tool_use(ctrl, message: str) -> None:
    """Pošalji poruku LLM Tool Use-u (Groq → Gemini) i izvrši odabrani alat.

    Zajednička ruta za stari (`_handle_message`) i V2 (`_handle_message_v2`,
    Faza 1+) put — u V2 putu prije popravke ovo se nije pozivalo za
    ANALYZE/REQUEST_CHANGE/PROPOSE/RUN_WORKFLOW/EXPORT/OTHER, nego se išlo
    direktno na plain chat bez alata. Vidi
    agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.

    Ako uspije → izvrši alat i gotovo. Ako fallback_to_chat → ChatWorker.
    Ako error → regex fallback (_handle_message_regex_fallback).
    """
    from services.agent.chat.tool_dispatcher import ToolDispatcherWorker

    chat = ctrl.view.get_chat_panel()
    dispatcher = ToolDispatcherWorker(message, parent=ctrl.view)

    def _on_tool_call(name: str, args: dict, provider: str):
        logger.debug(f"[ToolUse] → {name}({args})")
        _execute_tool(ctrl, name, args, provider=provider)

    def _on_fallback(text: str, provider: str):
        logger.debug(f"[ToolUse] → fallback to ChatWorker")
        _audit_routing("tool_use", status="fallback_to_chat", provider=provider)
        _start_chat_worker(ctrl, message, fallback_reason="tool_use_no_match", provider=provider)

    def _on_error(err: str):
        logger.warning(f"[ToolUse] Error, falling back to regex: {err}")
        err_l = (err or "").lower()
        _audit_routing("tool_use", status="error", fallback_reason=(err or "")[:200])
        # Ako Tool Use padne jer nijedan provider (Groq/Gemini) nije podešen,
        # idi direktno na standardni chat umjesto regex fallback-a — nema
        # smisla probati Tool Use LLM poziv drugi put kroz drugi kod put.
        if "nema dostupnog ai providera" in err_l:
            chat.add_activity("⚠️ Tool use nedostupan, prelazim na standardni AI chat...")
            _start_chat_worker(ctrl, message, fallback_reason="no_provider_configured")
            return
        chat.add_activity("⚠️ Tool use nedostupan, koristim regex fallback...")
        _handle_message_regex_fallback(ctrl, message)

    dispatcher.tool_call_received.connect(_on_tool_call)
    dispatcher.fallback_to_chat.connect(_on_fallback)
    dispatcher.error_occurred.connect(_on_error)
    dispatcher.finished.connect(dispatcher.deleteLater)

    # Drži referencu da GC ne počisti
    if not hasattr(ctrl, '_tool_dispatchers'):
        ctrl._tool_dispatchers = []
    ctrl._tool_dispatchers.append(dispatcher)
    dispatcher.finished.connect(
        lambda: ctrl._tool_dispatchers.remove(dispatcher)
        if dispatcher in ctrl._tool_dispatchers else None
    )

    chat.add_activity("🤔 Analiziram upit...")
    dispatcher.start()


def _extract_similar_product_query(message: str) -> str:
    text = str(message or "").strip()
    if not text:
        return ""

    msg = text.lower()
    triggers = (
        "sličn", "slicn", "historij", "istorij", "ranij",
        "korišten", "koristen", "korišćen", "koriscen", "koliko puta",
        "upit o",
    )
    if not any(trigger in msg for trigger in triggers):
        return ""
    if re.fullmatch(r"\d[\d\s\.]{7,12}", msg):
        return ""

    patterns = (
        r"\b(?:za|o|na)\b\s+(.+)$",
        r"\b(?:proizvod|robu|naziv)\b\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        query = re.sub(r"[?.!,;:]+$", "", match.group(1).strip())
        query = re.sub(r"^(?:taj|ovu|ove|ovaj|proizvod|robu)\s+", "", query, flags=re.IGNORECASE)
        if query and len(query) >= 3 and "tarifni broj" not in query.lower():
            return query
    return ""


# ── Tool execution (mapira tool → servis) ────────────────────────────
# Vidi: docs/decisions/002-tool-dispatcher-integration.md#execute_tool-mapiranje

def _execute_tool(ctrl, name: str, args: dict, provider: str = "") -> None:
    """
    Izvrši tool call pozivom postojećeg servisa.
    Svaki tool mapira na postojeću funkciju/metodu.

    ToolPolicy gate (Faza A): alat koji nije u registry-ju
    (services/agent/chat/tool_policy.py) se odbija fail-closed, prije
    dispatch-a — bez obzira da li ime slučajno odgovara nekoj if/elif grani
    ispod. MUTATE alati ne smiju direktno izvršiti izmjenu drafta — vidi
    _propose_kolona_upis().

    Audit (Faza D, §8.2): svaki dispatch (uspješan ili sa izuzetkom) se
    bilježi sa trajanjem — izuzetak se samo loguje pa propagira dalje
    nepromijenjen (audit ne smije promijeniti postojeće ponašanje greške).
    """
    chat = ctrl.view.get_chat_panel()

    def _emit(result: ToolResult) -> None:
        chat.add_agent_message(render_tool_result_html(result))

    effect = effect_for(name)
    if effect is None:
        logger.warning(f"[ToolUse] Nepoznat alat (nije u ToolPolicy registry): {name}")
        _emit(ToolResult.unknown(
            "tool_dispatch",
            f"Nepoznata akcija: {name}",
            "ToolPolicy",
            args=args,
        ))
        _audit_routing("tool_use", tool=name, status="unknown_tool", provider=provider, source="ToolPolicy")
        return

    started = time.perf_counter()
    try:
        _dispatch_known_tool(ctrl, name, args, _emit)
    except Exception:
        _audit_routing(
            "tool_use", tool=name, effect=effect.value, status="error", provider=provider,
            source="_execute_tool", duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise
    else:
        _audit_routing(
            "tool_use", tool=name, effect=effect.value, status="dispatched", provider=provider,
            source="_execute_tool", duration_ms=(time.perf_counter() - started) * 1000,
        )


def _dispatch_prikazi(ctrl, args: dict) -> None:
    """SHOW — snapshot iz aktivnog drafta. Plan §8.2: prikazi(target, scope, ordinals).

    Vidi agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md — prije ove
    izmjene 'prikazi' je bio definisan za LLM ali _execute_tool nije imao granu
    za njega (Nepoznata akcija).
    """
    target = (args.get("target") or "application").lower()
    ordinals = args.get("ordinals") or []

    if target == "items" and ordinals:
        _pregledaj_naimenovanja(ctrl, indeksi=[int(o) for o in ordinals])
        return
    if target == "invoice" and ordinals:
        _pregledaj_faktura_stavku(ctrl, int(ordinals[0]))
        return

    scope_map = {
        "application": "all", "declaration": "all",
        "invoice": "invoice", "items": "naimenovanja", "header": "header",
    }
    _pregled_stanja_aplikacije(ctrl, scope_map.get(target, "all"))


def _dispatch_provjeri(ctrl, args: dict, _emit) -> None:
    """VALIDATE — stručna provjera. Plan §8.2: provjeri(target, scope, ordinals, depth).

    Vidi agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.
    """
    from services.agent.validation.renderer import render_summary_html, render_xml_readiness_html

    target = (args.get("target") or "application").lower()
    scope = args.get("scope") or "all"
    ordinals = [int(o) for o in (args.get("ordinals") or [])]
    depth = args.get("depth") or "summary"
    max_n = 1000 if depth == "full" else 10

    chat = ctrl.view.get_chat_panel()
    draft = ctrl.draft

    if target in ("invoice", "origin"):
        from services.agent.validation.invoice_review_service import provjeri_fakturu
        summary = provjeri_fakturu(draft, scope=scope, ordinals=ordinals)
        chat.add_agent_message(render_summary_html(summary, max_blocking=max_n, max_warnings=max_n))
    elif target == "items":
        from services.agent.validation.items_review_service import (
            provjeri_naimenovanja as _pregledaj_stavke_v2,
        )
        summary = _pregledaj_stavke_v2(draft, scope=scope, ordinals=ordinals)
        chat.add_agent_message(render_summary_html(summary, max_blocking=max_n, max_warnings=max_n))
    elif target == "header":
        from services.agent.validation.header_review_service import provjeri_zaglavlje
        summary = provjeri_zaglavlje(draft)
        chat.add_agent_message(render_summary_html(summary, max_blocking=max_n, max_warnings=max_n))
    elif target == "cross_tab":
        from services.agent.validation.header_review_service import (
            provjeri_usklađenost_tabova,
        )
        summary = provjeri_usklađenost_tabova(draft)
        chat.add_agent_message(render_summary_html(summary, max_blocking=max_n, max_warnings=max_n))
    elif target == "xml":
        from services.agent.validation.xml_readiness_service import (
            provjeri_spremnost_za_xml,
        )
        result = provjeri_spremnost_za_xml(draft)
        chat.add_agent_message(render_xml_readiness_html(result))
    elif target == "tariffs":
        _prikaz_tarifnih_trenutnih(ctrl)
    else:
        # application / declaration — puna provjera cijele deklaracije,
        # isti tok kao stari alat "validuj_deklaraciju"
        _compliance_check(ctrl)


def _dispatch_known_tool(ctrl, name: str, args: dict, _emit) -> None:
    """Elif lanac za poznate alate — izdvojeno iz _execute_tool radi audit omotača."""
    if name == "prikazi":
        _dispatch_prikazi(ctrl, args)

    elif name == "provjeri":
        _dispatch_provjeri(ctrl, args, _emit)

    elif name == "predlozi_tarife":
        filter_kw = args.get("filter", "")
        if filter_kw:
            # Vidi: services/agent/chat/tariff_intent_service.py → propose_by_keyword()
            ctrl.tariff_svc.propose_by_keyword(filter_kw)
        else:
            ctrl._predlozi_tarifne_brojeve()

    elif name == "pregled_stanja_aplikacije":
        _pregled_stanja_aplikacije(ctrl, args.get("scope", "all"))

    elif name == "provjeri_tarife":
        _prikaz_tarifnih_trenutnih(ctrl)

    elif name == "pretrazi_tarifu":
        naziv = args.get("naziv", "")
        if naziv:
            _pretrazi_tarifu(ctrl, naziv)
        else:
            result = ToolResult.needs_review(
                "pretrazi_tarifu",
                "Navedi naziv proizvoda za pretragu tarife.",
                "lokalni tool router",
                args=args,
            )
            result.next_action = "Primjer: tarifni broj za startno uze"
            result.effect = effect_for(name)
            _emit(result)

    elif name == "pretrazi_porijeklo":
        naziv = args.get("naziv", "")
        if naziv:
            _pretrazi_porijeklo(ctrl, naziv)
        else:
            result = ToolResult.needs_review(
                "pretrazi_porijeklo",
                "Navedi naziv proizvoda za pretragu porijekla.",
                "lokalni tool router",
                args=args,
            )
            result.next_action = "Primjer: porijeklo za kondenzator GCVC"
            result.effect = effect_for(name)
            _emit(result)

    elif name == "validuj_deklaraciju":
        _compliance_check(ctrl)

    elif name == "prikazi_naimenovanja":
        _pregledaj_naimenovanja(ctrl)

    elif name == "provjeri_naimenovanja":
        _provjeri_naimenovanja(ctrl)

    elif name == "upisi_u_kolonu":
        kolona = args.get("kolona", "")
        vrijednost = args.get("vrijednost", "")
        tab = args.get("tab", "faktura")

        if not kolona or not vrijednost:
            result = ToolResult.needs_review(
                "upisi_u_kolonu",
                "Navedi kolonu i vrijednost za upis.",
                "lokalni tool router",
                args=args,
            )
            result.next_action = "Primjer: upisi zemlja porijekla RS u faktura"
            result.effect = effect_for(name)
            _emit(result)
            return

        # Koristi NaimenovanjaIntentService._resolve_kolona za mapiranje
        svc = ctrl.naim_intent_svc
        atribut, resolved_tab = svc._resolve_kolona(kolona, tab_hint=tab)
        if not atribut:
            result = ToolResult.unknown(
                "upisi_u_kolonu",
                f"Kolona '{kolona}' nije prepoznata.",
                "NaimenovanjaIntentService._resolve_kolona",
                kolona=kolona,
                tab=tab,
            )
            result.next_action = "Pokušaj: tarifni broj, zemlja porijekla, povlastica, procedura, oznake, pakovanje, valuta, napomena"
            result.effect = effect_for(name)
            _emit(result)
            return

        # MUTATE (ToolPolicy) — ne izvršavati odmah, kreirati proposal karticu
        # koju korisnik mora eksplicitno potvrditi. Vidi _propose_kolona_upis().
        _propose_kolona_upis(ctrl, atribut, vrijednost, resolved_tab)

    elif name == "spoji_naimenovanja":
        ctrl._predlozi_spajanje_naimenovanja()

    elif name == "analiziraj_tarifne":
        _analiziraj_tarifne_historiju(ctrl)

    elif name == "pronadji_slicne_proizvode":
        naziv = args.get("naziv", "")
        if naziv:
            _pronadji_slicne_proizvode(ctrl, naziv)
        else:
            result = ToolResult.needs_review(
                "pronadji_slicne_proizvode",
                "Navedi naziv robe za pretragu sličnih proizvoda.",
                "lokalni tool router",
                args=args,
            )
            result.next_action = "Primjer: slicni proizvodi za grejac 2000w"
            result.effect = effect_for(name)
            _emit(result)

    else:
        logger.warning(f"[ToolUse] Nepoznat alat: {name}")
        _emit(ToolResult.unknown(
            "tool_dispatch",
            f"Nepoznata akcija: {name}",
            "ToolDispatcher",
            args=args,
        ))


def _start_chat_worker(ctrl, message: str, fallback_reason: str = "", provider: str = "") -> None:
    """Pokreće standardni ChatWorker za plain chat odgovor."""
    from gui.tabs.agent.widgets.chat_worker import ChatWorker
    chat = ctrl.view.get_chat_panel()
    memory_service = chat.get_memory_service()

    _audit_routing("plain_chat", source="_start_chat_worker", fallback_reason=fallback_reason, provider=provider)
    chat.add_activity("💬 Šaljem upit AI-u...")
    chat.show_typing_indicator()

    worker = ChatWorker(message, draft=ctrl.draft, parent=ctrl.view,
                        memory_service=memory_service)
    worker.stream_started.connect(chat.start_streaming)
    worker.token_received.connect(chat.append_stream_token)
    worker.response_ready.connect(lambda _: chat.finalize_streaming())
    worker.response_ready.connect(
        lambda text: (
            ctrl.budget.estimate_output(text),
            ctrl._check_budget_after_response(),
        )
    )
    worker.error_occurred.connect(lambda _: chat.cancel_streaming())
    worker.error_occurred.connect(lambda _: chat.hide_typing_indicator())
    worker.error_occurred.connect(lambda err: chat.add_agent_message(f"⚠️ {err}"))
    worker.finished.connect(worker.deleteLater)
    worker.start()

    if not hasattr(ctrl, '_chat_workers'):
        ctrl._chat_workers = []
    ctrl._chat_workers.append(worker)
    worker.finished.connect(
        lambda: ctrl._chat_workers.remove(worker) if worker in ctrl._chat_workers else None
    )


# ── Regex fallback (postojeći kod, koristi se kad Tool Use nije dostupan) ──
# Vidi: docs/decisions/002-tool-dispatcher-integration.md
# OVAJ KOD ĆE BITI UKLONJEN u Fazi 3 refaktoringa.

def _handle_message_regex_fallback(ctrl, message: str) -> None:
    """
    Fallback: regex keyword routing + IntentClassifier + ChatWorker.
    Koristi se samo kad ToolDispatcherWorker vrati error.
    """
    from gui.tabs.agent.widgets.chat_worker import ChatWorker, check_injection

    _audit_routing("regex_fallback", source="_handle_message_regex_fallback")
    chat = ctrl.view.get_chat_panel()
    msg = message.lower().strip()

    if _missing_invoice_field_from_context(ctrl, message):
        return

    origin_query = _extract_origin_product_query(message)
    if origin_query:
        _pretrazi_porijeklo(ctrl, origin_query)
        return

    # Redni brojevi na srpskom
    _has_ordinal = any(w in msg for w in _REDNI)
    _has_specific_items = bool(re.search(r'\b\d+\b', msg)) or _has_ordinal

    _upit_kw = ['koji je', 'koja je', 'koje je', 'koji su', 'koje su',
                'šta je', 'sta je', 'što je', 'sto je',
                'kakav je', 'kakva je', 'koliki je', 'kolika je',
                'pogledaj', 'pokaži', 'pokazi', 'prikaži', 'prikazi',
                'reci mi', 'kaži mi', 'kazi mi', 'napiši mi',
                'provjeri', 'provjeru', 'analiz', 'obrazloži']
    _is_query = any(kw in msg for kw in _upit_kw)

    # --- UPIS u kolonu ---
    _upis_glagoli = ['upiši', 'upisi', 'upisite', 'upišite', 'postavi', 'stavi', 'set', 'unesite', 'unesi']
    _upis_prijedlozi = ['u kolonu', 'u polje', 'u kolone', 'u tab', 'u faktur', 'u naim',
                        'u rubrik', 'na kolonu', 'za kolonu']
    _has_upis = any(g in msg for g in _upis_glagoli)
    _has_prijedlog = any(p in msg for p in _upis_prijedlozi)
    _has_postavi = 'postavi' in msg or ('stavi' in msg and ('na' in msg or 'u' in msg))
    _brisanje_kolone_kw = ['izbri', 'obri', 'ukloni', 'resetuj', 'ocisti', 'očisti',
                           'brisi', 'briši', 'prazni', 'isprazni']
    _has_brisanje_kolone = any(g in msg for g in _brisanje_kolone_kw)
    _kolone_naim = ['povlastic', 'zemlja', 'procedur', 'pakovan', 'rubrik', 'naim',
                    'preference', 'origin', 'oznake']
    _has_naim_kolona = any(k in msg for k in _kolone_naim)

    if (_has_upis and _has_prijedlog) or _has_postavi:
        result = ctrl._parse_upis_u_kolonu(message)
        if result:
            kolona, vrijednost, tab = result
            ctrl._upisi_u_kolonu(kolona, vrijednost, tab)
            return
    elif _has_brisanje_kolone and _has_naim_kolona and 'tarif' not in msg:
        result = ctrl._parse_upis_u_kolonu(message, brisanje=True)
        if result:
            kolona, _, tab = result
            ctrl._upisi_u_kolonu(kolona, '', tab)
            return

    # --- ZAPAMTI TARIFNI ---
    _zapamti_match = re.search(
        r'(?:zapamti|nauci|nauči|snimi|upamti|sacuvaj|sačuvaj|dodaj u bazu)\s+'
        r'(\d[\d\.\s]{5,12})\s+za\s+(.{3,60})',
        msg,
    )
    if _zapamti_match:
        _tariff_raw = _zapamti_match.group(1).strip()
        _naziv_raw = _zapamti_match.group(2).strip().rstrip('?! ')
        ctrl.tariff_svc.learn_tariff(_naziv_raw, _tariff_raw)
        return

    # --- FILTRIRANI TARIF ---
    _filter_tariff_match = re.search(
        r'(?:pogledaj|nađi|trazi|traži).{0,40}?(\w{3,})\s+upiši\s+(?:te\s+)?tarif'
        r'|upiši\s+(?:te\s+)?tarif\w*\s+za\s+(\w+)'
        r'|(\w+)\s+upiši\s+(?:te\s+)?tarif',
        msg
    )
    if _filter_tariff_match:
        keyword = next(g for g in _filter_tariff_match.groups() if g)
        _skip = {'te', 'sve', 'koji', 'koje', 'ovi', 'ove', 'tarif', 'tarifne', 'broj'}
        if keyword not in _skip and len(keyword) >= 3:
            ctrl._predlozi_tarifne_po_filteru(keyword)
            return

    # --- ANALIZA TARIFNIH vs HISTORIJA ---
    _analiza_kw = ('analiziraj tarif', 'analiza tarif', 'historij tarif', 'historija tarif',
                   'istorij tarif', 'uporedi tarif', 'uporeди tarif', 'konzistentni tarif',
                   'provjeri tarif.*historij', 'tarif.*istorij', 'tarif.*ranij')
    if any(kw in msg for kw in _analiza_kw) or (
        'tarif' in msg and any(w in msg for w in ('historij', 'istorij', 'ranij', 'analiz', 'konzistent'))
    ):
        _analiziraj_tarifne_historiju(ctrl)
        return

    similar_query = _extract_similar_product_query(message)
    if similar_query:
        _pronadji_slicne_proizvode(ctrl, similar_query)
        return

    # --- PROVJERI TARIF ZA KONKRETAN NAZIV ---
    _provjeri_tarif_match = re.search(
        r'(?:provjeri|testiraj|predloži|predlozi|traži|trazi|koji\s+je|kakav\s+je|daj)'
        r'(?:\s+\w+){0,4}\s+za\s+(.+)',
        msg
    )
    if _provjeri_tarif_match and 'tarif' not in msg:
        _provjeri_tarif_match = None
    if _provjeri_tarif_match:
        _uhvaceno = _provjeri_tarif_match.group(1).strip()
        if any(w in _uhvaceno for w in ['naim', 'stavk', 'prvo', 'drugi', 'treć']):
            _provjeri_tarif_match = None
    if _provjeri_tarif_match:
        naziv = _provjeri_tarif_match.group(1).strip().rstrip('?!')
        if naziv and len(naziv) >= 3:
            ctrl._provjeri_tarifni_za_naziv(naziv)
            return

    # --- PRETRAGA CARINSKE TARIFE ---
    _tarifa_pretrazi_match = re.search(
        r'(?:pretra[žz]i?|na[đd]i?|trazi|traži)\s+tarif[ua]\s+(?:za\s+)?(.+)'
        r'|(?:šta|sta|što|sto|koji|koja)\s+(?:je\s+)?tarif[ua]\s+(?:za\s+)?(.+)'
        r'|tarif[ua]\s+(?:za\s+|broj\s+)?(.+)',
        msg
    )
    _tarifa_kod_match = re.search(
        r'(?:provjeri|validir|pokaži|pokazi)\s+(?:tarifn[ui]\s+)?(?:kod\s+|broj\s+|oznaku\s+)?(\d{8,10})',
        msg
    )
    _tarifa_poglavlje_match = re.search(r'(?:poglavlje|odjeljak|glava)\s+(\d{1,2})', msg)

    if _tarifa_kod_match:
        _pretrazi_tarifu_po_kodu(ctrl, _tarifa_kod_match.group(1))
        return
    elif _tarifa_poglavlje_match:
        _pretrazi_tarifu_poglavlje(ctrl, _tarifa_poglavlje_match.group(1))
        return
    elif _tarifa_pretrazi_match:
        upit = next(g for g in _tarifa_pretrazi_match.groups() if g)
        upit = upit.strip().rstrip('?!')
        if upit and len(upit) >= 2:
            _pretrazi_tarifu(ctrl, upit)
            return

    # --- HIJERARHIJSKI PRIKAZ TARIFE ---
    _tree_kw = ['pokaži', 'pokazi', 'šta je', 'sta je', 'pregledaj', 'pregled',
                'hijerarh', 'drvo', 'stabla', 'drill', 'razradi', 'pogledaj',
                'nivo', 'nivou', 'struktura', 'hijerarhija']
    _has_tree_kw = any(kw in msg for kw in _tree_kw)
    _tariff_code_match = re.search(r'\b(\d{2,10})\b', msg)
    _tariff_code_from_msg = _tariff_code_match.group(1) if _tariff_code_match else None

    if _has_tree_kw and _tariff_code_from_msg and len(_tariff_code_from_msg) >= 2:
        _pretrazi_tarifu_hijerarhijski(ctrl, _tariff_code_from_msg)
        return

    # --- PRIJEDLOG TARIFNOG ZA NAIM/STAVKU ---
    _predlozi_kw = ['predloži', 'predlozi', 'prijedlog', 'predloži mi', 'predlozi mi',
                    'daj tarif', 'koji tarif', 'kakav tarif']
    _has_predlozi_tarif_naim = (
        any(kw in msg for kw in _predlozi_kw)
        and 'tarif' in msg
        and ('naim' in msg or 'stavk' in msg)
    )
    if _has_predlozi_tarif_naim:
        _ptn_digit = re.search(r'(?:naim\w*|stavk\w*)\s*\.?\s*(\d+)', msg)
        if _ptn_digit:
            _alternativni_tarifni_za_stavku(ctrl, item_ordinal=int(_ptn_digit.group(1)))
        elif _has_ordinal:
            _p_ord = next((v for k, v in _REDNI.items() if k in msg and v > 0), None)
            _alternativni_tarifni_za_stavku(ctrl, item_ordinal=_p_ord)
        else:
            _ptn_za = re.search(r'za\s+([a-zšđčćžA-ZŠĐČĆŽ][^,?!\n]{2,40})', msg)
            _naziv = _ptn_za.group(1).strip() if _ptn_za else ""
            _alternativni_tarifni_za_stavku(ctrl, item_query=_naziv)
        return

    # --- BRISANJE TARIFNIH BROJEVA ---
    _brisanje_glagoli = ['izbri', 'obri', 'ukloni', 'resetuj', 'ocisti', 'očisti',
                         'brisi', 'briši', 'delete', 'clear', 'prazni', 'isprazni']
    _has_brisanje = any(g in msg for g in _brisanje_glagoli)
    _has_tarif = 'tarif' in msg
    if _has_brisanje and _has_tarif:
        ctrl._obrisi_tarifne_brojeve()
        return

    # --- ALTERNATIVNI TARIFNI ---
    _alt_tariff_signals = [
        'drugi tarif', 'drugu tarifu', 'alternativni tarif', 'alternativnu tarifu',
        'nije tačan tarif', 'nije tacna tarif', 'pogrešan tarif', 'pogresan tarif',
        'nije dobar tarif', 'krivi tarif', 'promijeni tarif', 'drugačiji tarif',
        'drukciji tarif', 'ispravi tarif', 'ispravni tarif', 'preispitaj tarif',
    ]
    _is_alt_tariff = (
        any(sig in msg for sig in _alt_tariff_signals)
        or ('alternativ' in msg and 'tarif' in msg)
        or ('drugi' in msg and 'tarif' in msg and ('za' in msg or _has_specific_items))
    )
    if _is_alt_tariff:
        _alt_name_match = re.search(r'za\s+["\']?([a-zšđčćžA-ZŠĐČĆŽ0-9][^,?!\n]{2,50})', msg)
        _alt_quote_match = re.search(r'["\'](.{3,50})["\']', msg)
        item_q = ""
        item_ord = None
        if _alt_quote_match:
            item_q = _alt_quote_match.group(1).strip()
        elif _alt_name_match:
            item_q = _alt_name_match.group(1).strip().rstrip('?! ')
        _alt_ord_match = re.search(r'(?:stavk[ue]?|naim\w*|rb\.?|redni\s+br\.?)\s+(\d+)', msg)
        if _alt_ord_match:
            item_ord = int(_alt_ord_match.group(1))
        if item_ord is None and _has_ordinal:
            for _ord_word, _ord_num in _REDNI.items():
                if _ord_word in msg and _ord_num > 0:
                    item_ord = _ord_num
                    break
        _alternativni_tarifni_za_stavku(ctrl, item_query=item_q, item_ordinal=item_ord, is_alt=True)
        return

    # --- PREGLED TRENUTNIH TARIFNIH BROJEVA ---
    _pregled_tarifa_kw = [
        'pregledaj tarif', 'pregled tarif', 'pokaži tarif', 'pokazi tarif',
        'prikaži tarif', 'prikazi tarif', 'lista tarif', 'izlistaj tarif',
        'koji su tarif', 'koje tarif', 'trenutni tarif', 'uneseni tarif',
        'koji su uneseni tarif', 'šta ima tarif', 'sta ima tarif',
    ]
    if any(kw in msg for kw in _pregled_tarifa_kw):
        _prikaz_tarifnih_trenutnih(ctrl)
        return

    # --- BATCH TARIFNI PRIJEDLOZI ---
    _generalni_tarif_kw = [
        'popuni tarif', 'nađi sve bez tarif', 'nađi stavke bez tarif',
        'predloži sve tarif', 'predlozi sve tarif',
        'predloži tarif za sve', 'predlozi tarif za sve',
        'predloži mi sve tarif', 'predlozi mi sve tarif',
        'auto tarif', 'batch tarif',
        'tarifne brojeve za sve', 'tarifne za sve',
        'tarifne brojeve za stavke', 'tarifne za stavke',
        'stavke koje nemaju tarif', 'stavke bez tarif',
        'koje nemaju tarifni', 'nemaju tarifni',
        # "provjeri tarifne" — "provjeri" lažno udara u _is_query pa ga eksplicitno hvatamo ovdje
        'provjeri tarifne', 'provjeri tarifni', 'provjeri tarifu',
        'validiraj tarifne', 'validiraj tarifni',
        'provjera tarifnih', 'provjera tarifn',
    ]
    if any(kw in msg for kw in _generalni_tarif_kw):
        ctrl._predlozi_tarifne_brojeve()
        return
    elif any(kw in msg for kw in ['tarif', 'tarifn']):
        # Sve tarif-vezane poruke koje ne pogode eksplicitni keyword
        # idu kroz IntentClassifier — razumije slobodan tekst i razne varijante
        _klasificiraj_i_usmjeri(ctrl, message)
        return

    # --- PREGLED I VALIDACIJA NAIMENOVANJA ---
    _pregled_kw = [
        'pregledaj naim', 'pregled naim', 'prikaži naim', 'prikazi naim',
        'pokaži naim', 'pokazi naim', 'sva naimenovanja', 'sva naim',
        'detalji naim', 'detaljno naim', 'kompletno naim',
        'provjeri naim', 'provjera naim', 'validacija naim', 'validiraj naim',
        'da li su naimenovanja popunjen', 'da li su naim popunjen',
        'šta fali u naim', 'sta fali u naim', 'nedostaje u naim',
        'prazne rubrike', 'prazna polja naim', 'nepopunjene rubrike',
    ]
    if any(kw in msg for kw in _pregled_kw):
        if any(kw in msg for kw in ['provjer', 'valid', 'da li su', 'šta fali', 'sta fali',
                                    'nedostaje', 'prazn', 'nepopunjene']):
            _provjeri_naimenovanja(ctrl)
            return
        _naim_indices = [int(m) for m in re.findall(r'\b(\d+)\b', msg)
                         if 1 <= int(m) <= len(getattr(ctrl.draft, 'items', [])) + 5]
        _naim_ordinal = [_REDNI.get(w) for w in msg.split() if w in _REDNI]
        combined_indices = list(dict.fromkeys(_naim_indices + [x for x in _naim_ordinal if x]))
        if combined_indices:
            _pregledaj_naimenovanja(ctrl, combined_indices)
        else:
            _pregledaj_naimenovanja(ctrl)
        return

    # --- SPAJANJE NAIMENOVANJA ---
    _spajanje_kw = ['spoji naim', 'merge naim', 'grupiš naim', 'objedini naim',
                    'spoji naimenovanj', 'objedini naimenovanj', 'grupiši naimenovanj']
    if any(kw in msg for kw in _spajanje_kw) and not _has_specific_items:
        ctrl._predlozi_spajanje_naimenovanja()
        return

    # --- COMPLIANCE CHECK ---
    _compliance_kw = [
        'provjeri deklaraciju', 'provjera deklaracije', 'da li je sve u redu',
        'compliance', 'kompletnost', 'provjeri sve', 'validacija deklaracije',
        'šta nedostaje', 'sta nedostaje', 'greške u deklaraciji', 'pregled deklaracije',
    ]
    if any(kw in msg for kw in _compliance_kw):
        _compliance_check(ctrl)
        return

    # --- TOKEN BUDGET provjera ---
    budget_status, budget_msg = ctrl.budget.check()
    if budget_status == 'stop':
        chat.add_agent_message(budget_msg)
        return
    if budget_status == 'warn':
        chat.add_activity(budget_msg)

    ctrl.budget.estimate_input(message)

    # --- STANDARDNI LLM odgovor ---
    chat.add_activity("💬 Šaljem upit AI-u...")
    chat.show_typing_indicator()

    memory_service = chat.get_memory_service()

    from gui.tabs.agent.widgets.chat_worker import ChatWorker
    worker = ChatWorker(message, draft=ctrl.draft, parent=ctrl.view,
                        memory_service=memory_service)
    worker.stream_started.connect(chat.start_streaming)
    worker.token_received.connect(chat.append_stream_token)
    worker.response_ready.connect(lambda _: chat.finalize_streaming())
    worker.response_ready.connect(
        lambda text: (
            ctrl.budget.estimate_output(text),
            ctrl._check_budget_after_response(),
        )
    )
    worker.error_occurred.connect(lambda _: chat.cancel_streaming())
    worker.error_occurred.connect(lambda _: chat.hide_typing_indicator())
    worker.error_occurred.connect(lambda err: chat.add_agent_message(f"⚠️ {err}"))
    worker.finished.connect(worker.deleteLater)
    worker.start()

    if not hasattr(ctrl, '_chat_workers'):
        ctrl._chat_workers = []
    ctrl._chat_workers.append(worker)
    worker.finished.connect(
        lambda: ctrl._chat_workers.remove(worker) if worker in ctrl._chat_workers else None
    )


def _alternativni_tarifni_za_stavku(ctrl, item_query: str = "",
                                     item_ordinal: int = None,
                                     is_alt: bool = False) -> None:
    from PySide6.QtCore import QThread, Signal as _Signal

    chat = ctrl.view.get_chat_panel()

    if not ctrl.draft:
        chat.add_agent_message("⚠️ Nema učitanog drafta.")
        return

    naim_items = getattr(ctrl.draft, 'items', [])
    invoice_lines = getattr(ctrl.draft, 'invoice_lines', [])

    item_name = ""
    current_tariff = ""
    zemlja = ""
    iznos = 0.0
    found = False

    # 1. Naim po rednom broju
    if item_ordinal is not None and naim_items:
        for it in naim_items:
            if getattr(it, 'ordinal_no', None) == item_ordinal:
                item_name = getattr(it, 'goods_description', '') or ""
                current_tariff = getattr(it, 'tariff_code', '') or ""
                zemlja = getattr(it, 'origin_country_code', '') or ""
                found = True
                break

    # 2. Faktura linije po rednom broju
    if not found and item_ordinal is not None and invoice_lines:
        idx = item_ordinal - 1
        if 0 <= idx < len(invoice_lines):
            l = invoice_lines[idx]
            item_name = getattr(l, 'naziv_robe', '') or ""
            current_tariff = getattr(l, 'tarifni_broj', '') or ""
            zemlja = getattr(l, 'zemlja_porijekla', '') or ""
            iznos = getattr(l, 'iznos', 0) or 0
            found = True

    # 3. Fuzzy match po nazivu
    if not found and item_query:
        query_words = [w for w in re.findall(
            r'[a-zšđčćžA-ZŠĐČĆŽ0-9]{3,}', item_query.lower()
        )]
        best_hits = 0
        for it in naim_items:
            naziv = (getattr(it, 'goods_description', '') or '').lower()
            hits = sum(1 for w in query_words if w in naziv)
            if hits > best_hits:
                best_hits = hits
                item_name = getattr(it, 'goods_description', '') or ""
                current_tariff = getattr(it, 'tariff_code', '') or ""
                zemlja = getattr(it, 'origin_country_code', '') or ""
                found = True
        if not found or best_hits == 0:
            for l in invoice_lines:
                naziv = (getattr(l, 'naziv_robe', '') or '').lower()
                hits = sum(1 for w in query_words if w in naziv)
                if hits > best_hits:
                    best_hits = hits
                    item_name = getattr(l, 'naziv_robe', '') or ""
                    current_tariff = getattr(l, 'tarifni_broj', '') or ""
                    zemlja = getattr(l, 'zemlja_porijekla', '') or ""
                    iznos = getattr(l, 'iznos', 0) or 0
                    found = True
        if found and best_hits == 0:
            found = False

    if not found:
        if item_query:
            chat.add_agent_message(
                f"⚠️ Nisam pronašao stavku <b>'{item_query}'</b>. "
                f"Pokušaj navesti tačniji naziv ili redni broj."
            )
        elif item_ordinal:
            chat.add_agent_message(
                f"⚠️ Naimenovanje/stavka broj <b>{item_ordinal}</b> nije pronađena u draftu."
            )
        else:
            chat.add_agent_message(
                "⚠️ Navedi naziv robe ili redni broj, npr: "
                "<i>alternativni tarif za startno uže</i> ili "
                "<i>u prvom naimenovanju je pogrešan tarif</i>"
            )
        return

    if not item_name:
        item_name = item_query or f"stavka {item_ordinal}"

    chat.add_activity(f"🔍 Tražim alternative za: {item_name[:60]}...")
    chat.show_typing_indicator()

    _item_name = item_name
    _current_tariff = current_tariff
    _zemlja = zemlja
    _iznos = iznos
    _is_alt = is_alt

    # ═══════════════════════════════════════════════════════════
    # region — _AltTariffWorker
    # ═══════════════════════════════════════════════════════════

    class _AltTariffWorker(QThread):
        token_received = _Signal(str)
        stream_started = _Signal()
        response_ready = _Signal(str)
        error_occurred = _Signal(str)

        def run(self_):
            try:
                from gui.tabs.agent.widgets.llm_provider import LLMProvider, parse_llm_error
                zemlja_str_ = f" (zemlja porijekla: {_zemlja})" if _zemlja else ""
                if _current_tariff and _is_alt:
                    user_msg = (
                        f'Roba: "{_item_name}"{zemlja_str_}\n'
                        f'Postojeći tarif {_current_tariff} nije tačan.\n'
                        f'Predloži 4-5 ispravnijih HS tarifnih brojeva iz RAZLIČITIH poglavlja — '
                        f'razmotri materijal (plastika, sintetička vlakna, čelik, guma), '
                        f'funkciju i upotrebu robe.'
                    )
                else:
                    user_msg = (
                        f'Roba: "{_item_name}"{zemlja_str_}\n'
                        f'Predloži 4-5 HS tarifnih brojeva iz RAZLIČITIH poglavlja — '
                        f'razmotri materijal (plastika, sintetička vlakna, čelik, guma), '
                        f'funkciju i upotrebu robe.'
                    )
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Si stručnjak za HS carinsku nomenklaturu (Harmonizovani sistem, BiH tarifa). "
                            "PRAVILA:\n"
                            "1. Uvijek razmotri materijal (plastika, sintetička vlakna, čelik, guma...), "
                            "funkciju i upotrebu — ne samo doslovan prijevod naziva.\n"
                            "2. Predloži opcije iz RAZLIČITIH poglavlja HS-a — "
                            "ne fokusiraj se na jedno poglavlje.\n"
                            "3. Tarifni broj = 8 cifara bez tačaka.\n"
                            "Format, svaka opcija u novom redu:\n"
                            "**XXXXXXXX** — [naziv iz HS tarife] — [materijal/upotreba zašto odgovara]"
                        )
                    },
                    {"role": "user", "content": user_msg},
                ]
                provider = LLMProvider()
                self_.stream_started.emit()
                full = ""
                for token in provider.stream_chat(messages, max_tokens=400):
                    full += token
                    self_.token_received.emit(token)
                self_.response_ready.emit(full.strip())
            except Exception as e:
                from gui.tabs.agent.widgets.llm_provider import parse_llm_error
                self_.error_occurred.emit(parse_llm_error(e))

    worker = _AltTariffWorker(parent=ctrl.view)
    worker.stream_started.connect(chat.start_streaming)
    worker.token_received.connect(chat.append_stream_token)
    worker.response_ready.connect(lambda _: chat.finalize_streaming())
    worker.response_ready.connect(
        lambda text: (
            ctrl.budget.estimate_output(text),
            ctrl._check_budget_after_response(),
        )
    )
    worker.error_occurred.connect(lambda _: chat.cancel_streaming())
    worker.error_occurred.connect(lambda _: chat.hide_typing_indicator())
    worker.error_occurred.connect(lambda err: chat.add_agent_message(f"⚠️ {err}"))
    worker.finished.connect(worker.deleteLater)
    worker.start()

    if not hasattr(ctrl, '_chat_workers'):
        ctrl._chat_workers = []
    ctrl._chat_workers.append(worker)
    worker.finished.connect(
        lambda: ctrl._chat_workers.remove(worker) if worker in ctrl._chat_workers else None
    )


def _klasificiraj_i_usmjeri(ctrl, message: str) -> None:
    from PySide6.QtCore import QThread, Signal

    chat = ctrl.view.get_chat_panel()
    chat.add_activity("🤔 Analiziram šta tražiš...")

    # ═══════════════════════════════════════════════════════════
    # region — _ClassifierWorker (glavna implementacija svih handlera)
    # ═══════════════════════════════════════════════════════════

    class _ClassifierWorker(QThread):
        done = Signal(object)

        def __init__(self_, msg, dft):
            super().__init__()
            self_._msg = msg
            self_._dft = dft

        def run(self_):
            from services.agent.chat.intent_classifier import IntentClassifier
            clf = IntentClassifier()
            summary = IntentClassifier.build_draft_summary(self_._dft)
            result = clf.classify(self_._msg, summary)
            self_.done.emit(result)

    worker = _ClassifierWorker(message, ctrl.draft)

    def _on_classified(result):
        logger.debug(
            f"[IntentClassifier] intent={result.intent} "
            f"item_query={result.item_query!r} ordinal={result.item_ordinal}"
        )
        if result.intent == "ALT_TARIFF":
            _alternativni_tarifni_za_stavku(
                ctrl,
                item_query=result.item_query,
                item_ordinal=result.item_ordinal,
                is_alt=True,
            )
        elif result.intent == "SINGLE_TARIFF" and result.item_query:
            ctrl._provjeri_tarifni_za_naziv(result.item_query)
        elif result.intent == "BATCH_TARIFF":
            ctrl._predlozi_tarifne_brojeve()
        else:
            from gui.tabs.agent.widgets.chat_worker import ChatWorker
            memory_service = chat.get_memory_service()
            cw = ChatWorker(message, draft=ctrl.draft, parent=ctrl.view,
                            memory_service=memory_service)
            cw.stream_started.connect(chat.start_streaming)
            cw.token_received.connect(chat.append_stream_token)
            cw.response_ready.connect(lambda _: chat.finalize_streaming())
            cw.error_occurred.connect(lambda _: chat.cancel_streaming())
            cw.error_occurred.connect(lambda _: chat.hide_typing_indicator())
            cw.error_occurred.connect(lambda e: chat.add_agent_message(f"⚠️ {e}"))
            cw.finished.connect(cw.deleteLater)
            cw.start()

    worker.done.connect(_on_classified)
    worker.finished.connect(worker.deleteLater)
    worker.start()

    if not hasattr(ctrl, '_classifier_workers'):
        ctrl._classifier_workers = []
    ctrl._classifier_workers.append(worker)
    worker.finished.connect(
        lambda: ctrl._classifier_workers.remove(worker)
        if worker in ctrl._classifier_workers else None
    )


def _provjeri_naimenovanja(ctrl) -> None:
    """
    Provjera popunjenosti naimenovanja — prikazuje SAMO obavezne probleme.
    Opciona polja su opciona — ne prikazuju se pojedinačno.
    """
    from services.agent.validation.naimenovanja_review_service import NaimenovanjaReviewService

    chat = ctrl.view.get_chat_panel()

    if not ctrl.draft or not ctrl.draft.items:
        chat.add_agent_message("⚠️ Nema kreiranih naimenovanja u deklaraciji.")
        return

    naim_items = ctrl.draft.items
    chat.add_activity(f"🔍 Provjeravam {len(naim_items)} naimenovanja...")

    result = NaimenovanjaReviewService.provjeri_naimenovanja(naim_items)

    # Filtriraj: samo naimenovanja sa OBAVEZNIM praznim rubrikama
    problematic = [p for p in result['problemi'] if p.prazne_obavezne]

    if not problematic:
        # Nema praznih obaveznih — sve je u redu
        opcioni_msg = ""
        if result['total_praznih_opcionih'] > 0:
            opcioni_msg = (
                f"<br><small style='color:grey'>"
                f"({result['total_praznih_opcionih']} opcionih polja prazno — "
                f"opciona polja nisu obavezna)"
                f"</small>"
            )
        chat.add_agent_message(
            f"✅ <b>Sva {result['total_naim']} naimenovanja su uredno popunjena!</b>"
            f"{opcioni_msg}"
        )
        return

    # Prikaži SAMO problematična naimenovanja (ona sa praznim obaveznim)
    linije = []
    for p in problematic:
        tarif = p.tariff_code if p.tariff_code and p.tariff_code != '?' else "nema tarife"
        linije.append(
            f"❌ <b>Naim. {p.ordinal_no}</b> (tarifa: {tarif})<br>"
            f"&nbsp;&nbsp;Nedostaje: {', '.join(p.prazne_obavezne)}"
        )

    msg = (
        f"📋 <b>Provjera naimenovanja — {len(problematic)}/{result['total_naim']} "
        f"sa problemima:</b><br><br>"
        + "<br><br>".join(linije)
    )

    if result['total_praznih_opcionih'] > 0:
        msg += (
            f"<br><br><small style='color:grey'>"
            f"ℹ️ {result['total_praznih_opcionih']} opcionih polja prazno "
            f"({result['total_naim'] - len(problematic)} naim. nema obaveznih praznih polja)."
            f"</small>"
        )

    chat.add_agent_message(msg)


def _prikaz_tarifnih_trenutnih(ctrl) -> None:
    """
    Istorijska validacija tarifa — za svaku stavku traži istorijski odobreni
    tarif iz XML deklaracija i predlaže ga ako je razlicit od trenutnog.
    """
    chat = ctrl.view.get_chat_panel()
    lines = getattr(ctrl.draft, 'invoice_lines', []) if ctrl.draft else []
    if not lines:
        chat.add_agent_message("Nema učitanih stavki — učitaj fakturu prvo.")
        return

    chat.add_activity(f"Pretražujem istoriju za {len(lines)} stavki...")

    try:
        from services.agent.validation.historical_tariff_search_service import (
            HistoricalTariffSearchService,
        )
        from gui.tabs.agent.widgets.tariff_validation_dialog import TariffValidationDialog

        izvoznik = getattr(ctrl.draft, 'izvoznik_naziv', '') or ''
        primalac = getattr(ctrl.draft, 'primalac_naziv', '') or ''

        svc = HistoricalTariffSearchService()
        matches = svc.validate_lines(lines, izvoznik_naziv=izvoznik, uvoznik_naziv=primalac)
        auto_applied = getattr(svc, 'last_auto_applied', [])
        if auto_applied and hasattr(ctrl, '_refresh_faktura_tab'):
            ctrl._refresh_faktura_tab()

        if not matches:
            chat.add_agent_message(
                "Istorijska validacija zavrsena — svi tarifni brojevi se "
                "podudaraju sa bazom znanja ili nema istorijskih podataka za te stavke."
            )
            return

        parent_widget = getattr(ctrl.view, 'window', lambda: None)()
        dlg = TariffValidationDialog(matches, parent=parent_widget)

        # Kad korisnik prihvati → upisi u draft i osvjezi Faktura tab
        def _on_accepted(changes: list):
            for idx, tarif in changes:
                if 0 <= idx < len(ctrl.draft.invoice_lines):
                    ctrl.draft.invoice_lines[idx].tarifni_broj = tarif
            if hasattr(ctrl, '_refresh_faktura_tab'):
                ctrl._refresh_faktura_tab()
            # Sinhronizuj decision_state nakon istorijske validacije
            try:
                from services.decision.integration import sync_decision_state_after_autofill
                changed_lines = [
                    ctrl.draft.invoice_lines[idx] for idx, _ in changes
                    if 0 <= idx < len(ctrl.draft.invoice_lines)
                ]
                if changed_lines:
                    sync_decision_state_after_autofill(changed_lines, action_type="dialog_confirmed")
            except Exception:
                logger.warning("Decision sync istorijska validacija nije uspela", exc_info=True)

        dlg.tariffs_accepted.connect(_on_accepted)
        dlg.show()

        chat.add_agent_message(
            f"Istorijska validacija: <b>{len(matches)} stavki</b> ima drugaciji "
            f"istorijski tarif. Detalji u otvorenom prozoru."
        )
        chat.add_activity(
            f"Istorijska validacija: {len(matches)} prijedloga"
        )

    except Exception as e:
        chat.add_agent_message(f"Greska pri istorijskoj validaciji: {e}")


def _analiziraj_tarifne_historiju(ctrl) -> None:
    """Uporedi tarifne kodove u aktivnom draftu sa historijskim podacima."""
    chat = ctrl.view.get_chat_panel()
    chat.add_activity("📊 Analiziram tarifne brojeve u odnosu na istoriju...")
    try:
        from services.agent.chat.tariff_history_analysis_service import (
            analiziraj_tarifne_historiju,
        )
        html = analiziraj_tarifne_historiju(ctrl.draft)
        chat.add_agent_message(html)
    except Exception as e:
        logger.exception("Greška pri analizi tarifne historije")
        chat.add_agent_message(f"❌ Greška pri analizi: {escape(str(e))}")


def _pronadji_slicne_proizvode(ctrl, naziv: str) -> None:
    chat = ctrl.view.get_chat_panel()
    query = str(naziv or "").strip()
    if not query:
        chat.add_agent_message("⚠️ Navedi naziv robe za pretragu sličnih proizvoda.")
        return

    chat.add_activity("🔎 Tražim slične ranije proizvode u lokalnoj memoriji...")
    try:
        from services.agent.chat.similar_products_analysis_service import (
            render_similar_products_for_query,
        )

        html = render_similar_products_for_query(query)
        chat.add_agent_message(html)
    except Exception as e:
        logger.exception("Greška pri pretrazi sličnih proizvoda")
        chat.add_agent_message(f"❌ Greška pri pretrazi sličnih proizvoda: {escape(str(e))}")


def _pregled_stanja_aplikacije(ctrl, scope: str = "all") -> None:
    chat = ctrl.view.get_chat_panel()
    try:
        from services.agent.application_context_service import ApplicationContextService

        _get_conversation_context(ctrl)["last_app_scope"] = (scope or "all").lower()
        html = ApplicationContextService(ctrl.draft).format_html(scope)
        chat.add_agent_message(html)
    except Exception as e:
        logger.exception("Greška pri pregledu stanja aplikacije")
        chat.add_agent_message(f"❌ Greška pri pregledu stanja aplikacije: {escape(str(e))}")


def _provjeri_jedno_naimenovanje(ctrl, ordinal: int) -> None:
    from services.agent.validation.naimenovanja_review_service import NaimenovanjaReviewService

    chat = ctrl.view.get_chat_panel()
    item = _find_naimenovanje_by_ordinal(ctrl, ordinal)
    if not item:
        chat.add_agent_message(f"⚠️ Naimenovanje broj <b>{ordinal}</b> nije pronađeno.")
        return

    result = NaimenovanjaReviewService.provjeri_naimenovanja([item])
    problemi = result.get("problemi", [])
    problem = problemi[0] if problemi else None

    _remember_naimenovanje_context(ctrl, item)

    if not problem or not problem.prazne_obavezne:
        opcione = len(problem.prazne_opcione) if problem else 0
        suffix = (
            f"<br><small style='color:grey'>{opcione} opcionih polja je prazno.</small>"
            if opcione else ""
        )
        chat.add_agent_message(
            f"✅ <b>Naimenovanje Rb.{ordinal} nema praznih obaveznih rubrika.</b>{suffix}"
        )
        return

    missing = "<br>".join(f"• {escape(value)}" for value in problem.prazne_obavezne)
    chat.add_agent_message(
        f"⚠️ <b>Naimenovanje Rb.{ordinal} nije kompletno.</b><br>"
        f"Nedostaju obavezne rubrike:<br>{missing}"
    )


def _pregledaj_faktura_stavku(ctrl, ordinal: int) -> None:
    chat = ctrl.view.get_chat_panel()
    line = _find_invoice_line_by_ordinal(ctrl, ordinal)
    if not line:
        total = len(getattr(ctrl.draft, "invoice_lines", []) or []) if ctrl.draft else 0
        chat.add_agent_message(
            f"⚠️ Stavka broj <b>{ordinal}</b> ne postoji u Faktura tabu "
            f"(ukupno stavki: <b>{total}</b>)."
        )
        return

    naziv = getattr(line, "naziv_robe", "") or ""
    tariff = getattr(line, "tarifni_broj", "") or "—"
    country = getattr(line, "zemlja_porijekla", "") or "—"
    preference = getattr(line, "povlastica", "") or "—"
    invoice = getattr(line, "invoice_number", "") or "—"
    qty = getattr(line, "kolicina", 0) or 0
    unit = getattr(line, "jm", "") or ""
    amount = getattr(line, "iznos", 0) or 0
    currency = getattr(line, "valuta", "") or "EUR"
    gross = getattr(line, "bruto_kg", 0) or 0
    net = getattr(line, "neto_kg", 0) or 0
    assigned = getattr(line, "assigned_naimenovanje_ordinal", 0) or 0

    _remember_tariff_context(ctrl, tariff, product_name=naziv)
    _get_conversation_context(ctrl)["last_invoice_line_ordinal"] = ordinal

    chat.add_agent_message(
        f"<b>Faktura tab — stavka {ordinal}</b><br>"
        f"<b>Faktura:</b> {escape(str(invoice))}<br>"
        f"<b>Naziv robe:</b> {escape(str(naziv) or '—')}<br>"
        f"<b>Tarifni broj:</b> <code>{escape(str(tariff))}</code><br>"
        f"<b>Zemlja porijekla:</b> {escape(str(country))}<br>"
        f"<b>Povlastica:</b> {escape(str(preference))}<br>"
        f"<b>Količina:</b> {qty:g} {escape(str(unit))}<br>"
        f"<b>Iznos:</b> {amount:.2f} {escape(str(currency))}<br>"
        f"<b>Bruto/Neto:</b> {gross:.2f}/{net:.2f} kg"
        + (f"<br><b>Naimenovanje:</b> Rb.{assigned}" if assigned else "")
    )


def _upisi_tarifu_u_trenutnu_faktura_stavku(ctrl, tariff_code: str, save_mapping: bool = False) -> bool:
    chat = ctrl.view.get_chat_panel()
    code = _clean_tariff_code(tariff_code)
    if not code:
        return False

    ctx = _get_conversation_context(ctrl)
    ordinal = ctx.get("last_invoice_line_ordinal")
    if not ordinal:
        return False

    line = _find_invoice_line_by_ordinal(ctrl, int(ordinal))
    if not line:
        chat.add_agent_message(
            f"⚠️ Ne mogu upisati tarifni broj jer prethodno otvorena stavka {ordinal} više ne postoji."
        )
        return True

    product_name = _invoice_line_product_name(line) or f"stavka {ordinal}"
    line.tarifni_broj = code

    # Sinhronizuj decision_state nakon pojedinacnog upisa tarife
    try:
        from services.decision.integration import sync_decision_state_after_manual_edit
        from core.decision.decision_model import DecisionField
        sync_decision_state_after_manual_edit(line, DecisionField.TARIFF, code)
    except Exception:
        logger.warning("Decision sync single tariff nije uspeo", exc_info=True)

    _remember_tariff_context(ctrl, code, product_name=product_name)

    if hasattr(ctrl, "_refresh_faktura_tab"):
        ctrl._refresh_faktura_tab()
    elif getattr(ctrl, "tariff_svc", None) and getattr(ctrl.tariff_svc, "on_refresh_faktura", None):
        ctrl.tariff_svc.on_refresh_faktura()

    if save_mapping and getattr(ctrl, "tariff_svc", None):
        ctrl.tariff_svc.learn_tariff(product_name, code)
        chat.add_agent_message(
            f"✅ Tarifni broj <code>{escape(code)}</code> upisan je u Faktura tab, "
            f"stavka <b>{ordinal}</b>."
        )
    else:
        chat.add_agent_message(
            f"✅ Tarifni broj <code>{escape(code)}</code> upisan je u Faktura tab, "
            f"stavka <b>{ordinal}</b> — {escape(product_name)}."
        )
    return True


def _pregledaj_naimenovanja(ctrl, indeksi=None) -> None:
    from services.agent.validation.naimenovanja_review_service import NaimenovanjaReviewService

    chat = ctrl.view.get_chat_panel()

    if not ctrl.draft or not ctrl.draft.items:
        chat.add_agent_message("⚠️ Nema kreiranih naimenovanja u deklaraciji.")
        return

    naim_items = ctrl.draft.items

    if indeksi:
        items_to_show = []
        for i in indeksi:
            by_ordinal = next(
                (item for item in naim_items if getattr(item, "ordinal_no", None) == i),
                None,
            )
            if by_ordinal is not None:
                items_to_show.append(by_ordinal)
            elif 0 < i <= len(naim_items):
                items_to_show.append(naim_items[i - 1])
        naziv = f"Rb. {', '.join(str(i) for i in indeksi)}"
    else:
        items_to_show = naim_items
        naziv = f"sva {len(naim_items)} naimenovanja"

    if not items_to_show:
        chat.add_agent_message("⚠️ Naimenovanje sa tim rednim brojem ne postoji.")
        return

    chat.add_activity(f"📋 Pregledavam {naziv}...")

    linije = []
    for item in items_to_show:
        if len(items_to_show) == 1:
            _remember_naimenovanje_context(ctrl, item)
        pregled = NaimenovanjaReviewService.pregledaj_naimenovanje(item)
        rb = pregled.ordinal_no
        tarif = pregled.tariff_code or '⚠️ NEMA'
        zemlja = pregled.origin_country_code or '—'
        pov = pregled.preference_code or '—'
        proc = pregled.procedure_code or '—'

        opis_robe = (pregled.goods_description or '').strip() or '—'
        pak_kod = pregled.package_code or '—'
        pak_kol = pregled.package_qty or '—'
        oznake = (pregled.package_marks or '').strip() or '—'

        isprave = []
        for f_val in [pregled.attached_document1, pregled.attached_document2,
                      pregled.attached_document3, pregled.attached_document4,
                      pregled.attached_document5]:
            if f_val and f_val.strip():
                isprave.append(f_val.strip())
        isprave_str = ", ".join(isprave) if isprave else '—'

        bruto = pregled.gross_mass_kg or 0
        neto = pregled.net_mass_kg or 0
        iznos = pregled.item_value or 0
        valuta = pregled.currency or 'EUR'
        stat_vrijednost = pregled.statistical_value or 0
        dop_jed = pregled.supplementary_unit_code or ''
        dop_kol = pregled.supplementary_unit_qty or 0

        html = (
            f"<b>═══ Rb.{rb} ═══</b><br>"
            f"<b>Rb.31 — Pakovanje i opis:</b><br>"
            f"&nbsp;&nbsp;Opis robe: {opis_robe[:100]}<br>"
            f"&nbsp;&nbsp;Trgovački naziv: {(pregled.goods_trade_name or '—')[:50]}<br>"
            f"&nbsp;&nbsp;Oznake i br.: {oznake[:50]}<br>"
            f"&nbsp;&nbsp;Pakovanje: {pak_kod} × {pak_kol}<br>"
            f"<b>Rb.33 — Tarifni broj:</b> <code>{tarif}</code><br>"
            f"<b>Rb.34 — Zemlja porijekla:</b> {zemlja}<br>"
            f"<b>Rb.36 — Povlastica:</b> {pov}<br>"
            f"<b>Rb.37 — Postupak:</b> {proc}"
            f"{(' (prethodni: ' + pregled.procedure_prev_code + ')') if pregled.procedure_prev_code else ''}<br>"
            f"<b>Rb.35/38 — Mase:</b> Bruto {bruto:.3f} kg | Neto {neto:.3f} kg<br>"
            f"<b>Rb.41 — Dop.jedinice:</b> "
            f"{(str(dop_kol) + ' ' + str(dop_jed)) if dop_kol and dop_jed else '—'}<br>"
            f"<b>Rb.42 — Vrijednost:</b> {iznos:.2f} {valuta}<br>"
            f"<b>Rb.44 — Isprave:</b> {isprave_str}<br>"
            f"<b>Rb.46 — Stat.vrijednost:</b> {stat_vrijednost:.2f}<br>"
            f"<b>Rb.40 — Preth.dokumenti:</b> "
            f"{(pregled.previous_document or '—')}"
            f"{(', ' + pregled.previous_document2) if pregled.previous_document2 else ''}"
            f"{(', ' + pregled.previous_document3) if pregled.previous_document3 else ''}"
        )

        notes = (pregled.notes or '').strip()
        if notes:
            html += f"<br><b>Napomene:</b> {notes[:150]}"
        if pregled.source_invoice_refs:
            html += f"<br><b>Source fakture:</b> {', '.join(pregled.source_invoice_refs)}"

        linije.append(html)

    chat.add_agent_message("<br><br>".join(linije))


def _pretrazi_tarifu(ctrl, upit: str) -> None:
    chat = ctrl.view.get_chat_panel()
    chat.add_activity(f"🔍 Pretražujem tarifu za: {upit}")
    try:
        from services.tariff.tarifa_service import pretrazi, formatiraj_rezultate
        rezultati = pretrazi(upit, limit=10)
        html = formatiraj_rezultate(rezultati)
        chat.add_agent_message(
            f"<b>📋 Carinska tarifa 2026 — pretraga: '{upit}'</b><br><br>{html}"
            f"<br><br><small>Možeš pitati: <i>provjeri kod 3304990000</i> ili "
            f"<i>poglavlje 33</i></small>"
        )
    except Exception as e:
        chat.add_agent_message(f"❌ Greška pri pretrazi tarife: {e}")


def _display_origin_from_mcp(ctrl, chat, upit: str, mcp_result: dict) -> None:
    """Prikaži rezultate porijekla dobijene preko MCP servera."""
    origins = mcp_result.get("origins", [])
    if not origins:
        return

    zemlje = ", ".join(
        f"<b>{escape(o['country_code'])}</b> ({o['count']}x, {o['confidence']:.0%})"
        for o in origins[:5]
    )
    linije = []
    for o in origins[:8]:
        for ex in (o.get("examples") or [])[:2]:
            hs = ex.get("hs_code", "?")
            desc = escape((ex.get("commercial_desc") or "")[:70])
            linije.append(
                f"• <b>{escape(o['country_code'])}</b> — {desc} "
                f"<small>(tarifa {escape(hs)})</small>"
            )

    notes = mcp_result.get("notes", [])
    source_note = ""
    if notes:
        source_note = f"<br><small>Izvor: MCP server (PostgreSQL){' — ' + notes[0] if notes else ''}</small>"

    chat.add_agent_message(
        f"<b>🌍 Porijeklo proizvoda: '{escape(upit)}'</b><br><br>"
        f"Najčešće zemlje porijekla: {zemlje}.<br><br>"
        + "<br>".join(linije)
        + source_note
    )


def _pretrazi_porijeklo(ctrl, upit: str) -> None:
    # Docs: docs/sections/agent-origin-query-routing.md
    _remember_subject(ctrl, upit)
    chat = ctrl.view.get_chat_panel()
    chat.add_activity(f"🔍 Pretražujem porijeklo za: {upit}")

    # ── MCP server — probaj prvo centralizovanu pretragu ─────────────────
    try:
        from services.agent.mcp_facade import mcp_facade
        mcp_result = mcp_facade.find_product_origin(upit, limit=10)
        if mcp_result.get("found") and mcp_result.get("origins"):
            _display_origin_from_mcp(ctrl, chat, upit, mcp_result)
            return
    except Exception as e:
        logger.debug("[MCP] find_product_origin neuspješno: %s", e)

    # ── Lokalni SQLite indeks (fallback) ──────────────────────────────────
    try:
        from collections import Counter
        from services.agent.chat.declaration_search_service import DeclarationSearchService

        svc = DeclarationSearchService()
        rezultati = svc.search_by_goods(upit, limit=20)
        rezultati = [r for r in rezultati if (r.get("country_origin") or "").strip()]

        if not rezultati:
            _set_offered_action(ctrl, "search_archive", upit, "Pretraži lokalni arhiv")
            chat.add_agent_message(
                f"<b>🌍 Porijeklo proizvoda: '{escape(upit)}'</b><br><br>"
                "Nisam pronašao pouzdan zapis o zemlji porijekla u istorijskim XML deklaracijama. "
                "Neću predlagati tarifne brojeve za ovaj upit jer si tražio porijeklo, ne razvrstavanje robe.<br><br>"
                "Mogu dodatno pretražiti lokalni arhiv i bazu znanja za isti proizvod. "
                "Napiši <b>Pretraži</b> i nastaviću bez ponovnog pitanja."
            )
            return

        brojac = Counter((r.get("country_origin") or "").strip() for r in rezultati)
        zemlje = ", ".join(
            f"<b>{escape(zemlja)}</b> ({broj}x)"
            for zemlja, broj in brojac.most_common(5)
        )
        linije = []
        seen = set()
        for r in rezultati[:8]:
            key = (
                r.get("hs_code", ""),
                r.get("commercial_desc", "")[:40],
                r.get("country_origin", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            naziv = r.get("commercial_desc") or r.get("description") or ""
            linije.append(
                f"• <b>{escape(r.get('country_origin', ''))}</b> — "
                f"{escape(naziv[:70])} "
                f"<small>(tarifa {escape(r.get('hs_code', '') or '?')}, "
                f"povlastica {escape(r.get('preference', '') or '?')})</small>"
            )

        chat.add_agent_message(
            f"<b>🌍 Porijeklo proizvoda: '{escape(upit)}'</b><br><br>"
            f"U istorijskim deklaracijama najčešće se pojavljuje: {zemlje}.<br><br>"
            + "<br>".join(linije)
            + "<br><br><small>Izvor: lokalni indeks istorijskih XML deklaracija.</small>"
        )
    except Exception as e:
        chat.add_agent_message(f"❌ Greška pri pretrazi porijekla: {e}")


def _pretrazi_arhiv_za_proizvod(ctrl, upit: str) -> None:
    chat = ctrl.view.get_chat_panel()
    chat.add_activity(f"🔍 Pretražujem lokalni arhiv za: {upit}")
    try:
        from services.agent.chat.declaration_search_service import DeclarationSearchService

        svc = DeclarationSearchService()
        rezultati = svc.search_by_goods(upit, limit=12)

        if not rezultati:
            chat.add_agent_message(
                f"<b>🔎 Lokalni arhiv — pretraga: '{escape(upit)}'</b><br><br>"
                "Nisam pronašao isti ili dovoljno sličan proizvod u istorijskim XML deklaracijama."
            )
            return

        linije = []
        seen = set()
        for r in rezultati:
            key = (
                r.get("hs_code", ""),
                r.get("commercial_desc", "")[:45],
                r.get("country_origin", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            naziv = r.get("commercial_desc") or r.get("description") or ""
            linije.append(
                f"• <b>{escape(r.get('hs_code', '') or '?')}</b> — "
                f"{escape(naziv[:75])} "
                f"<small>(zemlja {escape(r.get('country_origin', '') or '?')}, "
                f"povlastica {escape(r.get('preference', '') or '?')})</small>"
            )
            if len(linije) >= 8:
                break

        chat.add_agent_message(
            f"<b>🔎 Lokalni arhiv — pretraga: '{escape(upit)}'</b><br><br>"
            + "<br>".join(linije)
            + "<br><br><small>Izvor: lokalni indeks istorijskih XML deklaracija.</small>"
        )
    except Exception as e:
        chat.add_agent_message(f"❌ Greška pri pretrazi lokalnog arhiva: {e}")


def _pretrazi_tarifu_po_kodu(ctrl, kod: str) -> None:
    chat = ctrl.view.get_chat_panel()
    _remember_tariff_context(ctrl, kod)
    chat.add_activity(f"🔍 Provjeravam tarifni kod: {kod}")
    try:
        from services.tariff.tarifa_service import validiraj_tarifni_broj, naziv_poglavlja
        r = validiraj_tarifni_broj(kod)
        if not r['valid']:
            chat.add_agent_message(
                f"❌ <b>Tarifna oznaka {kod}</b> nije pronađena u carinskoj tarifi 2026."
            )
            return
        stopa = r['stopa_uvozna']
        if stopa and not stopa.endswith('%'):
            stopa = stopa + '%'
        stopa_eu = r.get('stopa_eu', '')
        if stopa_eu and not stopa_eu.endswith('%'):
            stopa_eu = stopa_eu + '%'
        poglavlje = kod[:2]
        pog_naziv = naziv_poglavlja(poglavlje)
        chat.add_agent_message(
            f"<b>✅ Tarifna oznaka: {r['kod']}</b><br>"
            f"<b>Opis:</b> {r['naziv']}<br>"
            f"<b>Poglavlje {poglavlje}:</b> {pog_naziv}<br>"
            f"<b>Stopa (MFN):</b> {stopa or '—'} &nbsp;|&nbsp; "
            f"<b>EU:</b> {stopa_eu or '—'}"
        )
    except Exception as e:
        chat.add_agent_message(f"❌ Greška pri provjeri koda: {e}")


def _pretrazi_tarifu_poglavlje(ctrl, poglavlje: str) -> None:
    chat = ctrl.view.get_chat_panel()
    chat.add_activity(f"📂 Učitavam poglavlje {poglavlje} tarife...")
    try:
        from services.tariff.tarifa_service import trazi_poglavlje, naziv_poglavlja, formatiraj_rezultate
        naziv = naziv_poglavlja(poglavlje)
        stavke = trazi_poglavlje(poglavlje, limit=30)
        podbroji = [s for s in stavke if s['nivo'] == 'podbroj']
        html = formatiraj_rezultate(podbroji, max_rows=15)
        chat.add_agent_message(
            f"<b>📂 Poglavlje {poglavlje.zfill(2)}: {naziv}</b><br>"
            f"Ukupno tarifnih podbroja: <b>{len(podbroji)}</b><br><br>"
            f"{html}"
        )
    except Exception as e:
        chat.add_agent_message(f"❌ Greška pri učitavanju poglavlja: {e}")


def _pretrazi_tarifu_hijerarhijski(ctrl, kod: str) -> None:
    from services.tariff.tariff_tree_service import get_tree, get_full_path, format_tree_html
    chat = ctrl.view.get_chat_panel()
    kod_clean = kod.replace(' ', '').replace('.', '')
    chat.add_activity(f"🌳 Hijerarhijski prikaz za: {kod_clean}")
    try:
        path = get_full_path(kod_clean)
        if path:
            path_str = " → ".join(f"{p['kod']}" for p in path)
            chat.add_activity(f"📍 Put: {path_str}")
        tree = get_tree(kod_clean, depth=2)
        html = format_tree_html(tree)
        chat.add_agent_message(html)
    except Exception as e:
        chat.add_agent_message(f"❌ Greška: {e}")


def _compliance_check(ctrl) -> None:
    chat = ctrl.view.get_chat_panel()

    if not ctrl.draft or not getattr(ctrl.draft, 'invoice_lines', None):
        chat.add_agent_message("⚠️ Nema uvezenih stavki — učitaj fakturu prije provjere.")
        return

    chat.add_activity("🔍 Kompleksna provjera deklaracije u toku...")
    try:
        from services.agent.validation.declaration_validator_service import ComplianceCheckService
        from gui.tabs.agent.widgets.compliance_report_dialog import ComplianceReportDialog

        result = ComplianceCheckService().check(ctrl.draft)

        n_err   = len(result.errors)
        n_warn  = len(result.warnings)
        n_lines = len(ctrl.draft.invoice_lines)
        n_items = len(getattr(ctrl.draft, 'items', []) or [])

        context = (
            f"{n_lines} stavki fakture"
            + (f", {n_items} naimenovanja" if n_items else "")
        )

        parent_widget = getattr(ctrl.view, 'window', lambda: None)()
        dlg = ComplianceReportDialog(result, context=context, parent=parent_widget)
        dlg.show()

        # Kratka poruka u chatu kao potvrda
        if result.is_ok:
            chat.add_agent_message("✅ Provjera završena — sve uredu. Detalji u otvorenom prozoru.")
        else:
            chat.add_agent_message(
                f"📋 Provjera završena — <b>{n_err} greška</b>"
                + (f", <b>{n_warn} upozorenja</b>" if n_warn else "")
                + ". Detalji u otvorenom prozoru."
            )

        chat.add_activity(
            f"{'✅' if result.is_ok else '❌'} Compliance: "
            f"{n_err} grešaka, {n_warn} upozorenja"
        )
    except Exception as e:
        chat.add_agent_message(f"❌ Greška pri provjeri deklaracije: {e}")


def _izvrsi_spajanje_naimenovanja(ctrl, proposals, chat) -> None:
    from PySide6.QtWidgets import QApplication

    spojeno = 0
    for merge in proposals:
        items = ctrl.draft.items
        merged_indices = sorted(merge.indices, reverse=True)
        base_idx = min(merge.indices)
        base = items[base_idx]
        base.gross_mass_kg = merge.merged_bruto
        base.net_mass_kg = merge.merged_neto
        base.item_value = merge.merged_iznos
        base.supplementary_unit_qty = merge.merged_kolicina
        for idx in merged_indices:
            if idx != base_idx:
                del items[idx]
        for i, item in enumerate(items):
            item.ordinal_no = i + 1
        spojeno += len(merge.indices) - 1

    QApplication.processEvents()
    if ctrl.naimenovanje_tab:
        if hasattr(ctrl.naimenovanje_tab, 'reload_data'):
            ctrl.naimenovanje_tab.reload_data()
        elif hasattr(ctrl.naimenovanje_tab, 'reload'):
            ctrl.naimenovanje_tab.reload()

    faktura_widget = ctrl.faktura_tab
    if hasattr(ctrl.faktura_tab, 'view'):
        faktura_widget = ctrl.faktura_tab.view
    if faktura_widget and hasattr(faktura_widget, '_reload_naimenovanja_tab'):
        faktura_widget._reload_naimenovanja_tab()

    chat.add_agent_message(
        f"✅ <b>Spojeno {spojeno + len(proposals)} → {len(proposals)} naimenovanja.</b><br>"
        f"Količine, mase i iznosi su sabrani.<br>"
        f"Provjeri Naimenovanja tab."
    )


def _propose_kolona_upis(ctrl, atribut: str, vrijednost: str, tab: str) -> None:
    """
    Kreira proposal karticu za upis/brisanje vrijednosti u kolonu — MUTATE
    alat (ToolPolicy), nikad direktan upis. Korisnik mora kliknuti potvrdu
    prije nego se vrijednost stvarno upiše (_on_proposal_confirmed).

    Poziva se i iz Tool Use puta (_execute_tool, "upisi_u_kolonu") i iz
    regex fallback puta (agent_controller._upisi_u_kolonu) — isti mehanizam
    potvrde za oba, bez duplog puta.

    Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §5
    """
    naziv_kolone = _NAZIV_KOLONE.get(atribut, atribut)
    tab_naziv = "Faktura" if tab == 'faktura' else "Naimenovanja"

    n_stavki = 0
    if tab == 'faktura' and ctrl.draft and getattr(ctrl.draft, 'invoice_lines', None):
        n_stavki = len(ctrl.draft.invoice_lines)
    elif tab == 'naim' and ctrl.draft and getattr(ctrl.draft, 'items', None):
        n_stavki = len(ctrl.draft.items)

    # Zapamti tab za _on_proposal_confirmed — proposal_confirmed signal nosi
    # samo {atribut: vrijednost} dict, bez mjesta za tab, pa se čuva na ctrl.
    ctrl._pending_kolona_tab = tab
    # operation_id (Faza D, §16) — konzumira se atomarno u _on_proposal_confirmed/
    # _on_proposal_rejected, sprječava dvostruko izvršenje pri repliciranom signalu.
    ctrl._pending_kolona_operation_id = uuid.uuid4().hex

    akcija = f"Briše se {naziv_kolone}" if not vrijednost else f"Upisuje se {naziv_kolone}"
    proposal = {
        'title': f"{akcija}: {vrijednost}" if vrijednost else akcija,
        'subtitle': f"Primijeniće se na {n_stavki} stavki u {tab_naziv} tabu.",
        'fields': [
            {'label': naziv_kolone, 'key': atribut, 'value': vrijednost, 'editable': True},
        ],
        'apply_label': 'Potvrdi i upiši',
        'scope': f"{n_stavki} stavki, {tab_naziv}",
    }
    _show_proposal_card(ctrl, proposal)


def _show_proposal_card(ctrl, proposal: dict) -> None:
    from gui.tabs.agent.workflow_state import WorkflowState
    chat = ctrl.view.get_chat_panel()
    chat.show_proposal_card(proposal)
    ctrl.workflow.transition(WorkflowState.WAITING_USER_CONFIRMATION)


def _on_proposal_confirmed(ctrl, values: dict) -> None:
    from gui.tabs.agent.workflow_state import WorkflowState
    chat = ctrl.view.get_chat_panel()

    # Idempotencija (Faza D, §16 — zatvara poznat gap iz Faze A): operation_id
    # se konzumira ATOMARNO prije bilo kakvog izvršenja. Ako ga nema (već
    # obrađeno, ili repliciran/dupli signal na istoj proposal kartici),
    # tretiraj kao no-op umjesto da se mutacija izvrši drugi put.
    if not hasattr(ctrl, '_pending_kolona_operation_id'):
        logger.warning("[MutationGate] Potvrda bez pending operation_id — ignorišem (već obrađeno).")
        _audit_routing("local", tool="upisi_u_kolonu", status="ignored_no_pending_operation", confirmation="confirmed")
        return
    operation_id = ctrl._pending_kolona_operation_id
    del ctrl._pending_kolona_operation_id

    ctrl.workflow.transition(WorkflowState.APPLYING)

    # Tab je zapamćen u _propose_kolona_upis (proposal_confirmed signal nosi
    # samo values dict). 'faktura' ostaje default za bilo koji drugi buduci
    # proizvođač proposal kartice koji ovo polje ne postavlja.
    tab = getattr(ctrl, '_pending_kolona_tab', 'faktura')
    if hasattr(ctrl, '_pending_kolona_tab'):
        del ctrl._pending_kolona_tab

    if not values:
        chat.add_agent_message("⚠️ Prijedlog je prazan — ništa nije primijenjeno.")
        ctrl.workflow.transition(WorkflowState.COMPLETED)
        return

    upisano = 0
    for atribut, vrijednost in values.items():
        if not atribut:
            continue
        try:
            ctrl.naim_intent_svc.execute(atribut, vrijednost, tab=tab)
            upisano += 1
            # Decision Service sinhronizacija (Faza 0-6) — tarifa/zemlja/povlastica
            # imaju kanonski decision_state koji obicni setattr ne azurira.
            # Prazna vrijednost (brisanje) se ne sinhronizuje — nema "obrisi
            # odluku" koncepta u DeclarationDecisionService-u.
            decision_field = _DECISION_FIELD_BY_ATRIBUT.get(atribut)
            if decision_field is not None and tab == 'faktura' and vrijednost:
                for line in getattr(ctrl.draft, 'invoice_lines', None) or []:
                    try:
                        sync_decision_state_after_manual_edit(line, decision_field, vrijednost)
                    except Exception as sync_exc:
                        logger.warning(
                            "Decision sync (upisi_u_kolonu) nije uspio za liniju %s: %s",
                            getattr(line, 'line_no', '?'), sync_exc,
                        )
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri upisu {atribut}: {e}")

    poruke = ", ".join(f"{k}={v}" for k, v in values.items() if v)
    chat.add_agent_message(
        f"✅ <b>Prijedlog prihvaćen</b> — upisano {upisano} polja.<br>"
        f"<small style='color:grey;'>{poruke}</small>"
    )
    ctrl.workflow.transition(WorkflowState.COMPLETED)
    ctrl._save_session()
    _audit_routing(
        "local", tool="upisi_u_kolonu", status="ok", confirmation="confirmed",
        extra={"operation_id": operation_id, "upisano": upisano},
    )


def _on_proposal_rejected(ctrl) -> None:
    from gui.tabs.agent.workflow_state import WorkflowState
    operation_id = getattr(ctrl, '_pending_kolona_operation_id', '')
    if hasattr(ctrl, '_pending_kolona_operation_id'):
        del ctrl._pending_kolona_operation_id
    if hasattr(ctrl, '_pending_kolona_tab'):
        del ctrl._pending_kolona_tab
    ctrl.workflow.transition(WorkflowState.COMPLETED)
    _audit_routing(
        "local", tool="upisi_u_kolonu", status="ok", confirmation="rejected",
        extra={"operation_id": operation_id},
    )
