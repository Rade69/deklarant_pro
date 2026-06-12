"""Runtime skaliranje GUI-a prema veličini ekrana na kojem je prozor.

QT_SCALE_FACTOR (Qt env varijabla) postavlja se samo JEDNOM, prije
QApplication, i ne može se promijeniti u toku rada — pa kad korisnik
prebaci prozor na drugi monitor (npr. mali laptop ekran <-> veliki
eksterni monitor), Qt ostaje na startnom faktoru.

ScaleManager rješava to runtime preskaliranjem: smanji/vrati font cijele
aplikacije i registrovane fiksne veličine widgeta kad se prozor pojavi na
ekranu druge logičke širine. MainWindow poziva apply_scale() iz
screenChanged handlera.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

# Logička širina (px) koju zahtijeva najširi toolbar (Faktura tab, mjereno
# minimumSizeHint ≈ 2057px).
REFERENCE_WIDTH = 2060

# Ne dozvoli da font padne ispod ovog faktora — ostaje čitljiv.
MIN_SCALE = 0.6


class ScaleManager:
    """Singleton koji prati trenutni scale faktor cijele aplikacije."""

    _instance: Optional["ScaleManager"] = None

    def __init__(self, app: QApplication) -> None:
        self._app = app
        base_font = app.font()
        self._base_family = base_font.family()
        self._base_point_size = base_font.pointSizeF()
        self._scale = 1.0
        # widget -> (bazna_sirina, bazna_visina) u 100% pikselima
        self._fixed_widgets: dict[QWidget, tuple[Optional[int], Optional[int]]] = {}

    @classmethod
    def init(cls, app: QApplication) -> "ScaleManager":
        cls._instance = cls(app)
        return cls._instance

    @classmethod
    def instance(cls) -> Optional["ScaleManager"]:
        return cls._instance

    @property
    def scale(self) -> float:
        return self._scale

    def scale_for_width(self, available_width: int) -> float:
        """Vrati faktor skaliranja potreban da toolbar stane u zadatu
        logičku širinu ekrana (1.0 = bez skaliranja)."""
        if available_width <= 0:
            return 1.0
        return max(MIN_SCALE, min(1.0, available_width / REFERENCE_WIDTH))

    def register_fixed_size(
        self,
        widget: QWidget,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> None:
        """Registruj widget čiji su setFixedWidth/Height zadati u BAZNIM
        (100%) pikselima i odmah primijeni trenutni scale na njega."""
        self._fixed_widgets[widget] = (width, height)
        self._apply_fixed_size(widget, width, height)

    def apply_scale(self, scale: float) -> None:
        """Primijeni novi faktor skaliranja na font aplikacije i sve
        registrovane fiksne widgete. Bez efekta ako se faktor nije
        promijenio."""
        scale = max(MIN_SCALE, min(1.0, scale))
        if abs(scale - self._scale) < 0.005:
            return
        self._scale = scale

        font = QFont(self._base_family)
        font.setPointSizeF(max(1.0, self._base_point_size * scale))
        self._app.setFont(font)

        for widget, (w, h) in list(self._fixed_widgets.items()):
            self._apply_fixed_size(widget, w, h)

        self._repolish_and_relayout()

    def _repolish_and_relayout(self) -> None:
        """Forsiraj Qt da ponovo izračuna sizeHint/minimumSizeHint nakon
        promjene fonta.

        QApplication.setFont() šalje FontChange rekurzivno djeci
        top-level widgeta, ali QPushButton (i slični widgeti) keširaju
        svoj sizeHint i ne osvježavaju ga na taj event — samo
        unpolish()/polish() forsira ponovno računanje. Bez ovoga toolbar
        ostaje "zaleđen" na staroj (100%) veličini i ne stane na manji
        ekran.
        """
        for widget in self._app.allWidgets():
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            layout = widget.layout()
            if layout is not None:
                layout.invalidate()

        for top in self._app.topLevelWidgets():
            layout = top.layout()
            if layout is not None:
                layout.activate()

    def _apply_fixed_size(
        self, widget: QWidget, w: Optional[int], h: Optional[int]
    ) -> None:
        if w is not None:
            widget.setFixedWidth(round(w * self._scale))
        if h is not None:
            widget.setFixedHeight(round(h * self._scale))


def register_fixed_size(
    widget: QWidget, width: Optional[int] = None, height: Optional[int] = None
) -> None:
    """Pomoćna funkcija — registruje widget na aktivnom ScaleManager-u, ili
    samo postavi fiksnu veličinu ako ScaleManager nije inicijalizovan
    (npr. u izolovanim testovima/dijagnostici)."""
    mgr = ScaleManager.instance()
    if mgr is not None:
        mgr.register_fixed_size(widget, width, height)
        return
    if width is not None:
        widget.setFixedWidth(width)
    if height is not None:
        widget.setFixedHeight(height)
