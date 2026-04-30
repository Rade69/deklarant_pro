# gui/tabs/zaglavlje_controller.py

"""
Zaglavlje Controller - Orchestration Layer

Koordinacija između View i Service layer-a.
Nema business logike.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from gui.tabs.zaglavlje_view import ZaglavljeView
    from services.zaglavlje_service import ZaglavljeService
    from core.draft.draft import DeclarationDraft


logger = logging.getLogger("deklarant_pro.gui.zaglavlje_controller")


class ZaglavljeController:
    """
    Controller layer za Zaglavlje tab.
    
    Odgovornosti:
    - Orkestracija između View i Service
    - Event handling
    - Error handling
    - Progress tracking
    
    Nema business logike.
    """
    
    def __init__(
        self,
        view: 'ZaglavljeView',
        service: 'ZaglavljeService',
        save_draft_fn: Optional[Callable] = None,
        get_draft_fn: Optional[Callable] = None,
    ):
        """
        Inicijalizuj controller.

        Args:
            view: View instanca
            service: Service instanca
            save_draft_fn: Callback koji poziva ZaglavljeTab.save_to_draft()
            get_draft_fn: Callback koji vraća trenutni DeclarationDraft
        """
        self.view = view
        self.service = service
        self._save_draft_fn = save_draft_fn
        self._get_draft_fn = get_draft_fn
        self.logger = logger

        # Connect signals
        self._connect_signals()

        self.logger.info("ZaglavljeController inicijalizovan")

    def _connect_signals(self):
        """
        Poveži View signale sa controller metodama.

        Connections:
        - save_requested → _on_save
        - validation_requested → _on_validate
        - delete_requested → _on_delete
        - import_xml_requested → _on_import_xml
        - export_xml_requested → _on_export_xml
        - new_requested → _on_new
        - close_requested → _on_close
        - search_company_requested → _on_search_company
        - add_company_requested → _on_add_company
        """
        self.view.save_requested.connect(self._on_save)
        self.view.validation_requested.connect(self._on_validate)
        self.view.delete_requested.connect(self._on_delete)
        self.view.import_xml_requested.connect(self._on_import_xml)
        self.view.export_xml_requested.connect(self._on_export_xml)
        self.view.new_requested.connect(self._on_new)
        self.view.close_requested.connect(self._on_close)
        self.view.search_company_requested.connect(self._on_search_company)
        self.view.add_company_requested.connect(self._on_add_company)
        self.view.deklaracija_sifra_changed.connect(self._on_dekl_sifra_changed)
        self.view.valuta_changed.connect(self._on_valuta_changed)
    
    # ============================================================
    # EVENT HANDLERS
    # ============================================================

    def _on_validate(self):
        """
        Validiraj podatke prije XML exporta.

        Workflow:
        1. Snimi trenutne podatke u draft
        2. Pokušaj enhanced agent validaciju
        3. Ako nije dostupna, koristi osnovnu validaciju
        4. Prikaži rezultate u enhanced dialogu
        """
        try:
            self.logger.info("Validation requested")

            # 1. Snimi u draft da imamo najnovije podatke
            if self._save_draft_fn:
                self._save_draft_fn()

            # 2. Dohvati draft i view data
            draft = self._get_draft_fn() if self._get_draft_fn else None
            if draft is None:
                self.view.show_error("Nema draft podataka za validaciju.")
                return

            view_data = self.view.get_data()
            import_docs = self.view.get_import_attached_docs()
            
            # 3. Pokušaj enhanced agent validaciju
            enhanced_result = self._try_enhanced_validation(
                view_data, draft, import_docs
            )
            
            if enhanced_result:
                # Enhanced validacija uspješna
                return
            
            # 4. Fallback na osnovnu validaciju
            self._fallback_to_basic_validation(view_data, draft, import_docs)

        except Exception as e:
            self.logger.error(f"Validation failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri validaciji: {e}")
    
    def _try_enhanced_validation(
        self,
        view_data: Dict[str, Any],
        draft: Any,
        import_docs: List[Dict]
    ) -> bool:
        """
        Pokušaj enhanced agent validaciju.
        
        Returns:
            True ako je enhanced validacija korištena
        """
        try:
            from services.agent.declaration_validator_service import (
                validate_declaration_with_agent
            )
            from gui.dialogs.enhanced_validation_dialog import (
                show_enhanced_validation_dialog,
                DialogConfig
            )
            
            # Dobavi sve potrebne podatke
            naimenovanja_data = self._get_naimenovanja_data()
            invoice_lines = self._get_invoice_lines(draft)
            
            # Pokreni agent validaciju
            report = validate_declaration_with_agent(
                zaglavlje_data=view_data,
                naimenovanja_data=naimenovanja_data,
                invoice_lines=invoice_lines,
                draft=draft
            )
            
            # Prikaži enhanced dijalog
            config = DialogConfig(
                show_details=True,
                show_recommendations=True,
                allow_auto_fix=True,
                show_export_button=report.valid
            )
            
            result = show_enhanced_validation_dialog(report, self.view, config)
            
            if result:
                self.logger.info(f"Enhanced validation completed: {report.error_count} errors")
                
                # Ako je validno i korisnik želi export, pokreni export
                if report.valid:
                    self._on_export()
                
                return True
            
            return False
            
        except ImportError:
            self.logger.debug("Agent validation service nije dostupan")
            return False
        except Exception as e:
            self.logger.error(f"Enhanced validation failed: {e}", exc_info=True)
            return False
    
    def _fallback_to_basic_validation(
        self,
        view_data: Dict[str, Any],
        draft: Any,
        import_docs: List[Dict]
    ):
        """Fallback na osnovnu validaciju."""
        # Pokreni osnovnu validaciju
        result = self.service.validate(view_data, draft, import_docs)
        
        # Prikaži rezultate
        self._show_validation_result(result)
        
        self.logger.info(
            f"Basic validation complete: {result['error_count']} errors, "
            f"{result['warning_count']} warnings"
        )
    
    def _get_naimenovanja_data(self) -> List[Dict[str, Any]]:
        """Dobavi podatke naimenovanja iz draft-a."""
        draft = self._get_draft_fn() if self._get_draft_fn else None
        if not draft or not hasattr(draft, 'items'):
            return []
        
        naimenovanja_data = []
        for item in draft.items:
            item_data = {
                'tariff_code': getattr(item, 'tariff_code', ''),
                'goods_trade_name': getattr(item, 'goods_trade_name', ''),
                'origin_country_code': getattr(item, 'origin_country_code', ''),
                'preference_code': getattr(item, 'preference_code', ''),
                'gross_mass_kg': getattr(item, 'gross_mass_kg', 0),
                'net_mass_kg': getattr(item, 'net_mass_kg', 0),
                'item_value': getattr(item, 'item_value', 0),
            }
            naimenovanja_data.append(item_data)
        
        return naimenovanja_data
    
    def _get_invoice_lines(self, draft: Any) -> List[Dict[str, Any]]:
        """Dobavi stavke fakture iz draft-a."""
        if not draft or not hasattr(draft, 'invoice_lines'):
            return []
        
        invoice_lines = []
        for line in draft.invoice_lines:
            line_data = {
                'naziv_robe': getattr(line, 'naziv_robe', ''),
                'iznos': getattr(line, 'iznos', 0),
                'valuta': getattr(line, 'valuta', ''),
                'bruto_kg': getattr(line, 'bruto_kg', 0),
                'neto_kg': getattr(line, 'neto_kg', 0),
            }
            invoice_lines.append(line_data)
        
        return invoice_lines

    def _show_validation_result(self, result: dict):
        """
        Prikaži rezultate validacije u dialogu.

        Ako ima errors — prikaži ih i blokiraj dalje.
        Ako ima samo warnings — prikaži upozorenja.
        Ako je sve OK — prikaži success.
        """
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])
        valid = result.get("valid", False)

        if valid and not warnings:
            self.view.show_success(
                "✅ Validacija uspješna!\n\n"
                "Sva obavezna polja su popunjena i podaci su sinhronizovani.\n"
                "Možete nastaviti sa XML exportom."
            )
            return

        # Sastavi poruku
        msg_parts = []

        # Fixable akcije (auto-update)
        fixable = [e for e in errors if e.get("fixable")]
        fixable_warnings = [w for w in warnings if w.get("fixable")]
        all_fixable = fixable + fixable_warnings

        if errors:
            msg_parts.append(f"❌ {len(errors)} GREŠAKA (blokiraju export):\n")
            for i, err in enumerate(errors, 1):
                msg_parts.append(f"  {i}. {err['message']}")
            msg_parts.append("")

        if warnings:
            non_fixable_warnings = [
                w for w in warnings if not w.get("fixable")
            ]
            if non_fixable_warnings:
                msg_parts.append(
                    f"⚠️ {len(non_fixable_warnings)} UPOZORENJA:\n"
                )
                for i, w in enumerate(non_fixable_warnings, 1):
                    msg_parts.append(f"  {i}. {w['message']}")
                msg_parts.append("")

        if all_fixable:
            msg_parts.append(
                f"🔧 {len(all_fixable)} AUTOMATSKIH POPRAVKI dostupno:\n"
            )
            for i, item in enumerate(all_fixable, 1):
                msg_parts.append(f"  {i}. {item['message']}")
            msg_parts.append("")

        full_msg = "\n".join(msg_parts)

        # Ako ima fixable, ponudi auto-fix
        if all_fixable:
            reply = QMessageBox.question(
                self.view,
                "Rezultat validacije",
                full_msg + "\nŽelite li automatski popraviti ove greške?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._apply_auto_fixes(all_fixable)
                # Ponovo validiraj nakon fix-a
                if self._save_draft_fn:
                    self._save_draft_fn()
                view_data = self.view.get_data()
                draft = self._get_draft_fn() if self._get_draft_fn else None
                if draft:
                    new_result = self.service.validate(view_data, draft)
                    self._show_validation_result(new_result)
                return
            # Ako user kaže Ne, samo prikaži info
            QMessageBox.warning(
                self.view,
                "Validacija — ima grešaka",
                full_msg,
            )
        else:
            # Nema fixable — samo prikaži
            if errors:
                QMessageBox.critical(
                    self.view,
                    "Validacija — greške",
                    full_msg,
                )
            else:
                QMessageBox.information(
                    self.view,
                    "Validacija — upozorenja",
                    full_msg,
                )

    def _apply_auto_fixes(self, fixable_items: list):
        """
        Primijeni automatske popravke na view podatke.

        Podržane akcije:
        - auto_update_iznos: ažuriraj iznos iz fakture
        - auto_update_valuta: ažuriraj valutu iz fakture
        - auto_update_stavke: ažuriraj broj stavki
        """
        draft = self._get_draft_fn() if self._get_draft_fn else None
        if draft is None:
            return

        for item in fixable_items:
            action = item.get("fix_action", "")

            if action == "auto_update_iznos":
                invoice_lines = getattr(draft, "invoice_lines", []) or []
                iznos = sum(
                    getattr(l, "iznos", 0.0) or 0.0 for l in invoice_lines
                )
                widget = self.view.field_widgets.get("iznos")
                if widget and hasattr(widget, "setText"):
                    widget.setText(f"{iznos:.2f}")
                    self.logger.info(f"Auto-fix: iznos ažuriran na {iznos:.2f}")

            elif action == "auto_update_valuta":
                invoice_lines = getattr(draft, "invoice_lines", []) or []
                valuta = ""
                for line in invoice_lines:
                    v = getattr(line, "valuta", "") or ""
                    if v:
                        valuta = v
                        break
                widget = self.view.field_widgets.get("valuta")
                if widget and hasattr(widget, "setText"):
                    widget.setText(valuta)
                    self.logger.info(f"Auto-fix: valuta ažurirana na {valuta}")

            elif action == "auto_update_stavke":
                n_items = len(draft.items) if draft.items else 0
                widget = self.view.field_widgets.get("stavke")
                if widget and hasattr(widget, "setText"):
                    widget.setText(str(n_items))
                    self.logger.info(f"Auto-fix: broj stavki ažuriran na {n_items}")

        # Označi dirty
        self.view.data_changed.emit()

    def _on_save(self):
        """Snimi podatke u draft (in-memory)."""
        try:
            self.logger.info("Save requested")

            if self._save_draft_fn:
                self._save_draft_fn()
                self.view.show_success("Podaci sačuvani!")
                self.logger.info("Save successful")
            else:
                # Fallback: emituj data_changed da označi dirty
                self.view.data_changed.emit()
                self.view.show_success("Podaci sačuvani!")

        except Exception as e:
            self.logger.error(f"Save failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri čuvanju: {e}")
    
    def _on_delete(self):
        """Briši (očisti) zaglavlje — potvrdi i resetuj formu."""
        try:
            self.logger.info("Delete requested")

            if not self.view.confirm(
                "Da li ste sigurni da želite obrisati ovo zaglavlje?\n"
                "Svi uneseni podaci će biti izgubljeni.",
                "Potvrda brisanja"
            ):
                return

            self.view.clear_data()
            self.logger.info("Zaglavlje obrisano (forma resetovana)")

        except Exception as e:
            self.logger.error(f"Delete failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri brisanju: {e}")
    
    def _on_import_xml(self, filename: str):
        """
        Handle import XML event.
        
        Učitava OST iz draft.header_attached_documents (unos iz Rb.40.3)
        i dodaje ga u attached_documents — vidi docs/sections/ost-rb40.md
        
        Args:
            filename: Putanja do XML fajla
        """
        try:
            self.logger.info(f"Import XML requested: {filename}")
            current_view_docs = self.view.get_data().get("attached_documents", [])
            
            # Load data from XML via service
            data = self.service.load_from_xml(filename)

            # Rb.22 — iznos se uvijek uzima iz fakture/naim., ne iz XML-a
            # XML može sadržavati zastarjeli iznos iz prethodne deklaracije
            draft = self._get_draft_fn() if self._get_draft_fn else None
            if draft:
                invoice_lines = getattr(draft, 'invoice_lines', None) or []
                iznos_iz_fakture = sum(getattr(l, 'iznos', 0.0) or 0.0 for l in invoice_lines)
                if iznos_iz_fakture:
                    data['iznos'] = f"{iznos_iz_fakture:.2f}"
                    data['valuta'] = data.get('valuta') or next(
                        (getattr(l, 'valuta', '') for l in invoice_lines if getattr(l, 'valuta', '')),
                        ''
                    )
                
                # Broj fakture — uvijek iz fakture, ne iz XML-a
                # Skupljamo SVE brojeve faktura (može ih biti više u tabeli faktura)
                # Prioritet: line.invoice_number > line.raw['invoice_number'] > draft.ref_br
                brojevi_faktura = []
                for line in invoice_lines:
                    bf = getattr(line, 'invoice_number', '') or ''
                    if bf and bf not in brojevi_faktura:
                        brojevi_faktura.append(bf)
                
                if not brojevi_faktura:
                    for line in invoice_lines:
                        raw = getattr(line, 'raw', None) or {}
                        bf = raw.get('invoice_number', '') or ''
                        if bf and bf not in brojevi_faktura:
                            brojevi_faktura.append(bf)
                
                if brojevi_faktura:
                    # Svi brojevi spojeni sa | idu u N380 referencu
                    svi_brojevi = ' | '.join(brojevi_faktura)

                    # Dodaj/ažuriraj N380 u attached_documents sa svim brojevima faktura
                    docs = data.setdefault('attached_documents', [])
                    n380 = next((d for d in docs if d.get('code') == 'N380'), None)
                    if n380:
                        n380['number'] = svi_brojevi
                    else:
                        docs.append({
                            'code': 'N380',
                            'name': 'Faktura',
                            'number': svi_brojevi,
                            'from_rule': True,
                        })

                # Rub.6 (Uk. paketa) — uvijek iz fakture/naimenovanja, ne iz XML-a
                if hasattr(draft, 'items') and draft.items:
                    total_qty = sum(getattr(it, 'package_qty', 0.0) or 0.0 for it in draft.items)
                    if total_qty > 0:
                        draft.uk_paketa = f"{int(total_qty)}"
                if (not getattr(draft, 'uk_paketa', '')) and invoice_lines:
                    total_qty_inv = sum(getattr(l, 'kolicina', 0.0) or 0.0 for l in invoice_lines)
                    if total_qty_inv > 0:
                        draft.uk_paketa = f"{int(total_qty_inv)}"
                if getattr(draft, 'uk_paketa', ''):
                    data['uk_paketa'] = draft.uk_paketa

                # Rub.40.3 (rb40_broj): ručni unos u aplikaciji je izvor istine.
                # XML import ne smije prepisati postojeću vrijednost ako već postoji u draftu.
                rb40_broj_draft = (getattr(draft, 'rb40_broj', '') or '').strip()
                if rb40_broj_draft:
                    data['rb40_broj'] = rb40_broj_draft

                # Osiguraj da su PE1/PE2/PE3 iz Rub.44.4 sinhronizovani u header docs
                self._sync_pe_docs_from_items_to_header(draft)

                header_docs = getattr(draft, "header_attached_documents", None) if draft else None
                data['attached_documents'] = self._merge_import_docs_add_only_missing(
                    existing_docs=current_view_docs,
                    draft_header_docs=header_docs or [],
                    imported_docs=data.get('attached_documents', []) or [],
                )

            protected_codes = {
                (d.get("code") or "").strip().upper()
                for d in current_view_docs
                if isinstance(d, dict) and (d.get("code") or "").strip()
            }
            corrected = self._sanitize_attached_documents_after_import(data, protected_codes=protected_codes)

            # Populate view with data — _from_import=True briše stale ref-ove pri XML uvozu
            self.view.set_data(data, _from_import=True)

            # Odmah snimi u draft da bi ostali tabovi (Naimenovanja) imali ažurne trosak/kurs
            if self._save_draft_fn:
                self._save_draft_fn()

            if corrected > 0:
                self.view.show_warning(
                    f"Uvoz je ispravio {corrected} konflikt(a) u Rub.44 "
                    f"(PE referenca na pogrešnoj šifri dokumenta)."
                )

            self.view.show_success(f"Podaci učitani iz: {filename}")
            self.logger.info(f"Import successful: {filename}")
            
        except FileNotFoundError as e:
            self.logger.error(f"File not found: {e}")
            self.view.show_error(f"Fajl ne postoji: {filename}")
        
        except ValueError as e:
            self.logger.error(f"Invalid XML: {e}")
            self.view.show_error(f"Neispravan XML format: {e}")
        
        except Exception as e:
            self.logger.error(f"Import failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri uvozu: {e}")

    def _sync_pe_docs_from_items_to_header(self, draft) -> None:
        header_docs = getattr(draft, "header_attached_documents", None)
        items = getattr(draft, "items", None)
        if header_docs is None or not items:
            return

        pe_entries: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            candidates = [
                (getattr(item, "attached_document4", "") or "").strip(),
                (getattr(item, "attached_document3", "") or "").strip(),
                (getattr(item, "attached_document1", "") or "").strip(),
            ]
            for raw in candidates:
                if not raw:
                    continue
                parts = raw.split(" ", 1)
                sifra = parts[0].strip().upper()
                broj = parts[1].strip() if len(parts) > 1 else ""
                if sifra in {"PE1", "PE2", "PE3"}:
                    key = (sifra, broj)
                    if key not in seen:
                        seen.add(key)
                        pe_entries.append(key)

        if not pe_entries:
            return

        header_docs[:] = [d for d in header_docs if getattr(d, "code", "") not in {"PE1", "PE2", "PE3"}]

        from core.draft.draft import AttachedDocument
        naziv_map = {
            "PE1": "EUR.1 obrazac",
            "PE2": "Izjava na fakturi",
            "PE3": "Izjava ovlaštenog izvoznika",
        }
        for sifra, broj in pe_entries:
            header_docs.append(
                AttachedDocument(
                    code=sifra,
                    name=naziv_map.get(sifra, f"Dokument {sifra}"),
                    number=broj,
                    from_rule=(sifra == "PE1"),
                )
            )

    def _merge_import_docs_add_only_missing(
        self,
        existing_docs: List[Dict[str, Any]],
        draft_header_docs: List[Any],
        imported_docs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        existing_codes: set[str] = set()

        for d in existing_docs:
            if not isinstance(d, dict):
                continue
            code = (d.get("code") or "").strip()
            if not code:
                continue
            existing_codes.add(code.upper())
            merged.append({
                "code": code,
                "name": d.get("name", ""),
                "number": d.get("number", ""),
                "from_rule": bool(d.get("from_rule", False)),
            })

        for hd in draft_header_docs:
            code = (getattr(hd, "code", "") or "").strip()
            if not code:
                continue
            if code.upper() in existing_codes:
                continue
            existing_codes.add(code.upper())
            merged.append({
                "code": code,
                "name": getattr(hd, "name", ""),
                "number": getattr(hd, "number", ""),
                "from_rule": bool(getattr(hd, "from_rule", False)),
            })

        for d in imported_docs:
            if not isinstance(d, dict):
                continue
            code = (d.get("code") or "").strip()
            if not code:
                continue
            if code.upper() in existing_codes:
                continue
            existing_codes.add(code.upper())
            merged.append({
                "code": code,
                "name": d.get("name", ""),
                "number": d.get("number", ""),
                "from_rule": bool(d.get("from_rule", False)),
            })

        return merged

    def _sanitize_attached_documents_after_import(self, data: Dict[str, Any], protected_codes: Optional[set[str]] = None) -> int:
        docs = data.get("attached_documents")
        if not isinstance(docs, list):
            return 0

        corrected = 0
        protected = protected_codes or set()
        pe_prefix = re.compile(r"^\s*PE[123]\b", re.IGNORECASE)
        force_empty_codes = {"N730", "PZT", "DV1"}
        for d in docs:
            if not isinstance(d, dict):
                continue
            code = (d.get("code") or "").strip().upper()
            number = (d.get("number") or "").strip()
            if not code:
                continue

            # Za ove šifre referenca mora ostati prazna nakon XML uvoza.
            # Ako je šifra već bila ručno prisutna prije importa, ne diraj.
            if code in protected:
                continue
            if code in force_empty_codes and number:
                d["number"] = ""
                corrected += 1
                self.logger.warning(
                    f"Cleared import reference by rule: code={code}, number={number!r}"
                )
                continue

            if not number:
                continue

            # Za PE1/PE2/PE3 očisti prefiks iz reference ako XML dođe kao "pe3 0504-..."
            if code in {"PE1", "PE2", "PE3"} and pe_prefix.match(number):
                cleaned = pe_prefix.sub("", number).strip(" :,-")
                if cleaned != number:
                    d["number"] = cleaned
                    corrected += 1
                continue

            if code not in {"PE1", "PE2", "PE3"} and pe_prefix.match(number):
                d["number"] = ""
                corrected += 1
                self.logger.warning(
                    f"Sanitized conflicting doc reference: code={code}, number={number!r}"
                )

        return corrected
    
    def _on_export_xml(self):
        """Izvezi deklaraciju u ASYCUDA XML format."""
        try:
            self.logger.info("Export XML requested")

            # 1. Provjeri da li je validacija prošla
            draft = self._get_draft_fn() if self._get_draft_fn else None
            if draft is None:
                self.view.show_error("Nema draft podataka za export.")
                return

            view_data = self.view.get_data()
            import_docs = self.view.get_import_attached_docs()
            result = self.service.validate(view_data, draft, import_docs)

            if not result["valid"]:
                self.view.show_error(
                    f"❌ Nije moguće izvesti XML — validacija nije prošla.\n\n"
                    f"Pronađeno {result['error_count']} grešaka koje blokiraju export.\n"
                    f"Kliknite na dugme 'Provjeri' da pregledate i popravite greške."
                )
                self.logger.warning(
                    f"Export blocked: {result['error_count']} validation errors"
                )
                return

            if result["warnings"]:
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self.view,
                    "Upozorenje prije exporta",
                    f"⚠️ Validacija ima {len(result['warnings'])} upozorenja.\n\n"
                    f"{'; '.join(w['message'][:80] for w in result['warnings'][:3])}\n\n"
                    f"Da li želite nastaviti sa exportom?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            # 2. File dialog
            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self.view,
                "Izvezi u AsycudaWorld XML",
                "",
                "XML Files (*.xml);;All Files (*)"
            )

            if not filename:
                return

            if not filename.endswith('.xml'):
                filename += '.xml'

            # 3. Export
            if draft is not None:
                from exporters.asycuda_xml_builder import export_to_xml
                success = export_to_xml(draft, filename)
            else:
                data = self.view.get_data()
                success = self.service.export_to_xml(data, filename)

            if success:
                self.view.show_success(f"XML exportovan u: {filename}")
                self.logger.info(f"Export successful: {filename}")
                # Docs: docs/sections/asycuda-99-item-limit.md
                pending = getattr(draft, "pending_next_declaration", None)
                if pending is not None:
                    reply = QMessageBox.question(
                        self.view,
                        "Nastavi sa ostatkom",
                        "Ova deklaracija je izvezena.\n\n"
                        "Postoje preostale stavke koje su odvojene zbog ASYCUDA limita od 99 naimenovanja.\n"
                        "Da li želite sada učitati sljedeću deklaraciju sa ostatkom?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        main_window = self.view.window()
                        if hasattr(main_window, "continue_with_pending_declaration"):
                            if main_window.continue_with_pending_declaration():
                                self.view.show_success(
                                    "Učitana je sljedeća deklaracija sa preostalim stavkama."
                                )
                        else:
                            self.view.show_error(
                                "Nije pronađen mehanizam za učitavanje sljedeće deklaracije."
                            )
            else:
                self.view.show_error("Greška pri eksportu")

        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri eksportu: {e}")
    
    def _on_new(self):
        """Handle new declaration event."""
        try:
            self.logger.info("New declaration requested")
            
            # Confirm
            if not self.view.confirm(
                "Kreiraj novu praznu deklaraciju?\nNesačuvane promjene će biti izgubljene.",
                "Novi"
            ):
                return
            
            # Clear view
            self.view.clear_data()

            self.logger.info("New declaration created")

        except Exception as e:
            self.logger.error(f"New failed: {e}", exc_info=True)
            self.view.show_error(f"Greška: {e}")

    def _on_close(self):
        """Izlaz — snimi podatke u draft i obavijesti korisnika."""
        try:
            self.logger.info("Close requested")
            if self._save_draft_fn:
                self._save_draft_fn()
            # Zatvori glavni prozor (ako smo u standalone modu) ili ignoriši
            parent = self.view.window()
            if parent and parent is not self.view:
                parent.close()
        except Exception as e:
            self.logger.error(f"Close failed: {e}", exc_info=True)

    def _on_search_company(self, company_type: str):
        """
        Otvori dialog za pretragu kompanije po JIB-u.
        
        Args:
            company_type: Tip polja ('izvoznik' ili 'primalac')
        
        Workflow:
        1. Otvori PartnerSearchDialog
        2. Ako user odabere kompaniju, popuni view polja
        3. Handle errors
        """
        try:
            self.logger.info(f"Search company requested: {company_type}")
            
            # Odredi tip partnera
            partner_type = (
                "exporter"
                if company_type == "izvoznik"
                else "consignee"
                if company_type == "primalac"
                else "all"
            )
            
            # Otvori dijalog
            from gui.widgets import PartnerSearchDialog
            dialog = PartnerSearchDialog(self.view, partner_type=partner_type)
            
            if dialog.exec():
                partner = dialog.get_selected_partner()
                
                if partner:
                    self.logger.info(f"Partner selected: {partner.get('naziv', 'N/A')}")
                    
                    # Populate fields
                    self._populate_company_fields(company_type, partner)
                    
                    # Mark dirty
                    self.view.data_changed.emit()
                    
        except Exception as e:
            self.logger.error(f"Search company failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri pretrazi: {e}")
    
    def _on_add_company(self, company_type: str):
        """
        Dodaj novu kompaniju kroz dialog.
        
        Args:
            company_type: Tip polja ('izvoznik' ili 'primalac')
        
        Workflow:
        1. Otvori dialog za dodavanje
        2. Pozovi service.add_company(data)
        3. Refresh view
        4. Handle errors
        """
        try:
            self.logger.info(f"Add company requested: {company_type}")
            
            # TODO: Implement AddCompanyDialog
            # For now, show info message
            self.view.show_warning(f"Dodavanje nove kompanije ({company_type}) - u izradi")
            
        except Exception as e:
            self.logger.error(f"Add company failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri dodavanju: {e}")
    
    def _on_import_jci(self):
        """
        Import iz JCI formata.
        
        Workflow:
        1. Otvori file dialog
        2. Parsiraj JCI format
        3. Popuni podatke
        4. Handle errors
        """
        try:
            self.logger.info("JCI import requested")
            
            # TODO: Implement JCI import
            # For now, show info message
            self.view.show_warning("JCI import funkcionalnost - u izradi")
            
        except Exception as e:
            self.logger.error(f"JCI import failed: {e}", exc_info=True)
            self.view.show_error(f"Greška pri JCI importu: {e}")
    
    def _populate_oznaka_combo(self, sifra: str):
        """
        Popuni combo za oznaku postupka prema odabranoj šifri (EX/IM).
        
        Args:
            sifra: Šifra vrste deklaracije (npr. 'IM', 'EX')
        
        Workflow:
        1. Dohvati vrste deklaracija iz service-a
        2. Popuni combo sa odgovarajućim oznakama
        3. Handle errors
        """
        try:
            cb = self.view.field_widgets.get("deklaracija_oznaka")
            if not cb:
                return
            
            cb.blockSignals(True)
            cb.clear()
            
            # Dohvati oznake za odabranu šifru
            vrste = self.service.get_vrste_deklaracija()
            for oznaka, opis in vrste.get(sifra, []):
                cb.addItem(oznaka)
                cb.setItemData(cb.count() - 1, opis, Qt.ToolTipRole)
            
            cb.blockSignals(False)
            self.logger.debug(f"Populated oznaka combo for sifra={sifra}")
            
        except Exception as e:
            self.logger.error(f"Populate oznaka combo failed: {e}", exc_info=True)
    
    def _on_valuta_changed(self, valuta: str):
        """
        Auto-popuni Rb.23 (kurs) na osnovu valute u Rb.22.

        EUR → fiksni kurs 1.95583 (BiH nominalni kurs)
        USD/ostalo → dohvati srednji kurs od CBBH API-ja
        Prazno → ne radi ništa
        """
        if not valuta:
            return
        try:
            from services.agent.cbbh_exchange_service import get_cbbh_rate
            rate = get_cbbh_rate(valuta)
            if rate is None:
                self.logger.warning(f"[Rb.23] Nije moguće dohvatiti kurs za {valuta}")
                return
            kurs_widget = self.view.field_widgets.get("kurs")
            if kurs_widget is None:
                return
            formatted = f"{rate:.5f}".rstrip("0").rstrip(".")
            kurs_widget.setText(formatted)
            self.logger.info(f"[Rb.23] Kurs za {valuta} = {formatted}")
        except Exception as e:
            self.logger.error(f"[Rb.23] Greška pri dohvatanju kursa: {e}", exc_info=True)

    def _on_dekl_sifra_changed(self, sifra: str):
        """
        Event handler za promjenu šifre deklaracije (EX/IM).
        
        Args:
            sifra: Nova šifra (npr. 'IM' ili 'EX')
        
        Workflow:
        1. Kada se promijeni EX/IM, osvježi listu oznaka u combou
        2. Pozovi _populate_oznaka_combo
        """
        try:
            self.logger.debug(f"Deklaracija šifra changed: {sifra}")
            self._populate_oznaka_combo(sifra)
            
        except Exception as e:
            self.logger.error(f"Deklaracija šifra changed failed: {e}", exc_info=True)
    
    def _populate_company_fields(self, company_type: str, partner: dict):
        """
        Helper za popunjavanje polja kompanije.
        
        Args:
            company_type: Tip polja ('izvoznik' ili 'primalac')
            partner: Dictionary sa podacima partnera
        """
        # Mapiranje polja
        field_mapping = {
            'id': f'{company_type}_id',
            'naziv': f'{company_type}_r1',
            'adresa': f'{company_type}_r2',
            'grad': f'{company_type}_r3',
            'postanski_broj': f'{company_type}_r4',
            'drzava': f'{company_type}_r5',
        }
        
        for partner_field, view_field in field_mapping.items():
            if view_field in self.view.field_widgets:
                widget = self.view.field_widgets[view_field]
                value = partner.get(partner_field, '')
                
                if hasattr(widget, 'setText'):
                    widget.setText(str(value) if value else '')
                elif hasattr(widget, 'setCurrentText'):
                    widget.setCurrentText(str(value) if value else '')

    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def load_dropdowns(self):
        """
        Učitaj dropdown opcije iz baze.
        
        Popunjava:
        - Vrste deklaracija
        - Tipovi deklaracija
        - Vid unutra
        """
        try:
            self.logger.info("Loading dropdowns")
            
            # Load vrste deklaracija
            vrste = self.service.get_vrste_deklaracija()
            vrsta_widget = self.view.field_widgets.get('deklaracija_1')
            if vrsta_widget and hasattr(vrsta_widget, 'addItem'):
                vrsta_widget.clear()
                for sifra, items in vrste.items():
                    for oznaka, opis in items:
                        vrsta_widget.addItem(f"{sifra} - {opis}", sifra)
            
            # Load tipovi deklaracija - VIEW sada sam popunjava deklaracija_oznaka sa tipovima (A, Z, B)
            # Controller više ne treba da popunjava ovaj dropdown
            pass
            
            # Load vid prevoza (Rb.25/26) — dropdown "30 — Cestovni prevoz", u polju samo šifra
            vidovi = self.service.get_vid_unutra()
            for field_key in ('vid_25', 'vid_26'):
                vid_widget = self.view.field_widgets.get(field_key)
                if vid_widget and hasattr(vid_widget, 'addItem'):
                    vid_widget.clear()
                    for sifra, opis in vidovi:
                        vid_widget.addItem(f"{sifra} — {opis}", sifra)

            self.logger.info("Dropdowns loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load dropdowns: {e}", exc_info=True)
            # Don't show error to user - dropdowns can be filled manually
