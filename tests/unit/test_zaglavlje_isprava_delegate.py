from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem, QTableWidget

from gui.tabs.zaglavlje_view import IspravaDelegate


def test_exact_document_code_immediately_populates_name():
    app = QApplication.instance() or QApplication([])
    table = QTableWidget(1, 3)
    delegate = IspravaDelegate({"VOZ": "Vozarina do granice"}, table)
    index = table.model().index(0, 0)
    editor = delegate.createEditor(table.viewport(), QStyleOptionViewItem(), index)
    editor.show()
    editor.setFocus()

    QTest.keyClicks(editor, "voz")
    app.processEvents()

    assert editor.completer().completionCount() == 1
    assert editor.completer().currentCompletion() == "VOZ — Vozarina do granice"
    assert table.item(0, 1).text() == "Vozarina do granice"
