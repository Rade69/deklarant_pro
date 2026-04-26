import os
from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QTabWidget, QApplication, QMessageBox
from PySide6.QtCore import QFile, QTextStream, QIODevice, QSettings, QSize

import logging

logger = logging.getLogger("deklarant_pro.main_window")

try:
    import qtawesome as qta
except ImportError:
    qta = None

import logging
_dbg = logging.getLogger("asycuda_pro.resize_debug")

from config.settings import get_path_settings

from core.draft import DeclarationDraft
from gui.tabs.tab_factory import get_tab_factory
from gui.tabs.lazy_tab import LazyTab
from gui.tabs.admin_tab import AdminTab
from gui.tabs.agent_tab import AgentTab
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Deklarant Pro")

        # Postavi podrazumevanu veliÄinu (80% Full HD 1920x1080)
        self.resize(1536, 823)
        self.setMinimumSize(1200, 700)

        # Vrati geometriju prozora iz prethodne sesije
        self._restore_window_state()

        # 1. UÄitaj stilove
        self.load_stylesheet()

        # 2. Inicijalizacija draft-a
        self.draft = DeclarationDraft()
        self.draft.ensure_min_items(1)

        # 3. Kreiranje tabova (redosled: Faktura, Zaglavlje, Naimenovanja, Å ifrarnici)
        tabs = QTabWidget()

        # OmoguÄ‡i responsive resizing za tab widget
        from PySide6.QtWidgets import QSizePolicy
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Font za tab kartice (stilovi su u main_tabs.qss â€” bez inline setStyleSheet koji bi kreirao QSS bubble)
        from PySide6.QtGui import QFont
        tabs.setFont(QFont("Segoe UI", 9))
        tabs.setIconSize(QSize(20, 20))

        self.setCentralWidget(tabs)

        # Kreiranje tabova koristeÄ‡i TabFactory
        tab_factory = get_tab_factory()

        # Faktura tab â€” kreira se odmah (prikazuje se pri pokretanju)
        self.faktura_tab = tab_factory.create_tab('faktura', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.faktura_tab, self._tab_icon("fa5s.file-alt"), "Faktura")

        # Naimenovanja â€” lazy (QUiLoader + widget cache, inicijalizuje se pri prvom kliku)
        self.naimenovanje_tab = LazyTab(
            lambda: tab_factory.create_tab('naimenovanja', self.draft, self._on_dirty),
            parent=tabs,
        )
        tabs.addTab(self.naimenovanje_tab, self._tab_icon("fa5s.boxes"), "Naimenovanja")

        # Zaglavlje â€” lazy (5 DB upita pri inicijalizaciji)
        self.zaglavlje_tab = LazyTab(
            lambda: tab_factory.create_tab('zaglavlje', self.draft, self._on_dirty),
            parent=tabs,
        )
        tabs.addTab(self.zaglavlje_tab, self._tab_icon("fa5s.folder-open"), "Zaglavlje")

        # Å ifrarnici â€” lazy
        self.sifarnici_tab = LazyTab(
            lambda: tab_factory.create_tab('sifarnici', self.draft, self._on_dirty),
            parent=tabs,
        )
        tabs.addTab(self.sifarnici_tab, self._tab_icon("fa5s.list-alt"), "Å ifrarnici")

        # Admin tab (novi - plugin manager, settings, database, analytics, logs, system info)
        self.admin_tab = AdminTab(self)
        tabs.addTab(self.admin_tab, self._tab_icon("fa5s.cog"), "Admin")

        # Agent tab (novi - AI agent za automatsko procesiranje faktura)
        self.agent_tab = AgentTab(
            self,
            draft=self.draft,
            faktura_tab=self.faktura_tab,
            naimenovanje_tab=self.naimenovanje_tab,
            zaglavlje_tab=self.zaglavlje_tab,
        )
        tabs.addTab(self.agent_tab, self._tab_icon("fa5s.robot"), "Agent")

        # PoveÅ¾i FakturaView signal na agent controller za auto-provjeru naimenovanja
        # Vidi: docs/decisions/002-tool-dispatcher-integration.md
        if hasattr(self.faktura_tab, 'naimenovanja_created'):
            self.faktura_tab.naimenovanja_created.connect(
                self.agent_tab.controller.auto_provjeri_naimenovanja
            )

        # Postavi Admin Tab kao trenutni tab za testiranje (opciono - za development)
        # tabs.setCurrentWidget(self.admin_tab)

        # Registruj callback da aÅ¾urira sve tabove kada se draft podaci promene
        self.draft.register_data_change_callback(self._on_draft_data_changed)

        # OsvjeÅ¾i naimenovanja izraÄune (Rb.44/46) kad se tab aktivira
        self.tabs_widget = tabs
        tabs.currentChanged.connect(self._on_tab_changed)

    def _tab_icon(self, icon_name):
        from PySide6.QtGui import QIcon
        if qta is None:
            return QIcon()
        return qta.icon(icon_name, color="#1E3A5F")

    def continue_with_pending_declaration(self) -> bool:
        # Docs: docs/sections/asycuda-99-item-limit.md
        pending = getattr(self.draft, "pending_next_declaration", None)
        if pending is None:
            return False

        self._replace_draft_contents(pending)

        try:
            from services.create_naimenovanja_service import CreateNaimenovanjaService
            service = CreateNaimenovanjaService(self.draft)
            service.create_smart_group()
        except Exception as e:
            QMessageBox.critical(
                self,
                "GreÅ¡ka",
                f"Nije moguÄ‡e kreirati naimenovanja za sljedeÄ‡u deklaraciju:\n\n{e}",
            )
            return False

        self._reload_all_tabs_from_draft()
        self._on_dirty()
        return True

    def _replace_draft_contents(self, source: DeclarationDraft) -> None:
        callbacks = list(getattr(self.draft, "_data_change_callbacks", []) or [])
        for field_info in fields(DeclarationDraft):
            if field_info.name == "_data_change_callbacks":
                continue
            setattr(self.draft, field_info.name, deepcopy(getattr(source, field_info.name)))
        self.draft._data_change_callbacks = callbacks

    def _reload_all_tabs_from_draft(self) -> None:
        try:
            if hasattr(self.faktura_tab, "view"):
                view = self.faktura_tab.view
                if hasattr(view, "_set_weight_inputs_from_draft"):
                    view._set_weight_inputs_from_draft()
                view._load_data_from_draft()
        except Exception as _e:
            logger.debug("Reload faktura taba: %s", _e)

        try:
            if hasattr(self.naimenovanje_tab, "ensure_initialized"):
                naim_tab = self.naimenovanje_tab.ensure_initialized()
            else:
                naim_tab = self.naimenovanje_tab
            if hasattr(naim_tab, "reload_data"):
                naim_tab.reload_data()
        except Exception as _e:
            logger.debug("Reload naimenovanja taba: %s", _e)

        try:
            if hasattr(self.zaglavlje_tab, "load_from_draft"):
                self.zaglavlje_tab.load_from_draft(self.draft)
        except Exception as _e:
            logger.debug("Reload zaglavlje taba: %s", _e)

    def load_stylesheet(self):
        """
        UÄitaj sve QSS stilove u ispravnom redosledu.
        Redosled je bitan: kasniji stilovi mogu da pregaze ranije.
        """
        # Stil fajlovi u redosledu uÄitavanja
        style_files = [
            "asycuda_modern_material.qss",  # Osnovni stilovi
            "typography.qss",  # Tekst stilovi
            "spacing_system.qss",  # Razmaci
            "main_tabs.qss",  # Stilovi glavnog tab widgeta
            "zone_styling.qss",  # Hijerarhija zona
            "naimenovanja_components.qss",  # Komponente Naimenovanja taba
            "button_system.qss",  # Kategorije dugmadi
            "faktura_tab_v2.qss",  # Osnovni stilovi Faktura taba
            "QSS_header_toolbar_sistem.qss",  # Inputi, scrollbari, tabela, kombo
            "unified_color_system.qss",  # Unificirana paleta boja (najviÅ¡i prioritet)
        ]

        combined_style = ""
        settings = get_path_settings()
        styles_dir = settings.styles_dir

        for style_file in style_files:
            style_path = styles_dir / style_file  # Path objekat

            if style_path.exists():
                file = QFile(str(style_path))
                if file.open(QIODevice.ReadOnly | QIODevice.Text):
                    stream = QTextStream(file)
                    content = stream.readAll()
                    combined_style += f"\n/* ========== {style_file} ========== */\n"
                    combined_style += content
                    file.close()

        if combined_style:
            QApplication.instance().setStyleSheet(combined_style)

    def _on_dirty(self) -> None:
        current_title = self.windowTitle()
        if not current_title.endswith("*"):
            self.setWindowTitle(current_title + " *")

    def _on_tab_changed(self, index: int) -> None:
        """OsvjeÅ¾i naimenovanja tab kada se aktivira â€” da uzme svjeÅ¾e kurs/trosak iz drafta."""
        current_widget = self.tabs_widget.widget(index)

        # Inicijalizuj LazyTab odmah u currentChanged, PRIJE nego Qt mjeri
        # veliÄinu sadrÅ¾aja. Ako Äekamo showEvent, prozor se skupi na prazni placeholder.
        if hasattr(current_widget, 'ensure_initialized'):
            inner = current_widget.ensure_initialized()
        else:
            inner = current_widget

        if current_widget is self.naimenovanje_tab:
            naim_view = getattr(inner, "view", None)
            if naim_view and hasattr(naim_view, "_load_current_item"):
                naim_view._load_current_item()

        elif current_widget is self.zaglavlje_tab:
            # Uzmi aktivni draft iz FakturaView (moÅ¾e biti split draft, ne nuÅ¾no self.draft)
            active_draft = self.draft
            faktura_view = getattr(self.faktura_tab, "view", self.faktura_tab)
            if faktura_view and hasattr(faktura_view, "draft"):
                active_draft = faktura_view.draft
            if hasattr(self.zaglavlje_tab, "load_from_draft"):
                self.zaglavlje_tab.load_from_draft(active_draft)

    def _on_draft_data_changed(self) -> None:
        """Poziva se kada se draft podaci promene - aÅ¾urira sve tabove koji treba da se osveÅ¾e."""
        # SaÄuvaj samo ref-ove iz UI tabele u draft (ne zamjenjuje listu â€” Äuva programatski dodane doc-ove)
        # Puni save_to_draft() bi OBRISAO novododane VET/SAN/FIT doc-ove koji joÅ¡ nisu vidljivi u UI.
        try:
            if hasattr(self.zaglavlje_tab, 'view'):
                table_data = self.zaglavlje_tab.view.get_data().get('attached_documents', [])
                ui_by_code = {d['code']: d for d in table_data if d.get('code')}
                header_docs = getattr(self.draft, 'header_attached_documents', None) or []
                # 1. AÅ¾uriraj ref-ove za unose koji veÄ‡ postoje u draftu
                for doc in header_docs:
                    if doc.code in ui_by_code:
                        doc.number = ui_by_code[doc.code].get('number', doc.number)
                # 2. Dodaj unose koje je korisnik ruÄno kreirao u UI (nisu joÅ¡ u draftu)
                existing_codes = {d.code for d in header_docs}
                from core.draft.draft import AttachedDocument
                for code, d in ui_by_code.items():
                    if code not in existing_codes:
                        header_docs.append(AttachedDocument(
                            code=code,
                            name=d.get('name', ''),
                            number=d.get('number', ''),
                            from_rule=d.get('from_rule', False),
                        ))
        except Exception as _e:
            logger.debug("Rebuild priloÅ¾enih dokumenata: %s", _e)
        # AÅ¾uriraj zaglavlje tab da odrazi promene u draft-u
        self.zaglavlje_tab.load_from_draft(self.draft)

        # Opciono aÅ¾uriraj druge tabove ako je potrebno
        # Za sada Ä‡emo samo aÅ¾urirati zaglavlje tab jer je to na Å¡ta se fokusiramo

        # OsveÅ¾i UI da se osigura da su sve promene prikazane
        self.zaglavlje_tab.update()

    def _restore_window_state(self) -> None:
        """Vrati geometriju i poziciju prozora iz prethodne sesije."""
        settings = QSettings("DeklarantPro", "MainWindow")

        # Vrati geometriju (pozicija + veliÄina)
        geometry = settings.value("geometry")
        if geometry:
            # PokuÅ¡aj da vratiÅ¡, ali validiraj veliÄinu
            success = self.restoreGeometry(geometry)

            if not success:
                self._center_on_primary_screen()
            elif not success:
                self._center_on_primary_screen()
        else:
            # Prvo pokretanje - centriraj prozor na primarnom ekranu
            self._center_on_primary_screen()

    def _center_on_primary_screen(self) -> None:
        """Centriraj prozor na primarnom ekranu."""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def showEvent(self, event) -> None:
        """SaÄuvaj geometriju kada se prozor prikaÅ¾e (backup za closeEvent)."""
        super().showEvent(event)

        # Samo pri prvom prikazivanju
        if getattr(self, '_first_show_done', False):
            return
        self._first_show_done = True

        # SaÄuvaj poÄetnu poziciju nakon prvog prikazivanja
        settings = QSettings("DeklarantPro", "MainWindow")
        if not settings.value("geometry"):
            settings.setValue("geometry", self.saveGeometry())
            settings.sync()

    def closeEvent(self, event) -> None:
        """SaÄuvaj stanje prozora pre zatvaranja."""
        settings = QSettings("DeklarantPro", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.sync()  # Prisili trenutno pisanje na disk
        super().closeEvent(event)

