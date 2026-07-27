"""
Agent Controller - business logic za tri pipeline moda.

📄 Popravka dugmeta: memory/project_agent_button_fix.md
   docs/archive/2026-04-26/CHANGES_2026-04-26.md
"""

from PySide6.QtWidgets import QFileDialog, QApplication
from pathlib import Path
import os
import re
import logging
from .agent_view import AgentView
from .widgets.processing_worker import ProcessingWorker
from services.faktura.weight_guards import normalize_invoice_key

logger = logging.getLogger("deklarant_pro.agent.controller")


def _agent_invoice_token(value: str) -> str:
    stem = Path(value or "").stem.lower()
    stem = stem.replace("-", "").replace("_", "").replace(" ", "")
    for keyword in ("sreto", "blagic", "blagić", "loren"):
        stem = stem.replace(keyword, "")
    return re.sub(r"[^a-z0-9]", "", stem)


def _agent_invoice_sort_key(file_item) -> tuple:
    raw = getattr(file_item, "invoice_number", "") or getattr(file_item, "filepath", "")
    token = _agent_invoice_token(raw)
    parts = re.findall(r"\d+|[a-z]+", token)
    natural = tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)
    return (natural, token, Path(getattr(file_item, "filepath", "")).name.lower())


class AgentController:
    """
    Agent Controller sa tri pipeline moda:
    - Analiza: parsiranje + predlaganje tarifnih brojeva
    - Uvezi u deklaraciju: + Faktura tab + kreiranje Naimenovanja
    - Puna automatizacija: sve gore + izvoz u XML
    """

    def __init__(self, view: AgentView, draft=None, faktura_tab=None,
                 naimenovanje_tab=None, zaglavlje_tab=None):
        self.view = view
        self.draft = draft
        self.faktura_tab = faktura_tab
        self.naimenovanje_tab = naimenovanje_tab
        self.zaglavlje_tab = zaglavlje_tab

        self._worker = None
        self._current_mode = "Analiza"
        self._pending_action = None  # PendingAction koji čeka potvrdu
        self._pending_import_files = []  # Keširani fajlovi za Analiza mod

        # ── Workflow / Session / Budget ──
        from .workflow_state import WorkflowStateManager, WorkflowState
        from .session_manager import AgentSessionManager
        from .token_budget import TokenBudgetTracker

        self.workflow = WorkflowStateManager()
        self.workflow.on_state_changed = self._on_workflow_state_changed
        self.session = AgentSessionManager()
        self.budget = TokenBudgetTracker()

        # ── Service layer ──
        self._init_services()

        self._connect_signals()

        # ── Crash recovery — provjeri prekinutu sesiju ──
        self._try_restore_session()

    def _init_services(self):
        """Inicijalizuj service sloj sa callback-ovima."""
        from gui.tabs.agent.services.xml_workflow_service import XmlWorkflowService
        from gui.tabs.agent.services.import_pipeline_service import ImportPipelineService
        from gui.tabs.agent.services.chat_intent_handler import ChatIntentHandler
        self.xml_workflow_svc = XmlWorkflowService(self)
        self.import_pipeline_svc = ImportPipelineService(self)
        self.chat_intent_svc = ChatIntentHandler(self)

        from services.agent.chat.tariff_intent_service import TariffIntentService
        from services.agent.chat.merge_intent_service import MergeIntentService
        from services.agent.chat.naimenovanja_intent_service import NaimenovanjaIntentService
        from services.agent.learning.historical_learning_service_safe import HistoricalLearningServiceSafe

        chat = self.view.get_chat_panel()
        
        # Historical Learning Service — bez preloada pri startu
        # Profili se uče lazy (on-demand) pri prvom korišćenju
        self.historical_svc = HistoricalLearningServiceSafe()
        
        self.tariff_svc = TariffIntentService(self.draft)
        self.tariff_svc._controller_ref = self
        self.tariff_svc.on_activity = chat.add_activity
        self.tariff_svc.on_agent_message = chat.add_agent_message
        self.tariff_svc.on_set_pending = lambda a: setattr(self, '_pending_action', a)
        self.tariff_svc.on_refresh_faktura = self._refresh_faktura_tab

        self.merge_svc = MergeIntentService(self.draft)
        self.merge_svc.on_activity = chat.add_activity
        self.merge_svc.on_agent_message = chat.add_agent_message
        self.merge_svc.on_set_pending = lambda a: setattr(self, '_pending_action', a)
        self.merge_svc.on_refresh_naim = self._refresh_naimenovanja_tab
        self.merge_svc.on_refresh_faktura = self._refresh_faktura_tab

        self.naim_intent_svc = NaimenovanjaIntentService(self.draft)
        self.naim_intent_svc.on_agent_message = chat.add_agent_message
        self.naim_intent_svc.on_refresh_faktura = self._refresh_faktura_tab
        self.naim_intent_svc.on_refresh_naim = self._refresh_naimenovanja_tab

    def _refresh_faktura_tab(self):
        """Osvježi Faktura tab tabelu."""
        fw = self.faktura_tab.view if hasattr(self.faktura_tab, 'view') else self.faktura_tab
        if fw and hasattr(fw, '_load_data_from_draft'):
            fw._load_data_from_draft()

    def _refresh_naimenovanja_tab(self):
        """Osvježi Naimenovanja tab."""
        if self.naimenovanje_tab:
            getattr(self.naimenovanje_tab, 'reload_data', getattr(self.naimenovanje_tab, 'reload', lambda: None))()

    def auto_provjeri_naimenovanja(self):
        """
        Automatska provjera naimenovanja nakon kreiranja — kratak rezime.
        Poziva se preko signala naimenovanja_created iz FakturaView.
        Prikazuje samo rezime (broj praznih polja), ne detalje.
        Za detalje korisnik pita: "provjeri naimenovanja".

        📄 docs/decisions/002-tool-dispatcher-integration.md
        """
        from services.agent.validation.naimenovanja_review_service import NaimenovanjaReviewService

        chat = self.view.get_chat_panel()
        naim_items = self.draft.items if self.draft else []

        if not naim_items:
            return  # Bez naimenovanja — ništa ne prikazuj

        result = NaimenovanjaReviewService.provjeri_naimenovanja(naim_items)

        if result['is_complete']:
            chat.add_agent_message(
                f"✅ <b>{result['total_naim']} naimenovanja kreirano</b> — sve rubrike popunjene."
            )
            return

        # Kratak rezime — samo problematična naimenovanja
        problematic = [p for p in result['problemi'] if p.prazne_obavezne]
        optional_only = [p for p in result['problemi'] if not p.prazne_obavezne and p.prazne_opcione]

        parts = [f"📋 <b>{result['total_naim']} naimenovanja kreirano.</b>"]

        if problematic:
            rbs = ", ".join(f"Rb.{p.ordinal_no}" for p in problematic)
            parts.append(
                f"⚠️ <b>{result['total_praznih_obaveznih']}</b> praznih obaveznih polja "
                f"({rbs})."
            )

        if optional_only:
            parts.append(
                f"💡 <b>{result['total_praznih_opcionih']}</b> praznih opcionih polja "
                f"({len(optional_only)} naim.)."
            )

        parts.append("<small>Za detalje: <i>provjeri naimenovanja</i></small>")

        chat.add_agent_message("<br>".join(parts))

    def _connect_signals(self):
        """Poveži view signale sa handler metodama."""
        doc = self.view.get_document_panel()
        chat = self.view.get_chat_panel()
        header = self.view.get_header()

        doc.files_added.connect(self._on_files_added)
        doc.analyze_requested.connect(self._on_analyze_requested)
        doc.clear_requested.connect(self._on_clear_requested)
        doc.file_selected.connect(self._on_file_selected)

        # Mode promjena iz upload area
        doc.upload_area.mode_changed.connect(self._on_mode_changed)

        chat.message_sent.connect(self._on_chat_message)
        header.status_changed.connect(self._on_status_changed)

        # Reset dugme u chat header-u
        chat.connect_reset(self.reset_agent)

        # Proposal card signali
        chat.proposal_confirmed.connect(self._on_proposal_confirmed)
        chat.proposal_rejected.connect(self._on_proposal_rejected)

    # ─────────────────────────────────────────────────────────────────────────
    # WORKFLOW / SESSION / BUDGET — callback-ovi i helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_workflow_state_changed(self, state):
        """Prikaži novu fazu u Aktivnosti tabu i snimi sesiju."""
        self.view.get_chat_panel().add_activity(f"🔄 Faza: {self.workflow.label}")
        self._save_session()

    def _save_session(self):
        """Snimi trenutno stanje sesije u SQLite."""
        try:
            doc = self.view.get_document_panel()
            files = [f.filepath for f in doc.get_files()]
        except Exception:
            files = []
        self.session.save(
            workflow_state_value=self.workflow.state.value,
            selected_mode=self._current_mode,
            uploaded_files=files,
            token_input=self.budget.input_tokens,
            token_output=self.budget.output_tokens,
        )

    def _try_restore_session(self):
        """Crash recovery — upozori korisnika ako je prethodna sesija prekinuta."""
        try:
            last = self.session.load_latest_interrupted()
            if not last:
                return
            chat = self.view.get_chat_panel()
            state = last.get('workflow_state', 'nepoznato')
            total_tok = last.get('token_input', 0) + last.get('token_output', 0)
            files = last.get('uploaded_files', [])
            file_names = ', '.join(Path(f).name for f in files[:3]) if files else '—'
            chat.add_activity(
                f"⚠️ Prethodna sesija prekinuta u fazi: <b>{state}</b><br>"
                f"   Fajlovi: {file_names}<br>"
                f"   Tokeni: ~{total_tok:,}"
            )
            # Nastavi budget iz prethodne sesije
            self.budget.add(
                input_tokens=last.get('token_input', 0),
                output_tokens=last.get('token_output', 0),
            )
        except Exception:
            pass  # recovery nikad ne smije srušiti pokretanje

    def _on_mode_changed(self, mode: str):
        """Handle promjenu pipeline moda."""
        self._current_mode = mode
        self.view.get_chat_panel().add_activity(f"🔧 Režim: {mode}")

    def _on_files_added(self, filepaths: list):
        """Handle dodavanje novih fajlova u listu."""
        from .workflow_state import WorkflowState
        chat = self.view.get_chat_panel()
        chat.add_activity(f"✅ Dodato {len(filepaths)} fajlova")
        doc = self.view.get_document_panel()
        self.view.get_header().update_sesija(len(doc.get_files()))
        self.workflow.transition(WorkflowState.DOCUMENT_UPLOADED)

    def _on_analyze_requested(self):
        """Pokreni pipeline prema trenutno odabranom modu."""
        doc = self.view.get_document_panel()
        chat = self.view.get_chat_panel()
        files = doc.get_files()

        if not files:
            return

        if self._worker and self._worker.isRunning():
            chat.add_activity("⚠️ Procesiranje je već u toku!")
            return

        mode = doc.upload_area.get_mode()
        self._current_mode = mode

        self.view.get_header().set_status("Procesiranje")
        
        # ⭐ KLJUČNO: Prebaci na "Aktivnosti" tab da korisnik vidi progress!
        chat.tabs.setCurrentIndex(1)  # 0=Agent, 1=Aktivnosti, 2=Pitanja
        
        # ⭐ Pokaži loading state na dugmetu
        doc.upload_area.set_loading(True)

        try:
            chat.add_agent_message(
                f"🚀 Pokrećem <b>{mode}</b> za {len(files)} fajlova..."
            )
            chat.add_activity(f"\n{'='*60}")
            chat.add_activity(f"🚀 [{mode}] Počelo procesiranje {len(files)} fajlova")

            # Ažuriraj workflow stanje
            from .workflow_state import WorkflowState
            self.workflow.transition(WorkflowState.ANALYZING)

            # Kreiraj i pokreni background worker
            self._worker = ProcessingWorker(files)
            self._worker.progress.connect(chat.add_activity)
            self._worker.progress.connect(self._on_progress)
            self._worker.file_started.connect(self._on_file_started)
            self._worker.file_completed.connect(self._on_file_completed)
            self._worker.all_completed.connect(self._on_all_completed)
            self._worker.error_occurred.connect(self._on_error)
            self._worker.finished.connect(self._on_worker_finished)
            self._worker.finished.connect(self._worker.deleteLater)
            self._worker.start()
        except Exception:
            # Ako bilo šta pukne pri pokretanju, vrati dugme
            doc.upload_area.set_loading(False)
            raise

    def _on_worker_finished(self):
        """
        Sigurnosni reset UI stanja nakon završetka workera.
        Pokriva slučajeve kada all_completed/error callback ne vrati dugme.
        """
        try:
            doc = self.view.get_document_panel()
            doc.upload_area.set_loading(False)
            # Dugme treba biti aktivno samo ako postoje fajlovi u listi
            has_files = len(doc.get_files()) > 0
            doc.upload_area.btn_analyze.setEnabled(has_files)
            if has_files:
                self.view.get_header().set_status("Spreman")
        finally:
            self._worker = None

    def _on_file_started(self, filepath: str):
        """Ažuriraj tabelu - fajl počeo sa procesiranjem."""
        doc = self.view.get_document_panel()
        current = getattr(doc.file_table, "_files", {}).get(filepath)
        if current and current.status in {"Completed", "Skipped", "Error"}:
            return
        doc.file_table.update_file_status(filepath, 'Processing', 0.0)

    def _on_progress(self, message: str):
        """⭐ Prikaži progress poruku i u Agent tabu."""
        from pathlib import Path
        chat = self.view.get_chat_panel()
        
        # Samo prikaži relevantne poruke
        if message.startswith("📄 Parsing:"):
            filename = Path(message.replace("📄 Parsing:", "").strip()).name
            chat.add_agent_message(f"📄 <b>Parsiram:</b> {filename}")
        elif "✅" in message or "❌" in message:
            # Prikaži samo finalne rezultate
            if "KOMBINOVANO" in message or "Single import" in message:
                # Ekstraktuj broj stavki
                import re
                match = re.search(r'(\d+)\s*stavki', message)
                if match:
                    stavki = match.group(1)
                    chat.add_agent_message(f"✅ <b>Uvezeno {stavki} stavki</b>")
    def _on_file_completed(self, file_item):
        """Ažuriraj tabelu - fajl završio procesiranje."""
        doc = self.view.get_document_panel()
        doc.file_table.update_file_status(
            file_item.filepath,
            file_item.status,
            file_item.confidence,
            file_item.detected_parser or file_item.parser
        )

    def _normalize_finished_file_statuses(self, files: list):
        doc = self.view.get_document_panel()
        for file_item in files:
            if file_item.status == 'Processing' and file_item.invoice_lines:
                file_item.status = 'Completed'
                if file_item.confidence <= 0:
                    file_item.confidence = 1.0
                doc.file_table.update_file_status(
                    file_item.filepath,
                    file_item.status,
                    file_item.confidence,
                    file_item.detected_parser or file_item.parser
                )

    def _dedupe_completed_import_files(self, completed: list) -> list:
        combined = [f for f in completed if getattr(f, "is_combined", False)]
        consumed = {
            os.path.normcase(str(Path(path).resolve()))
            for f in completed
            for path in (getattr(f, "consumed_paths", []) or [])
        }
        if not combined and not consumed:
            return completed

        combined_tokens = {
            _agent_invoice_token(getattr(f, "invoice_number", "") or getattr(f, "filepath", ""))
            for f in combined
        }
        filtered = []
        for file_item in completed:
            resolved = os.path.normcase(str(Path(file_item.filepath).resolve()))
            token = _agent_invoice_token(getattr(file_item, "invoice_number", "") or file_item.filepath)
            is_excel_pair = file_item.file_type == "Excel" and token in combined_tokens
            if file_item not in combined and (resolved in consumed or is_excel_pair):
                file_item.status = "Skipped"
                file_item.invoice_lines = []
                self.view.get_document_panel().file_table.update_file_status(
                    file_item.filepath,
                    file_item.status,
                    file_item.confidence,
                    file_item.detected_parser or file_item.parser,
                )
                continue
            filtered.append(file_item)
        return filtered

    def _faktura_view(self):
        return self.faktura_tab.view if hasattr(self.faktura_tab, 'view') else self.faktura_tab

    def _safe_text_attr(self, obj, name: str) -> str:
        value = getattr(obj, name, "")
        return value if isinstance(value, str) else ""

    def _existing_invoice_keys_for_agent_import(self) -> set[str]:
        keys = set(getattr(self.draft, "invoice_weights", {}) or {})
        for line in getattr(self.draft, "invoice_lines", []) or []:
            key = normalize_invoice_key(getattr(line, "invoice_number", "") or "")
            if key:
                keys.add(key)
        return keys

    def _prepare_agent_import_plan(self, completed: list, fw):
        from services.import_workflow.adapters import from_file_item
        from services.import_workflow.prepare_service import prepare_import

        candidates = [
            from_file_item(file_item)
            for file_item in completed
            if file_item.status == 'Completed' and file_item.invoice_lines
        ]
        expected_exporter = AgentController._safe_text_attr(self, fw, "_expected_exporter") or AgentController._safe_text_attr(
            self,
            self.draft, "izvoznik_naziv"
        )
        expected_importer = AgentController._safe_text_attr(self, fw, "_expected_importer") or AgentController._safe_text_attr(
            self,
            self.draft, "primalac_naziv"
        )
        return prepare_import(
            candidates,
            existing_invoice_keys=AgentController._existing_invoice_keys_for_agent_import(self),
            expected_exporter=expected_exporter,
            expected_importer=expected_importer,
            expected_currency=AgentController._safe_text_attr(self, self.draft, "valuta"),
        )

    def _collect_agent_import_decisions(self, fw, plan, chat):
        from gui.tabs.faktura_view import FakturaView
        from services.import_workflow.decision_models import (
            CurrencyConflictResponse,
            InvoiceDecision,
            OriginDialogResolution,
            PartnerConflictResolution,
            PartnerConflictResponse,
            UserDecisions,
        )

        decisions = UserDecisions()
        for invoice in plan.invoices:
            decisions.invoice_decisions[invoice.internal_key] = InvoiceDecision(
                invoice_key=invoice.internal_key
            )

        if plan.partner_conflicts:
            chat.add_activity(f"⚠️ Konflikt partnera: {len(plan.partner_conflicts)}")
            if not FakturaView._confirm_import_partner_conflicts(fw, plan.partner_conflicts):
                decisions.aborted = True
                return decisions
            for conflict in plan.partner_conflicts:
                decisions.partner_conflict_responses.append(
                    PartnerConflictResponse(
                        invoice_key=conflict.invoice_key,
                        field_name=conflict.field_name,
                        expected=conflict.expected,
                        actual=conflict.actual,
                        resolution=PartnerConflictResolution.CONTINUE,
                    )
                )

        if plan.currency_conflicts:
            chat.add_activity(f"⚠️ Konflikt valute: {len(plan.currency_conflicts)}")
            if not FakturaView._confirm_import_currency_conflicts(fw, plan.currency_conflicts):
                decisions.aborted = True
                return decisions
            for conflict in plan.currency_conflicts:
                decisions.currency_conflict_responses.append(
                    CurrencyConflictResponse(
                        invoice_key=conflict.invoice_key,
                        expected=conflict.expected,
                        actual=conflict.actual,
                        resolution=PartnerConflictResolution.CONTINUE,
                    )
                )

        invoice_by_key = {invoice.internal_key: invoice for invoice in plan.invoices}
        for invoice_key, dialog_type in plan.origin_dialogs_needed:
            invoice = invoice_by_key.get(invoice_key)
            if invoice is None:
                continue
            label = dialog_type.value.upper()
            chat.add_activity(f"📄 [{invoice.display_name}] {label} dijalog...")
            response = FakturaView._collect_manual_origin_response(fw, invoice, dialog_type)
            decisions.invoice_decisions[invoice_key].origin_response = response
            if response.resolution == OriginDialogResolution.APPLIED:
                chat.add_activity(f"✅ [{invoice.display_name}] {label} primijenjen")
            else:
                chat.add_activity(f"ℹ️ [{invoice.display_name}] {label} preskočen")

        return decisions

    def _sync_faktura_after_agent_apply(self, fw, plan, apply_result) -> None:
        if fw and hasattr(fw, 'weight_manager'):
            fw.weight_manager.accumulated_bruto_kg = 0.0
            fw.weight_manager.accumulated_neto_kg = 0.0
            for bruto, neto in (getattr(self.draft, "invoice_weights", {}) or {}).values():
                fw.weight_manager.accumulated_bruto_kg += bruto or 0.0
                fw.weight_manager.accumulated_neto_kg += neto or 0.0
            if hasattr(fw, 'input_bruto') and hasattr(fw, '_format_weight'):
                fw.input_bruto.setText(fw._format_weight(fw.weight_manager.accumulated_bruto_kg))
            if hasattr(fw, 'input_neto') and hasattr(fw, '_format_weight'):
                fw.input_neto.setText(fw._format_weight(fw.weight_manager.accumulated_neto_kg))

        applied_keys = set(apply_result.applied_invoice_keys)
        applied = [invoice for invoice in plan.invoices if invoice.internal_key in applied_keys]
        if applied and fw:
            fw.last_invoice_name = applied[-1].invoice_number or applied[-1].display_name
            fw.last_import_count = len(applied[-1].invoice_lines)
            exporter = applied[-1].exporter.name if applied[-1].exporter else ""
            importer = applied[-1].importer.name if applied[-1].importer else ""
            if exporter:
                fw._expected_exporter = exporter
            if importer:
                fw._expected_importer = importer

    def _summarize_agent_import_plan(self, plan, apply_result, chat) -> None:
        applied_keys = set(apply_result.applied_invoice_keys)
        for invoice in plan.invoices:
            if invoice.internal_key not in applied_keys:
                continue
            bez_tarife = sum(1 for line in invoice.invoice_lines if not getattr(line, "tarifni_broj", ""))
            chat.add_agent_message(
                f"📄 <b>Faktura: {invoice.display_name}</b><br>"
                f"Stavki: {invoice.item_count} | Bez tarifnog: {bez_tarife}<br>"
                f"Bruto: {invoice.bruto_kg:,.1f}kg | Neto: {invoice.neto_kg:,.1f}kg"
            )

    def _apply_agent_origin_followups(self, decisions, chat) -> None:
        from services.import_workflow.decision_models import OriginDialogResolution
        from services.import_workflow.plan_models import OriginDialogType

        for decision in decisions.invoice_decisions.values():
            response = decision.origin_response
            if response is None:
                continue
            if response.dialog_type != OriginDialogType.EUR1:
                continue
            if response.resolution != OriginDialogResolution.APPLIED:
                continue
            if response.dialog_data:
                self._apply_eur1_to_naimenovanja(response.dialog_data, chat)

    def _on_all_completed(self, files: list):
        """Svi fajlovi završeni - izvrši pipeline logiku prema modu."""
        # ⭐ ODMAH ukloni loading state — pre bilo čega drugog
        doc = self.view.get_document_panel()
        doc.upload_area.set_loading(False)

        chat = self.view.get_chat_panel()
        self._normalize_finished_file_statuses(files)
        completed = [f for f in files if f.status == 'Completed']
        completed = self._dedupe_completed_import_files(completed)
        completed = sorted(completed, key=_agent_invoice_sort_key)
        errors = [f for f in files if f.status == 'Error']

        logger.debug(
            "_on_all_completed: mode=%r, completed=%d, errors=%d",
            self._current_mode, len(completed), len(errors),
        )

        chat.add_activity(
            f"✅ Procesiranje završeno: {len(completed)} uspješno, {len(errors)} grešaka"
        )
        self.view.get_header().set_status("Spreman")
        
        # ⭐ Prebaci nazad na Agent tab na kraju
        chat.tabs.setCurrentIndex(0)

        if not completed:
            chat.add_agent_message("❌ Nema uspješno procesiranih fajlova.")
            return

        # ── ANALIZA MOD: agent analizira bez uvoza u draft ────────────────────
        if self._current_mode == "Analiza":
            self._analiza_pipeline(completed, chat)
            return

        fw = AgentController._faktura_view(self)
        plan = AgentController._prepare_agent_import_plan(self, completed, fw)
        if plan.is_empty:
            chat.add_agent_message("❌ Nema stavki za uvoz u deklaraciju.")
            return

        chat.add_activity(
            f"📥 Pripremljeno faktura: {len(plan.invoices)} | "
            f"stavki: {plan.expected_total_items}"
        )
        if plan.skipped:
            chat.add_activity(f"⏭️ Preskočeno fajlova: {len(plan.skipped)}")
        if plan.failed:
            chat.add_activity(f"⚠️ Neuspjelo fajlova: {len(plan.failed)}")

        decisions = AgentController._collect_agent_import_decisions(self, fw, plan, chat)
        if decisions.aborted:
            chat.add_agent_message("ℹ️ Uvoz je otkazan prije izmjene deklaracije.")
            return

        if fw and hasattr(fw, '_push_undo_snapshot'):
            fw._push_undo_snapshot()

        from services.import_workflow.apply_service import apply_import_plan

        apply_result = apply_import_plan(self.draft, plan, decisions)
        if not apply_result.success:
            chat.add_agent_message(
                "❌ <b>Uvoz nije primijenjen.</b><br>"
                + "<br>".join(apply_result.errors[:3])
            )
            return

        all_processed_lines = list(self.draft.invoice_lines)
        processed_total = apply_result.total_items
        logger.debug("Draft sada ima %d stavki", len(self.draft.invoice_lines))

        AgentController._apply_agent_origin_followups(self, decisions, chat)
        AgentController._sync_faktura_after_agent_apply(self, fw, plan, apply_result)
        AgentController._summarize_agent_import_plan(self, plan, apply_result, chat)
        if fw and hasattr(fw, '_load_data_from_draft'):
            fw._load_data_from_draft()
        if fw and hasattr(fw, '_update_weight_totals'):
            fw._update_weight_totals()
        if fw and hasattr(fw, '_set_buttons_enabled'):
            fw._set_buttons_enabled(True)
        QApplication.processEvents()

        # ⭐ Prebaci na Faktura tab da korisnik vidi rezultate
        parent = self.view.parent()
        while parent:
            if 'MainWindow' in str(type(parent)):
                break
            parent = parent.parent()
        if parent:
            from PySide6.QtWidgets import QTabWidget
            tabs_widgets = parent.findChildren(QTabWidget)
            if tabs_widgets:
                tabs_widgets[0].setCurrentWidget(self.faktura_tab)

        # ⭐ Ponudi podjelu po zemljama ako ima više od jedne grupe
        if fw and hasattr(fw, '_offer_split_by_country'):
            fw._offer_split_by_country(all_processed_lines)

        # ⭐ KONAČNI REZIME SVIH FAKTURA
        total_bez = sum(1 for l in self.draft.invoice_lines if not l.tarifni_broj)

        if self._current_mode == "Puna automatizacija":
            chat.add_agent_message(
                f"✅ <b>Sve fakture uvezene!</b><br>"
                f"Ukupno stavki: <b>{processed_total}</b> | Bez tarifnog: <b>{total_bez}</b><br>"
                f"🤖 Pokrećem punu automatizaciju do XML izvoza..."
            )
            from .workflow_state import WorkflowState
            self.workflow.transition(WorkflowState.COMPLETED)

            # Prije popravke (2026-07-27) "Puna automatizacija" je pozivala
            # _puna_auto_pipeline direktno — mase → tarife → validacija →
            # naimenovanja, pa STAJE. Zaglavlje, cross-tab provjera, XML
            # readiness i sam izvoz su ostajali identično ručni kao u modu
            # "Uvezi u deklaraciju", što je ovaj režim učinilo praktično
            # beskorisnim (korisnička primjedba). run_declaration_workflow
            # iznutra ponovo koristi _puna_auto_pipeline za mase/tarife/
            # validaciju/naimenovanja (ništa se ne duplira), a zatim
            # NASTAVLJA kroz preostale kapije do stvarnog XML izvoza.
            # Vidi agent_reports/2026-07-27_puna-automatizacija-do-kraja.md.
            from services.agent.workflow.declaration_workflow_service import (
                AgentBusyError, run_declaration_workflow,
            )
            try:
                run_declaration_workflow(self, chat, fw=fw)
            except AgentBusyError:
                pass  # poruka je već prikazana unutar run_declaration_workflow
        else:
            analiza = self._proactive_analysis(all_processed_lines, fw)
            chat.add_agent_message(
                f"✅ <b>Uvezeno {processed_total} stavki.</b><br>{analiza}"
            )
            from .workflow_state import WorkflowState
            self.workflow.transition(WorkflowState.COMPLETED)

            # Istorijska provjera tarifa ODMAH nakon uvoza (korisnička primjedba
            # 2026-07-22 — SUSSINA slučaj). Ova grana ("Uvezi u deklaraciju" —
            # sve agent rute osim pune automatizacije, koja ima svoj poziv
            # gore preko _puna_auto_pipeline) je RAZLIČIT kod-put od
            # FakturaView._on_import_finished/_process_batch_records (koji su
            # Qt signal handleri za obični GUI import, ne agent import) — bez
            # ovoga bi agent uvoz NIKAD ne bio provjeren, čak ni nakon fixa
            # koji je taj drugi kod-put učinio uslovno-uvijek pozvanim.
            if fw and hasattr(fw, '_run_historical_tariff_validation'):
                fw._run_historical_tariff_validation(auto=False)

    def _analiza_pipeline(self, completed: list, chat):
        self.import_pipeline_svc.analiza_pipeline(completed, chat)

    def _analiza_uvezi_action(self):
        self.import_pipeline_svc.analiza_uvezi_action()

    def _analiza_auto_action(self):
        self.import_pipeline_svc.analiza_auto_action()

    def _proactive_analysis(self, lines: list, fw=None) -> str:
        """
        Generiši sažetak analize uvezenih stavki.
        Status bar: kompaktna jedna linija (diskretno).
        Chat: kratka 2-linije poruka bez prijedloga.
        """
        total = len(lines)
        if not total:
            return ""

        bez_tarife = [l for l in lines if not getattr(l, 'tarifni_broj', None)]
        bez_zemlje = [l for l in lines if not getattr(l, 'zemlja_porijekla', None)]
        sa_pov     = [l for l in lines if getattr(l, 'povlastica', None)]
        bez_eur1   = [
            l for l in sa_pov
            if not getattr(l, 'has_origin_statement', False)
            and not getattr(l, 'eur1_number', None)
        ]

        countries: dict = {}
        for l in lines:
            c = getattr(l, 'zemlja_porijekla', None) or '(nepoznato)'
            countries[c] = countries.get(c, 0) + 1

        zemlja_str = " | ".join(
            f"{k}:{v}" for k, v in sorted(countries.items(), key=lambda x: -x[1])[:5]
        )

        # ── Status bar (diskretno, jedna linija) ──
        if fw and hasattr(fw, 'set_analysis_summary'):
            problemi_sb = []
            if bez_tarife:
                problemi_sb.append(f"⚠️ {len(bez_tarife)} bez tarife")
            if bez_zemlje:
                problemi_sb.append(f"⚠️ {len(bez_zemlje)} bez zemlje")
            if bez_eur1:
                problemi_sb.append(f"⚠️ {len(bez_eur1)} bez EUR1")
            sb_text = f"🌍 {zemlja_str}"
            if problemi_sb:
                sb_text += "  " + " | ".join(problemi_sb)
            level = "warning" if problemi_sb else "success"
            fw.set_analysis_summary(sb_text, level)

        # ── Chat poruka (kratka, bez prijedloga) ──
        problemi_chat = []
        if bez_tarife:
            problemi_chat.append(f"<b>{len(bez_tarife)}</b> bez tarife")
        if bez_zemlje:
            problemi_chat.append(f"<b>{len(bez_zemlje)}</b> bez zemlje")
        if bez_eur1:
            problemi_chat.append(f"<b>{len(bez_eur1)}</b> bez EUR1")

        if problemi_chat:
            return (
                f"🌍 Porijeklo: {zemlja_str}<br>"
                f"⚠️ {' | '.join(problemi_chat)}"
            )
        return f"🌍 Porijeklo: {zemlja_str}<br>✅ Sve stavke uredne."

    def _puna_auto_pipeline(self, fw, chat, all_lines: list):
        self.import_pipeline_svc.puna_auto_pipeline(fw, chat, all_lines)

    def _get_preference_by_country(self, country_code: str, exporter_name: str = "") -> str:
        return self.import_pipeline_svc.get_preference_by_country(country_code, exporter_name)

    def _auto_handle_povlastice(self, invoice_lines: list, chat,
                                 has_origin_statement: bool = False) -> dict:
        return self.import_pipeline_svc.auto_handle_povlastice(invoice_lines, chat, has_origin_statement)

    def _apply_eur1_to_naimenovanja(self, eur1_data: dict, chat) -> None:
        self.import_pipeline_svc.apply_eur1_to_naimenovanja(eur1_data, chat)

    def _validiraj_prije_uvoza(self, invoice_lines: list, chat) -> tuple:
        return self.import_pipeline_svc.validiraj_prije_uvoza(invoice_lines, chat)

    def _generisi_izvjestaj(self, chat):
        return self.import_pipeline_svc.generisi_izvjestaj(chat)

    def _otvori_faktura_tab_nakon_uvoza(self, chat):
        self.import_pipeline_svc.otvori_faktura_tab_nakon_uvoza(chat)

    def _primjeni_xml_template(self, all_lines: list, chat, silent: bool = False):
        return self.xml_workflow_svc.primjeni_xml_template(all_lines, chat, silent)


    def _izvezi_xml(self, chat):
        self.xml_workflow_svc.izvezi_xml(chat)

    def _on_error(self, filepath: str, message: str):
        """Handle greška pri procesiranju fajla."""
        from .workflow_state import WorkflowState
        chat = self.view.get_chat_panel()
        filename = Path(filepath).name
        chat.add_activity(f"❌ Greška [{filename}]: {message}")
        self.workflow.transition(WorkflowState.FAILED)
        self._save_session()
        # Vrati dugme — ako all_completed ne stigne
        self.view.get_document_panel().upload_area.set_loading(False)

    def _on_clear_requested(self):
        """Očisti listu fajlova i otkaži worker ako radi."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        # Vrati dugme ako je bilo u loading stanju
        self.view.get_document_panel().upload_area.set_loading(False)
        self.view.get_chat_panel().add_activity("🗑️ Lista fajlova očišćena")
        self.view.get_header().update_sesija(0)
        self.workflow.reset()
        self.budget.reset()

    def reset_agent(self):
        """
        Reset chat dijaloga agenta: sakrij akcione dugmiće, obriši chat poruke,
        očisti keš analize i workflow stanje. Fajlovi ostaju netaknuti.
        """
        chat = self.view.get_chat_panel()

        # Sakrij akcione dugmiće
        chat.hide_action_buttons()

        # Obriši keširane fajlove iz Analiza moda
        self._pending_import_files = []
        self._pending_action = None

        # Obriši chat poruke (agent_view i activity_view)
        chat.agent_view.clear()
        chat.activity_view.clear()

        # Reset workflow
        self.workflow.reset()

        # Prikaži welcome poruku
        chat._add_welcome_message()
        chat.add_activity("🔄 Chat resetovan — spreman za novi razgovor")

    def _on_file_selected(self, file_item):
        """Handle klik na fajl u tabeli."""
        self.view.get_chat_panel().add_activity(f"👁️ Pregled: {file_item.filename}")

    def _on_chat_message(self, message: str):
        self.chat_intent_svc.handle_message(message)

    def _on_status_changed(self, status: str):
        """Handle promjenu statusa iz header-a."""
        self.view.get_chat_panel().add_activity(f"ℹ️ Status: {status}")

    def _check_budget_after_response(self):
        """Provjeri budget nakon LLM odgovora i snimi sesiju."""
        status, msg = self.budget.check()
        if msg:
            self.view.get_chat_panel().add_activity(msg)
        # Prikaži budget u aktivnostima svakih ~10k tokena
        total = self.budget.total
        if total > 0 and total % 10_000 < 500:
            self.view.get_chat_panel().add_activity(
                f"📊 Token budget: {self.budget.summary()}"
            )
        self._save_session()

    # ─────────────────────────────────────────────────────────────────────────
    # AGENT AKCIJE — prijedlog + potvrda + izvršavanje
    # ─────────────────────────────────────────────────────────────────────────

    def _predlozi_tarifne_brojeve(self):
        """Analizira stavke bez tarifnog broja — koristi TariffIntentService."""
        self.tariff_svc.propose_all()

    def _predlozi_tarifne_po_filteru(self, keyword: str):
        """Predlaže tarifne brojeve za stavke sa keyword u nazivu — koristi TariffIntentService."""
        self.tariff_svc.propose_by_keyword(keyword)

    def _on_tariff_llm_ready(self, local_proposals, llm_proposals, ukupno_bez, chat):
        """Prikaži prijedloge — koristi TariffIntentService."""
        self.tariff_svc._show_proposals(local_proposals, llm_proposals, ukupno_bez)

    def _predlozi_spajanje_naimenovanja(self):
        """Predlaže spajanje naimenovanja — koristi MergeIntentService."""
        self.merge_svc.find_candidates()

    def _execute_pending_action(self):
        """Izvrši pending akciju — koristi service."""
        action = self._pending_action
        self._pending_action = None
        if action.action_type == "fill_tariff":
            self.tariff_svc.execute_fill(action.proposals)
        elif action.action_type == "merge_naimenovanja":
            self.merge_svc.execute_merge(action.proposals)

    def _provjeri_tarifni_za_naziv(self, naziv_robe: str):
        """Provjeri tarifni za naziv — koristi TariffIntentService."""
        self.tariff_svc.check_tariff_for_name(naziv_robe)

    def _alternativni_tarifni_za_stavku(self, item_query: str = "", item_ordinal: int = None, is_alt: bool = False):
        self.chat_intent_svc.alternativni_tarifni_za_stavku(item_query, item_ordinal, is_alt)
    def _klasificiraj_i_usmjeri(self, message: str):
        self.chat_intent_svc.klasificiraj_i_usmjeri(message)
    def _obrisi_tarifne_brojeve(self):
        """Obriši tarifne brojeve — koristi TariffIntentService."""
        self.tariff_svc.delete_all()

    def _parse_upis_u_kolonu(self, message: str, brisanje: bool = False):
        """Parsiraj upis/brisanje kolone — koristi NaimenovanjaIntentService."""
        r = self.naim_intent_svc.parse(message, brisanje=brisanje)
        return (r.atribut, r.vrijednost, r.tab) if r else None

    def _upisi_u_kolonu(self, atribut: str, vrijednost: str, tab: str = 'faktura'):
        """
        Predloži upis vrijednosti u kolonu — zahtijeva potvrdu korisnika
        (MUTATE, vidi services/agent/chat/tool_policy.py). Stvaran upis se
        dešava tek u ChatIntentHandler._on_proposal_confirmed.
        """
        self.chat_intent_svc.propose_kolona_upis(atribut, vrijednost, tab)

    def _izvrsi_spajanje_naimenovanja(self, proposals, chat):
        self.chat_intent_svc.izvrsi_spajanje_naimenovanja(proposals, chat)
    def _provjeri_naimenovanja(self):
        self.chat_intent_svc.provjeri_naimenovanja()
    def _pregledaj_naimenovanja(self, indeksi=None):
        self.chat_intent_svc.pregledaj_naimenovanja(indeksi)
    def _pretrazi_tarifu(self, upit: str):
        self.chat_intent_svc.pretrazi_tarifu(upit)
    def _pretrazi_tarifu_po_kodu(self, kod: str):
        self.chat_intent_svc.pretrazi_tarifu_po_kodu(kod)
    def _pretrazi_tarifu_poglavlje(self, poglavlje: str):
        self.chat_intent_svc.pretrazi_tarifu_poglavlje(poglavlje)
    def _pretrazi_tarifu_hijerarhijski(self, kod: str):
        self.chat_intent_svc.pretrazi_tarifu_hijerarhijski(kod)
    def _compliance_check(self):
        self.chat_intent_svc.compliance_check()
    def show_proposal_card(self, proposal: dict):
        self.chat_intent_svc.show_proposal_card(proposal)
    def _on_proposal_confirmed(self, values: dict):
        self.chat_intent_svc.on_proposal_confirmed(values)
    def _on_proposal_rejected(self):
        self.chat_intent_svc.on_proposal_rejected()
