"""
ChatWorker - background thread za LLM pozive (Groq API).

ENHANCED: Dodato pamćenje konteksta chat sesije.
"""

import re
from PySide6.QtCore import QThread, Signal


# Kompatibilnost — stari kod koji importuje ovo ime
def _parse_groq_error(exc) -> str:
    from .llm_provider import parse_llm_error
    return parse_llm_error(exc)


# ── Prompt injection zaštita ─────────────────────────────────────────────────

_MAX_MESSAGE_LEN = 2000  # Carinska pitanja nikad ne trebaju više od ovoga

# Parovi (pattern, opis) — samo kombinacije koje su nedvosmisleno injection.
# "zanemari stavku/red/naimenovanje" su legitimne naredbe — ne blokiramo ih.
_INJECTION_PATTERNS = [
    # Zanemari + sistemski kontekst (ne stavku/red)
    (r'zanemari\s+.{0,40}(instrukcij|sistem[a-z]*\s+prompt|prethodni\s+kontekst|gore\s+napisano|pravil[a-z]*)',
     "pokušaj poništavanja sistemskih instrukcija"),
    # Ignore previous instructions
    (r'ignore\s+.{0,30}(previous|all\s+prior|above|system)\s*(instructions|prompt|context|rules)',
     "ignore instructions attempt"),
    # Forget everything / all instructions
    (r'forget\s+(everything|all\s+previous|all\s+instructions|above)',
     "forget instructions attempt"),
    # System role injection na početku poruke
    (r'^\s*(system\s*:|<\s*system\s*>|\[system\]|\[inst\])',
     "system role injection"),
    # "Ti si sada slobodan/neograničen/drugačiji AI"
    (r'ti\s+si\s+sada\s+.{0,30}(slobodan|bez\s+ograničen|drugačij|nov[i]?\s+ai|drukčij)',
     "uloga injection (sr)"),
    (r'you\s+are\s+now\s+.{0,30}(free|uncensored|different|new\s+ai|without\s+restrict)',
     "role injection (en)"),
    # Izvlačenje system prompta
    (r'(ispisi|pokaži|prikaži|napiši|reproduce|print|reveal|output|show)\s+.{0,30}'
     r'(system\s*prompt|cijeli\s+kontekst|sve\s+instrukcij|gornji\s+tekst|initial\s+prompt)',
     "pokušaj izvlačenja system prompta"),
    # Jailbreak ključne riječi
    (r'\b(jailbreak|do\s+anything\s+now|\bDAN\b|developer\s+mode\s+enabled)',
     "jailbreak keyword"),
    # Ponavljanje specijalnih znakova (obično dio injection payloada)
    (r'[<>\[\]{}]{6,}',
     "sumnjivi specijalni znakovi"),
]
_INJECTION_RE = [
    (re.compile(pat, re.IGNORECASE | re.DOTALL), opis)
    for pat, opis in _INJECTION_PATTERNS
]


def check_injection(message: str) -> str | None:
    """
    Provjeri da li poruka izgleda kao prompt injection napad.

    Returns:
        None  — poruka je uredna
        str   — opis problema (ne šalji LLM-u, prikaži korisniku)
    """
    if len(message) > _MAX_MESSAGE_LEN:
        return f"Poruka je predugačka ({len(message)} znakova). Maksimum je {_MAX_MESSAGE_LEN}."

    for pattern, opis in _INJECTION_RE:
        if pattern.search(message):
            print(f"[SecurityFilter] Blokirana poruka — {opis}: {message[:80]!r}")
            return (
                "⚠️ Poruka je blokirana iz sigurnosnih razloga.\n"
                "Ako imaš legitimno pitanje o carinjenju, molim te preformuliši ga."
            )
    return None


