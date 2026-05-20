"""
Chat Intent Handler

Logika za obradu chat poruka u agentu: Tool Use routing (primarni),
keyword detekcija (fallback), i LLM chat.

📄 docs/decisions/001-tool-use-refactoring.md
   docs/decisions/002-tool-dispatcher-integration.md

Premješteno iz agent_controller.py radi smanjenja veličine controllera.
"""

import json
import re
import logging
from html import escape

logger = logging.getLogger("deklarant_pro.agent.chat_intent")

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
    'peti': 5, 'petog': 5, 'šesti': 6, 'sedmi': 7,
    'osmi': 8, 'deveti': 9, 'deseti': 10,
    'posljednji': -1, 'zadnji': -1,
}


class ChatIntentHandler:
    """Upravljanje chat porukom — Tool Use routing (primarni) + keyword fallback."""

    def __init__(self, controller):
        self._ctrl = controller
        self._dispatcher_workers = []  # ToolDispatcherWorker instances

    # ── Javni API ────────────────────────────────────────────────────

    def handle_message(self, message: str) -> None:
        _handle_message(self._ctrl, message)

    # ── Tool Execution ───────────────────────────────────────────────
    # Vidi: docs/decisions/002-tool-dispatcher-integration.md

    def execute_tool(self, name: str, args: dict) -> None:
        """Izvrši tool call — mapira alat na postojeći servis."""
        _execute_tool(self._ctrl, name, args)

    def alternativni_tarifni_za_stavku(self, item_query: str = "",
                                        item_ordinal: int = None,
                                        is_alt: bool = False) -> None:
        _alternativni_tarifni_za_stavku(self._ctrl, item_query, item_ordinal, is_alt)

    def klasificiraj_i_usmjeri(self, message: str) -> None:
        _klasificiraj_i_usmjeri(self._ctrl, message)

    def provjeri_naimenovanja(self) -> None:
        _provjeri_naimenovanja(self._ctrl)

    def pregledaj_naimenovanja(self, indeksi=None) -> None:
        _pregledaj_naimenovanja(self._ctrl, indeksi)

    def pretrazi_tarifu(self, upit: str) -> None:
        _pretrazi_tarifu(self._ctrl, upit)

    def pretrazi_porijeklo(self, upit: str) -> None:
        _pretrazi_porijeklo(self._ctrl, upit)

    def pretrazi_tarifu_po_kodu(self, kod: str) -> None:
        _pretrazi_tarifu_po_kodu(self._ctrl, kod)

    def pretrazi_tarifu_poglavlje(self, poglavlje: str) -> None:
        _pretrazi_tarifu_poglavlje(self._ctrl, poglavlje)

    def pretrazi_tarifu_hijerarhijski(self, kod: str) -> None:
        _pretrazi_tarifu_hijerarhijski(self._ctrl, kod)

    def compliance_check(self) -> None:
        _compliance_check(self._ctrl)

    def izvrsi_spajanje_naimenovanja(self, proposals, chat) -> None:
        _izvrsi_spajanje_naimenovanja(self._ctrl, proposals, chat)

    def show_proposal_card(self, proposal: dict) -> None:
        _show_proposal_card(self._ctrl, proposal)

    def on_proposal_confirmed(self, values: dict) -> None:
        _on_proposal_confirmed(self._ctrl, values)

    def on_proposal_rejected(self) -> None:
        _on_proposal_rejected(self._ctrl)


# ── Implementacija (slobodne funkcije) ────────────────────────────────


