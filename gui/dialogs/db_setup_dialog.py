# gui/dialogs/db_setup_dialog.py
"""
Dialog za konfiguraciju baze podataka pri prvom pokretanju.

Prikazuje se kad:
  - .env fajl ne postoji, ili
  - konekcija na bazu ne uspije

Korisnik unosi host, port, ime baze, korisnika i lozinku,
testira konekciju i snima u .env fajl.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QFrame,
    QRadioButton, QButtonGroup, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor, QPalette

# Putanja do .env fajla
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


# ─────────────────────────────────────────────────────────────
# Worker za test konekcije u pozadini (ne blokira UI)
# ─────────────────────────────────────────────────────────────

class _ConnectionWorker(QObject):
    finished = Signal(bool, str)  # (uspjeh, poruka)

    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        super().__init__()
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password

    def run(self):
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=5,
            )
            version = conn.server_version
            conn.close()
            major = version // 10000
            minor = (version % 10000) // 100
            self.finished.emit(True, f"PostgreSQL {major}.{minor}")
        except Exception as e:
            self.finished.emit(False, str(e))


# ─────────────────────────────────────────────────────────────
# Glavni dialog
# ─────────────────────────────────────────────────────────────

class DbSetupDialog(QDialog):
    """
    Dialog za postavljanje konekcije na bazu podataka.
    Prikazuje se pri prvom pokretanju ili ako konekcija ne uspije.
    """

    def __init__(self, error_msg: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deklarant Pro — Podešavanje baze podataka")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._thread: Optional[QThread] = None
        self._worker: Optional[_ConnectionWorker] = None
        self._connection_ok = False
        self._build_ui(error_msg)

    # ─────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────

    def _build_ui(self, error_msg: Optional[str]):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Naslov
        title = QLabel("Podešavanje baze podataka")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Poruka o grešci (ako postoji)
        if error_msg:
            err_frame = QFrame()
            err_frame.setStyleSheet(
                "QFrame { background: #fff0f0; border: 1px solid #e74c3c; border-radius: 4px; padding: 4px; }"
            )
            err_layout = QVBoxLayout(err_frame)
            err_layout.setContentsMargins(10, 8, 10, 8)
            err_label = QLabel(f"Greška pri konekciji:\n{error_msg}")
            err_label.setStyleSheet("color: #c0392b; font-size: 12px;")
            err_label.setWordWrap(True)
            err_layout.addWidget(err_label)
            layout.addWidget(err_frame)

        # Izbor tipa instalacije
        type_label = QLabel("Tip instalacije:")
        type_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(type_label)

        self._btn_local = QRadioButton("Lokalna instalacija — baza na ovom računaru (localhost)")
        self._btn_server = QRadioButton("Server instalacija — baza na mreži (Ubuntu Server)")
        self._btn_local.setChecked(True)

        self._type_group = QButtonGroup(self)
        self._type_group.addButton(self._btn_local, 0)
        self._type_group.addButton(self._btn_server, 1)
        self._btn_local.toggled.connect(self._on_type_changed)

        layout.addWidget(self._btn_local)
        layout.addWidget(self._btn_server)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #ddd;")
        layout.addWidget(sep)

        # Forma za unos
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._host = QLineEdit("localhost")
        self._host.setPlaceholderText("npr. 192.168.1.100 ili localhost")
        form.addRow("Host / IP:", self._host)

        self._port = QLineEdit("5432")
        self._port.setMaximumWidth(80)
        form.addRow("Port:", self._port)

        self._dbname = QLineEdit("deklarant_pro")
        form.addRow("Ime baze:", self._dbname)

        self._user = QLineEdit("postgres")
        form.addRow("Korisnik:", self._user)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Lozinka za PostgreSQL")
        form.addRow("Lozinka:", self._password)

        layout.addLayout(form)

        # Status label
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setMinimumHeight(24)
        layout.addWidget(self._status)

        # Dugmad
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_test = QPushButton("Testiraj konekciju")
        self._btn_test.setMinimumHeight(34)
        self._btn_test.clicked.connect(self._test_connection)

        self._btn_save = QPushButton("Snimi i nastavi")
        self._btn_save.setMinimumHeight(34)
        self._btn_save.setEnabled(False)
        self._btn_save.setStyleSheet(
            "QPushButton { background: #2980b9; color: white; border-radius: 4px; font-weight: bold; }"
            "QPushButton:disabled { background: #bdc3c7; color: #7f8c8d; }"
            "QPushButton:hover { background: #3498db; }"
        )
        self._btn_save.clicked.connect(self._save_and_accept)

        btn_row.addWidget(self._btn_test)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_save)
        layout.addLayout(btn_row)

        # Napomena
        note = QLabel(
            "Podaci se snimaju u .env fajl u folderu aplikacije.\n"
            "Lozinka se čuva u plain-text formatu — zaštiti pristup fajlu."
        )
        note.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # Popuni iz postojećeg .env ako postoji
        self._load_existing_env()

    # ─────────────────────────────────────────────────
    # Logika
    # ─────────────────────────────────────────────────

    def _on_type_changed(self, checked: bool):
        if self._btn_local.isChecked():
            self._host.setText("localhost")
            self._user.setText("postgres")
        else:
            current = self._host.text()
            if current == "localhost":
                self._host.setText("")
                self._host.setPlaceholderText("npr. 192.168.1.100")
            self._user.setText("deklarant_app")
        self._btn_save.setEnabled(False)
        self._connection_ok = False
        self._status.setText("")

    def _load_existing_env(self):
        """Popuni formu iz postojećeg .env ako postoji."""
        if not _ENV_PATH.exists():
            return
        mapping = {}
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                mapping[key.strip()] = val.strip()

        host = mapping.get("DB_HOST", "localhost")
        # Unix socket putanja → tretiramo kao localhost
        if host.startswith("/"):
            host = "localhost"
        self._host.setText(host)
        self._port.setText(mapping.get("DB_PORT", "5432"))
        self._dbname.setText(mapping.get("DB_NAME", "deklarant_pro"))
        self._user.setText(mapping.get("DB_USER", "postgres"))
        self._password.setText(mapping.get("DB_PASSWORD", ""))

        if host != "localhost":
            self._btn_server.setChecked(True)

    def _test_connection(self):
        self._btn_test.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._connection_ok = False
        self._set_status("Testiranje konekcije...", "gray")

        host = self._host.text().strip()
        port_text = self._port.text().strip()
        dbname = self._dbname.text().strip()
        user = self._user.text().strip()
        password = self._password.text()

        if not all([host, port_text, dbname, user]):
            self._set_status("Popuni sva polja.", "red")
            self._btn_test.setEnabled(True)
            return

        try:
            port = int(port_text)
        except ValueError:
            self._set_status("Port mora biti broj (npr. 5432).", "red")
            self._btn_test.setEnabled(True)
            return

        # Pokrenuti u QThread da ne blokira UI
        self._thread = QThread()
        self._worker = _ConnectionWorker(host, port, dbname, user, password)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_connection_result)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_connection_result(self, success: bool, message: str):
        self._btn_test.setEnabled(True)
        if success:
            self._connection_ok = True
            self._set_status(f"Konekcija uspješna ({message})", "green")
            self._btn_save.setEnabled(True)
        else:
            self._connection_ok = False
            self._set_status(f"Konekcija nije uspjela:\n{message}", "red")
            self._btn_save.setEnabled(False)

    def _save_and_accept(self):
        if not self._connection_ok:
            return
        self._write_env()
        self.accept()

    def _write_env(self):
        """Snimi konfiguraciju u .env fajl."""
        host = self._host.text().strip()
        port = self._port.text().strip()
        dbname = self._dbname.text().strip()
        user = self._user.text().strip()
        password = self._password.text()

        # Pročitaj postojeći .env da sačuvamo API ključeve i ostalo
        existing: dict[str, str] = {}
        if _ENV_PATH.exists():
            for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    existing[key.strip()] = val.strip()

        # Ažuriraj DB parametre
        existing["DB_HOST"] = host
        existing["DB_PORT"] = port
        existing["DB_NAME"] = dbname
        existing["DB_USER"] = user
        existing["DB_PASSWORD"] = password

        # Zapiši nazad
        lines = [
            "# Deklarant Pro - Konfiguracija baze podataka",
            f"DB_HOST={existing.pop('DB_HOST')}",
            f"DB_PORT={existing.pop('DB_PORT')}",
            f"DB_NAME={existing.pop('DB_NAME')}",
            f"DB_USER={existing.pop('DB_USER')}",
            f"DB_PASSWORD={existing.pop('DB_PASSWORD')}",
            "",
        ]
        # Ostale vrijednosti iz existing (API ključevi, itd.)
        skip = {"DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"}
        for key, val in existing.items():
            if key not in skip:
                lines.append(f"{key}={val}")

        _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _set_status(self, text: str, color: str):
        colors = {
            "green": "#27ae60",
            "red": "#c0392b",
            "gray": "#7f8c8d",
        }
        self._status.setStyleSheet(f"color: {colors.get(color, '#000')};")
        self._status.setText(text)


# ─────────────────────────────────────────────────────────────
# Helper funkcija za poziv iz app/run.py
# ─────────────────────────────────────────────────────────────

def check_and_setup_db(app) -> bool:
    """
    Provjeri konekciju na bazu. Ako ne uspije, prikaži setup dialog.

    Returns:
        True  — konekcija OK, aplikacija može da nastavi
        False — korisnik je zatvorio dialog bez snimanja
    """
    # Pokušaj konekciju
    error_msg = _try_connect()
    if error_msg is None:
        return True  # Sve OK

    # Konekcija nije uspjela — prikaži dialog
    dialog = DbSetupDialog(error_msg=error_msg)
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        # Reload .env i ponovo inicijalizuj settings
        _reload_settings()
        return True

    return False


def _try_connect() -> Optional[str]:
    """
    Pokuša da se spoji na bazu. Vraća None ako je OK, poruku greške ako nije.
    """
    try:
        # Resetuj singleton da pokupi eventualno novi .env
        _reload_settings()
        from database.db import get_db_connection
        with get_db_connection() as conn:
            conn.cursor().execute("SELECT 1")
        return None
    except Exception as e:
        return str(e)


def _reload_settings():
    """Resetuj settings singleton da pokupi promjene iz .env."""
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH, override=True)

    import config.settings as s
    s._db_settings = None
    import database.db as db
    if db._connection_pool is not None:
        try:
            db._connection_pool.closeall()
        except Exception:
            pass
        db._connection_pool = None
