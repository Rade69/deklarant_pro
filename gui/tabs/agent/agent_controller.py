"""
Agent Controller - business logic za tri pipeline moda.
"""

from PySide6.QtWidgets import QFileDialog
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

        # ── Service layer ──
        self._init_services()

        self._connect_signals()

    def _init_services(self):
        """Inicijalizuj service sloj sa callback-ovima."""
        from services.agent.tariff_intent_service import TariffIntentService
        from services.agent.merge_intent_service import MergeIntentService
        from services.agent.naimenovanja_intent_service import NaimenovanjaIntentService

        chat = self.view.get_chat_panel()
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

    def _on_mode_changed(self, mode: str):
        """Handle promjenu pipeline moda."""
        self._current_mode = mode
        self.view.get_chat_panel().add_activity(f"🔧 Režim: {mode}")

    def _on_files_added(self, filepaths: list):
        """Handle dodavanje novih fajlova u listu."""
        chat = self.view.get_chat_panel()
        chat.add_activity(f"✅ Dodato {len(filepaths)} fajlova")
        doc = self.view.get_document_panel()
        self.view.get_header().update_sesija(len(doc.get_files()))

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

        # ⭐ KLJUČNO: Prikupi samo stavke iz kombinovanih ILI samostalnih fajlova
        # Kad je PDF+Excel par (sortirano: Excel PRVI, PDF DRUGI):
        # - Excel (prvi): file_item.is_combined=False → PRESKOČI (sadržan u PDF-u)
        # - PDF (drugi): file_item.is_combined=True  → UZMI (kombinovani rezultat)

        all_lines = []
        total_bruto = 0.0
        total_neto = 0.0
        combined_files = []
        single_files = []

        for file_item in completed:
            if file_item.is_combined:
                combined_files.append(file_item)
                all_lines.extend(file_item.invoice_lines)
                total_bruto += file_item.bruto_kg
                total_neto += file_item.neto_kg
            else:
                single_files.append(file_item)

        # Standalone fajlovi koji NISU upareni sa kombinovanim → dodaj ih
        if combined_files:
            from services.import_service import _similar_invoice_number
            for f in single_files:
                # Preskači fajl ako mu je par već u combined_files (bez obzira na tip)
                is_consumed = any(
                    _similar_invoice_number(Path(f.filepath).stem, Path(c.filepath).stem)
                    for c in combined_files
                )
                if not is_consumed:
                    all_lines.extend(f.invoice_lines)
                    total_bruto += f.bruto_kg
                    total_neto += f.neto_kg
        else:
            # Nema kombinovanih - dodaj sve single fajlove (standalone import)
            for f in single_files:
                all_lines.extend(f.invoice_lines)
                total_bruto += f.bruto_kg
                total_neto += f.neto_kg

        # Agregatni has_origin_statement iz svih procesiranih fajlova
        has_origin_statement = any(getattr(f, 'has_origin_statement', False) for f in completed)

        print(f"[AgentController] Ukupno invoice_lines: {len(all_lines)}, draft: {self.draft is not None}")
        print(f"[AgentController] Kombinovani: {len(combined_files)}, Samostalni: {len(single_files)}")
        print(f"[AgentController] Ukupne težine: bruto={total_bruto:.3f}kg, neto={total_neto:.3f}kg")
        print(f"[AgentController] has_origin_statement={has_origin_statement}")
        chat.add_activity(f"📊 Ukupno stavki: {len(all_lines)}, mode: {self._current_mode}")

        # Mode 1: Analiza - samo prikaži rezultate
        if self._current_mode == "Analiza":
            chat.add_agent_message(
                f"✅ <b>Analiza završena!</b><br>"
                f"Pronađeno <b>{len(all_lines)}</b> stavki iz {len(completed)} fajlova.<br>"
                f"Kliknite na fajl za pregled rezultata."
            )
            return

        # Mode 2 i 3: Uvezi u deklaraciju
        self._uvezi_u_deklaraciju(all_lines, chat, total_bruto, total_neto, has_origin_statement)

        # Mode 3: Puna automatizacija - XML template + export
        if self._current_mode == "Puna automatizacija":
            self._primjeni_xml_template(all_lines, chat)
            self._izvezi_xml(chat)

    def _get_preference_by_country(self, country_code: str) -> str:
        """Vrati šifru povlastice na osnovu koda zemlje porijekla."""
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
                              has_origin_statement: bool = False):
        """
        Uvezi invoice_lines u draft i kreiraj naimenovanja.

        Args:
            invoice_lines: Lista InvoiceLine stavki
            chat: ChatPanel za logging
            total_bruto: Ukupna bruto težina iz ImportResult (ne iz linija!)
            total_neto: Ukupna neto težina iz ImportResult (ne iz linija!)
        """
        print(f"[AgentController] _uvezi_u_deklaraciju: {len(invoice_lines)} stavki, bruto={total_bruto:.3f}kg, neto={total_neto:.3f}kg")
        
        if not self.draft:
            chat.add_activity("⚠️ Draft nije dostupan - ne mogu uvesti u deklaraciju")
            return

        # 0. ⭐ NOVO: Validacija PRIJE uvoza
        chat.add_activity("🔍 Validacija prije uvoza...")
        valid, greške = self._validiraj_prije_uvoza(invoice_lines, chat)
        
        if not valid:
            chat.add_agent_message(
                f"❌ <b>Validacija nije uspješna!</b><br><br>"
                f"Detalji:<br>"
                f"{'<br>'.join(greške)}<br><br>"
                f"Uvoz je obustavljen. Ispravi greške i pokušaj ponovo."
            )
            return

        # 1a. ⭐ AUTO-HANDLE POVLASTICE (prije uvoza u draft)
        chat.add_activity("🌍 Auto-postavljanje povlastica...")
        self._auto_handle_povlastice(invoice_lines, chat, has_origin_statement)

        # 1b. ⭐ SAMO UVEZI PODATKE (ne traži tarifne još!)
        chat.add_activity(f"📥 Uvoz {len(invoice_lines)} stavki...")
        self.draft.invoice_lines.clear()
        self.draft.invoice_lines.extend(invoice_lines)
        
        print(f"[AgentController] Draft sada ima {len(self.draft.invoice_lines)} stavki")
        chat.add_activity(f"✅ Uvezeno {len(invoice_lines)} stavki")

        # 2. ⭐ PAUZA DA SE UI OSVJEŽI (bitno za Qt!)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        # 3. ⭐ OTVORI FAKTURA TAB (prije bilo kakve obrade!)
        # Postavi agent_mode=True da se spriječe blokirajući GUI dijalozi
        faktura_view = self.faktura_tab
        if hasattr(self.faktura_tab, 'view'):
            faktura_view = self.faktura_tab.view
        if faktura_view and hasattr(faktura_view, 'set_agent_mode'):
            faktura_view.set_agent_mode(True)
            chat.add_activity("🤖 Faktura tab: agent mod aktivan (bez dijaloga)")

        self._otvori_faktura_tab_nakon_uvoza(chat)

        # 4. ⭐ POZOVII POSTOJEĆU LOGIKU IZ FAKTURA TABA
        # Ovo je ISTO što bi korisnik uradio ručno:
        # - Klikne "Auto-popuni tarifne"
        # - Klikne "Izračunaj mase"
        
        # Nađi pravi widget (FakturaView unutar FakturaTabRefactored)
        faktura_widget = self.faktura_tab
        if hasattr(self.faktura_tab, 'view'):
            faktura_widget = self.faktura_tab.view  # FakturaView
        
        if faktura_widget:
            # ⭐ PRVO: Postavi težine u toolbar iz ImportResult (proslijeđene od _on_all_completed)
            # NIKAD ne računaj iz invoice_lines — PDF stavke često imaju neto_kg=0 per liniji!
            if total_bruto > 0 or total_neto > 0:
                if hasattr(faktura_widget, 'input_bruto') and hasattr(faktura_widget, 'input_neto'):
                    faktura_widget.input_bruto.setText(f"{total_bruto:,.3f}")
                    faktura_widget.input_neto.setText(f"{total_neto:,.3f}")
                    chat.add_activity(f"⚖️ Težine postavljene: Bruto={total_bruto:.2f}kg, Neto={total_neto:.2f}kg")
            
            chat.add_activity("🤖 Pokrećem auto-popunu tarifnih brojeva...")
            try:
                # Koristi AutoFillService (isti kao "Auto-popuni" dugme)
                from services.faktura.auto_fill_service import AutoFillService
                auto_fill = AutoFillService()
                
                # Popuni tarifne brojeve (Mapping Service - brzo!)
                result = auto_fill.fill_tariff_numbers(
                    self.draft.invoice_lines,
                    min_similarity=0.92
                )
                
                chat.add_activity(
                    f"✅ Auto-popuna završena:<br>"
                    f"  • Pronađeno: {result['matched']}<br>"
                    f"  • Nije nađeno: {result['unmatched']}<br>"
                    f"  • Preskočeno: {result['skipped']}"
                )
                
                # Refresh tabele
                if hasattr(faktura_widget, '_load_data_from_draft'):
                    faktura_widget._load_data_from_draft()
                
            except Exception as e:
                import traceback
                print(f"[AgentController] Auto-fill greška: {e}")
                print(traceback.format_exc())
                chat.add_activity(f"⚠️ Greška pri auto-popuni: {e}")

            chat.add_activity("🤖 Izračunavam mase...")
            try:
                # Koristi MassCalculator (isti kao "Izračunaj mase" dugme)
                from services.faktura.mass_calculator import MassCalculator
                mass_calc = MassCalculator()
                
                # Uzmi težine iz toolbar input polja
                bruto_total = 0.0
                neto_total = 0.0
                
                if hasattr(faktura_widget, 'input_bruto') and hasattr(faktura_widget, 'input_neto'):
                    bruto_text = faktura_widget.input_bruto.text().strip()
                    neto_text = faktura_widget.input_neto.text().strip()
                    
                    try:
                        bruto_total = float(bruto_text.replace(",", "") or "0")
                        neto_total = float(neto_text.replace(",", "") or "0")
                    except:
                        pass
                
                if bruto_total > 0 or neto_total > 0:
                    # Izračunaj mase
                    result = mass_calc.calculate_masses(
                        self.draft.invoice_lines,
                        bruto_total,
                        neto_total
                    )
                    
                    chat.add_activity(
                        f"✅ Mase izračunate:<br>"
                        f"  • Ažurirano: {result['updated']} stavki<br>"
                        f"  • Preskočeno: {result['skipped']} stavki"
                    )
                else:
                    chat.add_activity("ℹ️ Nema težina za izračun (bruto=0, neto=0)")
                
                # Konačni refresh
                if hasattr(faktura_widget, '_load_data_from_draft'):
                    faktura_widget._load_data_from_draft()
                
            except Exception as e:
                import traceback
                print(f"[AgentController] Mass calculator greška: {e}")
                print(traceback.format_exc())
                chat.add_activity(f"⚠️ Greška pri izračunu masa: {e}")

        # 5. ⭐ EUR1 DIALOG — mora biti PRIJE kreiranja naimenovanja!
        # Naimenovanja se kreiraju iz invoice_lines, pa eur1_number mora biti postavljen
        # na stavkama PRIJE create_smart_group().
        eur1_primijenjen = False
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
            try:
                from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog
                dialog = Eur1QuickDialog(self.draft.invoice_lines, self.view)
                result_dlg = dialog.exec()

                if result_dlg == 1:
                    eur1_data = dialog.get_data()
                    if eur1_data:
                        updated_count = Eur1QuickDialog.apply_eur1_data(
                            self.draft.invoice_lines, eur1_data
                        )
                        chat.add_activity(f"✅ EUR.1 primijenjen na {updated_count} stavki")
                        eur1_primijenjen = True
                        # Refresh faktura tabele da se vide EUR1 brojevi
                        faktura_widget = self.faktura_tab
                        if hasattr(self.faktura_tab, 'view'):
                            faktura_widget = self.faktura_tab.view
                        if hasattr(faktura_widget, '_load_data_from_draft'):
                            faktura_widget._load_data_from_draft()
                else:
                    chat.add_activity("ℹ️ EUR.1 dialog preskočen — unesi broj ručno u Faktura tabu")
            except Exception as e:
                chat.add_activity(f"⚠️ EUR.1 dialog greška: {e}")

        # 6. Kreiraj naimenovanja (NAKON EUR1 — da budu uključeni u Rub.44.4)
        try:
            from services.create_naimenovanja_service import CreateNaimenovanjaService
            service = CreateNaimenovanjaService(self.draft)
            count = service.create_smart_group()
            chat.add_activity(f"✅ Kreirano {count} naimenovanja")

            # Osvježi Faktura tab — isti redoslijed kao ručni unos (_on_create_naimenovanja)
            faktura_widget = self.faktura_tab
            if hasattr(self.faktura_tab, 'view'):
                faktura_widget = self.faktura_tab.view
            if faktura_widget:
                # 1. Ponovo učitaj tabelu — popunjava kolonu "Naimenov"
                if hasattr(faktura_widget, '_load_data_from_draft'):
                    faktura_widget._load_data_from_draft()
                # 2. Osvježi Naimenovanja tab (i Zaglavlje Rb.6)
                if hasattr(faktura_widget, '_reload_naimenovanja_tab'):
                    faktura_widget._reload_naimenovanja_tab()
                elif self.naimenovanje_tab:
                    try:
                        if hasattr(self.naimenovanje_tab, 'reload_data'):
                            self.naimenovanje_tab.reload_data()
                        elif hasattr(self.naimenovanje_tab, 'reload'):
                            self.naimenovanje_tab.reload()
                    except Exception as e:
                        chat.add_activity(f"⚠️ Greška pri osvježavanju naimenovanja taba: {e}")
            chat.add_activity("✅ Faktura i Naimenovanja tab osvježeni")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri kreiranju naimenovanja: {e}")

        # 7. ⭐ Auto-popuni Rb.22 valuta iz naimenovanja/fakture
        try:
            if not self.draft.valuta and self.draft.items:
                self.draft.valuta = self.draft.items[0].currency or "EUR"
            if not self.draft.iznos and self.draft.items:
                self.draft.iznos = sum(item.item_value or 0.0 for item in self.draft.items)
            if self.draft.valuta:
                chat.add_activity(
                    f"✅ Rb.22: valuta={self.draft.valuta}, iznos={self.draft.iznos:,.2f}"
                )
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri popuni Rb.22: {e}")

        # 8. ⭐ Resetuj agent_mode (korisnik može ručno importovati poslije)
        if faktura_view and hasattr(faktura_view, 'set_agent_mode'):
            faktura_view.set_agent_mode(False)

        # 8. ⭐ Generiši izvještaj sa analizom
        self._generisi_izvjestaj(chat)

        eur1_poruka = (
            f"<br>⚠️ <b>{len(eur1_pending_lines)} stavki čeka ručni unos EUR1 broja</b> "
            f"(povlastica postavljena automatski)."
            if eur1_pending_lines and not eur1_primijenjen
            else ""
        )

        chat.add_agent_message(
            f"✅ <b>Uvoz završen!</b><br>"
            f"Uvezeno <b>{len(invoice_lines)}</b> stavki.<br>"
            f"Tarifni brojevi i mase automatski popunjeni.<br>"
            f"Povlastice auto-postavljene po zemlji porijekla."
            f"{eur1_poruka}<br>"
            f"Provjeri Faktura i Naimenovanja tabove."
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

    def _primjeni_xml_template(self, all_lines: list, chat):
        """
        Korak za Puna automatizacija:
        Pronađi stari XML sa istim pošiljaocem i primijeni whitelist polja na draft zaglavlje.

        Pokušava naći pošiljaoca iz:
        1. InvoiceLine.exporter.name (ako importer popunjava)
        2. import_type iz ProcessingWorker file_item-a
        3. Naziva fajla (npr. "pekabesko-123.xlsx")
        """
        if not self.draft:
            return

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
            return

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
            chat.add_activity("ℹ️ Nije nađen odgovarajući XML template — popuni zaglavlje ručno")
            return

        # ── Primijeni template na draft ──────────────────────────
        applied = svc.apply_to_draft(self.draft, match.fields)

        if not applied:
            chat.add_activity("ℹ️ Sva zaglavlje polja već popunjena — template nije primijenjen")
            return

        chat.add_activity(f"✅ Primijenjeno {len(applied)} zaglavlje polja iz templatea")

        # ── Pokušaj osvježiti Zaglavlje tab ─────────────────────
        if self.zaglavlje_tab:
            try:
                if hasattr(self.zaglavlje_tab, 'reload_data'):
                    self.zaglavlje_tab.reload_data()
                elif hasattr(self.zaglavlje_tab, 'load_from_draft'):
                    self.zaglavlje_tab.load_from_draft()
                elif hasattr(self.zaglavlje_tab, 'refresh'):
                    self.zaglavlje_tab.refresh()
                chat.add_activity("✅ Zaglavlje tab osvježen")
            except Exception as e:
                chat.add_activity(f"⚠️ Greška pri osvježavanju Zaglavlje taba: {e}")

        # ── Prikaži dijalog sa rezimeom ──────────────────────────
        try:
            from gui.dialogs.zaglavlje_template_dialog import ZaglavljeTemplateDialog
            dialog = ZaglavljeTemplateDialog(match, applied, parent=self.view)
            result = dialog.exec()
            if result != 1:
                # Korisnik odbacio — resetuj primjenjena polja
                for field_name in applied:
                    try:
                        setattr(self.draft, field_name, "")
                    except Exception:
                        pass
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
        chat = self.view.get_chat_panel()
        filename = Path(filepath).name
        chat.add_activity(f"❌ Greška [{filename}]: {message}")

    def _on_clear_requested(self):
        """Očisti listu fajlova i otkaži worker ako radi."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self.view.get_chat_panel().add_activity("🗑️ Lista fajlova očišćena")
        self.view.get_header().update_sesija(0)

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

        # --- DETEKCIJA NAMJERE: provjera tarifnog za konkretan naziv robe ---
        # Format: "provjeri tarifni za X", "testiraj tarif za X", "koji je tarif za X"
        _provjeri_tarif_match = _re.search(
            r'(?:provjeri|testiraj|predloži|predlozi|traži|trazi|koji\s+je|kakav\s+je)\s+'
            r'tarif\w*\s+za\s+(.+)',
            msg
        )
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

        # --- DETEKCIJA NAMJERE: brisanje tarifnih brojeva (MORA BITI ISPRED popune!) ---
        # Provjera: prisutan glagol brisanja I "tarif" u poruci
        _brisanje_glagoli = ['izbri', 'obri', 'ukloni', 'resetuj', 'ocisti', 'očisti',
                             'brisi', 'briši', 'delete', 'clear', 'prazni', 'isprazni']
        _has_brisanje = any(g in msg for g in _brisanje_glagoli)
        _has_tarif = 'tarif' in msg
        if _has_brisanje and _has_tarif:
            self._obrisi_tarifne_brojeve()
            return

        # Eksplicitni batch zahtjev (popuni sve / nađi sve bez)
        _generalni_tarif_kw = ['popuni tarif', 'nađi sve bez tarif', 'nađi stavke bez tarif',
                                'predloži sve tarif', 'predlozi sve tarif',
                                'auto tarif', 'batch tarif']

        if any(kw in msg for kw in _generalni_tarif_kw):
            # Batch: traži sve bez tarifnog broja
            self._predlozi_tarifne_brojeve()
            return
        elif _is_query and any(kw in msg for kw in ['tarif', 'tarifn', 'naim', 'stavk']):
            # Informativni upit o tarifi/naimenovanju → LLM
            pass
        elif any(kw in msg for kw in ['tarif', 'tarifn']) and not _has_specific_items and not _is_query:
            # Generalni "tarife" bez konteksta → batch prijedlog
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

    # ─────────────────────────────────────────────────────────────────────────
    # AGENT AKCIJE — prijedlog + potvrda + izvršavanje
    # ─────────────────────────────────────────────────────────────────────────

    def _predlozi_tarifne_brojeve(self):
        """Analizira stavke bez tarifnog broja — lokalna baza pa LLM fallback."""
        from .agent_actions import TariffProposal, PendingAction
        from services.tariff_mapping_service import TariffMappingService
        from .widgets.tariff_llm_worker import TariffLLMWorker

        chat = self.view.get_chat_panel()

        if not self.draft or not self.draft.invoice_lines:
            chat.add_agent_message("⚠️ Nema učitanih stavki u Faktura tabu.")
            return

        bez_tarife = [
            (i, line) for i, line in enumerate(self.draft.invoice_lines)
            if not line.tarifni_broj or not line.tarifni_broj.strip()
        ]

        if not bez_tarife:
            chat.add_agent_message("✅ Sve stavke već imaju upisane tarifne brojeve.")
            return

        chat.add_activity(f"🔍 Tražim u lokalnoj bazi za {len(bez_tarife)} stavki...")

        # 1. Pokušaj lokalnu bazu znanja
        svc = TariffMappingService()
        proposals = []
        bez_lokalne = []

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

        if bez_lokalne:
            chat.add_activity(
                f"✅ Lokalna baza: {len(proposals)} prijedloga. "
                f"🤖 Pitam AI za preostalih {len(bez_lokalne)} stavki..."
            )
            # 2. LLM fallback u pozadini
            worker = TariffLLMWorker(bez_lokalne, parent=self.view)
            worker.proposals_ready.connect(
                lambda llm_proposals: self._on_tariff_llm_ready(proposals, llm_proposals, len(bez_tarife), chat)
            )
            worker.error_occurred.connect(
                lambda err: self._on_tariff_llm_ready(proposals, [], len(bez_tarife), chat)
            )
            worker.finished.connect(worker.deleteLater)
            if not hasattr(self, '_tariff_workers'):
                self._tariff_workers = []
            self._tariff_workers.append(worker)
            worker.finished.connect(
                lambda: self._tariff_workers.remove(worker) if worker in self._tariff_workers else None
            )
            worker.start()
        else:
            self._on_tariff_llm_ready(proposals, [], len(bez_tarife), chat)

    def _predlozi_tarifne_po_filteru(self, keyword: str):
        """Predlaže tarifne brojeve samo za stavke čiji naziv_robe sadrži keyword."""
        from .agent_actions import TariffProposal
        from services.tariff_mapping_service import TariffMappingService
        from .widgets.tariff_llm_worker import TariffLLMWorker

        chat = self.view.get_chat_panel()

        if not self.draft or not self.draft.invoice_lines:
            chat.add_agent_message("⚠️ Nema učitanih stavki u Faktura tabu.")
            return

        kw = keyword.lower().strip()

        # Filtriraj po ključnoj riječi u nazivu
        filtrirane = [
            (i, line) for i, line in enumerate(self.draft.invoice_lines)
            if kw in (getattr(line, 'naziv_robe', '') or '').lower()
        ]

        if not filtrirane:
            chat.add_agent_message(f"⚠️ Nema stavki čiji naziv sadrži '{keyword}'.")
            return

        chat.add_activity(f"🔍 Nađeno {len(filtrirane)} stavki s '{keyword}', tražim tarifne...")

        # Lokalna baza znanja
        svc = TariffMappingService()
        proposals = []
        bez_lokalne = []

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

        if bez_lokalne:
            chat.add_activity(
                f"✅ Lokalna baza: {len(proposals)}. "
                f"🤖 AI za preostalih {len(bez_lokalne)}..."
            )
            worker = TariffLLMWorker(bez_lokalne, parent=self.view)
            worker.proposals_ready.connect(
                lambda llm_p: self._on_tariff_llm_ready(proposals, llm_p, len(filtrirane), chat)
            )
            worker.error_occurred.connect(
                lambda err: self._on_tariff_llm_ready(proposals, [], len(filtrirane), chat)
            )
            worker.finished.connect(worker.deleteLater)
            if not hasattr(self, '_tariff_workers'):
                self._tariff_workers = []
            self._tariff_workers.append(worker)
            worker.finished.connect(
                lambda: self._tariff_workers.remove(worker) if worker in self._tariff_workers else None
            )
            worker.start()
        else:
            self._on_tariff_llm_ready(proposals, [], len(filtrirane), chat)

    def _on_tariff_llm_ready(self, local_proposals, llm_proposals, ukupno_bez, chat):
        """Prikaži kombinirane prijedloge (lokalni + LLM) korisniku."""
        from .agent_actions import PendingAction

        svi = local_proposals + llm_proposals

        if not svi:
            chat.add_agent_message(
                f"⚠️ Nisam uspio naći prijedloge za <b>{ukupno_bez}</b> stavki "
                f"ni u lokalnoj bazi ni putem AI-a.<br>"
                f"Pokušaj pretraživanjem tarifne tarife ili ručnim unosom."
            )
            return

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

        self._pending_action = PendingAction(
            action_type="fill_tariff",
            proposals=svi,
            description=f"Upiši {len(svi)} tarifnih brojeva"
        )

        chat.add_agent_message(
            f"📋 Prijedlozi za <b>{len(svi)}</b> od {ukupno_bez} stavki:<br><br>"
            + "<br>".join(linije)
            + napomena
            + "<br><br>✏️ <b>Upisujem u tabelu? Odgovori: Da / Ne</b>"
        )

    def _predlozi_spajanje_naimenovanja(self):
        """Pronalazi naimenovanja sa istim tarifnim brojem i predlaže spajanje."""
        from .agent_actions import NaimenovanjaSpajanje, PendingAction
        from collections import defaultdict

        chat = self.view.get_chat_panel()

        if not self.draft or not self.draft.items:
            chat.add_agent_message("⚠️ Nema naimenovanja u deklaraciji.")
            return

        chat.add_activity("🔍 Analiziram naimenovanja...")

        # Grupiši po tarifnom broju + zemlja + povlastica
        grupe = defaultdict(list)
        for i, item in enumerate(self.draft.items):
            kljuc = (
                item.tariff_code.strip(),
                item.origin_country_code.strip(),
                item.preference_code.strip()
            )
            grupe[kljuc].append((i, item))

        # Pronađi grupe sa 2+ naimenovanja
        kandidati = [(k, v) for k, v in grupe.items() if len(v) >= 2]

        if not kandidati:
            chat.add_agent_message("✅ Nema naimenovanja sa istim tarifnim brojem koja bi se mogla spojiti.")
            return

        proposals = []
        linije = []

        for (tariff, zemlja, pov), stavke in kandidati:
            indices = [i for i, _ in stavke]
            items = [item for _, item in stavke]

            merged_kolicina = sum(it.supplementary_unit_qty or 0 for it in items)
            merged_bruto = sum(it.gross_mass_kg or 0 for it in items)
            merged_neto = sum(it.net_mass_kg or 0 for it in items)
            merged_iznos = sum(it.item_value or 0 for it in items)

            # Naziv: najduži goods_description ili kombinacija
            merged_naziv = max(
                (it.goods_description for it in items),
                key=len,
                default=""
            )

            proposals.append(NaimenovanjaSpajanje(
                indices=indices,
                tariff_code=tariff,
                merged_naziv=merged_naziv,
                merged_kolicina=merged_kolicina,
                merged_bruto=round(merged_bruto, 3),
                merged_neto=round(merged_neto, 3),
                merged_iznos=round(merged_iznos, 2)
            ))

            nazivi = " + ".join(
                (it.goods_description[:30] for it in items)
            )
            linije.append(
                f"&nbsp;&nbsp;• Tarifa <b>{tariff}</b> ({zemlja}) — "
                f"{len(stavke)} naim. → spoji:<br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;Kol: {merged_kolicina:.2f} | "
                f"Bruto: {merged_bruto:.3f}kg | Neto: {merged_neto:.3f}kg | "
                f"Iznos: {merged_iznos:.2f}<br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;<small>{nazivi}</small>"
            )

        self._pending_action = PendingAction(
            action_type="merge_naimenovanja",
            proposals=proposals,
            description=f"Spoji {sum(len(p.indices) for p in proposals)} naimenovanja u {len(proposals)}"
        )

        chat.add_agent_message(
            f"📋 Pronašao sam <b>{len(kandidati)}</b> grupu(e) za spajanje:<br><br>"
            + "<br><br>".join(linije)
            + "<br><br>🔀 <b>Spajam naimenovanja? Odgovori: Da / Ne</b>"
        )

    def _execute_pending_action(self):
        """Izvrši pending akciju nakon potvrde korisnika."""
        from PySide6.QtWidgets import QApplication

        chat = self.view.get_chat_panel()
        action = self._pending_action
        self._pending_action = None

        if action.action_type == "fill_tariff":
            self._izvrsi_popunu_tarife(action.proposals, chat)

        elif action.action_type == "merge_naimenovanja":
            self._izvrsi_spajanje_naimenovanja(action.proposals, chat)

    def _izvrsi_popunu_tarife(self, proposals, chat):
        """Upiši predložene tarifne brojeve u draft i osvježi Faktura tab."""
        from PySide6.QtWidgets import QApplication

        upisano = 0
        for p in proposals:
            line = self.draft.invoice_lines[p.line_index]
            line.tarifni_broj = p.proposed_tariff
            upisano += 1

        # Osvježi Faktura tab
        faktura_widget = self.faktura_tab
        if hasattr(self.faktura_tab, 'view'):
            faktura_widget = self.faktura_tab.view
        if faktura_widget and hasattr(faktura_widget, '_load_data_from_draft'):
            QApplication.processEvents()
            faktura_widget._load_data_from_draft()

        chat.add_agent_message(
            f"✅ <b>Upisano {upisano} tarifnih brojeva</b> u Faktura tab.<br>"
            f"Provjeri tabelu i korigiši ako je potrebno."
        )

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

    def _parse_upis_u_kolonu(self, message: str, brisanje: bool = False):
        """
        Pokušava parsirati poruku u (atribut, vrijednost, tab).

        Podržani formati:
        - "upiši EUP u kolonu povlastica"
        - "upiši EUP u rubriku povlastica naim"
        - "postavi povlasticu na EUP"
        - "upiši 4000 u proceduru u naim"
        - "obriši kolonu povlastica u naim"

        Returns: (atribut, vrijednost, tab) ili None
        """
        import re as _re
        msg_lower = message.lower().strip()

        # Detektuj eksplicitni tab hint
        tab_hint = None
        if any(k in msg_lower for k in ['naim', 'naimenovanj', 'rubrik']):
            tab_hint = 'naim'
        elif any(k in msg_lower for k in ['faktur', 'invoice']):
            tab_hint = 'faktura'

        if brisanje:
            # Format brisanje: "obriši kolonu KOLONA [u naim]"
            m = _re.search(r'(?:izbri|obri|ukloni|ocisti|prazni|brisi)[a-zšđčćž]*\s+(?:kolonu?|polje|rubrik[ua]?)?\s*(.+)',
                           msg_lower)
            if m:
                kolona_raw = m.group(1).strip().rstrip('.')
                # Ukloni tab hint iz kolona_raw
                for hint in ['u naim', 'u faktur', 'naim', 'faktur']:
                    kolona_raw = kolona_raw.replace(hint, '').strip()
                atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
                if atribut:
                    return atribut, '', tab
            return None

        def _strip_tab_hints(s):
            for hint in [' u naim', ' u faktur', ' naim', ' faktur']:
                s = s.replace(hint, '')
            return s.strip().rstrip('.')

        # Format 1: "upiši/unesi/stavi VRIJEDNOST u [kolonu/polje/rubriku] KOLONA"
        # Vrijednost može biti višeznačna (npr. "PE1 000123/2025") — hvata sve do " u "
        m = _re.search(
            r'(?:upi[sš][a-zšđčćž]*|unesi[a-z]*|stavi[a-z]*|set)\s+(.+?)\s+u\s+(?:kolonu?|polje|rubriku?)?\s*(.+)',
            msg_lower
        )
        if m:
            vrijednost = m.group(1).strip().upper()
            kolona_raw = _strip_tab_hints(m.group(2))
            atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
            if atribut:
                return atribut, vrijednost, tab

        # Format 2: "postavi KOLONA na VRIJEDNOST"
        m = _re.search(r'postavi\s+(.+?)\s+na\s+(\S+)', msg_lower)
        if m:
            kolona_raw = _strip_tab_hints(m.group(1))
            vrijednost = m.group(2).strip().upper()
            # Ukloni padežne nastavke sa kraja kolone: povlasticu→povlastica, proceduru→procedura
            kolona_raw = _re.sub(r'[uaie]$', 'a', kolona_raw)
            atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
            if atribut:
                return atribut, vrijednost, tab

        # Format 3: "VRIJEDNOST u kolonu/rubriku KOLONA"
        m = _re.search(r'(\S+)\s+u\s+(?:kolonu?|polje|rubriku?)\s+(.+)', msg_lower)
        if m:
            vrijednost = m.group(1).strip().upper()
            kolona_raw = _strip_tab_hints(m.group(2))
            atribut, tab = self._resolve_kolona(kolona_raw, tab_hint)
            if atribut:
                return atribut, vrijednost, tab

        return None

    def _resolve_kolona(self, kolona_raw: str, tab_hint=None):
        """Pretvori slobodan naziv kolone u (atribut, tab)."""
        k = kolona_raw.lower().strip()
        # Direktni match
        if k in self._KOLONA_MAP:
            atrib, tab = self._KOLONA_MAP[k]
            return atrib, tab_hint or tab
        # Parcijalni match
        for kw, (atrib, tab) in self._KOLONA_MAP.items():
            if kw in k or k in kw:
                return atrib, tab_hint or tab
        return '', tab_hint or 'faktura'

    def _upisi_u_kolonu(self, atribut: str, vrijednost: str, tab: str = 'faktura'):
        """Upiši vrijednost u zadani atribut svih stavki u odgovarajućem tabu."""
        from PySide6.QtWidgets import QApplication

        chat = self.view.get_chat_panel()

        naziv_kolone = {
            # Faktura
            'tarifni_broj': 'Tarifni broj', 'zemlja_porijekla': 'Zemlja porijekla',
            'povlastica': 'Povlastica', 'eur1_number': 'EUR.1', 'valuta': 'Valuta',
            'naziv_robe': 'Naziv robe', 'kolicina': 'Količina', 'jm': 'JM',
            # Naim
            'tariff_code': 'Tarifni broj', 'origin_country_code': 'Zemlja porijekla',
            'preference_code': 'Povlastica', 'procedure_code': 'Rub.37 Procedura',
            'procedure_prev_code': 'Prethodni postupak', 'currency': 'Valuta',
            'package_code': 'Pakovanje (kod)', 'package_marks': 'Oznake i broj',
            'package_qty': 'Broj paketa', 'goods_description': 'Opis robe',
            'goods_trade_name': 'Trgovački naziv',
            'previous_document': 'Rub.40', 'previous_document2': 'Rub.40.2',
            'previous_document3': 'Rub.40.3',
            'attached_document1': 'Rub.44.1', 'attached_document2': 'Rub.44.2',
            'attached_document3': 'Rub.44.3', 'attached_document4': 'Rub.44.4',
            'attached_document5': 'Rub.44.5',
            'statistical_value': 'Statistička vrijednost (Rub.46)',
            'item_value': 'Vrijednost (Rub.42)', 'notes': 'Napomena',
        }.get(atribut, atribut)

        from typing import Any
        # Konvertuj vrijednost u odgovarajući tip (float polja)
        _float_attrs = {
            'kolicina', 'bruto_kg', 'neto_kg', 'iznos',
            'gross_mass_kg', 'net_mass_kg', 'item_value', 'statistical_value',
            'package_qty', 'supplementary_unit_qty',
        }
        typed_value: Any = vrijednost
        if atribut in _float_attrs:
            try:
                typed_value = float(vrijednost.replace(',', '.')) if vrijednost else 0.0
            except (ValueError, AttributeError):
                chat.add_agent_message(f"⚠️ '{vrijednost}' nije broj. Upotrijebite numeričku vrijednost.")
                return

        if tab == 'faktura':
            if not self.draft or not self.draft.invoice_lines:
                chat.add_agent_message("⚠️ Nema učitanih stavki u Faktura tabu.")
                return
            upisano = sum(
                1 for line in self.draft.invoice_lines
                if hasattr(line, atribut) and not setattr(line, atribut, typed_value)
            )
            faktura_widget = self.faktura_tab
            if hasattr(self.faktura_tab, 'view'):
                faktura_widget = self.faktura_tab.view
            if faktura_widget and hasattr(faktura_widget, '_load_data_from_draft'):
                QApplication.processEvents()
                faktura_widget._load_data_from_draft()
        else:  # naim
            if not self.draft or not self.draft.items:
                chat.add_agent_message("⚠️ Nema kreiranih naimenovanja.")
                return
            upisano = sum(
                1 for item in self.draft.items
                if hasattr(item, atribut) and not setattr(item, atribut, typed_value)
            )
            if self.naimenovanje_tab and hasattr(self.naimenovanje_tab, 'reload_data'):
                QApplication.processEvents()
                self.naimenovanje_tab.reload_data()

        tab_naziv = "Faktura" if tab == 'faktura' else "Naimenovanja"
        akcija = "Obrisano iz" if vrijednost == '' else f"Upisano <b>{vrijednost}</b> u"
        chat.add_agent_message(
            f"✅ {akcija} kolone <b>{naziv_kolone}</b> ({tab_naziv} tab) "
            f"— {upisano} stavki."
        )

    def _provjeri_tarifni_za_naziv(self, naziv_robe: str):
        """Pozovi HybridTariffAgent za konkretan naziv robe i prikaži rezultat u chatu."""
        from services.agent.hybrid_tariff_agent import HybridTariffAgent
        from PySide6.QtCore import QThread, Signal, QObject

        chat = self.view.get_chat_panel()
        chat.add_activity(f"🔍 Provjera tarifnog za: {naziv_robe}")
        chat.show_typing_indicator()

        class _TariffCheckWorker(QThread):
            done = Signal(dict)
            error = Signal(str)

            def __init__(self, naziv):
                super().__init__()
                self._naziv = naziv

            def run(self):
                try:
                    agent = HybridTariffAgent()
                    result = agent.decide_tariff(self._naziv)
                    self.done.emit(result)
                except Exception as e:
                    self.error.emit(str(e))

        worker = _TariffCheckWorker(naziv_robe)

        def _on_done(result):
            chat.hide_typing_indicator()
            confidence = result.get('confidence', 0)
            tarifni = result.get('tarifni_broj', 'N/A')
            metoda = result.get('method', 'N/A')
            needs_review = result.get('needs_review', False)
            explanation = result.get('explanation', '')
            candidates = result.get('candidates', [])

            if confidence >= 0.85:
                conf_ikona = "✅"
                conf_status = "visok — auto-prihvati"
            elif confidence >= 0.60:
                conf_ikona = "⚠️"
                conf_status = "srednji — pregledaj"
            else:
                conf_ikona = "❌"
                conf_status = "nizak — obavezno pregledaj"

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

            chat.add_agent_message("<br>".join(lines))
            chat.add_activity(f"✅ Tarifni za '{naziv_robe}': {tarifni} ({confidence:.0%})")
            if not hasattr(self, '_tariff_check_workers'):
                self._tariff_check_workers = []
            if worker in self._tariff_check_workers:
                self._tariff_check_workers.remove(worker)

        def _on_error(err):
            chat.hide_typing_indicator()
            chat.add_agent_message(f"❌ Greška pri provjeri tarifnog: {err}")

        worker.done.connect(_on_done)
        worker.error.connect(_on_error)
        worker.finished.connect(worker.deleteLater)

        if not hasattr(self, '_tariff_check_workers'):
            self._tariff_check_workers = []
        self._tariff_check_workers.append(worker)
        worker.start()

    def _obrisi_tarifne_brojeve(self):
        """Obriši sve tarifne brojeve iz draft.invoice_lines i osvježi Faktura tab."""
        from PySide6.QtWidgets import QApplication

        chat = self.view.get_chat_panel()

        if not self.draft or not self.draft.invoice_lines:
            chat.add_agent_message("⚠️ Nema učitanih stavki.")
            return

        obrisano = 0
        for line in self.draft.invoice_lines:
            if getattr(line, 'tarifni_broj', None):
                line.tarifni_broj = ''
                obrisano += 1

        # Osvježi Faktura tab
        faktura_widget = self.faktura_tab
        if hasattr(self.faktura_tab, 'view'):
            faktura_widget = self.faktura_tab.view
        if faktura_widget and hasattr(faktura_widget, '_load_data_from_draft'):
            QApplication.processEvents()
            faktura_widget._load_data_from_draft()

        chat.add_agent_message(
            f"✅ Obrisano <b>{obrisano}</b> tarifnih brojeva iz Faktura taba."
        )

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

