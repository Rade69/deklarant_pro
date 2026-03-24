"""
ChatWorker - background thread za LLM pozive (Groq API).

ENHANCED: Dodato pamćenje konteksta chat sesije.
" tačno moram uraditi da ga aktiviram.add()""

import re
from PySide6.QtCore import QThread, Signal


class ChatWorker(QThread):
    """Poziva Groq API u pozadini da ne blokira UI."""

    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, message: str, draft=None, parent=None, 
                 memory_service=None):
        super().__init__(parent)
        self.message = message
        self.draft = draft
        # ENHANCED: Memory service za pamćenje konteksta
        self.memory_service = memory_service

    def run(self):
        try:
            from groq import Groq
            from dotenv import dotenv_values
            import os
            from pathlib import Path

            # Čitaj direktno iz .env
            env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
            env_vars = dotenv_values(env_path) if env_path.exists() else {}

            api_key = env_vars.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
            if not api_key:
                self.error_occurred.emit("GROQ_API_KEY nije pronađen u .env fajlu.")
                return

            # Izgradi kontekst iz drafta
            context = self._build_context()

            # ENHANCED: Dobij chat historiju iz memorije
            chat_history = []
            if self.memory_service:
                chat_history = self.memory_service.get_context(max_messages=10)
            
            # ENHANCED: Dodaj korisničku poruku u memoriju PRIJE slanja
            if self.memory_service:
                self.memory_service.add_user_message(self.message)

            client = Groq(api_key=api_key)
            
            # ENHANCED: Sastavi poruke sa historijom
            messages = self._build_messages(context, chat_history)
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.2,
                max_tokens=1500,
            )

            text = response.choices[0].message.content.strip()
            
            # ENHANCED: Dodaj AI odgovor u memoriju NAKON dobijanja
            if self.memory_service:
                self.memory_service.add_assistant_message(text)
            
            self.response_ready.emit(text)

        except Exception as e:
            self.error_occurred.emit(f"LLM greška: {e}")

    def _build_messages(self, context: str, chat_history: list) -> list:
        """
        ENHANCED: Sastavi messages listu za API sa chat historijom.
        
        Format:
        1. System prompt (kontekst + sistemske instrukcije)
        2. Chat historija (zadnjih 10 poruka)
        3. Trenutna korisnička poruka
        """
        system = {"role": "system", "content": self._system_prompt(context)}
        
        messages = [system]
        
        # ENHANCED: Dodaj chat historiju (bez system poruka iz historije)
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

        # === SVE STAVKE (kompaktan format) ===
        sve_stavke = []
        for i, l in enumerate(lines, 1):
            naziv = getattr(l, 'naziv_robe', '') or ''
            tarifa = getattr(l, 'tarifni_broj', '') or '?'
            zemlja = getattr(l, 'zemlja_porijekla', '') or '?'
            kolicina = getattr(l, 'kolicina', None)
            jm = getattr(l, 'jm', '') or ''
            bruto = getattr(l, 'bruto_kg', 0) or 0
            neto = getattr(l, 'neto_kg', 0) or 0
            pov = getattr(l, 'povlastica', '') or '-'
            eur1 = getattr(l, 'eur1_number', '') or ''
            kol_str = f"{kolicina} {jm}".strip() if kolicina else '?'
            eur1_str = f" eur1={eur1}" if eur1 else ""
            tarifa_marker = "" if tarifa != '?' else " ⚠️NEMA_TARIFE"
            zemlja_marker = "" if zemlja != '?' else " ⚠️NEMA_ZEMLJE"
            sve_stavke.append(
                f"  {i:3d}. {naziv[:55]:<55} | tarifa={tarifa}{tarifa_marker} | "
                f"zemlja={zemlja}{zemlja_marker} | kol={kol_str} | "
                f"bruto={bruto:.2f}kg neto={neto:.2f}kg | pov={pov}{eur1_str}"
            )

        # === PRIJEDLOZI IZ BAZE ZNANJA za stavke bez tarife ===
        kb_prijedlozi = []
        if bez_tarife_list:
            try:
                from services.tariff_mapping_service import TariffMappingService
                mapping_svc = TariffMappingService()
                for l in bez_tarife_list[:20]:  # Max 20 upita
                    naziv = getattr(l, 'naziv_robe', '') or ''
                    product_code = getattr(l, 'product_code', '') or ''
                    zemlja = getattr(l, 'zemlja_porijekla', '') or ''
                    mapping = mapping_svc.find_mapping(
                        product_code, naziv,
                        min_similarity=0.60,
                        zemlja_porijekla=zemlja
                    )
                    if mapping:
                        kb_prijedlozi.append(
                            f"  '{naziv[:50]}' → tarifa={mapping.tarifni_broj} "
                            f"(sličnost={mapping.similarity:.0%}, "
                            f"korišten {mapping.usage_count}x)"
                        )
                    else:
                        kb_prijedlozi.append(f"  '{naziv[:50]}' → (nije u bazi znanja)")
            except Exception as e:
                kb_prijedlozi.append(f"  (greška pri upitu baze znanja: {e})")

        # === ISTORIJA IZ DEKLARACIJA (RAG) za stavke bez tarife ===
        rag_prijedlozi = []
        if bez_tarife_list:
            try:
                from services.agent.tariff_rag_service import TariffRAGService
                rag_svc = TariffRAGService()
                seen_queries = set()
                for l in bez_tarife_list[:10]:
                    naziv = getattr(l, 'naziv_robe', '') or ''
                    if naziv and naziv not in seen_queries:
                        seen_queries.add(naziv)
                        results = rag_svc.search_historical(naziv, limit=2)
                        for r in results:
                            rag_prijedlozi.append(
                                f"  '{naziv[:40]}' → tarifa={r.get('tarifni_kod', '?')} "
                                f"(historija: {r.get('naziv_robe', '')[:40]})"
                            )
            except Exception:
                pass  # RAG nije kritičan

        # === Sastavni kontekst ===
        ctx = [
            f"=== STANJE DRAFTA ===",
            f"Ukupno stavki: {total}",
            f"Bez tarifnog broja: {len(bez_tarife_list)}",
            f"Bez zemlje porijekla: {len(bez_zemlje_list)}",
            f"Sa povlasticom: {sa_povlasticom}",
            f"Čeka EUR1 broj: {bez_eur1}",
            f"Zemlja distribucija: {country_str}",
            "",
            f"=== SVE STAVKE ({total}) ===",
        ]
        ctx.extend(sve_stavke)

        if kb_prijedlozi:
            ctx.append("")
            ctx.append(f"=== BAZA ZNANJA — prijedlozi tarife za stavke bez tarife ===")
            ctx.extend(kb_prijedlozi)

        if rag_prijedlozi:
            ctx.append("")
            ctx.append(f"=== ISTORIJA DEKLARACIJA — prijedlozi tarife ===")
            ctx.extend(rag_prijedlozi)

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

        # === VALIDACIJA TARIFNIH BROJEVA — samo kada se traži pregled/provjera ===
        if self._is_review_request(msg):
            tariff_validation = self._build_tariff_validation_context(lines)
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

    @staticmethod
    def _is_review_request(msg: str) -> bool:
        """Da li korisnik traži pregled/validaciju deklaracije?"""
        keywords = [
            'pregled', 'pregledaj', 'provjeri', 'provjera', 'validiraj', 'validacija',
            'uskladi', 'usklađ', 'tarifni broj', 'tarife', 'ispravan', 'ispravnost',
            'greška', 'grešk', 'da li je sve', 'sve u redu', 'review', 'check'
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
        Za svaki jedinstveni tarifni broj iz drafta dohvata opis iz Carinske tarife.
        Rezultat omogućava Groq-u da poredi nazive robe sa zvaničnim opisima tarife.
        """
        if not lines:
            return []
        # Skupi jedinstvene tarifne brojeve (max 30 da ne preopteretimo kontekst)
        seen = {}
        for l in lines:
            code = getattr(l, 'tarifni_broj', None)
            naziv = getattr(l, 'naziv_robe', '') or ''
            if code and code not in seen:
                seen[code] = naziv
            if len(seen) >= 20:
                break
        if not seen:
            return []
        try:
            from services.knowledge_base.kb_service import KnowledgeBaseService
            svc = KnowledgeBaseService()
            stats = svc.get_stats()
            if stats["doc_count"] == 0:
                return []
            descriptions = svc.get_tariff_descriptions(list(seen.keys()))
            lines_out = []
            lines_out.append(
                f"  {'Tarifni br.':<14} {'Naziv u deklaraciji':<45} Opis iz tarife"
            )
            lines_out.append("  " + "-" * 110)
            for code, naziv in seen.items():
                opis_chunk = descriptions.get(code)
                if opis_chunk:
                    # Izvuci samo prvi red odlomka koji sadrži kod — najrelevantniji dio
                    opis = self._extract_tariff_line(code, opis_chunk)
                else:
                    opis = "(nije pronađen u tarifi)"
                lines_out.append(
                    f"  {code:<14} {naziv[:40]:<41} {opis[:80]}"
                )
            return lines_out
        except Exception:
            return []

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
        """Da li korisnik pita za historijske deklaracije, partnere ili bazu?"""
        keywords = [
            # Historija deklaracija
            'historij', 'prethodn', 'ranije', 'deklaracij', 'xml', 'asycuda',
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
                    ctx.append(f"\nHistorijske stavke sa tarifom {tariff_match}:")
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
                    ctx.append(f"\nRoba pronađena u historijskim deklaracijama:")
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
                    ctx.append(f"\nPartneri pronađeni u historijskim deklaracijama:")
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
            results = []
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    for word in words[:3]:
                        cur.execute(
                            "SELECT code, name, type FROM public.traders "
                            "WHERE name ILIKE %s LIMIT 5",
                            (f"%{word}%",)
                        )
                        for row in cur.fetchall():
                            results.append(
                                f"  [{row['type']}] {row['name']} (kod: {row['code']})"
                            )
            return list(dict.fromkeys(results))  # deduplicate
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
            "Ti si AI asistent za carinsku deklaraciju u aplikaciji AsycudaPro (Bosna i Hercegovina).\n"
            "Odgovaraš na srpskom jeziku (latinica), konkretno i korisno.\n\n"
            "TVOJE SPOSOBNOSTI:\n"
            "- Vidiš SVE stavke iz aktivnog drafta (fakture) — sa tarifnim brojevima, zemljama, težinama, povlasticama\n"
            "- Imaš pristup bazi znanja (product_tariff_mapping) — prijedlozi tarife za nepoznate proizvode\n"
            "- Imaš pristup istoriji deklaracija — tarife koje su ranije korišćene za iste/slične proizvode\n"
            "- Imaš pristup zakonskoj regulativi (carinski zakoni, pravilnici BiH) — relevantni odlomci su priloženi u kontekstu\n"
            "- Možeš pretraživati arhiv od 2500+ historijskih XML deklaracija iz sistema ASYCUDA\n"
            "- Možeš pretraživati PostgreSQL bazu podataka: partnere (izvoznike, primaoce), tarifne mappinge\n"
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
            "- Ako vidiš stavke označene sa ⚠️NEMA_TARIFE — predloži konkretni tarifni broj\n"
            "- Koristi prijedloge iz baze znanja i istorije kao osnovu, ali ih provjeri sa znanjem\n"
            "- Ako nisi siguran za tarifni broj — reci to jasno i predloži alternativu za provjeru\n"
            "- Odgovori na specifična pitanja o konkretnim stavkama (npr. 'Stavka 5 — koji tarif?')\n\n"
            "PREGLED DEKLARACIJE (kad korisnik traži provjeru/pregled/validaciju):\n"
            "- U kontekstu imaš sekciju 'TARIFNI BROJEVI — opisi iz Carinske tarife 2026'\n"
            "- Svaki red sadrži: tarifni broj | naziv robe iz deklaracije | opis iz zvanične tarife\n"
            "- Tvoj zadatak: poredi naziv robe sa opisom tarife i prijavi neusklađenosti\n"
            "- Format odgovora: tabela sa kolonama Tarifni br. | Roba | Status | Komentar\n"
            "- Status može biti: ✅ Usklađeno | ⚠️ Provjeri | ❌ Neusklađeno\n"
            "- Na kraju daj ukupnu ocjenu deklaracije i prioritetne preporuke\n\n"
            f"{context}"
            f"{memory_info}"
        )
