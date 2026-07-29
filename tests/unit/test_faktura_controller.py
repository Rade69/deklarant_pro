"""
Testovi za FakturaController i FakturaTab — direktni import i funkcionalnost.
"""
from __future__ import annotations

import pytest

from core.draft.draft import DeclarationDraft, InvoiceLine


class TestFakturaControllerImport:
    """Startup import testovi."""

    def test_controller_importable(self):
        from gui.tabs.faktura_controller import FakturaController
        assert FakturaController is not None

    def test_controller_instantiable(self):
        from gui.tabs.faktura_controller import FakturaController
        draft = DeclarationDraft()
        ctrl = FakturaController(get_draft_fn=lambda: draft)
        assert ctrl is not None

    def test_validate_and_color_rows_no_crash(self):
        from gui.tabs.faktura_controller import FakturaController
        draft = DeclarationDraft()
        draft.invoice_lines = [InvoiceLine(naziv_robe="Test", tarifni_broj="08052190")]
        ctrl = FakturaController(get_draft_fn=lambda: draft)
        result = ctrl.validate_and_color_rows(draft)
        assert isinstance(result, dict)
        assert "validated_count" in result
        assert result["validated_count"] == 1

    def test_normalize_item_tariffs_no_zfill(self):
        """Kodovi kraći od 8 cifara OSTAJU nepromijenjeni (projektno pravilo)."""
        from gui.tabs.faktura_controller import FakturaController
        draft = DeclarationDraft()
        ctrl = FakturaController(get_draft_fn=lambda: draft)
        items = [InvoiceLine(tarifni_broj="3304990")]  # 7 cifara
        ctrl.normalize_item_tariffs(items)
        # NE SMIJE postati "03304990" — ostaje "3304990"
        assert items[0].tarifni_broj == "3304990"

    def test_bulk_change_tariff_normalizes(self):
        from gui.tabs.faktura_controller import FakturaController
        draft = DeclarationDraft()
        draft.invoice_lines = [InvoiceLine(tarifni_broj="")]
        ctrl = FakturaController(get_draft_fn=lambda: draft)
        updated = ctrl.bulk_change_tariff(draft, [0], "0805.21.90")
        assert updated == 1
        assert draft.invoice_lines[0].tarifni_broj == "08052190"

    def test_partner_consistency(self):
        from gui.tabs.faktura_controller import FakturaController
        draft = DeclarationDraft()
        ctrl = FakturaController(get_draft_fn=lambda: draft)
        ok, warnings = ctrl.check_partner_consistency(
            "Exporter d.o.o.", "Importer d.o.o.",
            "Exporter d.o.o.", "Importer d.o.o.",
        )
        assert ok is True
        assert warnings == []


class TestFakturaTabImport:
    """FakturaTab startup import testovi."""

    def test_faktura_tab_importable(self):
        from gui.tabs.faktura_tab import FakturaTab
        assert FakturaTab is not None

    def test_faktura_tab_instantiable(self, qtbot):
        from gui.tabs.faktura_tab import FakturaTab
        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        assert tab.controller is not None

    def test_signals_exist_on_view(self, qtbot):
        from gui.tabs.faktura_tab import FakturaTab
        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        assert hasattr(tab.view, "validate_requested")
        assert hasattr(tab.view, "import_requested")
        assert hasattr(tab.view, "create_naimenovanja_requested")

    def test_validate_signal_connected(self, qtbot):
        """Signal je povezan na handler (ne puca pri emitovanju)."""
        from gui.tabs.faktura_tab import FakturaTab
        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        # Emituj signal — ne smije pasti
        tab.view.validate_requested.emit("all", [])


class TestDistStandalone:
    """Root i dist_client samostalni import."""

    def test_dist_controller_exists(self):
        import sys
        # Samo provjeri da fajl postoji
        from pathlib import Path
        dist_ctrl = Path("dist_client/gui/tabs/faktura_controller.py")
        assert dist_ctrl.exists(), "dist_client Controller ne postoji"

    def test_dist_tab_exists(self):
        from pathlib import Path
        dist_tab = Path("dist_client/gui/tabs/faktura_tab.py")
        assert dist_tab.exists(), "dist_client FakturaTab ne postoji"
