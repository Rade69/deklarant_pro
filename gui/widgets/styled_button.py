"""
Deklarant Pro - Styled Button System
5 button categories according to UI/UX proposal
"""

from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize
from enum import Enum


class ButtonType(Enum):
    """
    5 button categories:
    1. PRIMARY - Main action (green) - ONLY 1 per screen
    2. NAVIGATION - Movement (blue) - Safe, no risk
    3. SECONDARY - Optional actions (neutral gray)
    4. DESTRUCTIVE - Deletion (red) - Warning!
    5. ASSIST - Smart automation (purple)
    """
    PRIMARY = "btn_primary"
    NAVIGATION = "btn_navigation"
    SECONDARY = "btn_secondary"
    DESTRUCTIVE = "btn_destructive"
    ASSIST = "btn_assist"


class StyledButton(QPushButton):
    """
    Button with predefined styling category.

    Usage:
        # Method 1: Direct
        btn = StyledButton("Save", ButtonType.PRIMARY, icon="💾")

        # Method 2: Helper functions
        btn = PrimaryButton("Save", icon="💾")
        btn = NavigationButton(">>")
        btn = DestructiveButton("Delete", icon="🗑")

    Args:
        text: Button text
        button_type: One of ButtonType enum values
        icon: Either emoji string or path to icon file
        parent: Parent widget
    """

    def __init__(
        self,
        text: str,
        button_type: ButtonType = ButtonType.SECONDARY,
        icon: str = None,
        parent=None
    ):
        super().__init__(text, parent)

        # Set CSS class based on button type
        self.setProperty("class", button_type.value)

        # Add icon if provided
        if icon:
            # If it's a short string (emoji), prepend to text
            if len(icon) <= 2:
                self.setText(f"{icon} {text}")
            # If it's a file path, load as QIcon
            else:
                self.setIcon(QIcon(icon))
                self.setIconSize(QSize(16, 16))

        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)

    def setButtonType(self, button_type: ButtonType):
        """Change button type/category"""
        self.setProperty("class", button_type.value)
        self.style().unpolish(self)
        self.style().polish(self)


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS - Quick button creation
# ═══════════════════════════════════════════════════════════════

def PrimaryButton(text: str, icon: str = None, parent=None) -> StyledButton:
    """
    Create PRIMARY button (green).
    Use for: Main action - ONLY 1 per screen!
    Examples: Save, Submit, OK
    """
    return StyledButton(text, ButtonType.PRIMARY, icon, parent)


def NavigationButton(text: str, icon: str = None, parent=None) -> StyledButton:
    """
    Create NAVIGATION button (blue).
    Use for: Movement, no data risk
    Examples: <<, <, >, >>, Next, Previous
    """
    return StyledButton(text, ButtonType.NAVIGATION, icon, parent)


def SecondaryButton(text: str, icon: str = None, parent=None) -> StyledButton:
    """
    Create SECONDARY button (neutral gray).
    Use for: Optional actions
    Examples: New, Open, Export, Cancel
    """
    return StyledButton(text, ButtonType.SECONDARY, icon, parent)


def DestructiveButton(text: str, icon: str = None, parent=None) -> StyledButton:
    """
    Create DESTRUCTIVE button (red).
    Use for: Deletion, dangerous actions
    Examples: Delete, Remove, Clear All
    """
    return StyledButton(text, ButtonType.DESTRUCTIVE, icon, parent)


def AssistButton(text: str, icon: str = None, parent=None) -> StyledButton:
    """
    Create ASSIST button (purple).
    Use for: Smart automation, AI helpers
    Examples: Auto Calculate, Fill From..., Convert
    """
    return StyledButton(text, ButtonType.ASSIST, icon, parent)
