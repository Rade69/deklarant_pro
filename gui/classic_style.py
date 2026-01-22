"""
ASYCUDA Pro - Classic Windows Style System
Tačna replika originalnog dizajna
"""

from PySide6.QtGui import QColor, QFont


class ClassicColors:
    """Boje iz originalnog dizajna"""
    
    # Pozadine
    BACKGROUND_MAIN = "#f0f0f0"
    BACKGROUND_WHITE = "#ffffff"
    BACKGROUND_GREEN_LIGHT = "#f0fff0"
    BACKGROUND_GREEN_PANEL = "#e8f5e8"
    
    # Dugmad
    BUTTON_BACKGROUND = "#e0e0e0"
    BUTTON_HOVER = "#d0d0d0"
    BUTTON_PRESSED = "#c0c0c0"
    BUTTON_BORDER = "#999999"
    
    # Input polja
    INPUT_BACKGROUND = "#ffffff"
    INPUT_BORDER = "#999999"
    INPUT_FOCUS_BORDER = "#0078d7"
    
    # Tabela
    TABLE_HEADER_BG = "#0078d7"
    TABLE_HEADER_TEXT = "#ffffff"
    TABLE_ROW_EVEN = "#ffffff"
    TABLE_ROW_ODD = "#f5f5f5"
    TABLE_SELECTED = "#cce8ff"
    TABLE_BORDER = "#cccccc"
    
    # Tekst
    TEXT_PRIMARY = "#000000"
    TEXT_DISABLED = "#999999"


class ClassicFonts:
    """Fontovi iz originalnog dizajna"""
    
    @staticmethod
    def normal(size=11):
        """Standardni font - Arial 11px"""
        return QFont("Arial", size)
    
    @staticmethod
    def bold(size=11):
        """Bold font - Arial 11px Bold"""
        font = QFont("Arial", size)
        font.setBold(True)
        return font
    
    @staticmethod
    def small(size=9):
        """Mali font - Arial 9px"""
        return QFont("Arial", size)