def _extract_origin_product_query(message: str) -> str:
    # Docs: docs/sections/agent-origin-query-routing.md
    msg = (message or "").strip()
    lower = msg.lower()
    if not any(k in lower for k in ("porijekl", "porekl", "origin", "zemlja por")):
        return ""
    if re.search(r'\b(upiši|upisi|upišite|upisite|postavi|unesi|unesite|stavi)\b', lower):
        return ""

    quote = re.search(r'["\']([^"\']{3,100})["\']', msg)
    if quote:
        return quote.group(1).strip()

    parts = [p.strip() for p in re.split(r'[,;\n]+', msg) if p.strip()]
    non_origin_parts = [
        p for p in parts
        if not re.search(r'porijekl|porekl|origin|zemlja por', p, flags=re.IGNORECASE)
    ]
    if non_origin_parts:
        return max(non_origin_parts, key=len).strip().rstrip("?! .")

    patterns = [
        r'(?:potra[žz]i|pretra[žz]i|prona[đd]i|na[đd]i|tra[žz]i|trazi)\s+(?:mi\s+)?(?:porijekl\w*|porekl\w*|origin|zemlju\s+porijekla|zemlja\s+porijekla)\s+(?:za\s+)?(.+)',
        r'(?:porijekl\w*|porekl\w*|origin|zemlja\s+porijekla)\s+(?:ovog\s+proizvoda\s+)?(?:za\s+)?(.+)',
        r'(?:koja|koje|koji)\s+je\s+(?:zemlja\s+porijekla|porijeklo|poreklo|origin)\s+(?:za\s+)?(.+)',
        r'odakle\s+je\s+(?:proizvod\s+)?(.+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, msg, flags=re.IGNORECASE)
        if match:
            query = match.group(1).strip().rstrip("?! .")
            query = re.sub(r'\b(ovog|ovaj|tog|taj|proizvoda|proizvod)\b', '', query, flags=re.IGNORECASE)
            query = re.sub(r'\s+', ' ', query).strip()
            if len(query) >= 3:
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
    for word, ordinal in _REDNI.items():
        if ordinal > 0 and word in msg:
            return ordinal
    return None


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
        from services.tarifa_service import validiraj_tarifni_broj

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
    naim_ordinal = _extract_specific_naimenovanje_request(message)
    if naim_ordinal is not None:
        _pregledaj_naimenovanja(ctrl, [naim_ordinal])
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


def _handle_message(ctrl, message: str) -> None:
    """
    Primarni entry point za chat poruke.
    Flow: injection → pending → Tool Use (DeepSeek) → regex fallback → ChatWorker.

    📄 docs/decisions/002-tool-dispatcher-integration.md
    """
    from gui.tabs.agent.widgets.chat_worker import ChatWorker, check_injection
    from services.agent.chat.tool_dispatcher import ToolDispatcherWorker

    chat = ctrl.view.get_chat_panel()

    blocked = check_injection(message)
    if blocked:
        chat.add_agent_message(blocked)
        return

    msg_lower = message.lower().strip()

    if _resolve_followup(ctrl, message):
        return

    if _resolve_contextual_request(ctrl, message):
        return

    if _is_naimenovanja_review_request(message):
        if _is_naimenovanja_validation_request(message):
            _provjeri_naimenovanja(ctrl)
        else:
            _pregledaj_naimenovanja(ctrl)
        return

    origin_query = _extract_origin_product_query(message)
    if origin_query:
        _remember_subject(ctrl, origin_query)
        _pretrazi_porijeklo(ctrl, origin_query)
        return

    # --- POTVRDA pending akcije ---
    POTVRDE = {'da', 'odobri', 'potvrdi', 'yes', 'ok', 'u redu', 'slažem se'}
    OTKAZI = {'ne', 'odustani', 'cancel', 'no', 'storno'}

    if ctrl._pending_action:
        if msg_lower in POTVRDE or msg_lower.startswith('da ') or msg_lower.startswith('odobr'):
            ctrl._execute_pending_action()
            return
        if msg_lower in OTKAZI:
            ctrl._pending_action = None
            chat.add_agent_message("❌ Akcija otkazana.")
            return

    # ═══════════════════════════════════════════════════════════════
    # Faza 2: Tool Use routing (PRIMARNI) — DeepSeek bira alat
    # Ako uspije → izvrši alat i gotovo
    # Ako fallback_to_chat → ChatWorker
    # Ako error → regex fallback (_handle_message_regex_fallback)
    # ═══════════════════════════════════════════════════════════════
    # Vidi: docs/decisions/001-tool-use-refactoring.md

    dispatcher = ToolDispatcherWorker(message, parent=ctrl.view)

    def _on_tool_call(name: str, args: dict):
        logger.debug(f"[ToolUse] → {name}({args})")
        _execute_tool(ctrl, name, args)

    def _on_fallback(text: str):
        logger.debug(f"[ToolUse] → fallback to ChatWorker")
        _start_chat_worker(ctrl, message)

    def _on_error(err: str):
        logger.warning(f"[ToolUse] Error, falling back to regex: {err}")
        err_l = (err or "").lower()
        # Ako Tool Use padne jer DeepSeek nije podešen, idi na standardni chat
        # (Groq/Gemini) umjesto regex fallback-a koji daje "prebrz" lokalni routing.
        if "deepseek api ključ nije podešen" in err_l or "deepseek" in err_l and "ključ" in err_l:
            chat.add_activity("⚠️ Tool use nedostupan, prelazim na standardni AI chat...")
            _start_chat_worker(ctrl, message)
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
    # Kraj Tool Use bloka — ostatak _handle_message se NE izvršava
    return


# ── Tool execution (mapira tool → servis) ────────────────────────────
# Vidi: docs/decisions/002-tool-dispatcher-integration.md#execute_tool-mapiranje

def _execute_tool(ctrl, name: str, args: dict) -> None:
    """
    Izvrši tool call pozivom postojećeg servisa.
    Svaki tool mapira na postojeću funkciju/metodu.
    """
    chat = ctrl.view.get_chat_panel()

    if name == "predlozi_tarife":
        filter_kw = args.get("filter", "")
        if filter_kw:
            # Vidi: services/agent/chat/tariff_intent_service.py → propose_by_keyword()
            ctrl.tariff_svc.propose_by_keyword(filter_kw)
        else:
            ctrl._predlozi_tarifne_brojeve()

    elif name == "provjeri_tarife":
        _prikaz_tarifnih_trenutnih(ctrl)

    elif name == "pretrazi_tarifu":
        naziv = args.get("naziv", "")
        if naziv:
            _pretrazi_tarifu(ctrl, naziv)
        else:
            chat.add_agent_message("⚠️ Navedi naziv proizvoda za pretragu tarife.")

    elif name == "pretrazi_porijeklo":
        naziv = args.get("naziv", "")
        if naziv:
            _pretrazi_porijeklo(ctrl, naziv)
        else:
            chat.add_agent_message("⚠️ Navedi naziv proizvoda za pretragu porijekla.")

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
            chat.add_agent_message("⚠️ Navedi kolonu i vrijednost za upis.")
            return

        # Koristi NaimenovanjaIntentService._resolve_kolona za mapiranje
        svc = ctrl.naim_intent_svc
        atribut, resolved_tab = svc._resolve_kolona(kolona, tab_hint=tab)
        if not atribut:
            chat.add_agent_message(
                f"⚠️ Kolona '{kolona}' nije prepoznata. "
                f"Pokušaj: tarifni broj, zemlja porijekla, povlastica, "
                f"procedura, oznake, pakovanje, valuta, napomena..."
            )
            return

        svc.execute(atribut, vrijednost, resolved_tab)

    elif name == "spoji_naimenovanja":
        ctrl._predlozi_spajanje_naimenovanja()

    elif name == "analiziraj_tarifne":
        _analiziraj_tarifne_historiju(ctrl)

    else:
        logger.warning(f"[ToolUse] Nepoznat alat: {name}")
        chat.add_agent_message(f"⚠️ Nepoznata akcija: {name}")


def _start_chat_worker(ctrl, message: str) -> None:
    """Pokreće standardni ChatWorker za plain chat odgovor."""
    from gui.tabs.agent.widgets.chat_worker import ChatWorker
    chat = ctrl.view.get_chat_panel()
    memory_service = chat.get_memory_service()

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

    chat = ctrl.view.get_chat_panel()
    msg = message.lower().strip()

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

    class _ClassifierWorker(QThread):
        done = Signal(object)

        def __init__(self_, msg, dft):
            super().__init__()
            self_._msg = msg
            self_._dft = dft

        def run(self_):
            from services.agent.intent_classifier import IntentClassifier
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
    from services.agent.naimenovanja_review_service import NaimenovanjaReviewService

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


def _pregledaj_naimenovanja(ctrl, indeksi=None) -> None:
    from services.agent.naimenovanja_review_service import NaimenovanjaReviewService

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
        from services.tarifa_service import pretrazi, formatiraj_rezultate
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
        from services.agent.declaration_search_service import DeclarationSearchService

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
        from services.agent.declaration_search_service import DeclarationSearchService

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
        from services.tarifa_service import validiraj_tarifni_broj, naziv_poglavlja
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
        from services.tarifa_service import trazi_poglavlje, naziv_poglavlja, formatiraj_rezultate
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
    from services.tariff_tree_service import get_tree, get_full_path, format_tree_html
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
        from services.agent.compliance_check_service import ComplianceCheckService
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


def _show_proposal_card(ctrl, proposal: dict) -> None:
    from gui.tabs.agent.workflow_state import WorkflowState
    chat = ctrl.view.get_chat_panel()
    chat.show_proposal_card(proposal)
    ctrl.workflow.transition(WorkflowState.WAITING_USER_CONFIRMATION)


def _on_proposal_confirmed(ctrl, values: dict) -> None:
    from gui.tabs.agent.workflow_state import WorkflowState
    chat = ctrl.view.get_chat_panel()
    ctrl.workflow.transition(WorkflowState.APPLYING)

    if not values:
        chat.add_agent_message("⚠️ Prijedlog je prazan — ništa nije primijenjeno.")
        ctrl.workflow.transition(WorkflowState.COMPLETED)
        return

    upisano = 0
    for atribut, vrijednost in values.items():
        if not atribut or not vrijednost:
            continue
        try:
            ctrl.naim_intent_svc.execute(atribut, vrijednost, tab='faktura')
            upisano += 1
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri upisu {atribut}: {e}")

    poruke = ", ".join(f"{k}={v}" for k, v in values.items() if v)
    chat.add_agent_message(
        f"✅ <b>Prijedlog prihvaćen</b> — upisano {upisano} polja.<br>"
        f"<small style='color:grey;'>{poruke}</small>"
    )
    ctrl.workflow.transition(WorkflowState.COMPLETED)
    ctrl._save_session()


def _on_proposal_rejected(ctrl) -> None:
    from gui.tabs.agent.workflow_state import WorkflowState
    ctrl.workflow.transition(WorkflowState.COMPLETED)
