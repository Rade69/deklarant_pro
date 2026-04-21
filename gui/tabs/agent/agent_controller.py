"""
Agent Controller - business logic za tri pipeline moda.
"""

from PySide6.QtWidgets import QFileDialog, QApplication
from pathlib import Path
from .agent_view import AgentView
from .widgets.processing_worker import ProcessingWorker


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

        from services.agent.tariff_intent_service import TariffIntentService
        from services.agent.merge_intent_service import MergeIntentService
        from services.agent.naimenovanja_intent_service import NaimenovanjaIntentService
        from services.agent.historical_learning_service_safe import HistoricalLearningServiceSafe

        chat = self.view.get_chat_panel()
        
        # Historical Learning Service
        self.historical_svc = HistoricalLearningServiceSafe()
        
        # Preload top exportera u background-u
        try:
            # Pokreni u background thread-u da ne blokira UI
            import threading
            def preload_in_background():
                try:
                    loaded = self.historical_svc.preload_top_exporters(limit=10)
                    if loaded > 0:
                        logger.debug(f"✅ Preloaded {loaded} top exportera u background-u")
                except Exception:
                    pass  # Silent error
            
            thread = threading.Thread(target=preload_in_background, daemon=True)
            thread.start()
        except Exception:
            pass  # Silent error
        
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
        self._worker.progress.connect(self._on_progress)  # ⭐ Prikaži i u Agent tabu
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_completed.connect(self._on_file_completed)
        self._worker.all_completed.connect(self._on_all_completed)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_file_started(self, filepath: str):
        """Ažuriraj tabelu - fajl počeo sa procesiranjem."""
        doc = self.view.get_document_panel()
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
        elif "⚖️" in message:
            # Prikaži težine
            chat.add_activity(message)  # Samo u Aktivnosti tabu

    def _on_file_completed(self, file_item):
        """Ažuriraj tabelu - fajl završio procesiranje."""
        doc = self.view.get_document_panel()
        doc.file_table.update_file_status(
            file_item.filepath,
            file_item.status,
            file_item.confidence,
            file_item.detected_parser or file_item.parser
        )

    def _on_all_completed(self, files: list):
        """Svi fajlovi završeni - izvrši pipeline logiku prema modu."""
        chat = self.view.get_chat_panel()
        completed = [f for f in files if f.status == 'Completed']
        errors = [f for f in files if f.status == 'Error']

        print(f"[AgentController] _on_all_completed: mode='{self._current_mode}', completed={len(completed)}, errors={len(errors)}")

        chat.add_activity(
            f"✅ Procesiranje završeno: {len(completed)} uspješno, {len(errors)} grešaka"
        )
        self.view.get_header().set_status("Spreman")
        
        # ⭐ Ukloni loading state i vrati dugme
        doc = self.view.get_document_panel()
        doc.upload_area.set_loading(False)
        
        # ⭐ Prebaci nazad na Agent tab na kraju
        chat.tabs.setCurrentIndex(0)

        if not completed:
            chat.add_agent_message("❌ Nema uspješno procesiranih fajlova.")
            return

        # ── ANALIZA MOD: agent analizira bez uvoza u draft ────────────────────
        if self._current_mode == "Analiza":
            self._analiza_pipeline(completed, chat)
            return

        # ⭐ KLJUČNO: Prikupi samo stavke iz kombinovanih ILI samostalnih fajlova
        combined_files = []
        single_files = []
        for file_item in completed:
            if file_item.is_combined:
                combined_files.append(file_item)
            else:
                single_files.append(file_item)

        # ⭐ Obradi SVAKU fakturu ZASEBNO sa posebnim dijalogom
        all_processed_lines = []
        processed_total = 0
        total_bruto_kg = 0.0
        total_neto_kg = 0.0
        for file_item in completed:
            if file_item.status != 'Completed' or not file_item.invoice_lines:
                continue

            lines = file_item.invoice_lines
            invoice_name = file_item.invoice_number or Path(file_item.filepath).stem
            has_os = file_item.has_origin_statement
            bruto = file_item.bruto_kg
            neto = file_item.neto_kg

            # Privremeno uvezi u draft za dijalog
            self.draft.invoice_lines.clear()
            self.draft.invoice_lines.extend(lines)

            chat.add_activity(f"📥 [{invoice_name}] Uvoz {len(lines)} stavki...")
            QApplication.processEvents()

            # Akumuliraj težine za sve fakture
            total_bruto_kg += bruto
            total_neto_kg += neto

            # Refresh tabele
            fw = self.faktura_tab.view if hasattr(self.faktura_tab, 'view') else self.faktura_tab
            if fw and hasattr(fw, '_load_data_from_draft'):
                fw._load_data_from_draft()

            # ⭐ PRIKAŽI REZIME FAKTURE
            bez_tarife = sum(1 for l in lines if not l.tarifni_broj)
            chat.add_agent_message(
                f"📄 <b>Faktura: {invoice_name}</b><br>"
                f"Stavki: {len(lines)} | Bez tarifnog: {bez_tarife}<br>"
                f"Bruto: {bruto:,.1f}kg | Neto: {neto:,.1f}kg"
            )

            # ⭐ DIJALOG ZA OVU FAKTURU
            if has_os:
                chat.add_activity(f"📄 [{invoice_name}] Ima izjavu — otvaram PE2 dijalog...")
                try:
                    from gui.dialogs.pe2_quick_dialog import PE2QuickDialog
                    dialog = PE2QuickDialog(self.draft.invoice_lines, self.view, invoice_number=invoice_name)
                    result_dlg = dialog.exec()
                    if result_dlg == 1:
                        pe2_data = dialog.get_data()
                        if pe2_data:
                            PE2QuickDialog.apply_pe2_data(self.draft.invoice_lines, pe2_data)
                            chat.add_activity(f"✅ [{invoice_name}] PE2 primijenjen")
                    else:
                        chat.add_activity(f"ℹ️ [{invoice_name}] PE2 preskočen")
                except Exception as e:
                    chat.add_activity(f"⚠️ [{invoice_name}] PE2 greška: {e}")
            else:
                # Prikaži EUR.1 dijalog za sve stavke koje imaju zemlju porijekla,
                # bez PE2 izjave i bez EUR.1 broja — bez obzira na to da li je
                # povlastica postavljena (Leburić ima povlastica="" → falsy, ali
                # i dalje treba EUR.1 dijalog)
                eur1_pending = [l for l in lines
                                if getattr(l, 'zemlja_porijekla', None)
                                and not getattr(l, 'has_origin_statement', False)
                                and not getattr(l, 'eur1_number', None)]
                if eur1_pending:
                    chat.add_activity(f"📋 [{invoice_name}] {len(eur1_pending)} stavki → EUR.1 dijalog...")
                    try:
                        from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog
                        dialog = Eur1QuickDialog(self.draft.invoice_lines, self.view, invoice_number=invoice_name)
                        result_dlg = dialog.exec()
                        if result_dlg == 1:
                            eur1_data = dialog.get_data()
                            if eur1_data:
                                Eur1QuickDialog.apply_eur1_data(self.draft.invoice_lines, eur1_data)
                                self._apply_eur1_to_naimenovanja(eur1_data, chat)
                                chat.add_activity(f"✅ [{invoice_name}] EUR.1 primijenjen")
                        else:
                            chat.add_activity(f"ℹ️ [{invoice_name}] EUR.1 preskočen")
                    except Exception as e:
                        chat.add_activity(f"⚠️ [{invoice_name}] EUR.1 greška: {e}")

            # Sačuvaj procesirane linije (sa mogućim izmjenama iz dijaloga)
            all_processed_lines.extend(self.draft.invoice_lines)
            processed_total += len(lines)

        # ⭐ SAČUVAJ SVE LINJE U DRAFT (sve fakture zajedno)
        self.draft.invoice_lines.clear()
        self.draft.invoice_lines.extend(all_processed_lines)
        print(f"[AgentController] Draft sada ima {len(self.draft.invoice_lines)} stavki")

        # Osvježi Faktura tab i upiši akumulirane težine u toolbar
        fw = self.faktura_tab.view if hasattr(self.faktura_tab, 'view') else self.faktura_tab
        if fw:
            if hasattr(fw, '_load_data_from_draft'):
                fw._load_data_from_draft()
            # Resetuj i akumuliraj ukupne težine svih faktura
            if hasattr(fw, 'weight_manager') and hasattr(fw, '_accumulate_weights'):
                fw.weight_manager.accumulated_bruto_kg = 0.0
                fw.weight_manager.accumulated_neto_kg = 0.0
                fw._accumulate_weights(total_bruto_kg, total_neto_kg)
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

        # ⭐ KONAČNI REZIME SVIH FAKTURA
        total_bez = sum(1 for l in self.draft.invoice_lines if not l.tarifni_broj)

        if self._current_mode == "Puna automatizacija":
            chat.add_agent_message(
                f"✅ <b>Sve fakture uvezene!</b><br>"
                f"Ukupno stavki: <b>{processed_total}</b> | Bez tarifnog: <b>{total_bez}</b><br>"
                f"🤖 Pokrećem automatski pipeline..."
            )
            from .workflow_state import WorkflowState
            self.workflow.transition(WorkflowState.COMPLETED)
            self._puna_auto_pipeline(fw, chat, all_processed_lines)
        else:
            chat.add_agent_message(
                f"✅ <b>Sve fakture uvezene!</b><br>"
                f"Ukupno stavki: <b>{processed_total}</b><br>"
                f"Bez tarifnog: <b>{total_bez}</b><br><br>"
                f"💡 <b>Šta dalje?</b><br>"
                f"  • Reci <i>'popuni tarifne'</i> za prijedloge<br>"
                f"  • Pregledaj tablicu i ručno dopuni<br>"
                f"  • Kad si spreman, reci <i>'kreiraj naimenovanja'</i>"
            )
            from .workflow_state import WorkflowState
            self.workflow.transition(WorkflowState.COMPLETED)

    def _analiza_pipeline(self, completed: list, chat):
        self.import_pipeline_svc.analiza_pipeline(completed, chat)

    def _analiza_uvezi_action(self):
        self.import_pipeline_svc.analiza_uvezi_action()

    def _analiza_auto_action(self):
        self.import_pipeline_svc.analiza_auto_action()

    def _puna_auto_pipeline(self, fw, chat, all_lines: list):
        self.import_pipeline_svc.puna_auto_pipeline(fw, chat, all_lines)

    def _get_preference_by_country(self, country_code: str, exporter_name: str = "") -> str:
        return self.import_pipeline_svc.get_preference_by_country(country_code, exporter_name)

    def _auto_handle_povlastice(self, invoice_lines: list, chat,
                                 has_origin_statement: bool = False) -> dict:
        return self.import_pipeline_svc.auto_handle_povlastice(invoice_lines, chat, has_origin_statement)

    def _apply_eur1_to_naimenovanja(self, eur1_data: dict, chat) -> None:
        self.import_pipeline_svc.apply_eur1_to_naimenovanja(eur1_data, chat)

    def _izracunaj_težine_interno(self, invoice_lines: list, chat) -> int:
        return self.import_pipeline_svc.izracunaj_tezine_interno(invoice_lines, chat)

    def _validiraj_prije_uvoza(self, invoice_lines: list, chat) -> tuple:
        return self.import_pipeline_svc.validiraj_prije_uvoza(invoice_lines, chat)

    def _generisi_izvjestaj(self, chat):
        return self.import_pipeline_svc.generisi_izvjestaj(chat)

    def _uvezi_u_deklaraciju(self, invoice_lines: list, chat,
                              total_bruto: float = 0.0, total_neto: float = 0.0,
                              has_origin_statement: bool = False, completed: list = None):
        self.import_pipeline_svc.uvezi_u_deklaraciju(
            invoice_lines, chat, total_bruto, total_neto, has_origin_statement, completed
        )

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

    def _on_clear_requested(self):
        """Očisti listu fajlova i otkaži worker ako radi."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
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
        """Upiši vrijednost u kolonu — koristi NaimenovanjaIntentService."""
        self.naim_intent_svc.execute(atribut, vrijednost, tab)

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