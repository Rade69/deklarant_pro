"""
Chat Intent Handler

Logika za obradu chat poruka u agentu: keyword detekcija, routing na akcije
(tarifni, pretraga tarife, naimenovanja, compliance, spajanje) i LLM fallback.

Premješteno iz agent_controller.py radi smanjenja veličine controllera.
"""

import re
import logging

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
    """Upravljanje chat porukom — keyword routing i LLM fallback."""

    def __init__(self, controller):
        self._ctrl = controller

    # ── Javni API ────────────────────────────────────────────────────

    def handle_message(self, message: str) -> None:
        _handle_message(self._ctrl, message)

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


def _handle_message(ctrl, message: str) -> None:
    from gui.tabs.agent.widgets.chat_worker import ChatWorker, check_injection

    chat = ctrl.view.get_chat_panel()

    blocked = check_injection(message)
    if blocked:
        chat.add_agent_message(blocked)
        return

    msg = message.lower().strip()

    # --- POTVRDA pending akcije ---
    POTVRDE = {'da', 'odobri', 'potvrdi', 'yes', 'ok', 'u redu', 'slažem se'}
    OTKAZI = {'ne', 'odustani', 'cancel', 'no', 'storno'}

    if ctrl._pending_action:
        if msg in POTVRDE or msg.startswith('da ') or msg.startswith('odobr'):
            ctrl._execute_pending_action()
            return
        if msg in OTKAZI:
            ctrl._pending_action = None
            chat.add_agent_message("❌ Akcija otkazana.")
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
        _REDNI_NAIM = {
            'prvi': 1, 'prvog': 1, 'prvo': 1, 'prva': 1,
            'drugi': 2, 'drugog': 2, 'drugo': 2, 'druga': 2,
            'treći': 3, 'trećeg': 3, 'treće': 3, 'treca': 3, 'treceg': 3,
            'četvrti': 4, 'cetvrti': 4, 'četvrtog': 4,
            'peti': 5, 'petog': 5, 'šesti': 6, 'sedmi': 7,
            'osmi': 8, 'deveti': 9, 'deseti': 10,
        }
        _naim_indices = [int(m) for m in re.findall(r'\b(\d+)\b', msg)
                         if 1 <= int(m) <= len(getattr(ctrl.draft, 'items', [])) + 5]
        _naim_ordinal = [_REDNI_NAIM.get(w) for w in msg.split() if w in _REDNI_NAIM]
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
    from services.agent.naimenovanja_review_service import NaimenovanjaReviewService

    chat = ctrl.view.get_chat_panel()

    if not ctrl.draft or not ctrl.draft.items:
        chat.add_agent_message("⚠️ Nema kreiranih naimenovanja u deklaraciji.")
        return

    naim_items = ctrl.draft.items
    chat.add_activity(f"🔍 Provjeravam {len(naim_items)} naimenovanja...")

    result = NaimenovanjaReviewService.provjeri_naimenovanja(naim_items)

    if result['is_complete']:
        chat.add_agent_message(
            f"✅ <b>Sva {result['total_naim']} naimenovanja su kompletno popunjena!</b><br>"
            f"Nema praznih obaveznih ni opcionih rubrika."
        )
        return

    linije = []
    for p in result['problemi']:
        ob_str = ", ".join(p.prazne_obavezne) if p.prazne_obavezne else "—"
        op_str = ", ".join(p.prazne_opcione) if p.prazne_opcione else "—"
        status = "❌" if p.prazne_obavezne else "⚠️"
        linije.append(
            f"{status} <b>Rb.{p.ordinal_no}</b> (tarifa: {p.tariff_code})<br>"
            f"&nbsp;&nbsp;Obavezne: {ob_str}<br>"
            f"&nbsp;&nbsp;Opcione: {op_str}"
        )

    chat.add_agent_message(
        f"📋 <b>Provjera naimenovanja — rezime:</b><br><br>"
        f"Ukupno naimenovanja: <b>{result['total_naim']}</b><br>"
        f"Praznih obaveznih polja: <b style='color:red'>{result['total_praznih_obaveznih']}</b><br>"
        f"Praznih opcionih polja: <b style='color:orange'>{result['total_praznih_opcionih']}</b><br><br>"
        f"<b>Detalji po naimenovanjima:</b><br><br>"
        + "<br><br>".join(linije)
    )


def _pregledaj_naimenovanja(ctrl, indeksi=None) -> None:
    from services.agent.naimenovanja_review_service import NaimenovanjaReviewService

    chat = ctrl.view.get_chat_panel()

    if not ctrl.draft or not ctrl.draft.items:
        chat.add_agent_message("⚠️ Nema kreiranih naimenovanja u deklaraciji.")
        return

    naim_items = ctrl.draft.items

    if indeksi:
        items_to_show = [naim_items[i - 1] for i in indeksi if 0 < i <= len(naim_items)]
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


def _pretrazi_tarifu_po_kodu(ctrl, kod: str) -> None:
    chat = ctrl.view.get_chat_panel()
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

    chat.add_activity("🔍 Compliance check u toku...")
    try:
        from services.agent.compliance_check_service import ComplianceCheckService
        svc = ComplianceCheckService()
        result = svc.check(ctrl.draft)
        html = result.summary_html()
        n_err = len(result.errors)
        n_warn = len(result.warnings)
        header = (
            f"<b>📋 Provjera deklaracije</b> — "
            f"{len(ctrl.draft.invoice_lines)} stavki"
        )
        if result.is_ok:
            status = " <span style='color:#2d6a30;'>✅ sve uredu</span>"
        else:
            status = (
                f" <span style='color:#b05050;'>❌ {n_err} greška</span>"
                + (f", <span style='color:#b8963a;'>⚠️ {n_warn} upozorenja</span>" if n_warn else "")
            )
        chat.add_agent_message(f"{header}{status}<br><br>{html}")
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
