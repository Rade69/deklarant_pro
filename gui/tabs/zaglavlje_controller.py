# gui/tabs/zaglavlje_controller.py

"""
Zaglavlje Controller - Orchestration Layer

Koordinacija između View i Service layer-a.
Nema business logike.
"""

import logging
from typing import Callable, Optional, TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from gui.tabs.zaglavlje_view import ZaglavljeView
    from services.zaglavlje_service import ZaglavljeService
    from core.draft.draft import DeclarationDraft


logger = logging.getLogger("asycuda_pro.gui.zaglavlje_controller")


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
        - delete_requested → _on_delete
        - import_xml_requested → _on_import_xml
        - export_xml_requested → _on_export_xml
        - new_requested → _on_new
        - open_requested → _on_open
        - close_requested → _on_close
        - search_company_requested → _on_search_company
        - add_company_requested → _on_add_company
        """
        self.view.save_requested.connect(self._on_save)
        self.view.delete_requested.connect(self._on_delete)
        self.view.import_xml_requested.connect(self._on_import_xml)
        self.view.export_xml_requested.connect(self._on_export_xml)
        self.view.new_requested.connect(self._on_new)
        self.view.open_requested.connect(self._on_open)
        self.view.close_requested.connect(self._on_close)
        self.view.search_company_requested.connect(self._on_search_company)
        self.view.add_company_requested.connect(self._on_add_company)
        self.view.deklaracija_sifra_changed.connect(self._on_dekl_sifra_changed)
    
    # ============================================================
    # EVENT HANDLERS
    # ============================================================
    
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
        
        Args:
            filename: Putanja do XML fajla
        """
        try:
            self.logger.info(f"Import XML requested: {filename}")
            
            # Load data from XML via service
            data = self.service.load_from_xml(filename)
            
            # Populate view with data
            self.view.set_data(data)
            
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
    
    def _on_export_xml(self):
        """Izvezi deklaraciju u ASYCUDA XML format."""
        try:
            self.logger.info("Export XML requested")

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

            # Snimi trenutne podatke u draft prije exporta
            draft = None
            if self._save_draft_fn and self._get_draft_fn:
                self._save_draft_fn()
                draft = self._get_draft_fn()
            elif self._get_draft_fn:
                draft = self._get_draft_fn()

            if draft is not None:
                # Koristi AsycudaXMLBuilder za kompletan ASYCUDA XML
                from exporters.asycuda_xml_builder import export_to_xml
                success = export_to_xml(draft, filename)
            else:
                # Fallback na servisov export (bez draft-a)
                data = self.view.get_data()
                success = self.service.export_to_xml(data, filename)

            if success:
                self.view.show_success(f"XML exportovan u: {filename}")
                self.logger.info(f"Export successful: {filename}")
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
    
    def _on_open(self):
        """Otvori ASYCUDA XML deklaraciju (isti flow kao uvoz XML-a)."""
        try:
            self.logger.info("Open declaration requested")

            from PySide6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getOpenFileName(
                self.view,
                "Otvori deklaraciju",
                "",
                "ASYCUDA Files (*.xml *.asd);;All Files (*)"
            )

            if not filename:
                return

            # Delegiraj na isti handler kao Import XML
            self._on_import_xml(filename)

        except Exception as e:
            self.logger.error(f"Open failed: {e}", exc_info=True)
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
            
            # Load tipovi deklaracija
            tipovi = self.service.get_tipovi_deklaracija()
            tip_widget = self.view.field_widgets.get('deklaracija_oznaka')
            if tip_widget and hasattr(tip_widget, 'addItem'):
                tip_widget.clear()
                for sifra, opis in tipovi:
                    tip_widget.addItem(opis, sifra)
            
            # Load vid unutra
            vidovi = self.service.get_vid_unutra()
            vid_widget = self.view.field_widgets.get('vid_25')
            if vid_widget and hasattr(vid_widget, 'addItem'):
                vid_widget.clear()
                for sifra, opis in vidovi:
                    vid_widget.addItem(opis, sifra)
            
            self.logger.info("Dropdowns loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load dropdowns: {e}", exc_info=True)
            # Don't show error to user - dropdowns can be filled manually
