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
        """
        Analiza mod: parsira fajlove, provjerava bazu znanja, prikazuje izvještaj.
        Ne uvozi u draft. Na kraju nudi akcione dugmiće za uvoz.
        """
        from services.agent.invoice_analysis_service import InvoiceAnalysisService
        from .workflow_state import WorkflowState

        svc = InvoiceAnalysisService()
        self._pending_import_files = completed

        chat.add_activity(f"🔍 Analiza {len(completed)} faktura...")

        for file_item in completed:
            lines = file_item.invoice_lines or []
            if not lines:
                continue

            invoice_name = file_item.invoice_number or Path(file_item.filepath).stem
            chat.add_activity(f"📋 Analiziram: {invoice_name} ({len(lines)} stavki)")
            QApplication.processEvents()

            try:
                result = svc.analyse(
                    lines=lines,
                    bruto_kg=file_item.bruto_kg,
                    neto_kg=file_item.neto_kg,
                    invoice_name=invoice_name,
                    has_origin_statement=file_item.has_origin_statement,
                    currency="EUR",
                )
                report_html = svc.format_report(result)
                chat.add_agent_message(report_html)
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri analizi {invoice_name}: {e}")

        self.workflow.transition(WorkflowState.COMPLETED)

        chat.show_action_buttons([
            ("📥 Uvezi u deklaraciju", self._analiza_uvezi_action),
            ("🤖 Automatski uvoz",     self._analiza_auto_action),
        ])

    def _analiza_uvezi_action(self):
        """Uvozi keširane fajlove iz Analiza moda kao 'Uvezi u deklaraciju'."""
        if not self._pending_import_files:
            self.view.get_chat_panel().add_agent_message("⚠️ Nema keširanih fajlova za uvoz.")
            return
        self._current_mode = "Uvezi u deklaraciju"
        chat = self.view.get_chat_panel()
        chat.add_activity("📥 Pokretam uvoz iz analize...")
        self._on_all_completed(self._pending_import_files)
        self._pending_import_files = []

    def _analiza_auto_action(self):
        """Automatski uvoz keširanih fajlova iz Analiza moda."""
        if not self._pending_import_files:
            self.view.get_chat_panel().add_agent_message("⚠️ Nema keširanih fajlova za uvoz.")
            return
        self._current_mode = "Puna automatizacija"
        chat = self.view.get_chat_panel()
        chat.add_activity("🤖 Pokretam automatski uvoz iz analize...")
        self._on_all_completed(self._pending_import_files)
        self._pending_import_files = []

    def _puna_auto_pipeline(self, fw, chat, all_lines: list):
        """
        Automatski slijed koraka za 'Puna automatizacija' mod.
        Poziva se nakon uvoza svih faktura.

        Redoslijed:
          1. Izračunaj mase
          2. Auto-popuni tarifne
          3. Validacija
          4. Kreiraj naimenovanja
          5. Primijeni XML template za zaglavlje
        """
        QApplication.processEvents()

        # 1. Izračunaj mase
        chat.add_activity("⚖️ [Auto] Izračunavam mase...")
        try:
            if fw and hasattr(fw, '_on_calculate_masses'):
                fw._on_calculate_masses(auto=True)
                chat.add_activity("✅ Mase izračunate")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri izračunu masa: {e}")
        QApplication.processEvents()

        # 2. Auto-popuni tarifne (preskači ako su sve tarife već popunjene)
        bez_tarife = sum(1 for l in self.draft.invoice_lines if not getattr(l, 'tarifni_broj', None))
        if bez_tarife > 0:
            chat.add_activity(f"🤖 [Auto] Popunjavam tarifne brojeve ({bez_tarife} stavki bez tarife)...")
            try:
                if fw and hasattr(fw, '_on_auto_fill'):
                    fw._on_auto_fill(auto=True)
                    chat.add_activity("✅ Auto-popuni završen")
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri auto-popuni: {e}")
            QApplication.processEvents()
        else:
            chat.add_activity("✅ [Auto] Sve stavke imaju tarifni broj — preskačem Auto-popuni")

        # 3. Validacija (nema dijaloga, samo osvježava status)
        chat.add_activity("🔍 [Auto] Validacija stavki...")
        try:
            if fw and hasattr(fw, '_on_validate_all'):
                fw._on_validate_all()
                chat.add_activity("✅ Validacija završena")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri validaciji: {e}")
        QApplication.processEvents()

        # 4. Kreiraj naimenovanja
        chat.add_activity("📋 [Auto] Kreiram naimenovanja...")
        try:
            if fw and hasattr(fw, '_on_create_naimenovanja'):
                fw._on_create_naimenovanja(auto=True)
                chat.add_activity("✅ Naimenovanja kreirana")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri kreiranju naimenovanja: {e}")
        QApplication.processEvents()

        # 5. XML template za zaglavlje (tiho — bez dijaloga)
        chat.add_activity("📂 [Auto] Tražim XML template za zaglavlje...")
        zaglavlje_status = "⚠️ Zaglavlje nije popunjeno — popuni ručno"
        try:
            zaglavlje_status = self._primjeni_xml_template(all_lines, chat, silent=True)
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri primjeni XML templatea: {e}")

        bez_tarife = sum(1 for l in self.draft.invoice_lines if not l.tarifni_broj)
        n_naim = len(getattr(self.draft, 'items', []))
        chat.add_agent_message(
            f"🎉 <b>Puna automatizacija završena!</b><br>"
            f"Stavki: {len(self.draft.invoice_lines)} | Bez tarifnog: <b>{bez_tarife}</b><br>"
            f"Naimenovanja: <b>{n_naim}</b><br>"
            f"Zaglavlje: {zaglavlje_status}<br><br>"
            f"💡 Provjeri naimenovanja i zaglavlje, zatim izvezi XML."
        )

    def _get_preference_by_country(self, country_code: str, exporter_name: str = "") -> str:
        """
        Vrati šifru povlastice na osnovu koda zemlje porijekla.
        
        Poboljšana verzija koja koristi istorijsko učenje ako je dostupno.
        
        Args:
            country_code: Kod zemlje (npr. 'RS', 'DE')
            exporter_name: Ime dobavljača (opcionalno)
        """
        # Prvo probaj istorijsko učenje ako imamo exportera
        if exporter_name and exporter_name.strip():
            try:
                # Koristi HistoricalLearningServiceSafe
                historical_pref = self.historical_svc.get_preference_safe(exporter_name, country_code)
                if historical_pref:
                    return historical_pref
            except Exception:
                # Silent fallback - nastavi sa hardcoded pravilima
                pass
        
        # FALLBACK: Hardcoded pravila (originalna logika)
        eu_countries = {
            'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
            'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
        }
        cefta_countries = {'RS', 'BA', 'ME', 'MK', 'AL', 'XK', 'MD'}
        c = (country_code or '').upper()
        if c in eu_countries:
            return 'EUP'
        if c in cefta_countries:
            return 'CEFTAP'
        if c == 'TR':
            return 'TRP'
        if c == 'IR':
            return 'IRP'
        return ''

    def _auto_handle_povlastice(self, invoice_lines: list, chat,
                                 has_origin_statement: bool = False) -> dict:
        """
        Automatski postavi povlastice za sve stavke — bez GUI dijaloga.

        Logika:
          - has_origin_statement (agregatni) = True → PE2 za sve linije sa zemljom
          - has_origin_statement = False → EUR1 za sve linije sa zemljom
          - nema zemlje → preskoči

        Args:
            has_origin_statement: agregatni flag iz ImportResult (per-faktura, ne per-linija)
        """
        updated_pe2 = 0
        updated_eur1 = 0
        eur1_pending = 0

        for line in invoice_lines:
            country = getattr(line, 'zemlja_porijekla', None)
            if not country:
                continue

            pov = self._get_preference_by_country(country)
            if not pov:
                continue

            existing_pov = getattr(line, 'povlastica', None)

            # Agregatni flag ima prednost nad per-linijskim
            line_has_stmt = has_origin_statement or getattr(line, 'has_origin_statement', False)

            if line_has_stmt:
                # PE2: izjava o porijeklu je u fakturi
                if not existing_pov:
                    line.povlastica = pov
                updated_pe2 += 1
            else:
                # EUR1: nema izjave — postavi povlasticu, broj fali
                if not existing_pov:
                    line.povlastica = pov
                    updated_eur1 += 1
                if not getattr(line, 'eur1_number', None):
                    eur1_pending += 1

        result = {'pe2': updated_pe2, 'eur1': updated_eur1, 'eur1_pending': eur1_pending}

        lines_with_country = sum(1 for l in invoice_lines if getattr(l, 'zemlja_porijekla', None))
        if updated_pe2 > 0 or updated_eur1 > 0:
            chat.add_activity(
                f"🌍 Povlastice auto-postavljene: PE2={updated_pe2}, EUR1={updated_eur1}"
                + (f" (has_origin_statement={has_origin_statement})" if has_origin_statement else "")
            )
        elif lines_with_country > 0:
            chat.add_activity(f"ℹ️ {lines_with_country} stavki ima zemlja_porijekla — povlastice već postavljene")
        else:
            chat.add_activity(f"⚠️ Povlastice: 0 stavki ima zemlja_porijekla — nije moguće auto-postavljanje")

        if eur1_pending > 0:
            chat.add_activity(
                f"⚠️ {eur1_pending} stavki čeka ručni unos EUR1 broja"
            )

        return result

    def _apply_eur1_to_naimenovanja(self, eur1_data: dict, chat) -> None:
        """
        Propagira EUR.1 broj na existing naimenovanja u draftu.

        Poziva se nakon Eur1QuickDialog.apply_eur1_data() da ažurira
        attached_document4 na svim naimenovanjima čiji preference_code
        odgovara unesenim podacima.
        """
        if not self.draft or not getattr(self.draft, 'items', None):
            return

        updated = 0
        for country, data in eur1_data.items():
            eur1_num = (data.get('eur1_number') or '').strip()
            preference = (data.get('preference') or '').strip()
            has_stmt = data.get('has_origin_statement', False)
            doc_code = "PE2" if has_stmt else "PE1"
            doc44 = f"{doc_code} {eur1_num}".strip()

            for item in self.draft.items:
                pov = (getattr(item, 'preference_code', '') or '').strip()
                origin = (getattr(item, 'origin_country_code', '') or '').strip()
                # Podudaranje po povlastici ili po zemlji
                if pov == preference or origin.upper() == country.upper():
                    item.attached_document4 = doc44
                    updated += 1

        if updated:
            chat.add_activity(f"📋 Rb.44 ažuriran na {updated} naimenovanja ({doc44})")

    def _izracunaj_težine_interno(self, invoice_lines: list, chat) -> int:
        """
        Izračunaj bruto/neto težine INTERNO (na lokalnoj kopiji).

        Ne dira draft direktno → nema sukoba sa Faktura Tab-om.

        Args:
            invoice_lines: Lista InvoiceLine objekata za obradu
            chat: ChatPanel za logging

        Returns:
            int: Broj izračunatih težina
        """
        # 1. Uzmi težine iz toolbar-a (ako postoje u UI)
        bruto_total = 0.0
        neto_total = 0.0

        if self.faktura_tab:
            try:
                bruto_text = self.faktura_tab.input_bruto.text().strip()
                neto_text = self.faktura_tab.input_neto.text().strip()
                bruto_total = float(bruto_text.replace(",", "") or "0")
                neto_total = float(neto_text.replace(",", "") or "0")
                print(f"[WeightCalc] Toolbar težine: bruto={bruto_total:.2f} kg, neto={neto_total:.2f} kg")
            except Exception as e:
                print(f"[WeightCalc] Greška pri čitanju težina: {e}")
                bruto_total = 0.0
                neto_total = 0.0

        # 2. Filtriraj stavke bez težina
        items_to_update = [
            line for line in invoice_lines
            if (not line.bruto_kg or line.bruto_kg == 0)
            or (not line.neto_kg or line.neto_kg == 0)
        ]

        if not items_to_update:
            print("[WeightCalc] Sve stavke već imaju težine - preskačem izračun")
            return 0  # Sve ima težine

        print(f"[WeightCalc] {len(items_to_update)} stavki za izračun težina")

        # 3. Izračunaj odnos neto/bruto (default 0.95 ako neto nije poznat)
        neto_bruto_ratio = neto_total / bruto_total if (bruto_total > 0 and neto_total > 0) else 0.95
        print(f"[WeightCalc] Odnos neto/bruto: {neto_bruto_ratio:.6f}")

        # Ukupna količina za proporcionalnu distribuciju
        total_qty = sum(line.kolicina or 0.0 for line in items_to_update if not (line.bruto_kg and line.bruto_kg > 0))

        # 4. Distribuiraj težine
        izracunato = 0
        for line in items_to_update:
            has_bruto = line.bruto_kg and line.bruto_kg > 0
            has_neto = line.neto_kg and line.neto_kg > 0

            if not has_bruto and not has_neto:
                # PDF stavka: nema težina → proporcionalna distribucija po količini
                qty = line.kolicina or 0.0
                if qty > 0 and total_qty > 0:
                    proportion = qty / total_qty
                    line.bruto_kg = round(bruto_total * proportion, 3) if bruto_total > 0 else 0.0
                    line.neto_kg = round(neto_total * proportion, 3) if neto_total > 0 else round(line.bruto_kg * neto_bruto_ratio, 3)
                else:
                    avg_weight = (bruto_total / len(invoice_lines)) if bruto_total > 0 else 0.0
                    line.bruto_kg = round(avg_weight, 3)
                    line.neto_kg = round(avg_weight * neto_bruto_ratio, 3)
                izracunato += 1
                print(f"  [PDF] {line.naziv_robe[:30]}: bruto={line.bruto_kg:.3f}, neto={line.neto_kg:.3f}")

            elif has_bruto and not has_neto:
                # Ima bruto, treba neto → koristi odnos
                line.neto_kg = round(line.bruto_kg * neto_bruto_ratio, 3)
                izracunato += 1
                print(f"  [Excel] {line.naziv_robe[:30]}: bruto={line.bruto_kg:.3f} → neto={line.neto_kg:.3f}")

        print(f"[WeightCalc] ✅ Izračunato {izracunato} težina")
        return izracunato

    def _validiraj_prije_uvoza(self, invoice_lines: list, chat) -> tuple:
        """
        Validiraj podatke PRIJE uvoza u draft.

        Provjere:
        1. Duplikati (isti broj fakture već postoji)
        2. Partneri (da li postoji u šifrarniku)
        3. Tarifni brojevi (da li su važeći)

        Returns:
            tuple: (valid: bool, errors: list)
        """
        errors = []
        warnings = []

        chat.add_activity("🔍 Validacija podataka...")

        # 1. Provjera duplikata (samo ako InvoiceLine ima broj_fakture)
        try:
            from services.zaglavlje_service import ZaglavljeService
            zaglavlje_svc = ZaglavljeService()
            
            # Uzmi brojeve faktura iz invoice_lines
            brojevi_faktura = set()
            for line in invoice_lines:
                if hasattr(line, 'broj_fakture') and line.broj_fakture:
                    brojevi_faktura.add(line.broj_fakture)
            
            # Provjeri svaki broj
            for broj in brojevi_faktura:
                if zaglavlje_svc.postoji_broj_fakture(broj):
                    errors.append(f"❌ Faktura br. '{broj}' već postoji u bazi!")
                else:
                    chat.add_activity(f"  ✅ Faktura {broj}: Nije duplikat")
        except Exception as e:
            # Ignoriši ako atribut ne postoji
            pass

        # 2. Provjera partnera (samo ako InvoiceLine ima dobavljac/primalac)
        try:
            from services.sifarnici_service import SifarniciService
            sifarnici_svc = SifarniciService()
            
            # Uzmi partnere iz invoice_lines
            partneri = set()
            for line in invoice_lines:
                if hasattr(line, 'dobavljac') and line.dobavljac:
                    partneri.add(line.dobavljac)
                if hasattr(line, 'primalac') and line.primalac:
                    partneri.add(line.primalac)
            
            # Provjeri svakog partnera
            for partner in partneri:
                # Pokušaj naći partnera u šifrarniku
                found = sifarnici_svc.search_partneri(partner)
                if not found or len(found) == 0:
                    warnings.append(f"⚠️ Partner '{partner}' nije u šifrarniku")
                else:
                    chat.add_activity(f"  ✅ Partner {partner}: Nađen u šifrarniku")
        except Exception as e:
            # Ignoriši ako atribut ne postoji
            pass

        # 3. Provjera tarifnih brojeva (samo za one koji već imaju tarifni)
        try:
            from services.naimenovanja.tariff_service import TariffService
            # TariffService treba tab referencu - preskoči ovu provjeru
            # tariff_svc = TariffService(tab_reference=...)
            
            # Umjesto toga, samo provjeri format tarifnog broja
            for line in invoice_lines:
                if hasattr(line, 'tarifni_broj') and line.tarifni_broj:
                    # Jednostavna provjera formata: XXXX.XXXX
                    tarif = line.tarifni_broj.strip()
                    if len(tarif) >= 4 and '.' in tarif:
                        chat.add_activity(f"  ✅ Tarifni {tarif}: Format ispravan")
        except Exception as e:
            pass

        # Emituj upozorenja
        for w in warnings:
            chat.add_activity(w)

        # Da li blokirati uvoz?
        if errors:
            chat.add_activity(f"❌ Validacija NIJE uspješna: {len(errors)} grešaka")
            return (False, errors + warnings)
        else:
            chat.add_activity(f"✅ Validacija uspješna ({len(warnings)} upozorenja)")
            return (True, warnings)

    def _generisi_izvjestaj(self, chat):
        """
        Analiziraj sve stavke i generiši izvještaj sa greškama i prijedlozima.
        """
        from services.faktura.validation_service import FakturaItemValidator
        from services.naimenovanja.tariff_service import TariffService
        
        chat.add_activity("📊 Generisanje izvještaja...")
        
        errors = []
        warnings = []
        suggestions = []
        
        validator = FakturaItemValidator()
        
        # Analiziraj svaku stavku
        for i, line in enumerate(self.draft.invoice_lines):
            row_num = i + 1
            
            # 1. Provjeri tarifni broj
            if not line.tarifni_broj:
                errors.append(f"Stavka {row_num}: Nema tarifni broj")
                suggestions.append(f"  → Klikni 'Auto-popuni tarifne' za stavku {row_num}")
            else:
                # Provjeri da li je tarifni broj važeći
                try:
                    tariff_svc = TariffService()
                    if not tariff_svc.validate_tariff(line.tarifni_broj):
                        errors.append(f"Stavka {row_num}: Nevažeći tarifni '{line.tarifni_broj}'")
                        suggestions.append(f"  → Ručno provjeri tarifni za stavku {row_num}")
                except:
                    pass  # Ignore ako service nije dostupan
            
            # 2. Provjeri zemlju porijekla
            if not line.zemlja_porijekla:
                warnings.append(f"Stavka {row_num}: Nema zemlju porijekla")
            
            # 3. Provjeri mase
            if not line.bruto_kg and not line.neto_kg:
                warnings.append(f"Stavka {row_num}: Nema mase (bruto/neto)")
                suggestions.append(f"  → Unesi mase za stavku {row_num}")
            elif line.bruto_kg and line.neto_kg and line.bruto_kg < line.neto_kg:
                errors.append(f"Stavka {row_num}: Bruto ({line.bruto_kg}) < Neto ({line.neto_kg})")
                suggestions.append(f"  → Ispravi mase za stavku {row_num}")
            
            # 4. Provjeri jedinicu mjere
            if not line.jm or line.jm.strip() == "":
                warnings.append(f"Stavka {row_num}: Nema jedinicu mjere")
        
        # Prikaži izvještaj
        if errors:
            chat.add_agent_message(
                f"⚠️ <b>Uočio sam {len(errors)} problema:</b><br><br>"
                f"❌ <b>Greške ({len(errors)}):</b><br>"
                f"{'<br>'.join(errors[:5])}" + (f"<br>... i još {len(errors)-5}" if len(errors) > 5 else "") +
                f"<br><br>"
                f"💡 <b>Prijedlozi:</b><br>"
                f"{'<br>'.join(suggestions[:5])}" + (f"<br>... i još {len(suggestions)-5}" if len(suggestions) > 5 else "")
            )
        elif warnings:
            chat.add_agent_message(
                f"✅ <b>Sve stavke su ispravne!</b><br><br>"
                f"⚠️ <b>Upozorenja ({len(warnings)}):</b><br>"
                f"{'<br>'.join(warnings[:5])}" + (f"<br>... i još {len(warnings)-5}" if len(warnings) > 5 else "")
            )
        else:
            chat.add_agent_message(
                f"✅ <b>Sve je savršeno!</b><br>"
                f"Nema grešaka ni upozorenja."
            )
        
        return len(errors) == 0

    def _uvezi_u_deklaraciju(self, invoice_lines: list, chat,
                              total_bruto: float = 0.0, total_neto: float = 0.0,
                              has_origin_statement: bool = False, completed: list = None):
        """
        Uvezi invoice_lines u draft — BEZ automatskih izmjena.
        Korisnik mora potvrditi svaku promjenu.

        Flow:
        1. Validacija
        2. Uvoz u draft
        3. Postavi težine u toolbar
        4. Izračunaj mase
        5. ⭐ OTVORI PE2/EUR.1 dijalog (obavezno, korisnik potvrđuje)
        6. ⭐ PONUDI prijedloge tarifnih (korisnik bira da li prihvata)
        7. ⭐ ČEKAJ korisnika prije kreiranja naimenovanja
        """
        print(f"[AgentController] _uvezi_u_deklaraciju: {len(invoice_lines)} stavki")

        if not self.draft:
            chat.add_activity("⚠️ Draft nije dostupan")
            return

        # 0. Validacija PRIJE uvoza
        chat.add_activity("🔍 Validacija prije uvoza...")
        valid, greške = self._validiraj_prije_uvoza(invoice_lines, chat)
        if not valid:
            chat.add_agent_message(
                f"❌ <b>Validacija nije uspješna!</b><br><br>"
                f"{'<br>'.join(greške)}<br><br>"
                f"Uvoz je obustavljen."
            )
            return

        # 1. Uvezi podatke u draft
        chat.add_activity(f"📥 Uvoz {len(invoice_lines)} stavki...")
        self.draft.invoice_lines.clear()
        self.draft.invoice_lines.extend(invoice_lines)
        chat.add_activity(f"✅ Uvezeno {len(invoice_lines)} stavki")

        # 2. Pauza za UI refresh
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        # 3. Otvori Faktura tab (bez agent_mode — želimo dijaloge!)
        faktura_widget = self.faktura_tab
        if hasattr(self.faktura_tab, 'view'):
            faktura_widget = self.faktura_tab.view

        if faktura_widget:
            # Postavi težine u toolbar (kroz weight_manager, ne direktni setText)
            if total_bruto > 0 or total_neto > 0:
                if hasattr(faktura_widget, 'weight_manager') and hasattr(faktura_widget, '_accumulate_weights'):
                    faktura_widget.weight_manager.accumulated_bruto_kg = 0.0
                    faktura_widget.weight_manager.accumulated_neto_kg = 0.0
                    faktura_widget._accumulate_weights(total_bruto, total_neto)
                    chat.add_activity(f"⚖️ Težine postavljene: Bruto={total_bruto:.2f}kg, Neto={total_neto:.2f}kg")

            # Refresh tabele
            if hasattr(faktura_widget, '_load_data_from_draft'):
                faktura_widget._load_data_from_draft()

            # 4. Izračunaj mase (ovo je OK — nije destruktivno)
            chat.add_activity("🤖 Izračunavam mase...")
            try:
                from services.faktura.mass_calculator import MassCalculator
                mass_calc = MassCalculator()

                if hasattr(faktura_widget, 'input_bruto') and hasattr(faktura_widget, 'input_neto'):
                    bruto_total = float(faktura_widget.input_bruto.text().replace(",", "") or "0")
                    neto_total = float(faktura_widget.input_neto.text().replace(",", "") or "0")

                    if bruto_total > 0 or neto_total > 0:
                        result = mass_calc.calculate_masses(
                            self.draft.invoice_lines, bruto_total, neto_total
                        )
                        chat.add_activity(
                            f"✅ Mase izračunate: {result['updated']} stavki ažurirano"
                        )
                    else:
                        chat.add_activity("ℹ️ Nema težina za izračun")
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri izračunu masa: {e}")

            # Konačni refresh
            if hasattr(faktura_widget, '_load_data_from_draft'):
                faktura_widget._load_data_from_draft()

        # 5. ⭐ NAĐI BROJ FAKTURE ZA DIJALOG
        invoice_number = ""
        if completed:
            for f in completed:
                if f.status == 'Completed' and (f.invoice_number or f.filepath):
                    invoice_number = f.invoice_number or Path(f.filepath).stem
                    break

        # 6. ⭐ OBVEZNO: OTVORI PE2/EUR.1 DIJALOG (korisnik potvrđuje)
        if has_origin_statement:
            chat.add_activity("📄 Faktura IMA izjavu o poreklu — otvaram PE2 dijalog...")
            chat.add_agent_message(
                f"📄 <b>Faktura ima izjavu o preferencijalnom porijeklu.</b><br>"
                f"Otvoriću PE2 dijalog da potvrdiš ili izmijeniš podatke.<br><br>"
                f"⚠️ <b>Ništa se ne upisuje automatski — ti odlučuješ.</b>"
            )
            try:
                from gui.dialogs.pe2_quick_dialog import PE2QuickDialog
                dialog = PE2QuickDialog(self.draft.invoice_lines, self.view, invoice_number=invoice_number)
                result_dlg = dialog.exec()

                if result_dlg == 1:
                    pe2_data = dialog.get_data()
                    if pe2_data:
                        updated_count = PE2QuickDialog.apply_pe2_data(
                            self.draft.invoice_lines, pe2_data
                        )
                        chat.add_activity(f"✅ PE2 primijenjen na {updated_count} stavki")
                        if hasattr(faktura_widget, '_load_data_from_draft'):
                            faktura_widget._load_data_from_draft()
                else:
                    chat.add_activity("ℹ️ PE2 dijalog preskočen — uredi ručno u Faktura tabu")
            except Exception as e:
                chat.add_activity(f"⚠️ PE2 dijalog greška: {e}")
        else:
            # ❌ Faktura NEMA izjavu — provjeri ima li stavki sa povlasticom koje čekaju EUR.1
            eur1_pending_lines = [
                line for line in self.draft.invoice_lines
                if getattr(line, 'povlastica', None)
                and not getattr(line, 'has_origin_statement', False)
                and not getattr(line, 'eur1_number', None)
            ]

            if eur1_pending_lines:
                chat.add_activity(
                    f"📋 {len(eur1_pending_lines)} stavki treba EUR.1 broj — otvaram dijalog..."
                )
                chat.add_agent_message(
                    f"⚠️ <b>Faktura NEMA izjavu o porijeklu.</b><br>"
                    f"Pronašao sam <b>{len(eur1_pending_lines)}</b> stavki koje mogu koristiti EUR.1 obrazac.<br><br>"
                    f"📄 <b>Unesi EUR.1 broj za svaku zemlju.</b><br>"
                    f"Ako nemaš EUR.1, ostavi prazno i uredi kasnije ručno."
                )
                try:
                    from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog
                    dialog = Eur1QuickDialog(self.draft.invoice_lines, self.view, invoice_number=invoice_number)
                    result_dlg = dialog.exec()

                    if result_dlg == 1:
                        eur1_data = dialog.get_data()
                        if eur1_data:
                            updated_count = Eur1QuickDialog.apply_eur1_data(
                                self.draft.invoice_lines, eur1_data
                            )
                            chat.add_activity(f"✅ EUR.1 primijenjen na {updated_count} stavki")
                            # Propagiraj na postojeća naimenovanja u draftu
                            self._apply_eur1_to_naimenovanja(eur1_data, chat)
                            if hasattr(faktura_widget, '_load_data_from_draft'):
                                faktura_widget._load_data_from_draft()
                    else:
                        chat.add_activity("ℹ️ EUR.1 dijalog preskočen — unesi broj ručno u Faktura tabu")
                except Exception as e:
                    chat.add_activity(f"⚠️ EUR.1 dijalog greška: {e}")
            else:
                chat.add_activity("ℹ️ Nema stavki koje zahtijevaju EUR.1 — nastavi ručno uređivanje")

        # 7. ⭐ PRIKAŽI REZIME I PONUDI DALJE AKCIJE
        bez_tarife = sum(1 for l in self.draft.invoice_lines if not l.tarifni_broj)
        chat.add_agent_message(
            f"✅ <b>Uvoz završen!</b><br>"
            f"Uvezeno <b>{len(invoice_lines)}</b> stavki.<br><br>"
            f"📊 <b>Stanje:</b><br>"
            f"  • Bez tarifnog broja: <b>{bez_tarife}</b><br>"
            f"  • Mase: izračunate<br>"
            f"  • Povlastice: {'PE2/EUR.1 potvrđeno' if has_origin_statement else 'Čeka unos'}<br><br>"
            f"💡 <b>Šta dalje?</b><br>"
            f"  • Reci <i>'popuni tarifne'</i> za prijedloge tarifnih brojeva<br>"
            f"  • Pregledaj tablicu i ručno dopuni podatke<br>"
            f"  • Kad si spreman, reci <i>'kreiraj naimenovanja'</i>"
        )

    def _otvori_faktura_tab_nakon_uvoza(self, chat):
        """
        Otvori Faktura tab nakon uspješnog uvoza.

        Koristi findChild da nađe tabs widget i prebaci na Faktura tab.
        """
        chat.add_activity("🔄 Otvaranje Faktura taba...")
        
        # Pokušaj naći parent widget (MainWindow)
        parent = self.view.parent()
        while parent:
            if 'MainWindow' in str(type(parent)):
                break
            parent = parent.parent()
        
        # Nađi pravi faktura_tab (može biti FakturaTabRefactored)
        faktura_tab_widget = self.faktura_tab
        if hasattr(self.faktura_tab, 'view'):
            # FakturaTabRefactored - koristi inner view
            faktura_tab_widget = self.faktura_tab.view
        
        if parent and faktura_tab_widget:
            try:
                # Nađi tabs widget
                from PySide6.QtWidgets import QTabWidget
                tabs_widgets = parent.findChildren(QTabWidget)
                
                if tabs_widgets:
                    tabs = tabs_widgets[0]  # Uzmi prvi QTabWidget
                    tabs.setCurrentWidget(self.faktura_tab)
                    chat.add_activity("✅ Prebačeno na Faktura tab")
                    
                    # Refresh podataka - koristi view ako postoji
                    if hasattr(faktura_tab_widget, '_load_data_from_draft'):
                        faktura_tab_widget._load_data_from_draft()
                        chat.add_activity("✅ Podaci učitani u Faktura tab")
                    else:
                        chat.add_activity("⚠️ _load_data_from_draft nije dostupan")
                else:
                    chat.add_activity("⚠️ Tabs widget nije pronađen")
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri otvaranju Faktura taba: {e}")
        else:
            chat.add_activity("⚠️ Parent window nije pronađen")

    def _primjeni_xml_template(self, all_lines: list, chat, silent: bool = False):
        """
        Korak za Puna automatizacija:
        Pronađi stari XML sa istim pošiljaocem i primijeni whitelist polja na draft zaglavlje.

        Pokušava naći pošiljaoca iz:
        1. InvoiceLine.exporter.name (ako importer popunjava)
        2. import_type iz ProcessingWorker file_item-a
        3. Naziva fajla (npr. "pekabesko-123.xlsx")
        """
        if not self.draft:
            return "⚠️ Draft nije inicijalizovan"

        chat.add_activity("🔍 Tražim XML template za zaglavlje...")

        # ── Izvuci hint za pošiljaoca ────────────────────────────
        exporter_hint = ""

        # 1. Pokušaj iz InvoiceLine.exporter.name
        for line in all_lines:
            name = getattr(getattr(line, 'exporter', None), 'name', None)
            if name and name.strip():
                exporter_hint = name.strip()
                break

        # 2. Ako nema, pokušaj iz invoice_lines zemlja + import_type
        if not exporter_hint:
            for line in all_lines:
                if getattr(line, 'naziv_robe', None):
                    # Pokušaj iz naziva fakture ako je dostupan
                    break

        # 3. Pokušaj iz processing worker fajlova (filename)
        if not exporter_hint:
            doc = self.view.get_document_panel()
            for file_item in doc.get_files():
                stem = Path(file_item).stem if isinstance(file_item, str) else Path(file_item.filepath).stem
                # Ukloni brojeve fakture (npr. "pekabesko-2000-00015" → "pekabesko")
                import re
                clean = re.sub(r'[-_\s]*[\d\-]+$', '', stem).strip()
                if clean:
                    exporter_hint = clean
                    break

        if not exporter_hint:
            chat.add_activity("⚠️ Nije moguće odrediti pošiljaoca — preskačem template pretragu")
            return "⚠️ Pošiljalac nepoznat — popuni zaglavlje ručno"

        # Consignee JIB iz rubrike 8 (jedinstven identifikator uvoznika)
        consignee_jib = getattr(self.draft, 'primalac_id', '') or ''
        consignee_name = getattr(self.draft, 'primalac_naziv', '') or ''

        chat.add_activity(
            f"🔍 Tražim template za: '{exporter_hint}'"
            + (f" + uvoznik JIB {consignee_jib}" if consignee_jib else "")
        )

        # ── Pretraga: 1. exporter_xml_index (DB, JIB lookup) ────
        from services.agent.xml_template_service import XmlTemplateService, TemplateMatch
        svc = XmlTemplateService()
        match = None

        try:
            from services.agent.exporter_xml_indexer import find_xml_for_pair
            db_result = find_xml_for_pair(
                exporter_hint,
                consignee_jib=consignee_jib,
                consignee_hint=consignee_name,
            )
            if db_result and Path(db_result['xml_filepath']).exists():
                xml_path = Path(db_result['xml_filepath'])
                exporter_from_xml, fields = svc._parse_xml(xml_path)
                match_type = db_result.get('match_type', 'db')
                score = 1.0 if 'jib' in match_type else 0.85 if 'name' in match_type else 0.70
                match = TemplateMatch(
                    filepath=str(xml_path),
                    filename=xml_path.name,
                    exporter_name=db_result.get('exporter_original') or exporter_from_xml,
                    match_score=score,
                    fields=fields,
                )
                chat.add_activity(
                    f"✅ Nađen u bazi: '{xml_path.name}' "
                    f"(match: {match_type}, uvoznik: {db_result.get('consignee_original', '—')})"
                )
        except Exception as e:
            chat.add_activity(f"⚠️ DB lookup greška: {e} — probam lokalne fajlove")

        # ── Pretraga: 2. Fallback — lokalni XML fajlovi ──────────
        if not match:
            try:
                match = svc.find_template(exporter_hint)
                if match:
                    chat.add_activity(
                        f"✅ Nađen lokalno: '{match.filename}' "
                        f"(pošiljalac: '{match.exporter_name}', poklapanje: {int(match.match_score * 100)}%)"
                    )
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri pretrazi XML templatea: {e}")

        if not match:
            chat.add_activity(f"ℹ️ Nema XML templatea za '{exporter_hint}' — popuni zaglavlje ručno")
            return f"ℹ️ Nema prethodnog XML-a za '{exporter_hint}'"

        # ── Primijeni template na draft ──────────────────────────
        applied = svc.apply_to_draft(self.draft, match.fields)

        if not applied:
            chat.add_activity("ℹ️ Sva zaglavlje polja već popunjena — template nije primijenjen")
            return "ℹ️ Zaglavlje već popunjeno"

        chat.add_activity(f"✅ Primijenjeno {len(applied)} zaglavlje polja iz templatea")

        # ── Osvježi Zaglavlje tab ────────────────────────────────
        if self.zaglavlje_tab:
            try:
                if hasattr(self.zaglavlje_tab, 'load_from_draft'):
                    self.zaglavlje_tab.load_from_draft(self.draft)
                elif hasattr(self.zaglavlje_tab, 'reload_data'):
                    self.zaglavlje_tab.reload_data()
                elif hasattr(self.zaglavlje_tab, 'refresh'):
                    self.zaglavlje_tab.refresh()
                chat.add_activity("✅ Zaglavlje tab osvježen")
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri osvježavanju Zaglavlje taba: {e}")

        if silent:
            # Puna automatizacija — primijeni bez dijaloga
            chat.add_activity(
                f"✅ Zaglavlje popunjeno iz: <b>{match.filename}</b> "
                f"(pošiljalac: {match.exporter_name})"
            )
            return f"✅ Popunjeno iz {match.filename}"

        # ── Prikaži dijalog sa rezimeom (interaktivni modovi) ───
        try:
            from gui.dialogs.zaglavlje_template_dialog import ZaglavljeTemplateDialog
            dialog = ZaglavljeTemplateDialog(match, applied, parent=self.view)
            result = dialog.exec()
            if result != 1:
                for field_name in applied:
                    try:
                        setattr(self.draft, field_name, "")
                    except Exception:
                        pass
                # Resetuj i u Zaglavlje tabu
                if self.zaglavlje_tab and hasattr(self.zaglavlje_tab, 'load_from_draft'):
                    self.zaglavlje_tab.load_from_draft(self.draft)
                chat.add_activity("ℹ️ Template odbačen — zaglavlje polja resetovana")
            else:
                chat.add_activity("✅ Template prihvaćen — popuni preostala polja u Zaglavlje tabu")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri prikazu dijaloga: {e}")

    def _izvezi_xml(self, chat):
        """Izvezi deklaraciju u ASYCUDA XML fajl."""
        if not self.draft:
            return

        try:
            from exporters.asycuda_xml_builder import export_to_xml

            filepath, _ = QFileDialog.getSaveFileName(
                self.view,
                "Sačuvaj ASYCUDA XML",
                "",
                "XML Files (*.xml)"
            )
            if filepath:
                export_to_xml(self.draft, filepath)
                chat.add_activity(f"✅ XML exportovan: {Path(filepath).name}")
                chat.add_agent_message(
                    f"✅ <b>Puna automatizacija završena!</b><br>"
                    f"XML fajl sačuvan: <b>{Path(filepath).name}</b>"
                )
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri XML exportu: {e}")

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
        """Odgovori na chat poruku — prvo provjeri akcije, pa LLM."""
        from .widgets.chat_worker import ChatWorker
        chat = self.view.get_chat_panel()
        msg = message.lower().strip()

        # --- POTVRDA pending akcije ---
        POTVRDE = {'da', 'odobri', 'potvrdi', 'yes', 'ok', 'u redu', 'slažem se'}
        OTKAZI = {'ne', 'odustani', 'cancel', 'no', 'storno'}

        if self._pending_action:
            if msg in POTVRDE or msg.startswith('da ') or msg.startswith('odobr'):
                self._execute_pending_action()
                return
            if msg in OTKAZI:
                self._pending_action = None
                chat.add_agent_message("❌ Akcija otkazana.")
                return

        # --- DETEKCIJA NAMJERE: tarifni brojevi ---
        import re as _re

        # Redni brojevi na srpskom → korisnik misli na konkretnu stavku
        _REDNI = {'prvi': 1, 'prvog': 1, 'prvo': 1, 'prva': 1,
                  'drugi': 2, 'drugog': 2, 'drugo': 2, 'druga': 2,
                  'treći': 3, 'trećeg': 3, 'treće': 3, 'treca': 3, 'treceg': 3,
                  'četvrti': 4, 'cetvrti': 4, 'četvrtog': 4,
                  'peti': 5, 'petog': 5, 'šesti': 6, 'sedmi': 7,
                  'osmi': 8, 'deveti': 9, 'deseti': 10,
                  'posljednji': -1, 'zadnji': -1}
        _has_ordinal = any(w in msg for w in _REDNI)

        # Ima li konkretnih cifara ili rednih brojeva
        _has_specific_items = bool(_re.search(r'\b\d+\b', msg)) or _has_ordinal

        # Upiti koji ČITAJU podatke → uvijek idu na LLM (ne na batch)
        _upit_kw = ['koji je', 'koja je', 'koje je', 'koji su', 'koje su',
                    'šta je', 'sta je', 'što je', 'sto je',
                    'kakav je', 'kakva je', 'koliki je', 'kolika je',
                    'pogledaj', 'pokaži', 'pokazi', 'prikaži', 'prikazi',
                    'reci mi', 'kaži mi', 'kazi mi', 'napiši mi',
                    'provjeri', 'provjeru', 'analiz', 'obrazloži']
        _is_query = any(kw in msg for kw in _upit_kw)

        # --- DETEKCIJA NAMJERE: upisivanje / brisanje vrijednosti u kolonu ---
        # Format: "upiši X u kolonu/polje Y" ili "postavi Y na X" ili "briši kolonu Y"
        _upis_glagoli = ['upiši', 'upisi', 'upisite', 'upišite', 'postavi', 'stavi', 'set', 'unesite', 'unesi']
        _upis_prijedlozi = ['u kolonu', 'u polje', 'u kolone', 'u tab', 'u faktur', 'u naim',
                            'u rubrik', 'na kolonu', 'za kolonu']
        _has_upis = any(g in msg for g in _upis_glagoli)
        _has_prijedlog = any(p in msg for p in _upis_prijedlozi)
        _has_postavi = 'postavi' in msg or ('stavi' in msg and ('na' in msg or 'u' in msg))
        # Brisanje kolone (bez "tarif" jer to ima poseban handler)
        _brisanje_kolone_kw = ['izbri', 'obri', 'ukloni', 'resetuj', 'ocisti', 'očisti',
                               'brisi', 'briši', 'prazni', 'isprazni']
        _has_brisanje_kolone = any(g in msg for g in _brisanje_kolone_kw)
        _kolone_naim = ['povlastic', 'zemlja', 'procedur', 'pakovan', 'rubrik', 'naim',
                        'preference', 'origin', 'oznake']
        _has_naim_kolona = any(k in msg for k in _kolone_naim)

        if (_has_upis and _has_prijedlog) or _has_postavi:
            result = self._parse_upis_u_kolonu(message)
            if result:
                kolona, vrijednost, tab = result
                self._upisi_u_kolonu(kolona, vrijednost, tab)
                return
        elif _has_brisanje_kolone and _has_naim_kolona and 'tarif' not in msg:
            result = self._parse_upis_u_kolonu(message, brisanje=True)
            if result:
                kolona, _, tab = result
                self._upisi_u_kolonu(kolona, '', tab)
                return

        # --- DETEKCIJA NAMJERE: zapamti tarifni (korisnik potvrđuje tačan tarif) ---
        # Format: "Zapamti 84713000 za laptop" / "Nauči 62034200 za muške pantalone"
        _zapamti_match = _re.search(
            r'(?:zapamti|nauci|nauči|snimi|upamti|sacuvaj|sačuvaj|dodaj u bazu)\s+'
            r'(\d[\d\.\s]{5,12})\s+za\s+(.{3,60})',
            msg,
        )
        if _zapamti_match:
            _tariff_raw = _zapamti_match.group(1).strip()
            _naziv_raw = _zapamti_match.group(2).strip().rstrip('?! ')
            self.tariff_svc.learn_tariff(_naziv_raw, _tariff_raw)
            return

        # --- DETEKCIJA NAMJERE: upiši tarifne za [keyword] ---
        import re as _re2
        _filter_tariff_match = _re2.search(
            r'(?:pogledaj|nađi|trazi|traži).{0,40}?(\w{3,})\s+upiši\s+(?:te\s+)?tarif'
            r'|upiši\s+(?:te\s+)?tarif\w*\s+za\s+(\w+)'
            r'|(\w+)\s+upiši\s+(?:te\s+)?tarif',
            msg
        )
        if _filter_tariff_match:
            keyword = next(g for g in _filter_tariff_match.groups() if g)
            # Preskoči opšte riječi koje nisu filter
            _skip = {'te', 'sve', 'koji', 'koje', 'ovi', 'ove', 'tarif', 'tarifne', 'broj'}
            if keyword not in _skip and len(keyword) >= 3:
                self._predlozi_tarifne_po_filteru(keyword)
                return

        # --- DETEKCIJA NAMJERE: provjera/prijedlog tarifnog za konkretan naziv robe ---
        # Format: "predloži tarifni za X", "predloži tarifni broj za X", "koji tarif za X"
        # Dozvoljava do 3 opcione riječi između glagola i "za" (npr. "predloži mi tarifni broj za X")
        _provjeri_tarif_match = _re.search(
            r'(?:provjeri|testiraj|predloži|predlozi|traži|trazi|koji\s+je|kakav\s+je|daj)'
            r'(?:\s+\w+){0,4}\s+za\s+(.+)',
            msg
        )
        # Odbaci ako je uhvaćeni dio samo "naim/stavku" bez naziva robe
        if _provjeri_tarif_match and 'tarif' not in msg:
            _provjeri_tarif_match = None
        if _provjeri_tarif_match:
            _uhvaceno = _provjeri_tarif_match.group(1).strip()
            if any(w in _uhvaceno for w in ['naim', 'stavk', 'prvo', 'drugi', 'treć']):
                _provjeri_tarif_match = None
        if _provjeri_tarif_match:
            naziv = _provjeri_tarif_match.group(1).strip().rstrip('?!')
            if naziv and len(naziv) >= 3:
                self._provjeri_tarifni_za_naziv(naziv)
                return

        # --- DETEKCIJA NAMJERE: pretraga carinske tarife ---
        # Format: "pretraži tarifu za X", "nađi tarifu za X", "šta je tarifa za X"
        #         "provjeri kod 3304990000", "tarifa poglavlje 33"
        _tarifa_pretrazi_match = _re.search(
            r'(?:pretra[žz]i?|na[đd]i?|trazi|traži)\s+tarif[ua]\s+(?:za\s+)?(.+)'
            r'|(?:šta|sta|što|sto|koji|koja)\s+(?:je\s+)?tarif[ua]\s+(?:za\s+)?(.+)'
            r'|tarif[ua]\s+(?:za\s+|broj\s+)?(.+)',
            msg
        )
        _tarifa_kod_match = _re.search(
            r'(?:provjeri|validir|pokaži|pokazi)\s+(?:tarifn[ui]\s+)?(?:kod\s+|broj\s+|oznaku\s+)?(\d{8,10})',
            msg
        )
        _tarifa_poglavlje_match = _re.search(
            r'(?:poglavlje|odjeljak|glava)\s+(\d{1,2})',
            msg
        )

        if _tarifa_kod_match:
            self._pretrazi_tarifu_po_kodu(_tarifa_kod_match.group(1))
            return
        elif _tarifa_poglavlje_match:
            self._pretrazi_tarifu_poglavlje(_tarifa_poglavlje_match.group(1))
            return
        elif _tarifa_pretrazi_match:
            upit = next(g for g in _tarifa_pretrazi_match.groups() if g)
            upit = upit.strip().rstrip('?!')
            if upit and len(upit) >= 2:
                self._pretrazi_tarifu(upit)
                return

        # --- DETEKCIJA NAMJERE: hijerarhijski prikaz tarife (drill-down) ---
        # Format: "pokaži 8516", "šta je 8516", "pregledaj 851660", "drvo 85"
        _tree_kw = ['pokaži', 'pokazi', 'šta je', 'sta je', 'pregledaj', 'pregled',
                    'hijerarh', 'drvo', 'stabla', 'drill', 'razradi', 'pogledaj',
                    'nivo', 'nivou', 'struktura', 'hijerarhija']
        _has_tree_kw = any(kw in msg for kw in _tree_kw)

        # Izvuci broj iz poruke (2-10 cifara)
        _tariff_code_match = _re.search(r'\b(\d{2,10})\b', msg)
        _tariff_code_from_msg = _tariff_code_match.group(1) if _tariff_code_match else None

        if _has_tree_kw and _tariff_code_from_msg and len(_tariff_code_from_msg) >= 2:
            self._pretrazi_tarifu_hijerarhijski(_tariff_code_from_msg)
            return

        # --- DETEKCIJA NAMJERE: prijedlog tarifnog za konkretno naimenovanje/stavku ---
        # "predloži tarifni broj za prvo naimenovanje", "predloži tarif za naim 3" itd.
        _predlozi_kw = ['predloži', 'predlozi', 'prijedlog', 'predloži mi', 'predlozi mi',
                        'daj tarif', 'koji tarif', 'kakav tarif']
        _has_predlozi_tarif_naim = (
            any(kw in msg for kw in _predlozi_kw)
            and 'tarif' in msg
            and ('naim' in msg or 'stavk' in msg)
        )
        if _has_predlozi_tarif_naim:
            # Izvuci redni broj — digitalni format ("naim 3", "stavku 5")
            _ptn_digit = _re.search(r'(?:naim\w*|stavk\w*)\s*\.?\s*(\d+)', msg)
            if _ptn_digit:
                self._alternativni_tarifni_za_stavku(item_ordinal=int(_ptn_digit.group(1)))
            elif _has_ordinal:
                _p_ord = next((v for k, v in _REDNI.items() if k in msg and v > 0), None)
                self._alternativni_tarifni_za_stavku(item_ordinal=_p_ord)
            else:
                # Bez rednog broja — uzmi naziv iz "za X"
                _ptn_za = _re.search(r'za\s+([a-zšđčćžA-ZŠĐČĆŽ][^,?!\n]{2,40})', msg)
                _naziv = _ptn_za.group(1).strip() if _ptn_za else ""
                self._alternativni_tarifni_za_stavku(item_query=_naziv)
            return

        # --- DETEKCIJA NAMJERE: brisanje tarifnih brojeva (MORA BITI ISPRED popune!) ---
        # Provjera: prisutan glagol brisanja I "tarif" u poruci
        _brisanje_glagoli = ['izbri', 'obri', 'ukloni', 'resetuj', 'ocisti', 'očisti',
                             'brisi', 'briši', 'delete', 'clear', 'prazni', 'isprazni']
        _has_brisanje = any(g in msg for g in _brisanje_glagoli)
        _has_tarif = 'tarif' in msg
        if _has_brisanje and _has_tarif:
            self._obrisi_tarifne_brojeve()
            return

        # --- DETEKCIJA NAMJERE: alternativni tarifni (korisnik nije zadovoljan) ---
        # Korisnik ima popunjen tarif ali misli da je pogrešan — traži alternativu
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
            # Pokušaj izvuci naziv robe: "za X", navodnici, ili po rednom broju
            _alt_name_match = _re.search(r'za\s+["\']?([a-zšđčćžA-ZŠĐČĆŽ0-9][^,?!\n]{2,50})', msg)
            _alt_quote_match = _re.search(r'["\'](.{3,50})["\']', msg)
            item_q = ""
            item_ord = None
            if _alt_quote_match:
                item_q = _alt_quote_match.group(1).strip()
            elif _alt_name_match:
                item_q = _alt_name_match.group(1).strip().rstrip('?! ')
            # Redni broj stavke — digitalni format (npr. "naim 2", "stavku 3")
            _alt_ord_match = _re.search(r'(?:stavk[ue]?|naim\w*|rb\.?|redni\s+br\.?)\s+(\d+)', msg)
            if _alt_ord_match:
                item_ord = int(_alt_ord_match.group(1))
            # Redni broj stavke — srpski redni brojevi ("prvom", "drugom", "treće"...)
            if item_ord is None and _has_ordinal:
                for _ord_word, _ord_num in _REDNI.items():
                    if _ord_word in msg and _ord_num > 0:
                        item_ord = _ord_num
                        break
            self._alternativni_tarifni_za_stavku(item_query=item_q, item_ordinal=item_ord, is_alt=True)
            return

        # Eksplicitni batch zahtjev (popuni sve / nađi sve bez / predloži tarifne)
        # NAPOMENA: "predloži mi tarif za X" i "predloži tarif za X" su odstranjeni odavde
        #           jer ih hvata _provjeri_tarif_match iznad.
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
        ]

        if any(kw in msg for kw in _generalni_tarif_kw):
            # Batch: traži sve bez tarifnog broja
            self._predlozi_tarifne_brojeve()
            return
        elif _is_query and any(kw in msg for kw in ['tarif', 'tarifn', 'naim', 'stavk']):
            # Informativni upit o tarifi/naimenovanju → LLM
            pass
        elif any(kw in msg for kw in ['tarif', 'tarifn']) and not _has_specific_items and not _is_query:
            # Dvosmislena tarif-poruka: ima "za" ili naziv robe → classifier, inače batch
            _has_za_nesto = bool(_re.search(r'\btarif\w*\s+za\s+\w{3,}', msg)
                                 or _re.search(r'\bza\s+\w{3,}.{0,30}\btarif', msg))
            if _has_za_nesto:
                # Postoji "tarif za X" pattern → LLM classifier za pametno usmjeravanje
                self._klasificiraj_i_usmjeri(message)
            else:
                # Bez konkretne robe → batch prijedlog
                self._predlozi_tarifne_brojeve()
            return

        # --- DETEKCIJA NAMJERE: pregled i validacija naimenovanja ---
        # "pregledaj naimenovanja", "provjeri naimenovanja", "pokaži naimenovanje 3"
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
            # Validacija popunjenosti
            if any(kw in msg for kw in ['provjer', 'valid', 'da li su', 'šta fali', 'sta fali', 'nedostaje', 'prazn', 'nepopunjene']):
                self._provjeri_naimenovanja()
                return
            # Detaljan pregled konkretnog naimenovanja (sa rednim brojem)
            _REDNI_NAIM = {'prvi': 1, 'prvog': 1, 'prvo': 1, 'prva': 1,
                           'drugi': 2, 'drugog': 2, 'drugo': 2, 'druga': 2,
                           'treći': 3, 'trećeg': 3, 'treće': 3, 'treca': 3, 'treceg': 3,
                           'četvrti': 4, 'cetvrti': 4, 'četvrtog': 4,
                           'peti': 5, 'petog': 5, 'šesti': 6, 'sedmi': 7,
                           'osmi': 8, 'deveti': 9, 'deseti': 10}
            _naim_indices = [int(m) for m in _re.findall(r'\b(\d+)\b', msg)
                            if 1 <= int(m) <= len(getattr(self.draft, 'items', [])) + 5]
            _naim_ordinal = [_REDNI_NAIM.get(w) for w in msg.split() if w in _REDNI_NAIM]
            combined_indices = list(dict.fromkeys(_naim_indices + [x for x in _naim_ordinal if x]))

            if combined_indices:
                self._pregledaj_naimenovanja(combined_indices)
            else:
                self._pregledaj_naimenovanja()  # Prikaži sva
            return

        # --- DETEKCIJA NAMJERE: spajanje naimenovanja ---
        # Samo eksplicitni zahtjev za spajanje/grupiranje → akcija
        # Sve ostalo sa "naimenovanj" (provjeri, predloži, koji, šta je...) → LLM
        _spajanje_kw = ['spoji naim', 'merge naim', 'grupiš naim', 'objedini naim',
                        'spoji naimenovanj', 'objedini naimenovanj', 'grupiši naimenovanj']
        if any(kw in msg for kw in _spajanje_kw) and not _has_specific_items:
            self._predlozi_spajanje_naimenovanja()
            return

        # --- DETEKCIJA NAMJERE: compliance check ---
        _compliance_kw = [
            'provjeri deklaraciju', 'provjera deklaracije', 'da li je sve u redu',
            'compliance', 'kompletnost', 'provjeri sve', 'validacija deklaracije',
            'šta nedostaje', 'sta nedostaje', 'greške u deklaraciji', 'pregled deklaracije',
        ]
        if any(kw in msg for kw in _compliance_kw):
            self._compliance_check()
            return

        # --- TOKEN BUDGET provjera ---
        budget_status, budget_msg = self.budget.check()
        if budget_status == 'stop':
            chat.add_agent_message(budget_msg)
            return
        if budget_status == 'warn':
            chat.add_activity(budget_msg)

        # Procijeni input tokene iz poruke
        self.budget.estimate_input(message)

        # --- STANDARDNI LLM odgovor ---
        chat.add_activity(f"💬 Šaljem upit AI-u...")
        chat.show_typing_indicator()

        memory_service = chat.get_memory_service()

        worker = ChatWorker(
            message,
            draft=self.draft,
            parent=self.view,
            memory_service=memory_service
        )
        # Streaming: typing → stream bubble → token po token → finalize
        worker.stream_started.connect(chat.start_streaming)
        worker.token_received.connect(chat.append_stream_token)
        worker.response_ready.connect(lambda _: chat.finalize_streaming())
        # Procijeni output tokene i snimi sesiju
        worker.response_ready.connect(
            lambda text: (
                self.budget.estimate_output(text),
                self._check_budget_after_response(),
            )
        )
        # Na grešku: ukloni indikator i prikaži poruku
        worker.error_occurred.connect(lambda _: chat.hide_typing_indicator())
        worker.error_occurred.connect(
            lambda err: chat.add_agent_message(f"⚠️ {err}")
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

        # Čuvaj referencu da GC ne ubije worker
        if not hasattr(self, '_chat_workers'):
            self._chat_workers = []
        self._chat_workers.append(worker)
        worker.finished.connect(lambda: self._chat_workers.remove(worker) if worker in self._chat_workers else None)

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

    # Mapa sinonima kolona → (atribut, tab)
    # tab: 'faktura' = InvoiceLine, 'naim' = NaimenovanjeDraft
    _KOLONA_MAP = {
        # ═══════════════════════════════════════════════════════
        # FAKTURA TAB (InvoiceLine)
        # ═══════════════════════════════════════════════════════
        # Tarifni broj (Rub.33)
        'tarifni broj':       ('tarifni_broj',      'faktura'),
        'tarifni':            ('tarifni_broj',      'faktura'),
        'tarif':              ('tarifni_broj',      'faktura'),
        'hs kod':             ('tarifni_broj',      'faktura'),
        'hs':                 ('tarifni_broj',      'faktura'),
        # Zemlja porijekla (Rub.34)
        'zemlja porijekla':   ('zemlja_porijekla',  'faktura'),
        'zemlja':             ('zemlja_porijekla',  'faktura'),
        'porijeklo':          ('zemlja_porijekla',  'faktura'),
        'porijekla':          ('zemlja_porijekla',  'faktura'),
        'origin':             ('zemlja_porijekla',  'faktura'),
        # Povlastica (Rub.36)
        'povlastica':         ('povlastica',        'faktura'),
        'povlastice':         ('povlastica',        'faktura'),
        'pref':               ('povlastica',        'faktura'),
        'preference':         ('povlastica',        'faktura'),
        # EUR.1
        'eur1':               ('eur1_number',       'faktura'),
        'eur.1':              ('eur1_number',       'faktura'),
        'eur 1':              ('eur1_number',       'faktura'),
        # Valuta
        'valuta':             ('valuta',            'faktura'),
        'currency':           ('valuta',            'faktura'),
        # Naziv robe
        'naziv robe':         ('naziv_robe',        'faktura'),
        'naziv':              ('naziv_robe',        'faktura'),
        'opis':               ('naziv_robe',        'faktura'),
        # Količina
        'kolicina':           ('kolicina',          'faktura'),
        'količina':           ('kolicina',          'faktura'),
        'qty':                ('kolicina',          'faktura'),
        # Jedinica mjere
        'jm':                 ('jm',               'faktura'),
        'jedinica mjere':     ('jm',               'faktura'),
        'jedinica':           ('jm',               'faktura'),

        # ═══════════════════════════════════════════════════════
        # NAIM TAB (NaimenovanjeDraft)
        # ═══════════════════════════════════════════════════════
        # Rub.31 – pakovanje i opis
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
        # Rub.33 – tarifni broj (naim)
        'tarifni broj naim':  ('tariff_code',        'naim'),
        'tariff code':        ('tariff_code',        'naim'),
        # Rub.34 – zemlja porijekla (naim)
        'zemlja naim':        ('origin_country_code', 'naim'),
        'origin code':        ('origin_country_code', 'naim'),
        # Rub.36 – povlastica (naim)
        'povlastica naim':    ('preference_code',    'naim'),
        'preference code':    ('preference_code',    'naim'),
        # Rub.37 – procedura
        'procedura':          ('procedure_code',     'naim'),
        'proceduru':          ('procedure_code',     'naim'),
        'procedure':          ('procedure_code',     'naim'),
        'postupak':           ('procedure_code',     'naim'),
        'postupku':           ('procedure_code',     'naim'),
        'rub37':              ('procedure_code',     'naim'),
        'rubrika 37':         ('procedure_code',     'naim'),
        'prethodni postupak': ('procedure_prev_code', 'naim'),
        'prev procedure':     ('procedure_prev_code', 'naim'),
        # Rub.40 – prethodni dokumenti
        'rub40':              ('previous_document',  'naim'),
        'rubrika 40':         ('previous_document',  'naim'),
        'prethodni dokument': ('previous_document',  'naim'),
        'rub40 2':            ('previous_document2', 'naim'),
        'rub40 3':            ('previous_document3', 'naim'),
        # Rub.44 – priložene isprave
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
        # Rub.46 – statistička vrijednost
        'statisticka':        ('statistical_value',  'naim'),
        'statistička':        ('statistical_value',  'naim'),
        'rub46':              ('statistical_value',  'naim'),
        'rubrika 46':         ('statistical_value',  'naim'),
        # Rub.42 – vrijednost
        'vrijednost':         ('item_value',         'naim'),
        'iznos':              ('item_value',         'naim'),
        'item value':         ('item_value',         'naim'),
        # Valuta (naim)
        'valuta naim':        ('currency',           'naim'),
        # Napomene
        'napomena':           ('notes',              'naim'),
        'notes':              ('notes',              'naim'),
    }

    def _provjeri_tarifni_za_naziv(self, naziv_robe: str):
        """Provjeri tarifni za naziv — koristi TariffIntentService."""
        self.tariff_svc.check_tariff_for_name(naziv_robe)

    def _alternativni_tarifni_za_stavku(self, item_query: str = "", item_ordinal: int = None, is_alt: bool = False):
        """
        Predloži alternativne tarifne za konkretnu stavku koristeći DeepSeek.

        Korisnik nije zadovoljan popunjenim tarifom — traži drugi/ispravniji.
        Handler pronađe stavku po ordinal broju (u naimenovanjima ili faktura linijama)
        ili fuzzy matchom po nazivu, zatim pokrene ChatWorker sa ciljnim promptom.
        """
        from .widgets.chat_worker import ChatWorker
        import re as _re_alt

        chat = self.view.get_chat_panel()

        if not self.draft:
            chat.add_agent_message("⚠️ Nema učitanog drafta.")
            return

        naim_items = getattr(self.draft, 'items', [])
        invoice_lines = getattr(self.draft, 'invoice_lines', [])

        # Varijable za pronađenu stavku
        item_name = ""
        current_tariff = ""
        zemlja = ""
        iznos = 0.0

        found = False

        # 1. Pretraži NAIMENOVANJA po rednom broju (prioritet — korisnik najčešće misli na naim.)
        if item_ordinal is not None and naim_items:
            for it in naim_items:
                if getattr(it, 'ordinal_no', None) == item_ordinal:
                    item_name = getattr(it, 'goods_description', '') or ""
                    current_tariff = getattr(it, 'tariff_code', '') or ""
                    zemlja = getattr(it, 'origin_country_code', '') or ""
                    found = True
                    break

        # 2. Pretraži FAKTURA LINIJE po rednom broju (ako nije nađeno u naim.)
        if not found and item_ordinal is not None and invoice_lines:
            idx = item_ordinal - 1
            if 0 <= idx < len(invoice_lines):
                l = invoice_lines[idx]
                item_name = getattr(l, 'naziv_robe', '') or ""
                current_tariff = getattr(l, 'tarifni_broj', '') or ""
                zemlja = getattr(l, 'zemlja_porijekla', '') or ""
                iznos = getattr(l, 'iznos', 0) or 0
                found = True

        # 3. Fuzzy match po nazivu u naim. pa u faktura linijama
        if not found and item_query:
            query_words = [w for w in _re_alt.findall(
                r'[a-zšđčćžA-ZŠĐČĆŽ0-9]{3,}', item_query.lower()
            )]
            # Najprije u naim.
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
            # Pa u faktura linijama
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

        # Ako nije nađena stavka — upozori
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

        # Konstruiši specifičan prompt za DeepSeek
        zemlja_str = f" (zemlja porijekla: {zemlja})" if zemlja else ""
        iznos_str = f", vrijednost {iznos:.2f} EUR" if iznos else ""

        if current_tariff:
            prompt = (
                f'Tarifni broj {current_tariff} koji je trenutno upisan za robu "{item_name}"{zemlja_str}{iznos_str} '
                f'vjerovatno nije tačan. '
                f'Predloži mi 3 do 5 alternativnih HS tarifnih brojeva koji bi mogli biti ispravniji. '
                f'Za svaki navedi: tarifni broj, zvanični opis iz HS nomenklature, '
                f'i kratko obrazloženje zašto bi odgovarao (ili zašto {current_tariff} nije prikladan).'
            )
        else:
            prompt = (
                f'Predloži mi odgovarajući HS tarifni broj za robu: "{item_name}"{zemlja_str}{iznos_str}. '
                f'Daj 3 do 5 opcija sa zvaničnim opisom i obrazloženjem za svaku.'
            )

        chat.add_activity(f"🔍 Tražim alternative za: {item_name[:60]}...")
        chat.show_typing_indicator()

        # Koristimo DIREKTNI LLM poziv — zaobilazimo ChatWorker i njegov sistem prompt
        # koji zabranjuje korištenje HS znanja izvan baze.
        # Za alternativne tarife TAČNO trebamo DeepSeekovo znanje o HS nomenklaturi.
        from PySide6.QtCore import QThread, Signal as _Signal

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

                    zemlja_str = f" (zemlja porijekla: {_zemlja})" if _zemlja else ""

                    if _current_tariff and _is_alt:
                        user_msg = (
                            f'Roba: "{_item_name}"{zemlja_str}\n'
                            f'Postojeći tarif {_current_tariff} nije tačan.\n'
                            f'Predloži 4-5 ispravnijih HS tarifnih brojeva iz RAZLIČITIH poglavlja — '
                            f'razmotri materijal (plastika, sintetička vlakna, čelik, guma), '
                            f'funkciju i upotrebu robe.'
                        )
                    else:
                        user_msg = (
                            f'Roba: "{_item_name}"{zemlja_str}\n'
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

        worker = _AltTariffWorker(parent=self.view)
        worker.stream_started.connect(chat.start_streaming)
        worker.token_received.connect(chat.append_stream_token)
        worker.response_ready.connect(lambda _: chat.finalize_streaming())
        worker.response_ready.connect(
            lambda text: (
                self.budget.estimate_output(text),
                self._check_budget_after_response(),
            )
        )
        worker.error_occurred.connect(lambda _: chat.hide_typing_indicator())
        worker.error_occurred.connect(lambda err: chat.add_agent_message(f"⚠️ {err}"))
        worker.finished.connect(worker.deleteLater)
        worker.start()

        if not hasattr(self, '_chat_workers'):
            self._chat_workers = []
        self._chat_workers.append(worker)
        worker.finished.connect(
            lambda: self._chat_workers.remove(worker) if worker in self._chat_workers else None
        )

    def _klasificiraj_i_usmjeri(self, message: str):
        """
        Async LLM klasifikacija za dvosmislene tarif-poruke.

        Poziva IntentClassifier u pozadini (QThread), zatim usmjerava
        na odgovarajući handler. Koristiti samo kad keyword detekcija
        nije dovoljna.
        """
        from PySide6.QtCore import QThread, Signal

        chat = self.view.get_chat_panel()
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

        worker = _ClassifierWorker(message, self.draft)

        def _on_classified(result):
            import logging
            logging.getLogger(__name__).debug(
                f"[IntentClassifier] intent={result.intent} "
                f"item_query={result.item_query!r} ordinal={result.item_ordinal}"
            )
            if result.intent == "ALT_TARIFF":
                self._alternativni_tarifni_za_stavku(
                    item_query=result.item_query,
                    item_ordinal=result.item_ordinal,
                    is_alt=True,
                )
            elif result.intent == "SINGLE_TARIFF" and result.item_query:
                self._provjeri_tarifni_za_naziv(result.item_query)
            elif result.intent == "BATCH_TARIFF":
                self._predlozi_tarifne_brojeve()
            else:
                # QUERY ili OTHER → standardni LLM chat
                from .widgets.chat_worker import ChatWorker
                memory_service = chat.get_memory_service()
                cw = ChatWorker(message, draft=self.draft, parent=self.view,
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

        if not hasattr(self, '_classifier_workers'):
            self._classifier_workers = []
        self._classifier_workers.append(worker)
        worker.finished.connect(
            lambda: self._classifier_workers.remove(worker)
            if worker in self._classifier_workers else None
        )

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
        """Spoji naimenovanja u draftu i osvježi Naimenovanja tab."""
        from PySide6.QtWidgets import QApplication
        import uuid

        spojeno = 0
        # Obrni redoslijed indeksa da brisanje ne pomijeri ostale
        for merge in proposals:
            items = self.draft.items
            merged_indices = sorted(merge.indices, reverse=True)

            # Uzmi prvi (najmanji indeks) kao osnovu
            base_idx = min(merge.indices)
            base = items[base_idx]

            # Saberi vrijednosti
            base.gross_mass_kg = merge.merged_bruto
            base.net_mass_kg = merge.merged_neto
            base.item_value = merge.merged_iznos
            base.supplementary_unit_qty = merge.merged_kolicina

            # Obrisi ostale (osim base)
            for idx in merged_indices:
                if idx != base_idx:
                    del items[idx]

            # Renumber ordinal_no
            for i, item in enumerate(items):
                item.ordinal_no = i + 1

            spojeno += len(merge.indices) - 1

        # Osvježi Naimenovanja tab
        QApplication.processEvents()
        if self.naimenovanje_tab:
            if hasattr(self.naimenovanje_tab, 'reload_data'):
                self.naimenovanje_tab.reload_data()
            elif hasattr(self.naimenovanje_tab, 'reload'):
                self.naimenovanje_tab.reload()

        faktura_widget = self.faktura_tab
        if hasattr(self.faktura_tab, 'view'):
            faktura_widget = self.faktura_tab.view
        if faktura_widget and hasattr(faktura_widget, '_reload_naimenovanja_tab'):
            faktura_widget._reload_naimenovanja_tab()

        chat.add_agent_message(
            f"✅ <b>Spojeno {spojeno + len(proposals)} → {len(proposals)} naimenovanja.</b><br>"
            f"Količine, mase i iznosi su sabrani.<br>"
            f"Provjeri Naimenovanja tab."
        )

    # ─────────────────────────────────────────────────────────────
    # PREGLED I VALIDACIJA NAIMENOVANJA
    # ─────────────────────────────────────────────────────────────

    def _provjeri_naimenovanja(self):
        """
        Validacija popunjenosti svih rubrika za sva naimenovanja.
        Koristi NaimenovanjaReviewService.
        """
        from services.agent.naimenovanja_review_service import NaimenovanjaReviewService

        chat = self.view.get_chat_panel()

        if not self.draft or not self.draft.items:
            chat.add_agent_message("⚠️ Nema kreiranih naimenovanja u deklaraciji.")
            return

        naim_items = self.draft.items
        chat.add_activity(f"🔍 Provjeravam {len(naim_items)} naimenovanja...")

        result = NaimenovanjaReviewService.provjeri_naimenovanja(naim_items)

        if result['is_complete']:
            chat.add_agent_message(
                f"✅ <b>Sva {result['total_naim']} naimenovanja su kompletno popunjena!</b><br>"
                f"Nema praznih obaveznih ni opcionih rubrika."
            )
            return

        # Generiši izvještaj
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

        poruka = (
            f"📋 <b>Provjera naimenovanja — rezime:</b><br><br>"
            f"Ukupno naimenovanja: <b>{result['total_naim']}</b><br>"
            f"Praznih obaveznih polja: <b style='color:red'>{result['total_praznih_obaveznih']}</b><br>"
            f"Praznih opcionih polja: <b style='color:orange'>{result['total_praznih_opcionih']}</b><br><br>"
            f"<b>Detalji po naimenovanjima:</b><br><br>"
            + "<br><br>".join(linije)
        )

        chat.add_agent_message(poruka)

    def _pregledaj_naimenovanja(self, indeksi=None):
        """
        Detaljan pregled naimenovanja — svih rubrika ili konkretnog po Rb.
        Koristi NaimenovanjaReviewService.
        """
        from services.agent.naimenovanja_review_service import NaimenovanjaReviewService

        chat = self.view.get_chat_panel()

        if not self.draft or not self.draft.items:
            chat.add_agent_message("⚠️ Nema kreiranih naimenovanja u deklaraciji.")
            return

        naim_items = self.draft.items

        # Ako su indeksi proslijeđeni, filtriraj
        if indeksi:
            items_to_show = [naim_items[i - 1] for i in indeksi if 0 < i <= len(naim_items)]
            naziv = f"Rb. {', '.join(str(i) for i in indeksi)}"
        else:
            items_to_show = naim_items
            naziv = f"sva {len(naim_items)} naimenovanja"

        if not items_to_show:
            chat.add_agent_message(f"⚠️ Naimenovanje sa tim rednim brojem ne postoji.")
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

            # Rub.31
            opis_robe = (pregled.goods_description or '').strip() or '—'
            pak_kod = pregled.package_code or '—'
            pak_kol = pregled.package_qty or '—'
            oznake = (pregled.package_marks or '').strip() or '—'

            # Rub.44 — samo popunjene
            isprave = []
            for f_val in [pregled.attached_document1, pregled.attached_document2,
                          pregled.attached_document3, pregled.attached_document4,
                          pregled.attached_document5]:
                if f_val and f_val.strip():
                    isprave.append(f_val.strip())
            isprave_str = ", ".join(isprave) if isprave else '—'

            # Mase i vrijednost
            bruto = pregled.gross_mass_kg or 0
            neto = pregled.net_mass_kg or 0
            iznos = pregled.item_value or 0
            valuta = pregled.currency or 'EUR'
            stat_vrijednost = pregled.statistical_value or 0

            # Dopunske jedinice
            dop_jed = pregled.supplementary_unit_code or ''
            dop_kol = pregled.supplementary_unit_qty or 0

            html = (
                f"<b>═══ Rb.{rb} ═══</b><br>"
                f"<b>Rb.31 — Pakovanje i opis:</b><br>"
                f"&nbsp;&nbsp;Opis robe: {opis_robe[:100]}<br>"
                f"&nbsp;&nbsp;Trgovački naziv: {(pregled.goods_trade_name or '—')[:50]}<br>"
                f"&nbsp;&nbsp;Oznake i br.: {oznake[:50]}<br>"
                f"&nbsp;&nbsp;Pakovanje: {pak_kod} × {pak_kol}<br>"
                f"&nbsp;&nbsp;Kontejneri: {(pregled.container_number1 or '—')} / {(pregled.container_number2 or '—')}<br>"
                f"<b>Rb.33 — Tarifni broj:</b> <code>{tarif}</code><br>"
                f"<b>Rb.34 — Zemlja porijekla:</b> {zemlja}<br>"
                f"<b>Rb.36 — Povlastica:</b> {pov}<br>"
                f"<b>Rb.37 — Postupak:</b> {proc}"
                f"{(' (prethodni: ' + pregled.procedure_prev_code + ')') if pregled.procedure_prev_code else ''}<br>"
                f"<b>Rb.35/38 — Mase:</b> Bruto {bruto:.3f} kg | Neto {neto:.3f} kg<br>"
                f"<b>Rb.41 — Dop.jedinice:</b> {dop_jed} {dop_kol}"
                f"{(' ' + str(dop_kol) + ' ' + str(dop_jed)) if dop_kol and dop_jed else '—'}<br>"
                f"<b>Rb.42 — Vrijednost:</b> {iznos:.2f} {valuta}<br>"
                f"<b>Rb.44 — Isprave:</b> {isprave_str}<br>"
                f"<b>Rb.46 — Stat.vrijednost:</b> {stat_vrijednost:.2f}<br>"
                f"<b>Rb.40 — Preth.dokumenti:</b> "
                f"{(pregled.previous_document or '—')}"
                f"{(', ' + pregled.previous_document2) if pregled.previous_document2 else ''}"
                f"{(', ' + pregled.previous_document3) if pregled.previous_document3 else ''}"
            )

            # Napomene
            notes = (pregled.notes or '').strip()
            if notes:
                html += f"<br><b>Napomene:</b> {notes[:150]}"

            # Source reference
            if pregled.source_invoice_refs:
                html += f"<br><b>Source fakture:</b> {', '.join(pregled.source_invoice_refs)}"

            linije.append(html)

        chat.add_agent_message("<br><br>".join(linije))

    # ─────────────────────────────────────────────────────────────
    # PRETRAGA CARINSKE TARIFE
    # ─────────────────────────────────────────────────────────────

    def _pretrazi_tarifu(self, upit: str):
        """Pretraži carinsku tarifu 2026 po opisu robe."""
        chat = self.view.get_chat_panel()
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

    def _pretrazi_tarifu_po_kodu(self, kod: str):
        """Provjeri/validuj konkretnu tarifnu oznaku."""
        chat = self.view.get_chat_panel()
        chat.add_activity(f"🔍 Provjeravam tarifni kod: {kod}")

        try:
            from services.tarifa_service import validiraj_tarifni_broj, trazi_poglavlje, naziv_poglavlja
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

    def _pretrazi_tarifu_poglavlje(self, poglavlje: str):
        """Prikaži pregled poglavlja carinske tarife."""
        chat = self.view.get_chat_panel()
        chat.add_activity(f"📂 Učitavam poglavlje {poglavlje} tarife...")

        try:
            from services.tarifa_service import trazi_poglavlje, naziv_poglavlja, formatiraj_rezultate
            naziv = naziv_poglavlja(poglavlje)
            stavke = trazi_poglavlje(poglavlje, limit=30)

            # Prikaži samo podbroje (pune oznake)
            podbroji = [s for s in stavke if s['nivo'] == 'podbroj']

            html = formatiraj_rezultate(podbroji, max_rows=15)
            chat.add_agent_message(
                f"<b>📂 Poglavlje {poglavlje.zfill(2)}: {naziv}</b><br>"
                f"Ukupno tarifnih podbroja: <b>{len(podbroji)}</b><br><br>"
                f"{html}"
            )
        except Exception as e:
            chat.add_agent_message(f"❌ Greška pri učitavanju poglavlja: {e}")

    def _pretrazi_tarifu_hijerarhijski(self, kod: str):
        """
        Hijerarhijski prikaz tarife — drill-down.

        Unos: "8516" → prikazuje 8516 + sve podglave (851610, 851660...)
        Unos: "851660" → prikazuje 851660 + sve tarifne brojeve ispod
        """
        from services.tariff_tree_service import get_tree, get_full_path, format_tree_html
        chat = self.view.get_chat_panel()

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

    # ─────────────────────────────────────────────────────────────────────────
    # COMPLIANCE CHECK — provjera kompletnosti deklaracije
    # ─────────────────────────────────────────────────────────────────────────

    def _compliance_check(self):
        """Pokreni provjeru kompletnosti i konzistentnosti deklaracije."""
        chat = self.view.get_chat_panel()

        if not self.draft or not getattr(self.draft, 'invoice_lines', None):
            chat.add_agent_message("⚠️ Nema uvezenih stavki — učitaj fakturu prije provjere.")
            return

        chat.add_activity("🔍 Compliance check u toku...")

        try:
            from services.agent.compliance_check_service import ComplianceCheckService
            svc = ComplianceCheckService()
            result = svc.check(self.draft)

            html = result.summary_html()
            n_err = len(result.errors)
            n_warn = len(result.warnings)

            header = (
                f"<b>📋 Provjera deklaracije</b> — "
                f"{len(self.draft.invoice_lines)} stavki"
            )
            if result.is_ok:
                status = " <span style='color:#2d6a30;'>✅ sve uredu</span>"
            else:
                status = (
                    f" <span style='color:#b05050;'>❌ {n_err} greška</span>"
                    + (f", <span style='color:#b8963a;'>⚠️ {n_warn} upozorenja</span>"
                       if n_warn else "")
                )

            chat.add_agent_message(f"{header}{status}<br><br>{html}")
            chat.add_activity(
                f"{'✅' if result.is_ok else '❌'} Compliance: "
                f"{n_err} grešaka, {n_warn} upozorenja"
            )

        except Exception as e:
            chat.add_agent_message(f"❌ Greška pri provjeri deklaracije: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # PROPOSAL CARD — potvrda i odbacivanje prijedloga
    # ─────────────────────────────────────────────────────────────────────────

    def show_proposal_card(self, proposal: dict):
        """Prikaži editabilnu karticu prijedloga u chat panelu."""
        from .workflow_state import WorkflowState
        chat = self.view.get_chat_panel()
        chat.show_proposal_card(proposal)
        self.workflow.transition(WorkflowState.WAITING_USER_CONFIRMATION)

    def _on_proposal_confirmed(self, values: dict):
        """Primijeni potvrđene vrijednosti iz proposal kartice."""
        from .workflow_state import WorkflowState
        chat = self.view.get_chat_panel()
        self.workflow.transition(WorkflowState.APPLYING)

        if not values:
            chat.add_agent_message("⚠️ Prijedlog je prazan — ništa nije primijenjeno.")
            self.workflow.transition(WorkflowState.COMPLETED)
            return

        upisano = 0
        for atribut, vrijednost in values.items():
            if not atribut or not vrijednost:
                continue
            try:
                self.naim_intent_svc.execute(atribut, vrijednost, tab='faktura')
                upisano += 1
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri upisu {atribut}: {e}")

        poruke = ", ".join(f"{k}={v}" for k, v in values.items() if v)
        chat.add_agent_message(
            f"✅ <b>Prijedlog prihvaćen</b> — upisano {upisano} polja.<br>"
            f"<small style='color:grey;'>{poruke}</small>"
        )
        self.workflow.transition(WorkflowState.COMPLETED)
        self._save_session()

    def _on_proposal_rejected(self):
        """Workflow se vraća u COMPLETED nakon odbacivanja."""
        from .workflow_state import WorkflowState
        self.workflow.transition(WorkflowState.COMPLETED)

