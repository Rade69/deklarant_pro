"""
Tarifno pretrazivanje — mixin za ChatIntentHandler.

Izdvojeno iz chat_intent_handler.py (Nivo 3 refactor).
"""


class TariffHandlerMixin:
    """[THUNK] metode za tarifno pretrazivanje i porijeklo."""

    def alternativni_tarifni_za_stavku(self, item_query: str = "",
                                        item_ordinal: int = None,
                                        is_alt: bool = False) -> None:
        """[THUNK] → _alternativni_tarifni_za_stavku"""
        from .chat_intent_handler import _alternativni_tarifni_za_stavku
        _alternativni_tarifni_za_stavku(self._ctrl, item_query, item_ordinal, is_alt)

    def pretrazi_tarifu(self, upit: str) -> None:
        """[THUNK] → _pretrazi_tarifu"""
        from .chat_intent_handler import _pretrazi_tarifu
        _pretrazi_tarifu(self._ctrl, upit)

    def pretrazi_porijeklo(self, upit: str) -> None:
        """[THUNK] → _pretrazi_porijeklo"""
        from .chat_intent_handler import _pretrazi_porijeklo
        _pretrazi_porijeklo(self._ctrl, upit)

    def pretrazi_tarifu_po_kodu(self, kod: str) -> None:
        """[THUNK] → _pretrazi_tarifu_po_kodu"""
        from .chat_intent_handler import _pretrazi_tarifu_po_kodu
        _pretrazi_tarifu_po_kodu(self._ctrl, kod)

    def pretrazi_tarifu_poglavlje(self, poglavlje: str) -> None:
        """[THUNK] → _pretrazi_tarifu_poglavlje"""
        from .chat_intent_handler import _pretrazi_tarifu_poglavlje
        _pretrazi_tarifu_poglavlje(self._ctrl, poglavlje)

    def pretrazi_tarifu_hijerarhijski(self, kod: str) -> None:
        """[THUNK] → _pretrazi_tarifu_hijerarhijski"""
        from .chat_intent_handler import _pretrazi_tarifu_hijerarhijski
        _pretrazi_tarifu_hijerarhijski(self._ctrl, kod)
