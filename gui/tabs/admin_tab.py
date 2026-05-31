"""
Admin Tab - Central admin panel for Deklarant Pro.

Ovaj tab pruža pristup svim admin funkcionalnostima:
- Plugin Manager
- Settings
- Database Management
- Logs
- System Info
- Analytics
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from gui.tabs.admin.admin_view import AdminView
from gui.tabs.admin.admin_controller import AdminController
from services.admin.admin_service import AdminService


class AdminTab(QWidget):
    """
    Admin Tab - wrapper around 3-layer architecture.

    Ovaj tab ne prima Draft niti on_dirty callback jer je
    admin funkcionalnost nezavisna od deklaracija.
    """

    def __init__(self, parent=None):
        """
        Inicijalizacija Admin Tab-a.

        Args:
            parent: Parent widget (MainWindow)
        """
        super().__init__(parent)

        # Setup layers
        self._setup_layers()

        # Setup UI
        self._setup_ui()

    def _setup_layers(self):
        """Kreiraj View/Controller/Service layer-e."""
        # Service layer (business logic)
        self.service = AdminService()

        # View layer (UI)
        self.view = AdminView(parent=self)

        # Controller layer (orchestration)
        self.controller = AdminController(self.view, self.service)

    def _setup_ui(self):
        """Setup glavnog layout-a."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
