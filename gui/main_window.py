import os
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QTabWidget, QApplication, QMessageBox
from PySide6.QtCore import QFile, QTextStream, QIODevice

from asycuda_pro.core.draft import DeclarationDraft
from asycuda_pro.gui.tabs.naimenovanja_tab import NaimenovanjaTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ASYCUDA Pro")
        self.resize(1650, 890)

        # 1. Učitaj stilove koristeći preciznu putanju
        self.load_stylesheet()

        # 2. Inicijalizacija
        self.draft = DeclarationDraft()
        self.draft.ensure_min_items(1)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        self.naimenovanje_tab = NaimenovanjaTab(self.draft, on_dirty=self._on_dirty)
        tabs.addTab(self.naimenovanje_tab, "Naimenovanja")

    def load_stylesheet(self):
        """Učitava QSS stil iz styles foldera."""
        # Definišemo apsolutnu putanju koju si mi dao
        style_path = "/home/radovan/Desktop/PythonProjects/asycuda_pro/styles/asycuda_modern_material.qss"

        if os.path.exists(style_path):
            file = QFile(style_path)
            if file.open(QIODevice.ReadOnly | QIODevice.Text):
                stream = QTextStream(file)
                style_content = stream.readAll()
                file.close()

                # Primjenjujemo na nivou aplikacije
                QApplication.instance().setStyleSheet(style_content)
                print(f"✅ Stil uspješno primijenjen iz: {style_path}")
            else:
                print(f"❌ Fajl postoji, ali se ne može otvoriti.")
        else:
            error_msg = f"Nisam pronašao stil na putanji:\n{style_path}"
            print(f"⚠️ {error_msg}")
            QMessageBox.warning(self, "Greška", error_msg)

    def _on_dirty(self) -> None:
        current_title = self.windowTitle()
        if not current_title.endswith("*"):
            self.setWindowTitle(current_title + " *")
