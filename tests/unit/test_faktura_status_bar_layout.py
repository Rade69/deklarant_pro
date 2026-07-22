from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from gui.tabs.faktura_view import FakturaView


def test_status_bar_odvaja_sazetak_i_umanjuje_assembly():
    app = QApplication.instance() or QApplication([])
    view = MagicMock()

    container = FakturaView._create_status_bar(view)
    layout = container.layout()

    assert container.height() == 42
    assert view.lbl_validation.objectName() == "validationStatus"
    assert view.lbl_assembly.objectName() == "secondaryMetric"
    assert view.lbl_analysis.objectName() == "analysisSummary"
    assert layout.indexOf(view.lbl_analysis) > layout.indexOf(view.lbl_assembly)
    assert layout.itemAt(layout.indexOf(view.lbl_analysis) - 2).spacerItem() is not None
    assert app is not None
