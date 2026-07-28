"""
Phase 4 extensions for NaimenovanjaView — read/render API.

Dodaje View metode koje Controller koristi za čitanje forme i
renderovanje itema. Ove metode NE zavise od DB niti poslovne logike.
"""

from __future__ import annotations

import logging

from services.naimenovanja.models import NaimenovanjeRenderContext

logger = logging.getLogger(__name__)


def read_current_form(view) -> dict:
    """Pročitaj trenutne vrijednosti iz svih widgeta forme.

    Čita samo widgete koji su u field_map. Ne normalizuje vrijednosti
    (to radi Service). Ne dira draft.

    Returns:
        dict: {field_name: raw_value}
    """
    form_data = {}
    if not hasattr(view, "field_map"):
        return form_data

    for widget_name, field_name in view.field_map.items():
        if not field_name:
            continue
        widget = view._get_widget(widget_name) if hasattr(view, "_get_widget") else None
        if widget is None:
            continue
        try:
            if hasattr(view, "_read_widget_value"):
                value = view._read_widget_value(widget)
            elif hasattr(widget, "text"):
                value = widget.text() if callable(widget.text) else ""
            elif hasattr(widget, "currentText"):
                value = widget.currentText() if callable(widget.currentText) else ""
            elif hasattr(widget, "value"):
                value = widget.value() if callable(widget.value) else 0
            else:
                continue
            form_data[field_name] = value
        except Exception:
            continue
    return form_data


def render_current_item(view, context: NaimenovanjeRenderContext) -> None:
    """Prikaži item u formi koristeći render kontekst.

    Koristi is_loading guard da spriječi signalne petlje.
    Ne dira draft — samo prikazuje vrijednosti.

    Args:
        view: NaimenovanjaView instanca
        context: NaimenovanjeRenderContext sa svim poljima za prikaz
    """
    if not hasattr(view, "is_loading") or not hasattr(view, "field_map"):
        return

    was_loading = view.is_loading
    view.is_loading = True
    try:
        for widget_name, field_name in view.field_map.items():
            if not field_name:
                continue
            widget = view._get_widget(widget_name) if hasattr(view, "_get_widget") else None
            if widget is None:
                continue
            value = getattr(context, field_name, None)
            if value is None:
                continue
            try:
                if hasattr(widget, "setText"):
                    widget.setText(str(value))
                elif hasattr(widget, "setCurrentText"):
                    widget.setCurrentText(str(value))
                elif hasattr(widget, "setValue"):
                    widget.setValue(float(value) if isinstance(value, (int, float)) else 0)
            except Exception:
                pass
    finally:
        view.is_loading = was_loading
