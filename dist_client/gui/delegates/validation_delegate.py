"""
Validation Delegate for FakturaTabV2

Custom QStyledItemDelegate that renders validation colors for table cells.
Overrides the paint method to draw background colors based on validation state.
"""

from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QFont


class ValidationDelegate(QStyledItemDelegate):
    """
    Custom delegate that renders background colors based on validation state.

    Uses Qt.UserRole to store validation color for each row.
    Respects selection state and uses appropriate selection colors.
    """

    # Define custom role for storing validation color
    ValidationColorRole = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        """
        Create editor with larger font for better readability.

        Args:
            parent: Parent widget
            option: QStyleOptionViewItem
            index: QModelIndex

        Returns:
            QWidget editor
        """
        editor = super().createEditor(parent, option, index)

        # Set larger font for editor (čitljiv font za editovanje)
        if editor:

            # VAŽNO: Koristi px umjesto pt, i setuj PRIJE stylesheet-a!
            # Povećaj visinu editora direktno
            editor.setMinimumHeight(38)  # Optimalna visina

            # Dodaj vizualni highlight za edit mode SA ČITLJIVIM FONTOM
            # KRITIČNO: Koristi px a ne pt za font-size!
            # Font size: 14px - čitljiv ali stane u sve kolone
            stylesheet = """
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #E3F2FD;
                    border: 1px solid #2196F3;
                    padding: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    color: #000000;
                    selection-background-color: #1976D2;
                    selection-color: white;
                    min-height: 38px;
                }
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                    background-color: #FFFFFF;
                    border: 2px solid #2196F3;
                    font-size: 15px;
                }
            """
            editor.setStyleSheet(stylesheet)

        return editor

    def paint(self, painter, option, index):
        """
        Override paint to draw custom background color while respecting selection.

        Args:
            painter: QPainter instance
            option: QStyleOptionViewItem with style info
            index: QModelIndex for the item being painted
        """
        # Povećaj font za display text
        font = QFont()
        font.setPointSize(12)  # Čitljiv font za prikaz
        option.font = font

        # Check if item is selected
        is_selected = option.state & QStyle.State_Selected

        if is_selected:
            # Use system selection color when item is selected
            super().paint(painter, option, index)
        else:
            # Get validation color from item data
            color_data = index.data(self.ValidationColorRole)

            if color_data:
                bg = QColor(color_data)
                # Postavi Base i AlternateBase na istu boju da Qt ne prepiše
                # naš custom fill alternating bojom pri super().paint()
                option.palette.setColor(QPalette.Base, bg)
                option.palette.setColor(QPalette.AlternateBase, bg)
                painter.save()
                painter.fillRect(option.rect, bg)
                painter.restore()

            # Call base implementation to draw text and other elements
            super().paint(painter, option, index)