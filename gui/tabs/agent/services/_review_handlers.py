"""
Naimenovanja, compliance, spajanje i proposal card — mixin za ChatIntentHandler.

Izdvojeno iz chat_intent_handler.py (Nivo 3 refactor).
"""


class ReviewHandlerMixin:
    """[THUNK] metode za pregled, validaciju i predloge."""

    # ── Naimenovanja ─────────────────────────────────────────────

    def provjeri_naimenovanja(self) -> None:
        """[THUNK] → _provjeri_naimenovanja"""
        from .chat_intent_handler import _provjeri_naimenovanja
        _provjeri_naimenovanja(self._ctrl)

    def pregledaj_naimenovanja(self, indeksi=None) -> None:
        """[THUNK] → _pregledaj_naimenovanja"""
        from .chat_intent_handler import _pregledaj_naimenovanja
        _pregledaj_naimenovanja(self._ctrl, indeksi)

    # ── Compliance ───────────────────────────────────────────────

    def compliance_check(self) -> None:
        """[THUNK] → _compliance_check"""
        from .chat_intent_handler import _compliance_check
        _compliance_check(self._ctrl)

    # ── Spajanje naimenovanja i upis ────────────────────────────

    def izvrsi_spajanje_naimenovanja(self, proposals, chat) -> None:
        """[THUNK] → _izvrsi_spajanje_naimenovanja"""
        from .chat_intent_handler import _izvrsi_spajanje_naimenovanja
        _izvrsi_spajanje_naimenovanja(self._ctrl, proposals, chat)

    def propose_kolona_upis(self, atribut: str, vrijednost: str, tab: str = 'faktura') -> None:
        """[THUNK] → _propose_kolona_upis"""
        from .chat_intent_handler import _propose_kolona_upis
        _propose_kolona_upis(self._ctrl, atribut, vrijednost, tab)

    # ── Proposal Card ───────────────────────────────────────────

    def show_proposal_card(self, proposal: dict) -> None:
        """[THUNK] → _show_proposal_card"""
        from .chat_intent_handler import _show_proposal_card
        _show_proposal_card(self._ctrl, proposal)

    def on_proposal_confirmed(self, values: dict) -> None:
        """[THUNK] → _on_proposal_confirmed"""
        from .chat_intent_handler import _on_proposal_confirmed
        _on_proposal_confirmed(self._ctrl, values)

    def on_proposal_rejected(self) -> None:
        """[THUNK] → _on_proposal_rejected"""
        from .chat_intent_handler import _on_proposal_rejected
        _on_proposal_rejected(self._ctrl)
