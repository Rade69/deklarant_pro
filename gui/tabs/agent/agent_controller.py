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

        self._connect_signals()

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
        header.parser_changed.connect(self._on_parser_changed)

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
        parser_mode = self.view.get_header().parser_combo.currentText()
        self._worker = ProcessingWorker(files, parser_mode=parser_mode)
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

        # 3. Izračunaj odnos neto/bruto
        neto_bruto_ratio = neto_total / bruto_total if bruto_total > 0 else 0.95
        print(f"[WeightCalc] Odnos neto/bruto: {neto_bruto_ratio:.6f}")

        # 4. Distribuiraj težine
        izracunato = 0
        for line in items_to_update:
            has_bruto = line.bruto_kg and line.bruto_kg > 0
            has_neto = line.neto_kg and line.neto_kg > 0

            if not has_bruto and not has_neto:
                # PDF stavka: nema ništa → koristi količinu kao neto
                if line.kolicina and line.kolicina > 0:
                    line.neto_kg = line.kolicina  # Pretpostavka: kg = neto
                    line.bruto_kg = round(line.kolicina * 1.05, 3)  # +5% ambalaža
                    izracunato += 1
                    print(f"  [PDF] {line.naziv_robe[:30]}: neto={line.neto_kg:.3f}, bruto={line.bruto_kg:.3f}")
                else:
                    # Nema količine → koristi prosjek
                    avg_weight = (bruto_total / len(invoice_lines)) if bruto_total > 0 else 10.0
                    line.neto_kg = round(avg_weight * 0.95, 3)
                    line.bruto_kg = round(avg_weight, 3)
                    izracunato += 1
                    print(f"  [PDF AVG] {line.naziv_robe[:30]}: neto={line.neto_kg:.3f}, bruto={line.bruto_kg:.3f}")

            elif has_bruto and not has_neto:
                # Excel stavka: ima bruto, treba neto → koristi odnos
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
                    min_similarity=0.70
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

        chat.add_activity(f"🔍 Tražim template za pošiljaoca: '{exporter_hint}'")

        # ── Pretraga XML templatea ───────────────────────────────
        try:
            from services.agent.xml_template_service import XmlTemplateService
            svc = XmlTemplateService()
            match = svc.find_template(exporter_hint)
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri pretrazi XML templatea: {e}")
            return

        if not match:
            chat.add_activity("ℹ️ Nije nađen odgovarajući XML template — popuni zaglavlje ručno")
            return

        score_pct = int(match.match_score * 100)
        chat.add_activity(
            f"✅ Nađen template: '{match.filename}' "
            f"(pošiljalac: '{match.exporter_name}', poklapanje: {score_pct}%)"
        )

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
        """Odgovori na chat poruku koristeći Groq LLM."""
        from .widgets.chat_worker import ChatWorker
        chat = self.view.get_chat_panel()

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

    def _on_parser_changed(self, parser: str):
        """Handle promjenu parsera iz header-a."""
        self.view.get_chat_panel().add_activity(f"ℹ️ Parser: {parser}")
