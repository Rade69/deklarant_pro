from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

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


def test_faktura_tabela_ima_jasnu_hijerarhiju_redova():
    app = QApplication.instance() or QApplication([])
    view = MagicMock()

    table = FakturaView._create_table(view)
    style = table.styleSheet().lower()

    assert table.alternatingRowColors() is True
    assert table.hasMouseTracking() is True
    assert table.selectionBehavior() == QAbstractItemView.SelectRows
    assert "alternate-background-color: #eef4f7" in style
    assert "qtablewidget::item:hover:!selected" in style
    assert "background-color: #2c668f" in style
    assert "border-bottom: 2px solid #557d9a" in style
    assert app is not None


def test_blok_masa_ima_poravnata_polja_i_razmak_do_provjere():
    app = QApplication.instance() or QApplication([])
    view = MagicMock()
    view._create_button.side_effect = lambda text, *_args, **_kwargs: QPushButton(text)
    host = QWidget()
    layout = QHBoxLayout(host)

    FakturaView._populate_toolbar_section(view, layout, 3)

    panel = host.findChild(QWidget, "massControlsPanel")
    panel_layout = panel.layout()
    assert view.input_bruto.objectName() == "massInput"
    assert view.input_neto.objectName() == "massInput"
    assert view.input_bruto.height() == 26
    assert view.input_neto.height() == 26
    assert view.input_bruto.alignment() & Qt.AlignRight
    assert panel_layout.spacing() == 8
    assert panel_layout.contentsMargins().left() == 2
    assert app is not None
