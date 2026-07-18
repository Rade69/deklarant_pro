"""
Tariff Intent Service — predlog, provjera i brisanje tarifnih brojeva.

Business logika za:
- Batch predlog tarifnih brojeva (istorija dobavljača + lokalna baza + LLM fallback)
- Predlog po filter keyword-u
- Provjera tarifnog za konkretan naziv robe (HybridTariffAgent)
- Brisanje svih tarifnih brojeva
- Izvršenje popune tarifnih nakon potvrde

📄 Detalji: memory/project_tariff_history_prediction.md
   scripts/CHANGES_2026-04-26.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("deklarant_pro.agent.tariff_intent")


@dataclass
class TariffProposal:
    """Predlog tarifnog broja za jednu stavku."""
    line_index: int
    naziv_robe: str
    product_code: str
    proposed_tariff: str
    confidence: float
    source: str  # "istorija" | "baza_znanja" | "rag" | "llm"
    source_detail: str = ""  # npr. ime dobavljača, broj prethodnih upotreba


class TariffIntentService:
    """
    Service za tarifne operacije — nezavisan od GUI-a.
    Prima callbacks za UI interakcije.
    """

    def __init__(self, draft):
        self.draft = draft
        # Callback-i koje postavlja Controller
        self.on_activity: Optional[Callable[[str], None]] = None
        self.on_agent_message: Optional[Callable[[str], None]] = None
        self.on_set_pending: Optional[Callable[[Any], None]] = None
        self.on_refresh_faktura: Optional[Callable[[], None]] = None

    # ─────────────────────────────────────────────────────
    # BATCH PRIJEDLOG
    # ─────────────────────────────────────────────────────

    def propose_all(self) -> Optional[List[TariffProposal]]:
        """
        Analizira stavke bez tarifnog broja.
        Redosled: 1) istorija dobavljača  2) lokalna baza znanja  3) LLM
        Vraća predloge ili None ako su sve već popunjene.
        """
        if not self.draft or not self.draft.invoice_lines:
            self._msg("⚠️ Nema učitanih stavki u Faktura tabu.")
            return None

        bez_tarife = [
            (i, line) for i, line in enumerate(self.draft.invoice_lines)
            if not line.tarifni_broj or not line.tarifni_broj.strip()
        ]

        if not bez_tarife:
            self._msg("✅ Sve stavke već imaju upisane tarifne brojeve.")
            return None

        # ── 0. Dobavi ime dobavljača za istorijsku proveru ──
        exporter_name = self._get_exporter_name()

        self._activity(f"🔍 Tražim tarifne brojeve za {len(bez_tarife)} stavki...")

        from services.tariff_mapping_service import TariffMappingService
        from services.agent.tariff.tariff_suggestion_service import HybridMatchingService
        svc = TariffMappingService()
        hybrid = HybridMatchingService() if exporter_name else None
        proposals: List[TariffProposal] = []
        bez_lokalne: List[Tuple[int, Any]] = []

        # ── Batch lookup po product_code (1 SQL umjesto N) ──
        all_codes = [getattr(l, 'product_code', '') or '' for _, l in bez_tarife]
        batch_hits = svc.find_batch_by_product_codes(all_codes)

        istorijskih = 0

        for idx, line in bez_tarife:
            # ── 1. Prvo proveri istoriju dobavljača ──
            if exporter_name and hybrid:
                hist_match = self._try_history_match(
                    hybrid, exporter_name, line.product_code, line.naziv_robe,
                    getattr(line, 'zemlja_porijekla', '')
                )
                if hist_match:
                    hist_match.line_index = idx
                    proposals.append(hist_match)
                    istorijskih += 1
                    continue

            # ── 2. Batch hit po product_code ──
            code_key = (line.product_code or '').strip().upper()
            batch_mapping = batch_hits.get(code_key)
            if batch_mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=line.naziv_robe[:60],
                    product_code=line.product_code,
                    proposed_tariff=batch_mapping.tarifni_broj,
                    confidence=1.0,
                    source="baza_znanja"
                ))
                continue

            # ── 3. Lokalna baza — fuzzy/vote za linije bez product_code hita ──
            mapping = svc.find_mapping(
                product_code=line.product_code,
                naziv_robe=line.naziv_robe,
                min_similarity=0.92
            )
            if mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=line.naziv_robe[:60],
                    product_code=line.product_code,
                    proposed_tariff=mapping.tarifni_broj,
                    confidence=mapping.similarity if hasattr(mapping, 'similarity') else 1.0,
                    source="baza_znanja"
                ))
            else:
                bez_lokalne.append((idx, line))

        if istorijskih:
            self._activity(
                f"📚 Istorija ({exporter_name}): {istorijskih} stavki rešeno iz ranijih deklaracija"
            )

        return self._handle_llm_fallback(proposals, bez_lokalne, len(bez_tarife))

    # ─────────────────────────────────────────────────────
    # PRIJEDLOG PO FILTERU
    # ─────────────────────────────────────────────────────

    def propose_by_keyword(self, keyword: str) -> Optional[List[TariffProposal]]:
        """
        Predlaže tarifne brojeve za stavke čiji naziv_robe sadrži keyword.
        Redosled: 1) istorija dobavljača  2) lokalna baza  3) LLM
        """
        if not self.draft or not self.draft.invoice_lines:
            self._msg("⚠️ Nema učitanih stavki u Faktura tabu.")
            return None

        kw = keyword.lower().strip()

        filtrirane = [
            (i, line) for i, line in enumerate(self.draft.invoice_lines)
            if kw in (getattr(line, 'naziv_robe', '') or '').lower()
        ]

        if not filtrirane:
            self._msg(f"⚠️ Nema stavki čiji naziv sadrži '{keyword}'.")
            return None

        # ── 0. Dobavi ime dobavljača ──
        exporter_name = self._get_exporter_name()

        self._activity(f"🔍 Nađeno {len(filtrirane)} stavki s '{keyword}', tražim tarifne...")

        from services.tariff_mapping_service import TariffMappingService
        from services.agent.tariff.tariff_suggestion_service import HybridMatchingService
        svc = TariffMappingService()
        hybrid = HybridMatchingService() if exporter_name else None
        proposals: List[TariffProposal] = []
        bez_lokalne: List[Tuple[int, Any]] = []

        # ── Batch lookup po product_code (1 SQL umjesto N) ──
        all_codes = [getattr(l, 'product_code', '') or '' for _, l in filtrirane]
        batch_hits = svc.find_batch_by_product_codes(all_codes)

        istorijskih = 0

        for idx, line in filtrirane:
            naziv = (getattr(line, 'naziv_robe', '') or '').strip()
            product_code = (getattr(line, 'product_code', '') or '').strip()
            country = getattr(line, 'zemlja_porijekla', '') or ''

            # ── 1. Prvo istorija dobavljača ──
            if exporter_name and hybrid:
                hist_match = self._try_history_match(
                    hybrid, exporter_name, product_code, naziv, country
                )
                if hist_match:
                    hist_match.line_index = idx
                    proposals.append(hist_match)
                    istorijskih += 1
                    continue

            # ── 2. Batch hit po product_code ──
            batch_mapping = batch_hits.get(product_code.upper())
            if batch_mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=naziv[:60],
                    product_code=product_code,
                    proposed_tariff=batch_mapping.tarifni_broj,
                    confidence=1.0,
                    source="baza_znanja"
                ))
                continue

            # ── 3. Lokalna baza — fuzzy/vote za linije bez product_code hita ──
            mapping = svc.find_mapping(
                product_code=product_code,
                naziv_robe=naziv,
                min_similarity=0.92
            )
            if mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=naziv[:60],
                    product_code=product_code,
                    proposed_tariff=mapping.tarifni_broj,
                    confidence=mapping.similarity if hasattr(mapping, 'similarity') else 1.0,
                    source="baza_znanja"
                ))
            else:
                bez_lokalne.append((idx, line))

        if istorijskih:
            self._activity(
                f"📚 Istorija ({exporter_name}): {istorijskih} stavki rešeno iz ranijih deklaracija"
            )

        return self._handle_llm_fallback(proposals, bez_lokalne, len(filtrirane))

    # ─────────────────────────────────────────────────────
    # ISTORIJSKI MATCHING (dobavljač → tarifni broj)
    # ─────────────────────────────────────────────────────

    def _get_exporter_name(self) -> str:
        """Izvlači ime dobavljača (exporter) iz drafta."""
        if self.draft and hasattr(self.draft, 'exporter') and self.draft.exporter:
            name = getattr(self.draft.exporter, 'name', '') or ''
            if name.strip():
                return name.strip()
        if self.draft and self.draft.invoice_lines:
            for line in self.draft.invoice_lines:
                if hasattr(line, 'exporter') and line.exporter:
                    name = getattr(line.exporter, 'name', '') or ''
                    if name.strip():
                        return name.strip()
        return ""

    def _try_history_match(
        self, hybrid, exporter_name: str, product_code: str, naziv_robe: str, country: str
    ) -> Optional[TariffProposal]:
        """
        Pokušaj da nađeš tarifni broj iz istorije dobavljača.
        Koristi HybridMatchingService sa težinom na istorijskom match-u.
        """
        try:
            match = hybrid.find_hybrid_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                supplier=exporter_name,
                country=country,
                min_confidence=0.75
            )
            if match and match.confidence >= 0.82:
                detail = f"{exporter_name}, {match.explanation}"
                return TariffProposal(
                    line_index=-1,  # postaviće se u pozivaocu
                    naziv_robe=naziv_robe[:60],
                    product_code=product_code,
                    proposed_tariff=match.tariff_mapping.tarifni_broj,
                    confidence=match.confidence,
                    source="istorija",
                    source_detail=detail
                )
        except Exception:
            pass  # Silent — istorijski match nije kritičan
        return None

    # ─────────────────────────────────────────────────────
    # LLM FALLBACK
    # ─────────────────────────────────────────────────────

    def _handle_llm_fallback(self, local_proposals, bez_lokalne, ukupno_bez):
        """Pokušaj LLM za preostale stavke."""
        if not bez_lokalne:
            return self._show_proposals(local_proposals, [], ukupno_bez)

        self._activity(
            f"✅ Lokalna baza: {len(local_proposals)} prijedloga. "
            f"🤖 Pitam AI za preostalih {len(bez_lokalne)} stavki..."
        )

        # Pokreni LLM worker — callback će show_results
        from gui.tabs.agent.widgets.tariff_llm_worker import TariffLLMWorker
        worker = TariffLLMWorker(bez_lokalne, parent=self._view_ref())
        worker.proposals_ready.connect(
            lambda llm_p: self._show_proposals(local_proposals, llm_p, ukupno_bez)
        )
        worker.error_occurred.connect(
            lambda _: self._show_proposals(local_proposals, [], ukupno_bez)
        )
        worker.finished.connect(worker.deleteLater)

        # Sačuvaj referencu na controller-u da GC ne ubije
        ctrl = getattr(self, '_controller_ref', None)
        if ctrl:
            if not hasattr(ctrl, '_tariff_workers'):
                ctrl._tariff_workers = []
            ctrl._tariff_workers.append(worker)
            worker.finished.connect(
                lambda: ctrl._tariff_workers.remove(worker) if worker in ctrl._tariff_workers else None
            )
        worker.start()
        return None  # LLM je async — rezultat ide kroz callback

    def _show_proposals(self, local_proposals, llm_proposals, ukupno_bez):
        """Prikaži kombinirane prijedloge korisniku."""
        svi = local_proposals + llm_proposals

        if not svi:
            self._msg(
                f"⚠️ Nisam uspio naći prijedloge za <b>{ukupno_bez}</b> stavki "
                f"ni u lokalnoj bazi ni putem AI-a.<br>"
                f"Pokušaj pretraživanjem tarifne tarife ili ručnim unosom."
            )
            return svi

        from services.agent.validation.evidence_model import badge_colors_for_score

        linije = []
        for p in svi:
            pct = int(p.confidence * 100)
            if p.source == "istorija":
                izvor = "📚 istorija"
                detail = f" — {p.source_detail}" if p.source_detail else ""
            elif p.source == "baza_znanja":
                izvor = "📚 baza"
                detail = ""
            else:
                izvor = "🤖 AI"
                detail = ""
            badge_color, badge_bg = badge_colors_for_score(pct)
            pouzdanost = (
                f"<span style='background:{badge_bg}; color:{badge_color}; "
                f"padding:1px 6px; border-radius:4px; font-weight:600;'>{pct}%</span>"
            )
            linije.append(
                f"&nbsp;&nbsp;• <b>{p.proposed_tariff}</b> — {p.naziv_robe} "
                f"<small>({izvor}{detail}, pouzdanost {pouzdanost})</small>"
            )

        nema = ukupno_bez - len(svi)
        napomena = f"<br><small>⚠️ Za {nema} stavki nije nađen prijedlog.</small>" if nema else ""

        # Postavi pending akciju
        if self.on_set_pending:
            from gui.tabs.agent.agent_actions import PendingAction
            self.on_set_pending(PendingAction(
                action_type="fill_tariff",
                proposals=svi,
                description=f"Upiši {len(svi)} tarifnih brojeva"
            ))

        self._msg(
            f"📋 Prijedlozi za <b>{len(svi)}</b> od {ukupno_bez} stavki:<br><br>"
            + "<br>".join(linije)
            + napomena
            + "<br><br>✏️ <b>Upisujem u tabelu? Odgovori: Da / Ne</b>"
        )
        return svi

    # ─────────────────────────────────────────────────────
    # IZVRŠENJE POPUNE
    # ─────────────────────────────────────────────────────

    def execute_fill(self, proposals, chat=None):
        """Upiši predložene tarifne brojeve u draft i osvježi Faktura tab."""
        from PySide6.QtWidgets import QApplication

        upisano = 0
        changed_lines = []
        for p in proposals:
            line = self.draft.invoice_lines[p.line_index]
            line.tarifni_broj = p.proposed_tariff
            changed_lines.append(line)
            upisano += 1

        # Sinhronizuj decision_state nakon agent batch popune
        if changed_lines:
            try:
                from services.decision.integration import sync_decision_state_after_autofill
                sync_decision_state_after_autofill(changed_lines, action_type="dialog_confirmed")
            except Exception:
                logger.warning("Decision sync agent fill nije uspeo", exc_info=True)

        if self.on_refresh_faktura:
            QApplication.processEvents()
            self.on_refresh_faktura()

        self._msg(
            f"✅ <b>Upisano {upisano} tarifnih brojeva</b> u Faktura tab.<br>"
            f"Provjeri tabelu i korigiši ako je potrebno."
        )

    # ─────────────────────────────────────────────────────
    # BRISANJE
    # ─────────────────────────────────────────────────────

    def delete_all(self):
        """Obriši sve tarifne brojeve iz draft.invoice_lines."""
        from PySide6.QtWidgets import QApplication

        if not self.draft or not self.draft.invoice_lines:
            self._msg("⚠️ Nema učitanih stavki.")
            return

        obrisano = 0
        for line in self.draft.invoice_lines:
            if getattr(line, 'tarifni_broj', None):
                line.tarifni_broj = ''
                # Resetuj i decision_state za tarifu
                if line.decision_state:
                    from core.decision.decision_model import DecisionStatus
                    line.decision_state.tariff.status = DecisionStatus.UNKNOWN
                    line.decision_state.tariff.applied_value = ''
                obrisano += 1

        if self.on_refresh_faktura:
            QApplication.processEvents()
            self.on_refresh_faktura()

        self._msg(f"✅ Obrisano <b>{obrisano}</b> tarifnih brojeva iz Faktura taba.")

    # ─────────────────────────────────────────────────────
    # PRIJEDLOG TARIFNOG ZA KONKRETAN NAZIV (DeepSeek)
    # ─────────────────────────────────────────────────────

    def check_tariff_for_name(self, naziv_robe: str):
        """
        Predlaži tarifni broj za naziv robe.

        Tok:
        1. Lokalna baza znanja (TariffMappingService fuzzy match)
        2. RAG pretraga zvanicna_tarifa.db
        3. DeepSeek direktni poziv sa HS kontekstom iz RAG-a
        """
        self._activity(f"🔍 Tražim tarifni za: {naziv_robe}")

        from PySide6.QtCore import QThread, Signal

        svc_ref = self

        class _Worker(QThread):
            done = Signal(str)
            error = Signal(str)

            def __init__(self_, naziv):
                super().__init__()
                self_._naziv = naziv

            def run(self_):
                try:
                    naziv = self_._naziv

                    # DeepSeek direktno — bez RAG, bez baze kao konteksta
                    # RAG i baza znanja sidre model na pogrešan tarif.
                    # DeepSeek poznaje HS nomenklaturu — pustiti ga da klasificira slobodno.
                    from gui.tabs.agent.widgets.llm_provider import LLMProvider
                    provider = LLMProvider()

                    system_msg = (
                        "Si ekspert za carinsku tarifu (Harmonizovani sistem — HS/TARIC). "
                        "Odgovaraj na srpskom jeziku, kratko i precizno.\n"
                        "PRAVILA:\n"
                        "1. Uvijek razmotri materijal (plastika, sintetička vlakna, čelik, guma...), "
                        "funkciju i upotrebu — ne samo doslovan prijevod naziva.\n"
                        "2. Predloži opcije iz RAZLIČITIH poglavlja HS-a. "
                        "Npr. isti predmet može biti klasificiran u poglavlju 39 (plastika), "
                        "56 (sintetička vlakna/konopci), 73 (čelik) — sve ovisi o materijalu.\n"
                        "3. Nikada ne predlažaj samo jedno poglavlje. "
                        "Ako si nesiguran, navedite opcije za različite materijale.\n"
                        "4. Format odgovora (svaka opcija u novom redu):\n"
                        "**XXXXXXXX** — [naziv iz HS tarife] — [materijal i zašto odgovara]\n"
                        "5. Tarifni broj = 8 cifara bez tačaka. Bez uvoda, bez zaključka."
                    )

                    user_msg = (
                        f'Predloži tarifni HS broj za robu: "{naziv}"\n'
                        f'Daj 4-5 opcija iz RAZLIČITIH poglavlja: '
                        f'razmisli o sintetičkim vlaknima, plastici, gumi, metalu, '
                        f'dijelovima mašina — i objasni za koji materijal/upotrebu odgovara svaki.'
                    )

                    messages = [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ]
                    result = provider.complete(messages, max_tokens=350, use_small_model=False)
                    self_.done.emit(result.strip())

                except Exception as e:
                    self_.error.emit(str(e))

        worker = _Worker(naziv_robe)

        def _on_done(text):
            svc_ref._msg(
                f"<b>📌 Prijedlog tarifnog za: {naziv_robe}</b><br><br>"
                f"{text}<br><br>"
                f"💾 Da sačuvaš u bazu znanja, reci npr.:<br>"
                f"<i>Zapamti 84713000 za {naziv_robe}</i>"
            )
            svc_ref._activity(f"✅ Prijedlog tarifnog za '{naziv_robe}' gotov")

        def _on_error(err):
            svc_ref._msg(f"❌ Greška pri traženju tarifnog: {err}")

        worker.done.connect(_on_done)
        worker.error.connect(_on_error)
        worker.finished.connect(worker.deleteLater)

        ctrl = getattr(self, '_controller_ref', None)
        if ctrl:
            if not hasattr(ctrl, '_tariff_check_workers'):
                ctrl._tariff_check_workers = []
            ctrl._tariff_check_workers.append(worker)
        worker.start()

    # ─────────────────────────────────────────────────────
    # SNIMANJE U BAZU ZNANJA
    # ─────────────────────────────────────────────────────

    def learn_tariff(self, naziv_robe: str, tarifni_broj: str):
        """
        Sačuvaj mapiranje naziv_robe → tarifni_broj u bazu znanja.
        Korisnik eksplicitno kaže da je tarifni tačan.
        """
        import re
        # Normalizuj — samo cifre, 8 znakova
        digits = re.sub(r'\D', '', tarifni_broj)[:8]
        if len(digits) != 8:
            self._msg(
                f"⚠️ Tarifni broj mora imati 8 cifara (upisano: <b>{tarifni_broj}</b>).<br>"
                f"Primjer: <i>Zapamti 84713000 za laptop</i>"
            )
            return

        # Pronađi product_code ako roba postoji u draft.invoice_lines
        product_code = ""
        if self.draft and self.draft.invoice_lines:
            kw = naziv_robe.lower().strip()
            for line in self.draft.invoice_lines:
                if kw in (getattr(line, 'naziv_robe', '') or '').lower():
                    product_code = getattr(line, 'product_code', '') or ''
                    break

        try:
            from services.tariff_mapping_service import TariffMappingService
            svc = TariffMappingService()

            # Obriši sve stare zapise za ovaj naziv/product_code — korisnik potvrđuje tačan tarif.
            # Bez brisanja, stari pogrešni zapis (sa visokim usage_count) pobijedi pri auto-popuni.
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM catalogs.product_tariff_mapping
                        WHERE naziv_robe ILIKE %s
                           OR (product_code = %s AND product_code != '')
                    """, (f"%{naziv_robe}%", product_code or "__NONE__"))

            ok = svc.save_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                tarifni_broj=digits,
            )
            if ok:
                self._msg(
                    f"✅ <b>Zapamćeno!</b> <code>{digits}</code> → <b>{naziv_robe}</b><br>"
                    f"<small>Sačuvano u bazu znanja — koristiće se automatski pri sljedećem uvozu.</small>"
                )
            else:
                self._msg(f"⚠️ Nije sačuvano — provjeri tarifni broj <b>{digits}</b>.")
        except Exception as e:
            self._msg(f"❌ Greška pri snimanju: {e}")

    # ─────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────

    def _msg(self, text: str):
        if self.on_agent_message:
            self.on_agent_message(text)

    def _activity(self, text: str):
        if self.on_activity:
            self.on_activity(text)

    def _view_ref(self):
        """Vraća view referencu za parent widget."""
        ctrl = getattr(self, '_controller_ref', None)
        if ctrl and hasattr(ctrl, 'view'):
            return ctrl.view
        return None


