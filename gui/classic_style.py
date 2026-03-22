"""
ASYCUDA Pro - Classic Style
Definicije boja i fontova za klasičan izgled
"""

from PySide6.QtGui import QFont, QColor


class ClassicColors:
    """Klasične ASYCUDA boje"""
    BACKGROUND = QColor(240, 240, 240)
    TEXT = QColor(0, 0, 0)
    BORDER = QColor(128, 128, 128)
    HEADER_BG = QColor(220, 220, 220)
    GRID_LINE = QColor(200, 200, 200)


class ClassicFonts:
    """Klasični ASYCUDA fontovi"""

    @staticmethod
    def normal():
        """Standardni font"""
        font = QFont("Arial", 12)
        return font

    @staticmethod
    def bold():
        """Bold font"""
        font = QFont("Arial", 12)
        font.setBold(True)
        return font

    @staticmethod
    def small():
        """Mali font"""
        font = QFont("Arial", 11)
        return font
