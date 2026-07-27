"""
Karakterizacioni testovi: signali i Rub.40/44.

Faza 0 prema Codex planu §8.
"""
from __future__ import annotations

from PySide6.QtCore import Signal

from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
from gui.tabs.naimenovanja_view import NaimenovanjaView


class TestSignalCharacterization:

    def test_view_has_expected_signals(self, qtbot):
        """NaimenovanjaView ima sve signale koje očekujemo."""
        draft = DeclarationDraft()
        draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]
        view = NaimenovanjaView(draft=draft)
        qtbot.addWidget(view)

        # Naslijeđeni signali iz BaseTabView
        assert hasattr(view, "data_changed")
        assert isinstance(view.data_changed, Signal)

        # Specifični signali
        assert hasattr(view, "import_xml_requested")
        assert isinstance(view.import_xml_requested, Signal)

    def test_signal_count_after_reload(self, qtbot):
        """Nakon reload_data nema duplih konekcija."""
        draft = DeclarationDraft()
        draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1,
                       tariff_code="08052190", goods_description="Test")]
        view = NaimenovanjaView(draft=draft)
        qtbot.addWidget(view)

        # Broj signal receivera prije reloada
        receivers_before = view.data_changed.receivers if hasattr(view.data_changed, 'receivers') else 0

        view.reload_data()

        # Broj signal receivera poslije reloada
        receivers_after = view.data_changed.receivers if hasattr(view.data_changed, 'receivers') else 0

        assert receivers_after == receivers_before


class TestRub40Rub44Characterization:

    def test_rub40_widgets_exist(self, qtbot):
        """Rb.40 widgeti postoje nakon inicijalizacije."""
        draft = DeclarationDraft()
        draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]
        view = NaimenovanjaView(draft=draft)
        qtbot.addWidget(view)
        view.show()

        # Rb.40.1 (tip dokumenta X/Y/Z)
        rb40_1 = view._get_widget("le_rubrika40_1")
        assert rb40_1 is not None, "Rb.40.1 widget ne postoji"

    def test_rub44_pd_codes_exist(self, qtbot):
        """Rb.44 PD kodovi widget postoji."""
        draft = DeclarationDraft()
        draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]
        view = NaimenovanjaView(draft=draft)
        qtbot.addWidget(view)
        view.show()

        rb44 = view._get_widget("le_rubrika44_4")
        assert rb44 is not None, "Rb.44.4 widget ne postoji"


class TestPECharacterization:

    def test_pe_doc_normalization(self, qtbot):
        """PE dokument normalizacija radi ispravno."""
        from gui.tabs.naimenovanja_view import _pe_doc_code, _normalize_pe_document_text

        assert _pe_doc_code("PE1 EUR.1 12345") == "PE1"
        assert _pe_doc_code("PE2 12345") == "PE2"
        assert _pe_doc_code("PE3 12345") == "PE3"
        assert _pe_doc_code("N380 12345") == ""

        assert _normalize_pe_document_text("PE1  EUR.1  12345") == "PE1 EUR.1 12345"
