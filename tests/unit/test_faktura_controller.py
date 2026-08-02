"""
Testovi za FakturaController i FakturaTab — direktni import i funkcionalnost.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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

    def test_create_naimenovanja_passes_draft_uid_to_learning(self, monkeypatch):
        from gui.tabs.faktura_controller import FakturaController

        draft = DeclarationDraft()
        draft.draft_uid = "phase-1-controller-draft"
        draft.invoice_lines = [InvoiceLine(naziv_robe="Test", tarifni_broj="08052190")]
        ctrl = FakturaController(get_draft_fn=lambda: draft)

        class FakeCreateService:
            def __init__(self, received_draft):
                self.received_draft = received_draft

            def create_smart_group(self):
                return 1

        class FakeFacade:
            calls = []

            @classmethod
            def get_instance(cls):
                return cls()

            def learn_from_draft(self, lines, **kwargs):
                self.calls.append((lines, kwargs))

        monkeypatch.setattr(
            "services.naimenovanja.create_naimenovanja_service.CreateNaimenovanjaService",
            FakeCreateService,
        )
        monkeypatch.setattr("services.tariff_facade.TariffFacade", FakeFacade)

        result = ctrl.create_naimenovanja(draft)

        assert result == {"count": 1, "error": None}
        assert FakeFacade.calls == [
            (draft.invoice_lines, {"draft_uid": "phase-1-controller-draft"})
        ]


class TestLoadMasterList:
    """FakturaController.load_master_list() — Faza 7a (2026-08-02),
    izdvojeno iz FakturaView._on_load_master_list (direktni self.assembly
    pozivi mimo Controller-a)."""

    def _make_master_list_xlsx(self, tmp_path) -> str:
        from openpyxl import Workbook

        path = tmp_path / "glavna_lista.xlsx"
        wb = Workbook()
        sheet = wb.active
        sheet.append([
            "Rbr", "Šifra", "Naziv dobra / usluge", "JM", "Kol.",
            "Tarifni br", "Zemlja porekla", "Preferencijal",
        ])
        sheet.append([1, "A-1", "GREJAC", "KOM", 2, "8516802090", "IT", "DA"])
        wb.save(path)
        wb.close()
        return str(path)

    def test_vraca_count_draft_i_status(self, tmp_path):
        from gui.tabs.faktura_controller import FakturaController

        draft = DeclarationDraft()
        ctrl = FakturaController(get_draft_fn=lambda: draft)
        filepath = self._make_master_list_xlsx(tmp_path)

        count, new_draft, status = ctrl.load_master_list(filepath)

        assert count == 1
        assert len(new_draft.invoice_lines) == 1
        assert status["total"] == 1
        assert ctrl.assembly.master_list_loaded is True

    def test_ne_mijenja_ctrl_assembly_referencu(self, tmp_path):
        """load_master_list mutira POSTOJECI assembly objekat u mjestu -
        ne smije zamijeniti self.assembly novim objektom (za razliku od
        reset_assembly), jer View drzi istu referencu preko set_controller."""
        from gui.tabs.faktura_controller import FakturaController

        draft = DeclarationDraft()
        ctrl = FakturaController(get_draft_fn=lambda: draft)
        original_assembly = ctrl.assembly
        filepath = self._make_master_list_xlsx(tmp_path)

        ctrl.load_master_list(filepath)

        assert ctrl.assembly is original_assembly


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

    def test_faktura_tab_wires_controller_owned_services_to_view(self, qtbot):
        from gui.tabs.faktura_tab import FakturaTab

        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)

        assert tab.view.controller is tab.controller
        assert tab.view.assembly is tab.controller.assembly
        assert tab.controller.validator is not None

    def test_validation_issue_counts_uses_controller_validator(self, qtbot, monkeypatch):
        from gui.tabs.faktura_tab import FakturaTab

        draft = DeclarationDraft()
        line = InvoiceLine(naziv_robe="", tarifni_broj="")
        draft.invoice_lines = [line]
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        calls = []
        result = SimpleNamespace(
            errors=[SimpleNamespace(field="tarifni_broj", message="obavezan")],
            warnings=[],
        )
        monkeypatch.setattr(
            tab.controller,
            "validate_line",
            lambda received: calls.append(received) or result,
        )
        monkeypatch.setattr(tab.view.validation_cache, "get", lambda row: None)

        errors, warnings = tab.view._validation_issue_counts([0])

        assert calls == [line]
        assert errors == {"bez tarife": 1}
        assert warnings == {}

    def test_signals_exist_on_view(self, qtbot):
        from gui.tabs.faktura_tab import FakturaTab
        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        assert hasattr(tab.view, "validate_requested")
        assert hasattr(tab.view, "import_requested")
        assert hasattr(tab.view, "create_naimenovanja_requested")

    def test_validate_signal_connected(self, qtbot, monkeypatch):
        """Signal je povezan na handler (ne puca pri emitovanju)."""
        from gui.tabs.faktura_tab import FakturaTab
        from gui.utils.safe_message_box import SafeMessageBox
        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        monkeypatch.setattr(SafeMessageBox, "information", lambda *args, **kwargs: None)
        monkeypatch.setattr(SafeMessageBox, "warning", lambda *args, **kwargs: None)
        # Emituj signal — ne smije pasti
        tab.view.validate_requested.emit("all", [])


class TestDistStandalone:
    """Root i dist_client samostalni import."""

    def test_dist_faktura_modules_import_as_standalone_root(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from gui.tabs.faktura_controller import FakturaController; "
                    "from gui.tabs.faktura_tab import FakturaTab"
                ),
            ],
            cwd=Path("dist_client"),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    @pytest.mark.parametrize(
        "relative_path",
        [
            "gui/tabs/faktura_controller.py",
            "gui/tabs/faktura_tab.py",
            "gui/tabs/faktura_view.py",
            "gui/tabs/agent/services/import_pipeline_service.py",
            "services/faktura/models.py",
            "services/faktura/faktura_service.py",
            "services/faktura/mass_workflow_service.py",
            "services/faktura/auto_fill_workflow_service.py",
            "services/faktura/create_naimenovanja_workflow_service.py",
        ],
    )
    def test_dist_faktura_modules_match_root(self, relative_path):
        root_text = (
            Path(relative_path)
            .read_text(encoding="utf-8")
            .lstrip("\ufeff")
            .replace("\r\n", "\n")
        )
        dist_text = (
            Path("dist_client", relative_path)
            .read_text(encoding="utf-8")
            .lstrip("\ufeff")
            .replace("\r\n", "\n")
        )
        assert dist_text == root_text


class TestNoDoubleValidation:
    """Dokazuje da signal NE izaziva duplu validaciju ni itemChanged spam."""

    def test_validate_signal_handler_uses_block_signals(self, qtbot, monkeypatch):
        """Handler na FakturaTab koristi blockSignals — nema itemChanged."""
        from gui.tabs.faktura_tab import FakturaTab
        from core.draft.draft import DeclarationDraft, InvoiceLine
        from gui.utils.safe_message_box import SafeMessageBox

        draft = DeclarationDraft()
        draft.invoice_lines = [InvoiceLine(naziv_robe="Test", tarifni_broj="08052190")]
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        tab.view.show()
        monkeypatch.setattr(SafeMessageBox, "information", lambda *args, **kwargs: None)
        monkeypatch.setattr(SafeMessageBox, "warning", lambda *args, **kwargs: None)
        monkeypatch.setattr(tab.view, "_run_historical_tariff_validation", lambda *args, **kwargs: None)

        item_changed_count = 0
        def count_changes(*args):
            nonlocal item_changed_count
            item_changed_count += 1

        tab.view.table.itemChanged.connect(count_changes)
        tab.view.validate_requested.emit("all", [])

        assert item_changed_count == 0, (
            f"blockSignals nije korišten: {item_changed_count} itemChanged događaja"
        )

    def test_validate_button_emits_validate_signal(self, qtbot):
        """Dugme Provjeri emituje signal umjesto direktnog View handlera."""
        from gui.tabs.faktura_view import FakturaView
        from core.draft.draft import DeclarationDraft, InvoiceLine

        draft = DeclarationDraft()
        draft.invoice_lines = [InvoiceLine(naziv_robe="Test", tarifni_broj="08052190")]
        view = FakturaView(draft=draft)
        qtbot.addWidget(view)
        view.show()

        emitted = []
        view.validate_requested.connect(lambda scope, rows: emitted.append((scope, rows)))
        view.btn_validate.click()

        assert emitted == [("all", [])]

    def test_faktura_tab_validate_auto_uses_view_validation_adapter(self, qtbot, monkeypatch):
        from gui.tabs.faktura_tab import FakturaTab

        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        called = []
        monkeypatch.setattr(
            tab.view,
            "validate",
            lambda auto=False: called.append(auto) or (True, 0, 0),
        )

        assert tab.validate(auto=True) == (True, 0, 0)
        assert called == [True]

    def test_faktura_view_validate_is_public_adapter(self, qtbot, monkeypatch):
        from gui.tabs.faktura_view import FakturaView

        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        qtbot.addWidget(view)
        called = []
        monkeypatch.setattr(
            view,
            "_validate_all_items",
            lambda auto=False: called.append(auto) or (True, 0, 0),
        )

        assert view.validate(auto=True) == (True, 0, 0)
        assert called == [True]

    def test_faktura_tab_create_naimenovanja_uses_view_adapter(self, qtbot, monkeypatch):
        from gui.tabs.faktura_tab import FakturaTab

        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        called = []
        monkeypatch.setattr(
            tab.view,
            "create_naimenovanja",
            lambda auto=False: called.append(auto) or True,
        )

        assert tab.create_naimenovanja(auto=True) is True
        assert called == [True]

    def test_faktura_view_create_naimenovanja_is_public_adapter(self, qtbot, monkeypatch):
        from gui.tabs.faktura_view import FakturaView

        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        qtbot.addWidget(view)
        called = []
        monkeypatch.setattr(
            view,
            "_create_naimenovanja_from_draft",
            lambda auto=False: called.append(auto) or True,
        )

        assert view.create_naimenovanja(auto=True) is True
        assert called == [True]

    def test_faktura_tab_calculate_masses_uses_controller_service(self, qtbot, monkeypatch):
        from gui.tabs.faktura_tab import FakturaTab

        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        called = []
        monkeypatch.setattr(
            tab.view,
            "calculate_masses",
            lambda auto=False, controller=None: called.append((auto, controller)) or True,
        )

        assert tab.calculate_masses(auto=True) is True
        assert called == [(True, tab.controller)]

    def test_faktura_tab_auto_fill_uses_controller_service(self, qtbot, monkeypatch):
        from gui.tabs.faktura_tab import FakturaTab

        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        result = object()
        called = []
        monkeypatch.setattr(
            tab.view,
            "auto_fill",
            lambda auto=False, controller=None: called.append((auto, controller)) or result,
        )

        assert tab.auto_fill(auto=True) is result
        assert called == [(True, tab.controller)]

    def test_auto_fill_button_emits_signal(self, qtbot):
        from gui.tabs.faktura_view import FakturaView

        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        qtbot.addWidget(view)
        view.show()
        emitted = []
        view.auto_fill_requested.connect(lambda: emitted.append(True))

        view.btn_auto_fill.click()

        assert emitted == [True]
        assert not hasattr(view, "_on_auto_fill")

    def test_calculate_masses_button_emits_signal(self, qtbot):
        from gui.tabs.faktura_view import FakturaView

        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        qtbot.addWidget(view)
        view.show()
        emitted = []
        view.calculate_masses_requested.connect(lambda: emitted.append(True))

        view.btn_calc_masses.click()

        assert emitted == [True]
        assert not hasattr(view, "_on_calculate_masses")

    def test_create_naimenovanja_button_emits_signal_not_internal_handler(self, qtbot, monkeypatch):
        from gui.tabs.faktura_view import FakturaView

        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        qtbot.addWidget(view)
        view.show()
        internal_called = []
        emitted = []
        monkeypatch.setattr(
            view,
            "_create_naimenovanja_from_draft",
            lambda auto=False: internal_called.append(auto),
        )
        view.create_naimenovanja_requested.connect(lambda auto: emitted.append(auto))

        view.btn_create_naimenovanja.click()

        assert emitted == [False]
        assert internal_called == []

    def test_create_naimenovanja_signal_handler_uses_public_legacy_adapter(
        self, qtbot, monkeypatch
    ):
        from gui.tabs.faktura_tab import FakturaTab

        draft = DeclarationDraft()
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        called = []
        monkeypatch.setattr(
            tab,
            "create_naimenovanja",
            lambda auto=False: called.append(auto) or True,
        )

        tab.view.create_naimenovanja_requested.emit(False)

        assert called == [False]

    def test_manual_toolbar_signal_map_is_stabilized(self, qtbot, monkeypatch):
        from gui.tabs.faktura_tab import FakturaTab
        from gui.utils.safe_message_box import SafeMessageBox

        draft = DeclarationDraft()
        draft.invoice_lines = [InvoiceLine(naziv_robe="Test", tarifni_broj="08052190")]
        tab = FakturaTab(draft=draft)
        qtbot.addWidget(tab)
        tab.view.show()

        calls = []
        monkeypatch.setattr(SafeMessageBox, "information", lambda *args, **kwargs: None)
        monkeypatch.setattr(SafeMessageBox, "warning", lambda *args, **kwargs: None)
        monkeypatch.setattr(tab.view, "_run_historical_tariff_validation", lambda *args, **kwargs: None)
        monkeypatch.setattr(tab, "auto_fill", lambda auto=False: calls.append(("auto_fill", auto)))
        monkeypatch.setattr(tab, "calculate_masses", lambda auto=False: calls.append(("mase", auto)))
        monkeypatch.setattr(
            tab,
            "create_naimenovanja",
            lambda auto=False: calls.append(("naimenovanja", auto)) or True,
        )

        tab.view.btn_auto_fill.click()
        tab.view.btn_calc_masses.click()
        tab.view.btn_create_naimenovanja.click()

        assert calls == [
            ("auto_fill", False),
            ("mase", False),
            ("naimenovanja", False),
        ]
