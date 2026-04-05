"""
Tariff Intent Service — prijedlog, provjera i brisanje tarifnih brojeva.

Business logika za:
- Batch prijedlog tarifnih brojeva (lokalna baza + LLM fallback)
- Prijedlog po filter keyword-u
- Provjera tarifnog za konkretan naziv robe (HybridTariffAgent)
- Brisanje svih tarifnih brojeva
- Izvršenje popune tarifnih nakon potvrde
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class TariffProposal:
    """Prijedlog tarifnog broja za jednu stavku."""
    line_index: int
    naziv_robe: str
    product_code: str
    proposed_tariff: str
    confidence: float
    source: str  # "baza_znanja" | "rag" | "llm"


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
        Analizira stavke bez tarifnog broja — lokalna baza.
        Vraća prijedloge ili None ako su sve već popunjene.
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

        self._activity(f"🔍 Tražim u lokalnoj bazi za {len(bez_tarife)} stavki...")

        from services.tariff_mapping_service import TariffMappingService
        svc = TariffMappingService()
        proposals: List[TariffProposal] = []
        bez_lokalne: List[Tuple[int, Any]] = []

        for idx, line in bez_tarife:
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

        return self._handle_llm_fallback(proposals, bez_lokalne, len(bez_tarife))

    # ─────────────────────────────────────────────────────
    # PRIJEDLOG PO FILTERU
    # ─────────────────────────────────────────────────────

    def propose_by_keyword(self, keyword: str) -> Optional[List[TariffProposal]]:
        """
        Predlaže tarifne brojeve samo za stavke čiji naziv_robe sadrži keyword.
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

        self._activity(f"🔍 Nađeno {len(filtrirane)} stavki s '{keyword}', tražim tarifne...")

        from services.tariff_mapping_service import TariffMappingService
        svc = TariffMappingService()
        proposals: List[TariffProposal] = []
        bez_lokalne: List[Tuple[int, Any]] = []

        for idx, line in filtrirane:
            naziv = (getattr(line, 'naziv_robe', '') or '').strip()
            product_code = (getattr(line, 'product_code', '') or '').strip()
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

        return self._handle_llm_fallback(proposals, bez_lokalne, len(filtrirane))

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

        linije = []
        for p in svi:
            pct = int(p.confidence * 100)
            izvor = "📚 baza" if p.source == "baza_znanja" else "🤖 AI"
            linije.append(
                f"&nbsp;&nbsp;• <b>{p.proposed_tariff}</b> — {p.naziv_robe} "
                f"<small>({izvor}, {pct}% sigurnost)</small>"
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
        for p in proposals:
            line = self.draft.invoice_lines[p.line_index]
            line.tarifni_broj = p.proposed_tariff
            upisano += 1

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
                obrisano += 1

        if self.on_refresh_faktura:
            QApplication.processEvents()
            self.on_refresh_faktura()

        self._msg(f"✅ Obrisano <b>{obrisano}</b> tarifnih brojeva iz Faktura taba.")

    # ─────────────────────────────────────────────────────
    # PROVJERA TARIFNOG ZA NAZIV
    # ─────────────────────────────────────────────────────

    def check_tariff_for_name(self, naziv_robe: str):
        """Pozovi HybridTariffAgent za konkretan naziv robe."""
        self._activity(f"🔍 Provjera tarifnog za: {naziv_robe}")

        from PySide6.QtCore import QThread, Signal, QObject
        from services.agent.hybrid_tariff_agent import HybridTariffAgent

        class _TariffCheckWorker(QThread):
            done = Signal(dict)
            error = Signal(str)

            def __init__(self_, naziv):
                super().__init__()
                self_._naziv = naziv

            def run(self_):
                try:
                    agent = HybridTariffAgent()
                    result = agent.decide_tariff(self_._naziv)
                    self_.done.emit(result)
                except Exception as e:
                    self_.error.emit(str(e))

        worker = _TariffCheckWorker(naziv_robe)

        def _on_done(result):
            confidence = result.get('confidence', 0)
            tarifni = result.get('tarifni_broj', 'N/A')
            metoda = result.get('method', 'N/A')
            needs_review = result.get('needs_review', False)
            explanation = result.get('explanation', '')
            candidates = result.get('candidates', [])

            if confidence >= 0.85:
                conf_ikona, conf_status = "✅", "visok — auto-prihvati"
            elif confidence >= 0.60:
                conf_ikona, conf_status = "⚠️", "srednji — pregledaj"
            else:
                conf_ikona, conf_status = "❌", "nizak — obavezno pregledaj"

            lines = [
                f"<b>📌 Tarifni broj:</b> <code>{tarifni}</code>",
                f"<b>📊 Confidence:</b> {conf_ikona} {confidence:.0%} ({conf_status})",
                f"<b>🔧 Metoda:</b> {metoda}",
                f"<b>⚠️ Review:</b> {'DA' if needs_review else 'NE'}",
            ]
            if explanation:
                lines.append(f"<br><b>📝 Objašnjenje:</b><br>{explanation[:300]}")
            if candidates:
                alts = []
                for c in candidates[:3]:
                    alts.append(
                        f"• {c.get('tarifni_broj','?')} "
                        f"({c.get('confidence',0):.0%}) — "
                        f"{c.get('naziv_robe','')[:40]}"
                    )
                lines.append("<br><b>📋 Alternative:</b><br>" + "<br>".join(alts))

            self._msg("<br>".join(lines))
            self._activity(f"✅ Tarifni za '{naziv_robe}': {tarifni} ({confidence:.0%})")

        def _on_error(err):
            self._msg(f"❌ Greška pri provjeri tarifnog: {err}")

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
