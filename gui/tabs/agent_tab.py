"""
Agent Tab - wrapper.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from gui.tabs.agent.agent_view import AgentView
from gui.tabs.agent.agent_controller import AgentController


class AgentTab(QWidget):
    """Agent Tab wrapper sa podrškom za tri pipeline moda."""

    def __init__(self, parent=None, draft=None, faktura_tab=None,
                 naimenovanje_tab=None, zaglavlje_tab=None):
        super().__init__(parent)
        self._parent = parent  # MainWindow referenca
        self._draft = draft
        self._faktura_tab = faktura_tab
        self._naimenovanje_tab = naimenovanje_tab
        self._zaglavlje_tab = zaglavlje_tab
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI - kreira view i controller."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = AgentView(parent=self)
        self.controller = AgentController(
            self.view,
            draft=self._draft,
            faktura_tab=self._faktura_tab,
            naimenovanje_tab=self._naimenovanje_tab,
            zaglavlje_tab=self._zaglavlje_tab,
        )
        layout.addWidget(self.view)

    def otvori_faktura_tab(self):
        """
        Otvori Faktura tab i prikaži uvezene podatke.

        Poziva se nakon uspješnog procesiranja u režimu 'Uvezi u deklaraciju'.
        """
        if self._parent and self._faktura_tab:
            # Nađi tabs widget i prebaci na Faktura tab
            tabs_widget = self._parent.findChild(QWidget, "tabs")
            if tabs_widget:
                tabs_widget.setCurrentWidget(self._faktura_tab)
                
                # Ažuriraj podatke iz draft-a
                try:
                    faktura_view = self._faktura_tab
                    if hasattr(self._faktura_tab, 'view'):
                        faktura_view = self._faktura_tab.view
                    if hasattr(faktura_view, '_load_data_from_draft'):
                        faktura_view._load_data_from_draft()
                    print(f"[AgentTab] ✅ Otvoren Faktura tab sa uvezenim podacima")
                except Exception as e:
                    print(f"[AgentTab] ⚠️ Greška pri učitavanju: {e}")
