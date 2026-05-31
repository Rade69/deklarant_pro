"""
Theme Manager - Centralizovano upravljanje temama
"""

from typing import Dict, Optional


class ThemeManager:
    """Centralizovano upravljanje temama"""

    _instance = None
    _theme: Dict

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._theme = cls._load_theme()
        return cls._instance

    @staticmethod
    def _load_theme() -> Dict:
        """Učitava temu iz konfiguracije"""
        return {
            "colors": {
                "glavna": "#E3F2FD",
                "uvezi": "#E8F5E9",
                "uredi": "#FFF9C4",
                "izvezi": "#FFE0B2",
                "smart": "#F3E5F5",
                "valid": "#ccffcc",
                "warning": "#ffffcc",
                "error": "#ffcccc",
                "unmatched": "#cce5ff",
            },
            "fonts": {
                "header": "17px",
                "toolbar": "13px",
                "table": "10pt",
            },
            "border_radius": 6,
        }

    def get_color(self, name: str) -> str:
        """Dobij boju po imenu"""
        return self._theme["colors"].get(name, "#ffffff")

    def get_font(self, name: str) -> str:
        """Dobij font po imenu"""
        return self._theme["fonts"].get(name, "10pt")

    def get_border_radius(self) -> int:
        """Dobij radius za zaobljenje"""
        return self._theme["border_radius"]

    def set_color(self, name: str, value: str) -> None:
        """Postavi boju"""
        self._theme["colors"][name] = value

    def set_font(self, name: str, value: str) -> None:
        """Postavi font"""
        self._theme["fonts"][name] = value

    def set_border_radius(self, value: int) -> None:
        """Postavi radius za zaobljenje"""
        self._theme["border_radius"] = value