class ClassicStyleSheet:
    """Qt StyleSheet za klasičan Windows izgled"""
    
    @staticmethod
    def get_main_window_style():
        """Stil za glavni prozor"""
        return f"""
            QMainWindow {{
                background-color: {ClassicColors.BACKGROUND_MAIN};
            }}
            
            QWidget {{
                background-color: {ClassicColors.BACKGROUND_MAIN};
                color: {ClassicColors.TEXT_PRIMARY};
                font-family: Arial;
                font-size: 11px;
            }}
        """
    
    @staticmethod
    def get_button_style():
        """Stil za dugmad"""
        return f"""
            QPushButton {{
                background-color: {ClassicColors.BUTTON_BACKGROUND};
                border: 1px solid {ClassicColors.BUTTON_BORDER};
                border-radius: 3px;
                padding: 6px 12px;
                min-height: 24px;
                font-family: Arial;
                font-size: 11px;
                color: {ClassicColors.TEXT_PRIMARY};
            }}
            
            QPushButton:hover {{
                background-color: {ClassicColors.BUTTON_HOVER};
            }}
            
            QPushButton:pressed {{
                background-color: {ClassicColors.BUTTON_PRESSED};
            }}
            
            QPushButton:disabled {{
                color: {ClassicColors.TEXT_DISABLED};
                background-color: {ClassicColors.BACKGROUND_MAIN};
            }}
        """
    
    @staticmethod
    def get_input_style():
        """Stil za input polja"""
        return f"""
            QLineEdit {{
                background-color: {ClassicColors.INPUT_BACKGROUND};
                border: 1px solid {ClassicColors.INPUT_BORDER};
                border-radius: 2px;
                padding: 4px;
                min-height: 22px;
                font-family: Arial;
                font-size: 11px;
                color: {ClassicColors.TEXT_PRIMARY};
            }}
            
            QLineEdit:focus {{
                border: 1px solid {ClassicColors.INPUT_FOCUS_BORDER};
            }}
            
            QLineEdit:disabled {{
                background-color: {ClassicColors.BACKGROUND_MAIN};
                color: {ClassicColors.TEXT_DISABLED};
            }}
            
            QTextEdit {{
                background-color: {ClassicColors.INPUT_BACKGROUND};
                border: 1px solid {ClassicColors.INPUT_BORDER};
                border-radius: 2px;
                padding: 4px;
                font-family: Arial;
                font-size: 11px;
                color: {ClassicColors.TEXT_PRIMARY};
            }}
            
            QTextEdit:focus {{
                border: 1px solid {ClassicColors.INPUT_FOCUS_BORDER};
            }}
        """
    
    @staticmethod
    def get_combobox_style():
        """Stil za dropdown liste"""
        return f"""
            QComboBox {{
                background-color: {ClassicColors.INPUT_BACKGROUND};
                border: 1px solid {ClassicColors.INPUT_BORDER};
                border-radius: 2px;
                padding: 4px;
                min-height: 22px;
                font-family: Arial;
                font-size: 11px;
                color: {ClassicColors.TEXT_PRIMARY};
            }}
            
            QComboBox:focus {{
                border: 1px solid {ClassicColors.INPUT_FOCUS_BORDER};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid {ClassicColors.TEXT_PRIMARY};
                margin-right: 6px;
            }}
        """
    
    @staticmethod
    def get_table_style():
        """Stil za tabele"""
        return f"""
            QTableWidget {{
                background-color: {ClassicColors.INPUT_BACKGROUND};
                border: 1px solid {ClassicColors.TABLE_BORDER};
                gridline-color: {ClassicColors.TABLE_BORDER};
                font-family: Arial;
                font-size: 11px;
                color: {ClassicColors.TEXT_PRIMARY};
            }}
            
            QTableWidget::item {{
                padding: 4px 6px;
                border: none;
            }}
            
            QTableWidget::item:selected {{
                background-color: {ClassicColors.TABLE_SELECTED};
                color: {ClassicColors.TEXT_PRIMARY};
            }}
            
            QHeaderView::section {{
                background-color: {ClassicColors.TABLE_HEADER_BG};
                color: {ClassicColors.TABLE_HEADER_TEXT};
                padding: 4px 6px;
                border: 1px solid {ClassicColors.TABLE_BORDER};
                font-family: Arial;
                font-size: 11px;
                font-weight: bold;
            }}
        """
    
    @staticmethod
    def get_tab_style():
        """Stil za tab widget"""
        return f"""
            QTabWidget::pane {{
                border: 1px solid {ClassicColors.BUTTON_BORDER};
                background-color: {ClassicColors.BACKGROUND_WHITE};
            }}
            
            QTabBar::tab {{
                background-color: {ClassicColors.BUTTON_BACKGROUND};
                border: 1px solid {ClassicColors.BUTTON_BORDER};
                border-bottom: none;
                padding: 6px 16px;
                min-height: 28px;
                font-family: Arial;
                font-size: 11px;
                color: {ClassicColors.TEXT_PRIMARY};
            }}
            
            QTabBar::tab:selected {{
                background-color: {ClassicColors.BACKGROUND_WHITE};
            }}
            
            QTabBar::tab:hover {{
                background-color: {ClassicColors.BUTTON_HOVER};
            }}
        """
    
    @staticmethod
    def get_checkbox_style():
        """Stil za checkbox-e"""
        return f"""
            QCheckBox {{
                font-family: Arial;
                font-size: 11px;
                color: {ClassicColors.TEXT_PRIMARY};
                spacing: 6px;
            }}
            
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {ClassicColors.BUTTON_BORDER};
                border-radius: 2px;
                background-color: {ClassicColors.INPUT_BACKGROUND};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {ClassicColors.INPUT_FOCUS_BORDER};
                border: 1px solid {ClassicColors.INPUT_FOCUS_BORDER};
            }}
        """
    
    @staticmethod
    def get_global_style():
        """Globalni stil za celu aplikaciju"""
        return (
            ClassicStyleSheet.get_main_window_style() +
            ClassicStyleSheet.get_button_style() +
            ClassicStyleSheet.get_input_style() +
            ClassicStyleSheet.get_combobox_style() +
            ClassicStyleSheet.get_table_style() +
            ClassicStyleSheet.get_tab_style() +
            ClassicStyleSheet.get_checkbox_style()
        )