class ChatWorker(QThread):
    """Poziva Groq API u pozadini da ne blokira UI."""

    token_received = Signal(str)   # svaki streaming token
    stream_started = Signal()      # prije prvog tokena
    response_ready = Signal(str)   # cijeli tekst (za memoriju + fallback)
    error_occurred = Signal(str)

    def __init__(self, message: str, draft=None, parent=None,
                 memory_service=None):
        super().__init__(parent)
        self.message = message
        self.draft = draft
        self.memory_service = memory_service

    def run(self):
        try:
            from services.agent.llm_audit_log import (
                check_budget, estimate_tokens_messages, estimate_tokens, log_call
            )

            blocked = check_injection(self.message)
            if blocked:
                log_call(provider="none", tokens_in=0, tokens_out=0, blocked=True)
                self.error_occurred.emit(blocked)
                return

            from .llm_provider import LLMProvider, parse_llm_error

            provider = LLMProvider()
            if provider.active_provider() == "none":
                self.error_occurred.emit(
                    "Nema dostupnog AI ključa. Dodaj GROQ_API_KEY ili GEMINI_API_KEY u .env."
                )
                return

            context = self._build_context()

            chat_history = []
            if self.memory_service:
                chat_history = self.memory_service.get_context(max_messages=10)
            if self.memory_service:
                self.memory_service.add_user_message(self.message)

            messages = self._build_messages(context, chat_history)

            # Provjera token budžeta prije poziva
            tokens_in = estimate_tokens_messages(messages)
            budget_err = check_budget(tokens_in)
            if budget_err:
                self.error_occurred.emit(budget_err)
                return

            # === STREAMING — DeepSeek primarni, Groq/Gemini fallback ===
            self.stream_started.emit()
            full_text = ""
            for token in provider.stream_chat(messages, max_tokens=1500):
                full_text += token
                self.token_received.emit(token)

            text = full_text.strip()
            if self.memory_service:
                self.memory_service.add_assistant_message(text)

            # Audit log — bez sadržaja, samo metapodaci
            log_call(
                provider=provider.active_provider(),
                tokens_in=tokens_in,
                tokens_out=estimate_tokens(text),
            )

            self.response_ready.emit(text)

        except Exception as e:
            import traceback
            from .llm_provider import parse_llm_error
            print(f"[ChatWorker] GREŠKA: {e}")
            print(traceback.format_exc())
            self.error_occurred.emit(parse_llm_error(e))

    def _build_messages(self, context: str, chat_history: list) -> list:
        """
        ENHANCED: Sastavi messages listu za API sa chat istorijom.
        
        Format:
        1. System prompt (kontekst + sistemske instrukcije)
        2. Chat istorija (zadnjih 10 poruka)
        3. Trenutna korisnička poruka
        """
        system = {"role": "system", "content": self._system_prompt(context)}
        
        messages = [system]
        
        # ENHANCED: Dodaj chat istoriju (bez system poruka iz istorije)
        for hist_msg in chat_history:
            if hist_msg["role"] in ("user", "assistant"):
                messages.append({
                    "role": hist_msg["role"],
                    "content": hist_msg["content"]
                })
        
        # Trenutna poruka
        messages.append({"role": "user", "content": self.message})
        
        return messages

    def _build_context(self) -> str:
        if not self.draft:
            return "Draft je prazan — nisu uvezene fakture."

        lines = getattr(self.draft, 'invoice_lines', [])
        if not lines:
            return "Draft postoji ali nema uvezenih stavki."

        total = len(lines)
        bez_tarife_list = [l for l in lines if not getattr(l, 'tarifni_broj', None)]
        bez_zemlje_list = [l for l in lines if not getattr(l, 'zemlja_porijekla', None)]
        sa_povlasticom = sum(1 for l in lines if getattr(l, 'povlastica', None))
        bez_eur1 = sum(
            1 for l in lines
            if getattr(l, 'povlastica', None)
            and not getattr(l, 'has_origin_statement', False)
            and not getattr(l, 'eur1_number', None)
        )

        # Zemlja distribucija
        countries: dict = {}
        for l in lines:
            c = getattr(l, 'zemlja_porijekla', None) or '(nepoznato)'
            countries[c] = countries.get(c, 0) + 1
        country_str = ", ".join(f"{k}:{v}" for k, v in sorted(countries.items()))

        # === STAVKE — pametno skraćivanje za velike fakture ===
        _MAX_FULL = 15  # Smanjeno sa 30 na 15 da se uštede tokeni

        def _fmt_line(i, l):
            """Kompaktni format — štedi ~40% tokena."""
            naziv = getattr(l, 'naziv_robe', '') or ''
            tarifa = getattr(l, 'tarifni_broj', '') or '?'
            zemlja = getattr(l, 'zemlja_porijekla', '') or '?'
            kolicina = getattr(l, 'kolicina', None)
            jm = getattr(l, 'jm', '') or ''
            pov = getattr(l, 'povlastica', '') or '-'
            eur1 = getattr(l, 'eur1_number', '') or ''
            kol_str = f"{kolicina}{jm}".strip() if kolicina else '?'
            eur1_str = f" eur1={eur1}" if eur1 else ""
            tarifa_marker = "" if tarifa != '?' else " ⚠️NEMA_TARIFE"
            zemlja_marker = "" if zemlja != '?' else " ⚠️NEMA_ZEMLJE"
            # Kompaktni format: "  1. Mandarine | 08052190 | TR | 100kg | pov=P"
            return (
                f"  {i:3d}. {naziv[:40]:<40} | {tarifa}{tarifa_marker} | "
                f"{zemlja}{zemlja_marker} | {kol_str} | pov={pov}{eur1_str}"
            )

        # Identifikuj problematične stavke (prioritet za AI)
        def _is_problematic(l):
            no_tariff = not getattr(l, 'tarifni_broj', None)
            no_country = not getattr(l, 'zemlja_porijekla', None)
            needs_eur1 = (
                getattr(l, 'povlastica', None)
                and not getattr(l, 'has_origin_statement', False)
                and not getattr(l, 'eur1_number', None)
            )
            return no_tariff or no_country or needs_eur1

        sve_stavke = []
        if total <= _MAX_FULL:
            # Mala faktura — šalji sve
            ctx_header = f"=== SVE STAVKE ({total}) ==="
            for i, l in enumerate(lines, 1):
                sve_stavke.append(_fmt_line(i, l))
        else:
            # Velika faktura — prioritizuj problematične
            problematic = [(i, l) for i, l in enumerate(lines, 1) if _is_problematic(l)]
            ok_lines = [(i, l) for i, l in enumerate(lines, 1) if not _is_problematic(l)]

            ctx_header = (
                f"=== PROBLEMATIČNE STAVKE ({len(problematic)}/{total}) ===\n"
                f"  (Prikazane stavke koje zahtijevaju pažnju; "
                f"preostalih {len(ok_lines)} urednih stavki dato je kao sumarnik)"
            )
            for i, l in problematic[:50]:  # max 50 problematičnih
                sve_stavke.append(_fmt_line(i, l))

            if ok_lines:
                sve_stavke.append("")
                sve_stavke.append(f"  --- Uredne stavke — sumarnik po tarifi ({len(ok_lines)} stavki) ---")
                tariff_counts: dict = {}
                for _, l in ok_lines:
                    t = getattr(l, 'tarifni_broj', '?') or '?'
                    tariff_counts[t] = tariff_counts.get(t, 0) + 1
                for t, cnt in sorted(tariff_counts.items(), key=lambda x: -x[1])[:20]:
                    sve_stavke.append(f"  tarifa={t}: {cnt} stavki")

        # === ZONE KONTEKSTA — selektivno po tipu upita ===
        msg_lower = self.message.lower()
        zones = self._determine_context_zones(msg_lower)

        # Zone A: db_context — uvijek uključen
        ctx = [
            f"=== STANJE DRAFTA ===",
            f"Ukupno stavki: {total}",
            f"Bez tarifnog broja: {len(bez_tarife_list)}",
            f"Bez zemlje porijekla: {len(bez_zemlje_list)}",
            f"Sa povlasticom: {sa_povlasticom}",
            f"Čeka EUR1 broj: {bez_eur1}",
            f"Zemlja distribucija: {country_str}",
        ]

        # Zone B: session_context — pošiljalac/uvoznik/XML (uvijek ako postoji)
        session_lines = self._build_session_zone(lines)
        if session_lines:
            ctx.append("")
            ctx.extend(session_lines)

        ctx.extend(["", ctx_header])
        ctx.extend(sve_stavke)

        # Zone C: knowledge_context — KB + RAG prijedlozi (samo za tarif upite, ne za zakonska pitanja)
        if 'knowledge' in zones:
            knowledge_lines = self._build_knowledge_zone(bez_tarife_list)
            if knowledge_lines:
                ctx.append("")
                ctx.extend(knowledge_lines)

        # === NAIMENOVANJA (draft.items) — grupisane stavke za deklaraciju ===
        naim_items = getattr(self.draft, 'items', [])
        naim_pg_desc: dict = {}  # zvanični opisi tarifa za naimenovanja
        if naim_items:
            # Dohvati zvanične opise tarifa za sva naimenovanja odjednom
            naim_tariff_codes = [
                (getattr(it, 'tariff_code', '') or '').strip()
                for it in naim_items if getattr(it, 'tariff_code', None)
            ]
            naim_pg_desc = self._fetch_pg_tariff_descriptions(naim_tariff_codes) if naim_tariff_codes else {}

            ctx.append("")
            ctx.append(
                f"=== NAIMENOVANJA ({len(naim_items)} stavki u deklaraciji) ===\n"
                f"  (Naimenovanje = grupirana stavka carinske deklaracije; "
                f"više redova fakture sa istim tarifnim brojem spaja se u jedno naimenovanje)"
            )
            ctx.append(
                f"  {'Rb.':<5} {'Tarifni br.':<12} {'Opis robe (u deklaraciji)':<40} "
                f"{'Zvanični opis tarife':<40} {'Z.':<4} {'Povl.':<7} {'Bruto':>8} {'Neto':>8} {'Fakt.lin.':>9}"
            )
            ctx.append("  " + "-" * 135)
            for item in naim_items:
                rb    = getattr(item, 'ordinal_no', '?')
                tarif = getattr(item, 'tariff_code', '') or '⚠️NEMA'
                opis  = (getattr(item, 'goods_description', '') or '')[:39]
                zemlja = getattr(item, 'origin_country_code', '') or '?'
                pov   = getattr(item, 'preference_code', '') or '-'
                bruto = getattr(item, 'gross_mass_kg', 0) or 0
                neto  = getattr(item, 'net_mass_kg', 0) or 0
                zv_opis = naim_pg_desc.get(tarif, '')[:39] if tarif != '⚠️NEMA' else '(nema tarife)'
                n_lines = sum(
                    1 for l in lines
                    if getattr(l, 'assigned_naimenovanje_ordinal', 0) == rb
                )
                ctx.append(
                    f"  {rb:<5} {tarif:<12} {opis:<40} {zv_opis:<40} "
                    f"{zemlja:<4} {pov:<7} {bruto:>8.2f} {neto:>8.2f} {n_lines:>9}"
                )

            # ⭐ DETALJNE RUBRIKE — KOMPAKTNI FORMAT (štedi ~60% tokena)
            # Detalji se šalju samo kad korisnik eksplicitno traži
            ctx.append("")
            ctx.append("=== NAIMENOVANJA — SAŽETO (detalji na zahtjev) ===")
            for item in naim_items:
                rb = getattr(item, 'ordinal_no', '?')
                tarif = getattr(item, 'tariff_code', '') or 'NEMA'
                opis = (getattr(item, 'goods_description', '') or '')[:50]
                zemlja = getattr(item, 'origin_country_code', '') or '?'
                pov = getattr(item, 'preference_code', '') or '-'
                proc = getattr(item, 'procedure_code', '') or '-'
                bruto = getattr(item, 'gross_mass_kg', 0) or 0
                neto = getattr(item, 'net_mass_kg', 0) or 0
                ctx.append(
                    f"  Rb.{rb}: {tarif} | {opis} | Z:{zemlja} P:{pov} PR:{proc} | "
                    f"B:{bruto:.1f}kg N:{neto:.1f}kg"
                )

        if bez_zemlje_list:
            ctx.append("")
            ctx.append(f"=== STAVKE BEZ ZEMLJE PORIJEKLA ({len(bez_zemlje_list)}) ===")
            for l in bez_zemlje_list[:30]:
                ctx.append(f"  - {getattr(l, 'naziv_robe', '')[:60]}")

        msg = self.message.lower()

        # === ZAKONSKA REGULATIVA — samo kada pitanje traži zakonski/proceduralni kontekst ===
        if self._is_regulatory_question(msg):
            kb_regulativa = self._search_knowledge_base(self.message)
            if kb_regulativa:
                ctx.append("")
                ctx.append("=== ZAKONSKA REGULATIVA (relevantni odlomci) ===")
                ctx.extend(kb_regulativa)

        # === DETALJI KONKRETNIH NAIMENOVANJA — kad korisnik pita za Rb. X, Y ===
        if self._is_review_request(msg):
            # Pretvori redne brojeve (prvi, drugi...) i kardinalne (1, 2...) u listu indeksa
            _REDNI_MAP = {
                'prvi': 1, 'prvog': 1, 'prvo': 1, 'prva': 1,
                'drugi': 2, 'drugog': 2, 'drugo': 2, 'druga': 2,
                'treći': 3, 'trećeg': 3, 'treće': 3, 'treca': 3, 'treceg': 3,
                'četvrti': 4, 'cetvrti': 4, 'četvrtog': 4,
                'peti': 5, 'petog': 5, 'šesti': 6, 'sedmi': 7,
                'osmi': 8, 'deveti': 9, 'deseti': 10,
                'posljednji': len(naim_items), 'zadnji': len(naim_items),
            }
            _ordinal_indices = [v for k, v in _REDNI_MAP.items() if k in msg and v > 0]
            _digit_indices = [int(m) for m in re.findall(r'\b(\d+)\b', msg)
                              if 1 <= int(m) <= len(naim_items) + 5]
            mentioned_indices = list(dict.fromkeys(_digit_indices + _ordinal_indices))

            if mentioned_indices and naim_items:
                # Korisnik pita za konkretna naimenovanja — prikaži detalje sa fakturnih linija
                ctx.append("")
                ctx.append(f"=== DETALJI TRAŽENIH NAIMENOVANJA (Rb. {', '.join(map(str, mentioned_indices))}) ===")
                for i in mentioned_indices:
                    if 0 < i <= len(naim_items):
                        item = naim_items[i - 1]
                        tarif = getattr(item, 'tariff_code', '') or '(nema)'
                        opis = getattr(item, 'goods_description', '') or ''
                        zemlja = getattr(item, 'origin_country_code', '') or '?'
                        pov = getattr(item, 'preference_code', '') or '-'
                        bruto = getattr(item, 'gross_mass_kg', 0) or 0
                        neto = getattr(item, 'net_mass_kg', 0) or 0
                        zv_opis = naim_pg_desc.get(tarif, '(nije nađen u tarifi)')

                        ctx.append(f"  Rb.{i}: tarifa={tarif} | opis='{opis}' | zemlja={zemlja} | povl={pov}")
                        ctx.append(f"         bruto={bruto:.3f}kg | neto={neto:.3f}kg")
                        ctx.append(f"         Zvanični opis tarife {tarif}: {zv_opis}")

                        # Pronađi fakturne linije koje su grupisane u ovo naimenovanje
                        matching_lines = [
                            l for l in lines
                            if getattr(l, 'assigned_naimenovanje_ordinal', 0) == i
                        ]
                        if matching_lines:
                            ctx.append(f"         Fakturne linije ({len(matching_lines)}):")
                            for ml in matching_lines[:8]:
                                ml_tarif = getattr(ml, 'tarifni_broj', '') or '?'
                                ml_zemlja = getattr(ml, 'zemlja_porijekla', '') or '?'
                                ml_kol = getattr(ml, 'kolicina', '') or ''
                                ml_jm = getattr(ml, 'jm', '') or ''
                                ml_naziv = getattr(ml, 'naziv_robe', '') or ''
                                ctx.append(
                                    f"           - {ml_naziv[:55]} "
                                    f"({ml_kol} {ml_jm}) | tarifa={ml_tarif} | zemlja={ml_zemlja}"
                                )
                        else:
                            ctx.append(f"         Fakturne linije: 0 (naimenovanje bez dodjele)")
            else:
                # Generalni pregled — tarife za prvih 15 stavki (prioritet: bez tarife)
                bez = [l for l in lines if not getattr(l, 'tarifni_broj', None)]
                sa  = [l for l in lines if getattr(l, 'tarifni_broj', None)]
                target_lines = (bez + sa)[:15]
                tariff_validation = self._build_tariff_validation_context(target_lines)
                if tariff_validation:
                    ctx.append("")
                    ctx.append("=== TARIFNI BROJEVI — opisi iz Carinske tarife 2026 ===")
                    ctx.extend(tariff_validation)

        # === PRETRAGA XML DEKLARACIJA + BAZE ===
        if self._is_declaration_search(msg):
            decl_ctx = self._search_declarations_context(self.message)
            if decl_ctx:
                ctx.append("")
                ctx.extend(decl_ctx)

        return "\n".join(ctx)

    # ─────────────────────────────────────────────────────────────────────
    # ZONE KONTEKSTA — selektivno uključivanje po tipu upita
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _determine_context_zones(msg: str) -> set:
        """
        Odredi koje zone konteksta su potrebne za dati upit.

        Zone:
          'knowledge'  — KB + RAG prijedlozi tarife (za upite o tarifi/prijedlogu)
          'regulatory' — zakonski odlomci (za zakonska pitanja)
          'tariff_val' — opisi tarifa iz tarife 2026 (za pregled/validaciju)
          'declarations' — pretraga XML deklaracija

        db_context i session_context su uvijek uključeni.
        """
        zones = set()

        # Tarif/prijedlog → knowledge zona
        tariff_kw = [
            'tarif', 'tarifni', 'hs kod', 'hs code', 'predloži', 'predlozi',
            'popuni', 'procijeni', 'koji kod', 'koja tarifa', 'razvrstaj',
        ]
        if any(k in msg for k in tariff_kw):
            zones.add('knowledge')

        # Zakonska pitanja → regulatory zona (ali NE knowledge)
        regulatory_kw = [
            'zakon', 'pravilnik', 'propis', 'uredba', 'član', 'procedur',
            'postupak', 'uvjet', 'uslov', 'rok', 'slobodan promet', 'regulat',
            'konvencija', 'sporazum',
        ]
        if any(k in msg for k in regulatory_kw):
            zones.add('regulatory')
        else:
            # Za neregulativna pitanja dodaj knowledge ako ima stavki bez tarife
            zones.add('knowledge')

        # Pregled/validacija → tariff_val zona
        review_kw = [
            'provjeri', 'pregledaj', 'validiraj', 'ispravan', 'da li je sve',
            'sve u redu', 'review', 'check', 'pregled',
        ]
        if any(k in msg for k in review_kw):
            zones.add('tariff_val')

        # Pretraga deklaracija
        decl_kw = ['deklaracija', 'prethodni uvoz', 'xml', 'istorija uvoza']
        if any(k in msg for k in decl_kw):
            zones.add('declarations')

        return zones

    def _build_knowledge_zone(self, bez_tarife_list: list) -> list:
        """
        Zone C — KB + RAG prijedlozi tarife za stavke bez tarifnog broja.
        Preskači se za čisto zakonska pitanja.
        """
        if not bez_tarife_list:
            return []

        result = []

        # KB prijedlozi — docs/architecture/TARIFF_FACADE_REFACTORING.md
        kb_prijedlozi = []
        try:
            from services.tariff_facade import TariffFacade
            facade = TariffFacade.get_instance()
            for l in bez_tarife_list[:20]:
                naziv        = getattr(l, "naziv_robe",      "") or ""
                product_code = getattr(l, "product_code",    "") or ""
                zemlja       = getattr(l, "zemlja_porijekla", "") or ""
                fast = facade.suggest_fast(naziv, product_code)
                if fast and fast.tarifni_broj:
                    kb_prijedlozi.append(
                        f"  '{naziv[:50]}' → tarifa={fast.tarifni_broj} "
                        f"(sličnost={fast.confidence:.0%})"
                    )
                else:
                    kb_prijedlozi.append(f"  '{naziv[:50]}' → (nije u bazi znanja)")
        except Exception as e:
            kb_prijedlozi.append(f"  (greška pri upitu baze znanja: {e})")

        if kb_prijedlozi:
            result.append("=== BAZA ZNANJA — prijedlozi tarife za stavke bez tarife ===")
            result.extend(kb_prijedlozi)

        # RAG prijedlozi (istorija deklaracija)
        rag_prijedlozi = []
        try:
            from services.tariff_facade import TariffFacade
            facade = TariffFacade.get_instance()
            seen_queries: set = set()
            for l in bez_tarife_list[:10]:
                naziv = getattr(l, "naziv_robe", "") or ""
                if naziv and naziv not in seen_queries:
                    seen_queries.add(naziv)
                    historija = facade.rag_candidates(naziv, limit=2)
                    for r in historija:
                        rag_prijedlozi.append(
                            f"  '{naziv[:40]}' → tarifa={r.get('tarifni_kod', '?')} "
                            f"(istorija: {r.get('naziv_robe', '')[:40]})"
                        )
        except Exception:
            pass

        if rag_prijedlozi:
            if result:
                result.append("")
            result.append("=== ISTORIJA DEKLARACIJA — prijedlozi tarife ===")
            result.extend(rag_prijedlozi)

        return result

    def _build_session_zone(self, lines: list) -> list:
        """
        Zone B — pošiljalac/uvoznik + XML predložak.

        JIB se nikad ne šalje LLM-u — koristi se samo lokalno za XML lookup.
        Ako je SEND_SENSITIVE_DATA=false (default), imena partnera se maskiraju.
        """
        result = []
        exporter_name = ""
        consignee_jib = ""
        consignee_name = ""
        xml_lookup_info = ""

        first_line = lines[0] if lines else None
        if first_line:
            exp_party = getattr(first_line, 'exporter', None)
            if exp_party and getattr(exp_party, 'name', ''):
                exporter_name = exp_party.name

        if self.draft:
            consignee_jib = getattr(self.draft, 'primalac_id', '') or ''
            consignee_name = getattr(self.draft, 'primalac_naziv', '') or ''
            if not consignee_jib:
                consignee_jib = getattr(self.draft, 'izvoznik_id', '') or ''

        # XML lookup — lokalna operacija, koristi puna imena i JIB
        if exporter_name:
            try:
                from services.agent.exporter_xml_indexer import find_xml_for_pair
                match = find_xml_for_pair(
                    exporter_name,
                    consignee_jib=consignee_jib,
                    consignee_hint=consignee_name
                )
                if match:
                    import os
                    fname = os.path.basename(match['xml_filepath'])
                    xml_lookup_info = (
                        f"Pronađen XML predložak: {fname} "
                        f"(match: {match['match_type']})"
                        # consignee_original se namjerno izostavlja iz LLM konteksta
                    )
            except Exception:
                pass

        if not (exporter_name or consignee_name or consignee_jib):
            return result

        # Provjeri da li je dozvoljeno slanje osjetljivih podataka eksternom LLM-u
        import os
        send_sensitive = os.getenv("SEND_SENSITIVE_DATA", "false").strip().lower() == "true"

        result.append("=== POŠILJALAC / UVOZNIK ===")

        if send_sensitive:
            if exporter_name:
                result.append(f"Pošiljalac (iz fakture): {exporter_name}")
            if consignee_name:
                # JIB se nikad ne šalje — nije potreban LLM-u
                result.append(f"Uvoznik (rubrika 8): {consignee_name}")
            elif consignee_jib:
                result.append("Uvoznik (rubrika 8): [postoji, ime nije dostupno]")
        else:
            # Maskiranje — LLM zna da partneri postoje, ali ne zna ko su
            if exporter_name:
                result.append("Pošiljalac (iz fakture): [ime skriveno — SEND_SENSITIVE_DATA=false]")
            if consignee_name or consignee_jib:
                result.append("Uvoznik (rubrika 8): [ime skriveno — SEND_SENSITIVE_DATA=false]")

        if xml_lookup_info:
            result.append(f"XML predložak: {xml_lookup_info}")
        elif exporter_name:
            result.append("XML predložak: nije pronađen u bazi")

        return result

    @staticmethod
    def _is_review_request(msg: str) -> bool:
        """Da li korisnik traži pregled/validaciju/prijedlog tarife?"""
        keywords = [
            'pregled', 'pregledaj', 'provjeri', 'provjera', 'validiraj', 'validacija',
            'uskladi', 'usklađ', 'tarifni broj', 'tarife', 'ispravan', 'ispravnost',
            'greška', 'grešk', 'da li je sve', 'sve u redu', 'review', 'check',
            # Prijedlog tarife
            'predloži', 'predlozi', 'procijeni', 'procjeni', 'koji tarif', 'koja tarif',
            'tarifa za', 'hs kod', 'naimenovanj', 'stavk',
        ]
        return any(k in msg for k in keywords)

    @staticmethod
    def _is_regulatory_question(msg: str) -> bool:
        """Da li pitanje traži zakonski/proceduralni odgovor?"""
        keywords = [
            'zakon', 'pravilnik', 'propis', 'uredba', 'član', 'procedur', 'postupak',
            'uvjet', 'uslov', 'dokument', 'rok', 'privremeni', 'carinski', 'uvoz',
            'izvoz', 'povlastica', 'porijeklo', 'carinska vrijednost', 'eur1', 'pe1', 'pe2',
            'konvencija', 'sporazum', 'tarifa', 'obrada', 'slobodan promet', 'regulat'
        ]
        return any(k in msg for k in keywords)

    def _build_tariff_validation_context(self, lines: list) -> list:
        """
        Za svaki tarifni broj iz drafta dohvata zvanični opis iz Carinske tarife.

        Primarni izvor: PostgreSQL catalogs.zvanicna_tarifa (opis po tarifnom kodu).
        Fallback: KnowledgeBase PDF tarife.

        Omogućava LLM-u da poredi naziv robe sa zvaničnim opisom tarife i procijeni
        da li je tarifni broj ispravan.
        """
        if not lines:
            return []

        # Skupi sve tarifne kodove sa njihovim nazivima (po više stavki po tarifi)
        # Format: {kod: [naziv1, naziv2, ...]}
        tariff_to_names: dict = {}
        for l in lines:
            code = (getattr(l, 'tarifni_broj', None) or '').strip()
            naziv = (getattr(l, 'naziv_robe', '') or '').strip()
            if code:
                tariff_to_names.setdefault(code, [])
                if naziv and naziv not in tariff_to_names[code]:
                    tariff_to_names[code].append(naziv)
            if len(tariff_to_names) >= 30:
                break

        if not tariff_to_names:
            return []

        # Dohvati opise iz PostgreSQL (primarna baza)
        pg_descriptions = self._fetch_pg_tariff_descriptions(list(tariff_to_names.keys()))

        # Fallback: KnowledgeBase
        kb_descriptions = {}
        if len(pg_descriptions) < len(tariff_to_names):
            missing = [c for c in tariff_to_names if c not in pg_descriptions]
            try:
                from services.knowledge_base.kb_service import KnowledgeBaseService
                svc = KnowledgeBaseService()
                if svc.get_stats()["doc_count"] > 0:
                    raw = svc.get_tariff_descriptions(missing)
                    for code, chunk in raw.items():
                        kb_descriptions[code] = self._extract_tariff_line(code, chunk)
            except Exception:
                pass

        lines_out = []
        lines_out.append(
            f"  {'Tarif. br.':<12} {'Naziv robe (u deklaraciji)':<48} {'Zvanični opis iz tarife'}"
        )
        lines_out.append("  " + "-" * 120)

        for code, nazivi in tariff_to_names.items():
            opis = pg_descriptions.get(code) or kb_descriptions.get(code) or "(nije pronađen u tarifi)"
            # Sve nazive robe grupisane pod jedan tarifni kod
            for i, naziv in enumerate(nazivi[:3]):  # max 3 naziva po tarifi
                prefix = code if i == 0 else " " * len(code)
                lines_out.append(f"  {prefix:<12} {naziv[:47]:<48} {opis[:80]}")

        return lines_out

    @staticmethod
    def _fetch_pg_tariff_descriptions(codes: list) -> dict:
        """
        Dohvati opise tarifnih brojeva iz PostgreSQL catalogs.zvanicna_tarifa.

        Baza čuva 10-cifrene kodove (npr. '0805219000').
        Draft može imati 8-cifrene (npr. '08052190') — dodajemo '00' na kraj.

        Returns:
            {originalni_kod: opis_string}
        """
        result = {}
        if not codes:
            return result
        try:
            from database.db import get_db_connection

            def only_digits(c):
                return ''.join(ch for ch in c if ch.isdigit())

            # Gradi mapu: 10-cifreni_u_bazi → originalni_kod
            lookup: dict = {}  # {10-digit: original_code}
            for code in codes:
                d = only_digits(code)
                if len(d) == 8:
                    lookup[d + '00'] = code  # 08052190 → 0805219000
                elif len(d) == 10:
                    lookup[d] = code
                elif len(d) == 6:
                    lookup[d + '0000'] = code
                else:
                    lookup[d.ljust(10, '0')[:10]] = code

            if not lookup:
                return result

            placeholders = ', '.join(['%s'] * len(lookup))
            sql = f"""
                SELECT tarifni_kod, opis
                FROM catalogs.zvanicna_tarifa
                WHERE tarifni_kod IN ({placeholders})
            """
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, list(lookup.keys()))
                rows = cur.fetchall()

            for row in rows:
                db_code = only_digits(row['tarifni_kod'])
                orig = lookup.get(db_code)
                if orig:
                    result[orig] = (row['opis'] or '')[:150]

        except Exception as e:
            print(f"[ChatWorker] PG tariff lookup greška: {e}")

        return result

    @staticmethod
    def _extract_tariff_line(code: str, chunk_text: str) -> str:
        """Iz chunka izvlači redove koji sadrže tarifni kod ili opis pored koda."""
        # Formatirani oblik koda za pretragu u tekstu (npr. "0201 10 00")
        digits = "".join(c for c in code if c.isdigit())
        patterns = []
        if len(digits) >= 10:
            patterns.append(f"{digits[:4]} {digits[4:6]} {digits[6:8]} {digits[8:10]}")
        if len(digits) >= 8:
            patterns.append(f"{digits[:4]} {digits[4:6]} {digits[6:8]}")

        for pat in patterns:
            for line in chunk_text.split('\n'):
                if pat in line:
                    # Vrati tekst iza koda (opis)
                    idx = line.find(pat)
                    after = line[idx + len(pat):].strip()
                    if len(after) > 10:
                        return after[:150]

        # Fallback: prva smislena linija chunka
        first = chunk_text.strip().split('\n')[0]
        return first[:150]

    @staticmethod
    def _is_declaration_search(msg: str) -> bool:
        """Da li korisnik pita za istorijske deklaracije, partnere ili bazu?"""
        keywords = [
            # Istorija deklaracija
            'istorij', 'prethodn', 'ranije', 'deklaracij', 'xml', 'asycuda',
            'starih', 'arhiv', 'uvoz', 'izvoz',
            # Pretraga robe
            'pronađi', 'pretraži', 'nađi', 'potraži', 'koji tarifni',
            'koja tarifa', 'tarifa za', 'broj za', 'tarifni broj za',
            # Partneri / dobavljači
            'dobavljač', 'izvoznik', 'primalac', 'partner', 'firma',
            'kompanij', 'ko nam isporučuje', 'ko šalje',
            # Statistika
            'statistik', 'koliko puta', 'koliko deklaracij', 'najčešće',
            'koliko smo', 'ukupno', 'porijek',
            # Zemlja
            'zemlja porijekla', 'porijeklom iz', 'roba iz',
        ]
        return any(k in msg for k in keywords)

    def _search_declarations_context(self, query: str) -> list:
        """Pretražuje XML deklaracije i PostgreSQL bazu, vraća kontekst za AI."""
        ctx = []
        msg = query.lower()

        try:
            from services.agent.declaration_search_service import DeclarationSearchService
            svc = DeclarationSearchService()

            # Statistika indeksa (uvijek korisna)
            stats = svc.get_stats()
            ctx.append(
                f"=== ARHIV XML DEKLARACIJA ({stats['declarations']} deklaracija, "
                f"{stats['items']} stavki, {stats['unique_tariffs']} jedinstvenih tarifa) ==="
            )

            # Pretraga po tarifi
            tariff_match = self._extract_tariff_code(query)
            if tariff_match:
                results = svc.search_by_tariff(tariff_match, limit=8)
                if results:
                    ctx.append(f"\nIstorijske stavke sa tarifom {tariff_match}:")
                    for r in results:
                        ctx.append(
                            f"  {r.get('hs_code','?')} | "
                            f"{r.get('commercial_desc','')[:50]} | "
                            f"zemlja={r.get('country_origin','?')} | "
                            f"povlastica={r.get('preference','?')} | "
                            f"fajl={r.get('filename','?')}"
                        )

            # Pretraga po opisu robe (ako nije čisto pitanje o tarifi)
            if not tariff_match or 'pronađi' in msg or 'pretraži' in msg or 'nađi' in msg:
                results = svc.search_by_goods(query, limit=8)
                if results:
                    ctx.append(f"\nRoba pronađena u istorijskim deklaracijama:")
                    seen = set()
                    for r in results:
                        key = r.get('hs_code', '') + r.get('commercial_desc', '')[:30]
                        if key in seen:
                            continue
                        seen.add(key)
                        ctx.append(
                            f"  tarifa={r.get('hs_code','?')} | "
                            f"{r.get('commercial_desc','')[:55]} | "
                            f"zemlja={r.get('country_origin','?')} | "
                            f"povlastica={r.get('preference','?')}"
                        )

            # Pretraga po partneru
            partner_keywords = ['dobavljač', 'izvoznik', 'primalac', 'partner',
                                 'firma', 'kompanij', 'ko nam', 'ko šalje']
            if any(k in msg for k in partner_keywords):
                results = svc.search_by_partner(query, limit=6)
                if results:
                    ctx.append(f"\nPartneri pronađeni u istorijskim deklaracijama:")
                    for r in results:
                        ctx.append(
                            f"  Izvoznik: {r.get('exporter_name','?')[:50]} | "
                            f"Primalac: {r.get('consignee_name','?')[:40]} | "
                            f"JIB: {r.get('consignee_jib','?')}"
                        )

            # Pretraga po zemlji
            country_match = self._extract_country_code(query)
            if country_match:
                results = svc.search_by_country(country_match, limit=8)
                if results:
                    ctx.append(f"\nRoba porijeklom iz {country_match}:")
                    seen = set()
                    for r in results:
                        k = r.get('hs_code','') + r.get('commercial_desc','')[:20]
                        if k not in seen:
                            seen.add(k)
                            ctx.append(
                                f"  tarifa={r.get('hs_code','?')} | "
                                f"{r.get('commercial_desc','')[:55]} | "
                                f"povlastica={r.get('preference','?')}"
                            )

            # PostgreSQL pretraga partnera iz baze
            pg_results = self._search_pg_partners(query)
            if pg_results:
                ctx.append(f"\nPartneri u bazi podataka (PostgreSQL):")
                ctx.extend(pg_results)

        except Exception as e:
            ctx.append(f"  (greška pri pretrazi arhiva: {e})")

        return ctx

    @staticmethod
    def _extract_tariff_code(text: str) -> str:
        """Izvlači tarifni broj iz upita (npr. '16010099' ili '1601 10 00')."""
        digits = re.sub(r'\D', '', text)
        # Traži kontinuiranu sekvencu od 6-11 cifara
        match = re.search(r'\b(\d{6,11})\b', text.replace(' ', ''))
        if match:
            return match.group(1)
        # Ako cijeli query ima 6+ cifara
        if len(digits) >= 6:
            return digits[:11]
        return ""

    @staticmethod
    def _extract_country_code(text: str) -> str:
        """Izvlači ISO kod zemlje iz upita (npr. 'TR', 'DE', 'RS')."""
        known = {
            'tursk': 'TR', 'turkey': 'TR', 'turci': 'TR',
            'srbij': 'RS', 'srbija': 'RS',
            'njemačk': 'DE', 'germany': 'DE', 'njemacka': 'DE',
            'kina': 'CN', 'china': 'CN', 'kineski': 'CN',
            'italij': 'IT', 'italy': 'IT',
            'slovenij': 'SI', 'slovenija': 'SI',
            'hrvatska': 'HR', 'croati': 'HR',
            'bosn': 'BA', 'bih': 'BA',
            'eu ': 'EU', 'evropsk': 'EU',
            'finsk': 'FI', 'finska': 'FI',
        }
        msg = text.lower()
        for keyword, code in known.items():
            if keyword in msg:
                return code
        # Direktan ISO kod (2 velika slova)
        iso = re.search(r'\b([A-Z]{2})\b', text)
        if iso:
            return iso.group(1)
        return ""

    def _search_pg_partners(self, query: str) -> list:
        """Pretraga partnera u PostgreSQL bazi (traders, izvoznici, uvoznici)."""
        try:
            from database.db import get_db_connection
            words = [w for w in re.split(r'\s+', query) if len(w) >= 3]
            if not words:
                return []
            patterns = [f"%{w}%" for w in words[:3]]
            or_clause = " OR ".join(["name ILIKE %s"] * len(patterns))
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT code, name, type FROM public.traders "
                        f"WHERE {or_clause} LIMIT 15",
                        patterns,
                    )
                    results = [
                        f"  [{row['type']}] {row['name']} (kod: {row['code']})"
                        for row in cur.fetchall()
                    ]
            return list(dict.fromkeys(results))
        except Exception:
            return []

    def _search_knowledge_base(self, query: str) -> list:
        """Pretražuje Knowledge Base i vraća relevantne odlomke za kontekst."""
        try:
            from services.knowledge_base.kb_service import KnowledgeBaseService
            svc = KnowledgeBaseService()
            stats = svc.get_stats()
            if stats["doc_count"] == 0:
                return []
            results = svc.search(query, top_k=4, use_reranking=False)
            lines = []
            for r in results:
                lines.append(f"  [{r.filename}, str. {r.page_number}]")
                lines.append(f"  {r.chunk_text[:300]}")
                lines.append("")
            return lines
        except Exception as e:
            return []

    def _system_prompt(self, context: str) -> str:
        # ENHANCED: Dodaj info o chat memoriji
        memory_info = ""
        if self.memory_service:
            msg_count = len(self.memory_service)
            memory_info = f"\n\nNAPOMENA: Ovo je nastavak razgovora ({msg_count} poruka do sada). "
            memory_info += "Koristi kontekst ranije razgovora za bolje odgovore."
        
        return (
            "Ti si AI asistent za carinsku deklaraciju u aplikaciji Deklarant Pro (Bosna i Hercegovina).\n"
            "Odgovaraš na srpskom jeziku (latinica), konkretno i korisno.\n\n"
            "POJMOVI KOJE MORAŠ RAZUMJETI:\n"
            "- FAKTURNE LINIJE (invoice_lines): Pojedinačni redovi iz uvozne fakture — svaki red je jedan proizvod.\n"
            "  Polja: naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, kolicina, jm, bruto_kg, neto_kg.\n\n"
            "- NAIMENOVANJA (items): Grupisane stavke CARINSKE DEKLARACIJE.\n"
            "  PRAVILO GRUPIRANJA: Fakturne linije se grupišu po kombinaciji:\n"
            "    (tarifni_broj + zemlja_porijekla + povlastica + eur1_number)\n"
            "  Sve linije sa ISTOM tom kombinacijom → JEDNO naimenovanje.\n"
            "  Ako se razlikuje ijedan od ta 4 ključa → RAZLIČITA naimenovanja.\n"
            "  Primjer: 5 linija mandarina (sve tarifa=08052190, TR, TRP) → 1 naimenovanje\n"
            "           3 linije jabuka (08081000, RS, CEFTAP) + 5 mandarina → 2 naimenovanja\n"
            "  Masa se SABIRA od svih linija u grupi.\n"
            "  Opis = prvih 3 naziva robe spojeni sa '; '\n"
            "  Svako naimenovanje ima redni broj (Rb.). Rb.1 = prvo, Rb.10 = deseto.\n\n"
            "- ZAŠTO JE VIŠE NAIMENOVANJA nego što korisnik očekuje:\n"
            "  → Različite povlastice (npr. TRP vs EUP) → odvojeno\n"
            "  → Različite zemlje porijekla → odvojeno\n"
            "  → Različiti tarifni brojevi → odvojeno\n"
            "  → Različiti EUR.1 brojevi → odvojeno\n\n"
            "- Kad korisnik kaže 'naimenovanje 10 i 11' — misli na Rb. 10 i Rb. 11 u tabeli NAIMENOVANJA\n"
            "- Tarifni broj (HS kod): 8-10 cifara, format bez tačaka (npr. 84713000)\n\n"
            "TVOJE SPOSOBNOSTI:\n"
            "- Vidiš SVE fakturne linije i SVA naimenovanja iz aktivnog drafta — sa tarifima, zemljama, težinama\n"
            "- Imaš pristup bazi znanja (product_tariff_mapping) — prijedlozi tarife za nepoznate proizvode\n"
            "- Imaš pristup istoriji deklaracija — tarife koje su ranije korišćene za iste/slične proizvode\n"
            "- Imaš pristup zakonskoj regulativi (carinski zakoni, pravilnici BiH) — relevantni odlomci su priloženi u kontekstu\n"
            "- Možeš pretraživati arhiv od 2500+ istorijskih XML deklaracija iz sistema ASYCUDA\n"
            "- Možeš pretraživati PostgreSQL bazu podataka: partnere (izvoznike, primaoce), tarifne mappinge\n"
            "- Vidiš pošiljaoca (iz fakture) i uvoznika (JIB iz rubrike 8) — na osnovu toga pronalažen XML predložak iz baze\n"
            "- Možeš analizirati probleme i predlagati rješenja\n\n"
            "OBLASTI PODRŠKE:\n"
            "- Tarifni brojevi (HS/TARIC): koji tarifni broj odgovara kom proizvodu\n"
            "- Zemlja porijekla: koji ISO kod odgovara kojoj zemlji\n"
            "- Povlastice: EUP (EU), CEFTAP (CEFTA), TRP (Turska), PE2 (izjava o porijeklu), EUR1 (obrazac)\n"
            "- Validacija: provjera ispravnosti stavki, upozorenja na greške\n"
            "- Opšta pitanja o carinjenju u BIH\n"
            "- Pretraga arhiva: 'Koji tarifni broj smo koristili za X?', 'Pronađi deklaracije sa TR porijeklom'\n"
            "- Pretraga partnera: 'Ko nam isporučuje Y?', 'Pronađi dobavljača Z'\n"
            "- Tumačenje zakonskih odredbi (koristi odlomke iz sekcije ZAKONSKA REGULATIVA)\n"
            "- Pregled i validacija deklaracije — provjera usklađenosti tarifnih brojeva sa robom\n\n"
            "PRAVILA:\n"
            "- Odgovaraj KRATKO i KONKRETNO — bez dugih analiza, bez zaključaka, bez ponavljanja pitanja\n"
            "- Ako korisnik pita za tarifni broj: daj konkretnu opciju iz svog znanja o HS, "
            "navedi kao 8 cifara (npr. 56079090). Ako nisi siguran, daj 2-3 opcije.\n"
            "- Tarifne prijedloge iz baze znanja (kontekst) preferuj nad opštim znanjem\n"
            "- Ako korisnik pita nešto opšte o carinjenju — odgovori normalno, bez liste tarifa\n\n"
            "ANALIZA NAIMENOVANJA I TARIFE:\n"
            "U kontekstu imaš sekciju NAIMENOVANJA sa kolonama: Rb. | Tarifni br. | Opis | Zvanični opis tarife | ...\n"
            "Kada korisnik pita za konkretna naimenovanja (npr. 'naimenovanje 10 i 11'), imaš i sekciju\n"
            "'DETALJI TRAŽENIH NAIMENOVANJA' sa svim podacima za ta naimenovanja.\n\n"
            "OBAVEZNO za svako pomenuto naimenovanje:\n"
            "1. Navedi Rb., tarifni broj, opis robe i zvanični opis tarife iz konteksta\n"
            "2. Procijeni usklađenost: ✅ Usklađeno | ⚠️ Provjeri | ❌ Neusklađeno\n"
            "3. Ako tarife nema ili je netačna — predloži konkretan tarifni broj (samo cifre, npr. 84713000)\n"
            "4. Obrazloži zašto taj tarifni broj odgovara tom proizvodu\n"
            "Za opći pregled svih naimenovanja: tabela Rb. | Tarif. br. | Opis | Status | Komentar\n\n"
            f"{context}"
            f"{memory_info}"
        )
