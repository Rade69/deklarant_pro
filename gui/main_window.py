import os
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QTabWidget, QApplication, QMessageBox
from PySide6.QtCore import QFile, QTextStream, QIODevice, QSettings

from config.settings import get_path_settings

from core.draft import DeclarationDraft
from gui.tabs.tab_factory import get_tab_factory
from gui.tabs.admin_tab import AdminTab
from gui.tabs.agent_tab import AgentTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ASYCUDA Pro")

        # Postavi podrazumevanu veličinu (80% Full HD 1920x1080)
        self.resize(1536, 823)

        # Postavi maksimalnu širinu da spreči window manager da je napravi preširoku
        self.setMaximumWidth(1650)

        # Vrati geometriju prozora iz prethodne sesije
        self._restore_window_state()

        # 1. Učitaj stilove
        self.load_stylesheet()

        # 2. Inicijalizacija draft-a
        self.draft = DeclarationDraft()
        self.draft.ensure_min_items(1)

        # 3. Kreiranje tabova (redosled: Faktura, Zaglavlje, Naimenovanja, Šifrarnici)
        tabs = QTabWidget()

        # Omogući responsive resizing za tab widget
        from PySide6.QtWidgets import QSizePolicy
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Font za tab kartice (stilovi su u main_tabs.qss — bez inline setStyleSheet koji bi kreirao QSS bubble)
        from PySide6.QtGui import QFont
        tabs.setFont(QFont("Arial", 16, QFont.Bold))

        self.setCentralWidget(tabs)

        # Kreiranje tabova koristeći TabFactory
        tab_factory = get_tab_factory()
        
        # Faktura tab (Refaktorisan - 3-layer arhitektura)
        self.faktura_tab = tab_factory.create_tab('faktura', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.faktura_tab, "📄 Faktura")

        # Naimenovanja tab (rubrike 31-46)
        self.naimenovanje_tab = tab_factory.create_tab('naimenovanja', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.naimenovanje_tab, "📦 Naimenovanja")

        # Zaglavlje tab (rubrike 1-49)
        self.zaglavlje_tab = tab_factory.create_tab('zaglavlje', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.zaglavlje_tab, "🗂️ Zaglavlje")

        # Šifrarnici tab
        self.sifarnici_tab = tab_factory.create_tab('sifarnici', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.sifarnici_tab, "📋 Šifrarnici")

        # Admin tab (novi - plugin manager, settings, database, analytics, logs, system info)
        self.admin_tab = AdminTab(self)
        tabs.addTab(self.admin_tab, "⚙️ Admin")

        # Agent tab (novi - AI agent za automatsko procesiranje faktura)
        self.agent_tab = AgentTab(
            self,
            draft=self.draft,
            faktura_tab=self.faktura_tab,
            naimenovanje_tab=self.naimenovanje_tab,
            zaglavlje_tab=self.zaglavlje_tab,
        )
        tabs.addTab(self.agent_tab, "🤖 Agent")

        # Postavi Admin Tab kao trenutni tab za testiranje (opciono - za development)
        # tabs.setCurrentWidget(self.admin_tab)

        # Registruj callback da ažurira sve tabove kada se draft podaci promene
        self.draft.register_data_change_callback(self._on_draft_data_changed)

        # Osvježi naimenovanja izračune (Rb.44/46) kad se tab aktivira
        self.tabs_widget = tabs
        tabs.currentChanged.connect(self._on_tab_changed)

    def load_stylesheet(self):
        """
        Učitaj sve QSS stilove u ispravnom redosledu.
        Redosled je bitan: kasniji stilovi mogu da pregaze ranije.
        """
        # Stil fajlovi u redosledu učitavanja
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
            "unified_color_system.qss",  # Unificirana paleta boja (najviši prioritet)
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
        """Osvježi naimenovanja tab kada se aktivira — da uzme svježe kurs/trosak iz drafta."""
        current_widget = self.tabs_widget.widget(index)
        if current_widget is self.naimenovanje_tab:
            # Pozovi refresh na naimenovanja view da ponovo izračuna Rb.44 i Rb.46
            naim_view = getattr(self.naimenovanje_tab, "view", None)
            if naim_view and hasattr(naim_view, "_load_current_item"):
                naim_view._load_current_item()

    def _on_draft_data_changed(self) -> None:
        """Poziva se kada se draft podaci promene - ažurira sve tabove koji treba da se osveže."""
        # Ažuriraj zaglavlje tab da odrazi promene u draft-u
        self.zaglavlje_tab.load_from_draft(self.draft)

        # Opciono ažuriraj druge tabove ako je potrebno
        # Za sada ćemo samo ažurirati zaglavlje tab jer je to na šta se fokusiramo

        # Osveži UI da se osigura da su sve promene prikazane
        self.zaglavlje_tab.update()

    def _restore_window_state(self) -> None:
        """Vrati geometriju i poziciju prozora iz prethodne sesije."""
        settings = QSettings("AsycudaPro", "MainWindow")

        # Vrati geometriju (pozicija + veličina)
        geometry = settings.value("geometry")
        if geometry:
            # Pokušaj da vratiš, ali validiraj veličinu
            success = self.restoreGeometry(geometry)

            # Proveri da li je vraćena veličina preširoka ili pogrešna visina (odbaci stare podešavanja)
            MAX_WIDTH = 1650  # Maksimalna prihvatljiva širina
            CORRECT_HEIGHT = 823  # Ispravna visina
            if self.width() > MAX_WIDTH or self.height() != CORRECT_HEIGHT:
                self.resize(1536, 823)  # Prisili ispravnu veličinu
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
        """Sačuvaj geometriju kada se prozor prikaže (backup za closeEvent)."""
        super().showEvent(event)

        # PRISILI veličinu nakon što se prozor prikaže (u slučaju da window manager pregazi)
        MAX_WIDTH = 1650
        CORRECT_HEIGHT = 823
        if self.width() > MAX_WIDTH or self.height() != CORRECT_HEIGHT:
            self.resize(1536, 823)
            self._center_on_primary_screen()

        # Sačuvaj početnu poziciju nakon prvog prikazivanja
        settings = QSettings("AsycudaPro", "MainWindow")
        if not settings.value("geometry"):
            settings.setValue("geometry", self.saveGeometry())
            settings.sync()  # Prisili trenutno pisanje

    def closeEvent(self, event) -> None:
        """Sačuvaj stanje prozora pre zatvaranja."""
        settings = QSettings("AsycudaPro", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.sync()  # Prisili trenutno pisanje na disk
        super().closeEvent(event)
