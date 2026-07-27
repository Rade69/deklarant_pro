"""
Testovi za popravke wiring gapova u Agent V2 implementaciji (2026-07-27).

Vidi agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md za pun opis
četiri nalaza koje ovi testovi pokrivaju:

  1. _execute_tool nije imao granu za "prikazi"/"provjeri" — LLM Tool Use bi
     dobio "Nepoznata akcija" za alate koje sam definiše u tool_definitions.py.
  2. _handle_message_v2 je za ANALYZE/REQUEST_CHANGE/PROPOSE/RUN_WORKFLOW/
     EXPORT/OTHER pozivao plain chat bez tools=, umjesto Tool Use.
  3. _puna_auto_pipeline i XML izvoz nisu bili povezani ni na jedan "jedna
     komanda vodi cijeli proces" kod-put (declaration_workflow_state.py i
     automation_levels.py su postojali, ali se nigdje nisu pozivali).
  4. _xml_preflight je samo provjeravao da 'items' nije prazan (export_to_xml
     je bio uvezen ali nikad pozvan) — prava builder greška bi bila
     prijavljena kao READY. _izvezi_xml nije pozivao nijednu provjeru
     spremnosti prije izvoza.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.draft.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft


def _minimal_ready_draft() -> DeclarationDraft:
    """Isti fixture kao test_all_validation_services_smoke.py — sve kapije prolaze."""
    d = DeclarationDraft()
    d.deklaracija_tip = "IM"
    d.izvoznik_naziv = "Exporter d.o.o."
    d.primalac_naziv = "Importer d.o.o."
    d.deklarant_naziv = "Deklarant d.o.o."
    d.valuta = "EUR"
    d.invoice_lines = [InvoiceLine(
        naziv_robe="Test proizvod", tarifni_broj="08052190",
        bruto_kg=100.0, neto_kg=90.0, iznos=500.0,
        kolicina=10, jm="kom", zemlja_porijekla="DE",
    )]
    d.items = [NaimenovanjeDraft(
        item_id="1", ordinal_no=1,
        tariff_code="08052190", goods_description="Test proizvod",
        origin_country_code="DE", gross_mass_kg=100.0, net_mass_kg=90.0,
    )]
    return d


# ── Nalaz 1: _execute_tool dispatch za "prikazi"/"provjeri" ──────────────


class TestPrikaziProvjeriDispatch:
    def test_prikazi_ne_vraca_nepoznata_akcija(self):
        from gui.tabs.agent.services.chat_intent_handler import _execute_tool

        ctrl = MagicMock()
        chat = MagicMock()
        ctrl.view.get_chat_panel.return_value = chat
        ctrl.draft = _minimal_ready_draft()

        _execute_tool(ctrl, "prikazi", {"target": "invoice"})

        for call in chat.add_agent_message.call_args_list:
            assert "Nepoznata akcija" not in call[0][0]

    def test_provjeri_ne_vraca_nepoznata_akcija(self):
        from gui.tabs.agent.services.chat_intent_handler import _execute_tool

        ctrl = MagicMock()
        chat = MagicMock()
        ctrl.view.get_chat_panel.return_value = chat
        ctrl.draft = _minimal_ready_draft()

        _execute_tool(ctrl, "provjeri", {"target": "items"})

        for call in chat.add_agent_message.call_args_list:
            assert "Nepoznata akcija" not in call[0][0]

    def test_provjeri_xml_koristi_xml_readiness_service(self):
        """provjeri(target=xml) mora proizvesti stvaran readiness rezultat, ne generičku poruku."""
        from gui.tabs.agent.services.chat_intent_handler import _dispatch_provjeri

        ctrl = MagicMock()
        chat = MagicMock()
        ctrl.view.get_chat_panel.return_value = chat
        ctrl.draft = _minimal_ready_draft()

        _dispatch_provjeri(ctrl, {"target": "xml"}, None)

        rendered = chat.add_agent_message.call_args[0][0]
        assert "Spremnost za XML izvoz" in rendered

    def test_provjeri_svaki_target_dostize_granu(self):
        """Regresiona zaštita: svaki target iz tool_definitions.py TOOLS enum-a
        mora imati granu u _dispatch_provjeri, inače se tiho vraća na
        _compliance_check (application/declaration fallback) — provjeravamo
        da nijedan poznat target ne izazove izuzetak."""
        from gui.tabs.agent.services.chat_intent_handler import _dispatch_provjeri

        ctrl = MagicMock()
        chat = MagicMock()
        ctrl.view.get_chat_panel.return_value = chat
        ctrl.draft = _minimal_ready_draft()
        ctrl.tariff_svc = MagicMock()

        targets = ("application", "invoice", "tariffs", "origin", "items",
                   "header", "declaration", "cross_tab", "xml")
        for target in targets:
            _dispatch_provjeri(ctrl, {"target": target}, None)  # ne smije baciti


# ── Nalaz 2: _handle_message_v2 koristi Tool Use za ANALYZE/REQUEST_CHANGE/... ──


class TestHandleMessageV2Routing:
    def _make_ctrl(self):
        ctrl = MagicMock()
        chat = MagicMock()
        ctrl.view.get_chat_panel.return_value = chat
        ctrl._pending_action = None
        return ctrl, chat

    @patch("gui.tabs.agent.services.chat_intent_handler._check_agent_v2_enabled", return_value=True)
    @patch("services.agent.chat.intent_resolver.resolve")
    def test_analyze_ide_na_tool_use_ne_plain_chat(self, mock_resolve, _mock_switch):
        from services.agent.chat.intent_model import AgentIntent, IntentAction, IntentTarget, IntentSource
        from gui.tabs.agent.services.chat_intent_handler import _handle_message

        mock_resolve.return_value = AgentIntent(
            action=IntentAction.ANALYZE, target=IntentTarget.TARIFFS,
            source=IntentSource.LOCAL, confidence=0.9,
        )
        ctrl, chat = self._make_ctrl()

        with patch("gui.tabs.agent.services.chat_intent_handler._dispatch_via_tool_use") as mock_tool_use, \
             patch("gui.tabs.agent.services.chat_intent_handler._start_chat_worker") as mock_plain_chat:
            _handle_message(ctrl, "analiziraj tarifne")

        mock_tool_use.assert_called_once()
        mock_plain_chat.assert_not_called()

    @patch("gui.tabs.agent.services.chat_intent_handler._check_agent_v2_enabled", return_value=True)
    @patch("services.agent.chat.intent_resolver.resolve")
    def test_run_workflow_poziva_orkestrator_ne_tool_use(self, mock_resolve, _mock_switch):
        from services.agent.chat.intent_model import AgentIntent, IntentAction, IntentTarget, IntentSource
        from gui.tabs.agent.services.chat_intent_handler import _handle_message

        mock_resolve.return_value = AgentIntent(
            action=IntentAction.RUN_WORKFLOW, target=IntentTarget.DECLARATION,
            source=IntentSource.LOCAL, confidence=0.9,
        )
        ctrl, chat = self._make_ctrl()

        with patch(
            "services.agent.workflow.declaration_workflow_service.run_declaration_workflow"
        ) as mock_run:
            _handle_message(ctrl, "pripremi deklaraciju")

        mock_run.assert_called_once()

    @patch("gui.tabs.agent.services.chat_intent_handler._check_agent_v2_enabled", return_value=True)
    @patch("services.agent.chat.intent_resolver.resolve")
    def test_export_poziva_izvezi_xml_direktno(self, mock_resolve, _mock_switch):
        from services.agent.chat.intent_model import AgentIntent, IntentAction, IntentTarget, IntentSource
        from gui.tabs.agent.services.chat_intent_handler import _handle_message

        mock_resolve.return_value = AgentIntent(
            action=IntentAction.EXPORT, target=IntentTarget.XML,
            source=IntentSource.LOCAL, confidence=0.95,
        )
        ctrl, chat = self._make_ctrl()

        with patch(
            "gui.tabs.agent.services.xml_workflow_service.XmlWorkflowService.izvezi_xml"
        ) as mock_izvezi:
            _handle_message(ctrl, "izvezi xml")

        mock_izvezi.assert_called_once()


# ── Nalaz 4a: _xml_preflight stvarno poziva builder, ne mutira produkcioni draft ──


class TestXmlPreflight:
    def test_prazan_items_je_blokada(self):
        from services.agent.validation.xml_readiness_service import _xml_preflight

        d = DeclarationDraft()
        assert _xml_preflight(d) is False

    def test_ispravan_draft_prolazi_preflight(self):
        from services.agent.validation.xml_readiness_service import _xml_preflight

        assert _xml_preflight(_minimal_ready_draft()) is True

    def test_builder_greska_se_hvata_kao_blokada(self):
        """Ako AsycudaXMLBuilder.build() baci izuzetak, preflight mora vratiti
        False — prije popravke export_to_xml nije bio ni pozivan, pa se prava
        builder greška nikad nije mogla vidjeti."""
        from services.agent.validation.xml_readiness_service import _xml_preflight

        with patch(
            "exporters.asycuda_xml_builder.AsycudaXMLBuilder.build",
            side_effect=ValueError("simulirana builder greška"),
        ):
            assert _xml_preflight(_minimal_ready_draft()) is False

    def test_preflight_ne_mutira_produkcioni_draft(self):
        """AsycudaXMLBuilder._apply_known_tariff_corrections() mutira draft.items
        u hodu — preflight mora raditi nad kopijom, ne nad originalu."""
        from services.agent.validation.xml_readiness_service import _xml_preflight

        draft = _minimal_ready_draft()
        original_tariff = draft.items[0].tariff_code
        original_revision = getattr(draft, "revision", 0)

        _xml_preflight(draft)

        assert draft.items[0].tariff_code == original_tariff
        assert getattr(draft, "revision", 0) == original_revision

    def test_nedostupan_builder_je_blokada(self):
        from services.agent.validation.xml_readiness_service import _xml_preflight

        with patch.dict("sys.modules", {"exporters.asycuda_xml_builder": None}):
            assert _xml_preflight(_minimal_ready_draft()) is False


class TestReadinessFailClosed:
    def test_kvar_obavezne_provjere_blokira_izvoz(self):
        from services.agent.validation.finding_model import FindingCode
        from services.agent.validation.xml_readiness_service import (
            ReadinessStatus,
            provjeri_spremnost_za_xml,
        )

        with patch(
            "services.agent.validation.invoice_review_service.provjeri_fakturu",
            side_effect=RuntimeError("simuliran pad baze"),
        ):
            result = provjeri_spremnost_za_xml(_minimal_ready_draft())

        assert result.status == ReadinessStatus.BLOCKED
        assert "invoice_validation" in result.checks_skipped
        assert any(f.code == FindingCode.REQUIRED_CHECK_FAILED for f in result.all_findings)

    def test_kvar_preflight_orchestracije_blokira_izvoz(self):
        from services.agent.validation.finding_model import FindingCode
        from services.agent.validation.xml_readiness_service import (
            ReadinessStatus,
            provjeri_spremnost_za_xml,
        )

        with patch(
            "services.agent.validation.xml_readiness_service._xml_preflight",
            side_effect=RuntimeError("simulirana tehnička greška"),
        ):
            result = provjeri_spremnost_za_xml(_minimal_ready_draft())

        assert result.status == ReadinessStatus.BLOCKED
        assert "xml_preflight" in result.checks_skipped
        assert any(f.code == FindingCode.REQUIRED_CHECK_FAILED for f in result.all_findings)


# ── Nalaz 4b: _izvezi_xml poziva readiness prije izvoza ──────────────────


class TestIzvezhiXml:
    def _make_ctrl(self, draft):
        ctrl = MagicMock()
        ctrl.draft = draft
        return ctrl

    def test_blokiran_draft_ne_otvara_file_dialog(self):
        from gui.tabs.agent.services.xml_workflow_service import _izvezi_xml

        ctrl = self._make_ctrl(DeclarationDraft())  # prazan -> BLOCKED
        chat = MagicMock()

        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName") as mock_dialog:
            _izvezi_xml(ctrl, chat)

        mock_dialog.assert_not_called()
        poruke = " ".join(c[0][0] for c in chat.add_agent_message.call_args_list)
        assert "nije moguć" in poruke

    def test_odbijena_potvrda_ne_kreira_fajl(self):
        from gui.tabs.agent.services.xml_workflow_service import _izvezi_xml

        ctrl = self._make_ctrl(_minimal_ready_draft())
        chat = MagicMock()

        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName") as mock_dialog:
            _izvezi_xml(ctrl, chat, confirm_fn=lambda title, q: False)

        mock_dialog.assert_not_called()
        poruke = " ".join(c[0][0] for c in chat.add_agent_message.call_args_list)
        assert "otkazan" in poruke.lower()

    def test_otkazan_file_dialog_ne_zove_export(self):
        from gui.tabs.agent.services.xml_workflow_service import _izvezi_xml

        ctrl = self._make_ctrl(_minimal_ready_draft())
        chat = MagicMock()

        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", "")), \
             patch("exporters.asycuda_xml_builder.export_to_xml") as mock_export:
            _izvezi_xml(ctrl, chat, confirm_fn=lambda title, q: True)

        mock_export.assert_not_called()

    def test_potvrdjen_izvoz_poziva_export_to_xml(self):
        from gui.tabs.agent.services.xml_workflow_service import _izvezi_xml

        ctrl = self._make_ctrl(_minimal_ready_draft())
        chat = MagicMock()

        with patch(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            return_value=("C:/tmp/test.xml", ""),
        ), patch("exporters.asycuda_xml_builder.export_to_xml") as mock_export:
            _izvezi_xml(ctrl, chat, confirm_fn=lambda title, q: True)

        mock_export.assert_called_once()
        poruke = " ".join(c[0][0] for c in chat.add_agent_message.call_args_list)
        assert "izvezen" in poruke.lower()

    def test_izmjena_drafta_nakon_potvrde_ponistava_readiness(self):
        from gui.tabs.agent.services.xml_workflow_service import _izvezi_xml

        draft = _minimal_ready_draft()
        ctrl = self._make_ctrl(draft)
        chat = MagicMock()

        def confirm_and_mutate(_title, _question):
            draft.mark_dirty()
            return True

        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName") as mock_dialog, \
             patch("exporters.asycuda_xml_builder.export_to_xml") as mock_export:
            _izvezi_xml(ctrl, chat, confirm_fn=confirm_and_mutate)

        mock_dialog.assert_not_called()
        mock_export.assert_not_called()
        poruke = " ".join(c[0][0] for c in chat.add_agent_message.call_args_list)
        assert "promijenjena" in poruke.lower()


# ── Nalaz 3: declaration_workflow_state — stvarne kapije, ne "lista nije prazna" ──


class TestDeclarationWorkflowState:
    def test_prazan_draft_staje_na_files_imported(self):
        from services.agent.workflow.declaration_workflow_state import compute_state_from_draft

        state = compute_state_from_draft(DeclarationDraft())
        assert len(state.gates) == 1
        assert state.gates[0].name == "files_imported"
        assert not state.gates[0].passed

    def test_kompletan_draft_prolazi_sve_kapije(self):
        from services.agent.workflow.declaration_workflow_state import (
            GATE_ORDER, compute_state_from_draft,
        )

        state = compute_state_from_draft(_minimal_ready_draft())
        assert [g.name for g in state.gates] == list(GATE_ORDER)
        assert state.all_passed

    def test_nedostajuca_tarifa_blokira_tariffs_resolved_ali_ne_kasnije(self):
        from services.agent.workflow.declaration_workflow_state import compute_state_from_draft

        d = _minimal_ready_draft()
        d.invoice_lines[0].tarifni_broj = ""

        state = compute_state_from_draft(d)
        assert not state.gate("tariffs_resolved").passed


# ── Nalaz 3: declaration_workflow_service — orkestrator + single-flight brava ──


class TestDeclarationWorkflowService:
    def _fake_chat(self):
        chat = MagicMock()
        chat.messages = []
        chat.add_agent_message.side_effect = lambda m: chat.messages.append(m)
        chat.add_activity.side_effect = lambda m: chat.messages.append(m)
        return chat

    def test_prazan_draft_stopped_at_files_imported(self):
        from services.agent.workflow.declaration_workflow_service import run_declaration_workflow

        ctrl = MagicMock()
        ctrl.draft = DeclarationDraft()
        ctrl.faktura_tab = None
        ctrl._declaration_workflow_running = False
        chat = self._fake_chat()

        result = run_declaration_workflow(ctrl, chat)

        assert not result.completed
        assert result.stopped_at == "files_imported"

    def test_kompletan_draft_dolazi_do_izvoza(self):
        from services.agent.workflow.declaration_workflow_service import run_declaration_workflow

        ctrl = MagicMock()
        ctrl.draft = _minimal_ready_draft()
        ctrl.faktura_tab = None
        ctrl._declaration_workflow_running = False
        chat = self._fake_chat()

        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName") as mock_dialog:
            result = run_declaration_workflow(ctrl, chat, confirm_fn=lambda t, q: False)

        assert result.completed
        mock_dialog.assert_not_called()  # potvrda odbijena prije file dialoga

    def test_single_flight_brava_odbija_paralelnu_radnju(self):
        from services.agent.workflow.declaration_workflow_service import (
            AgentBusyError, run_declaration_workflow,
        )

        ctrl = MagicMock()
        ctrl.draft = DeclarationDraft()
        ctrl._declaration_workflow_running = True
        chat = self._fake_chat()

        with pytest.raises(AgentBusyError):
            run_declaration_workflow(ctrl, chat)

    def test_brava_se_oslobadja_nakon_zavrsetka(self):
        from services.agent.workflow.declaration_workflow_service import run_declaration_workflow

        ctrl = MagicMock()
        ctrl.draft = DeclarationDraft()
        ctrl.faktura_tab = None
        ctrl._declaration_workflow_running = False
        chat = self._fake_chat()

        run_declaration_workflow(ctrl, chat)

        assert ctrl._declaration_workflow_running is False


# ── Renderer — HTML escape (aktivirano prvi put na chat izlazu ovom popravkom) ──


class TestRendererEscaping:
    def test_render_summary_html_escapuje_naziv_robe(self):
        from services.agent.validation.finding_model import (
            FindingSeverity, ValidationFinding, ValidationSummary,
        )
        from services.agent.validation.renderer import render_summary_html

        finding = ValidationFinding(
            severity=FindingSeverity.BLOCKING,
            code="MISSING_TARIFF",
            target="invoice",
            location="<script>alert(1)</script>",
            message="Naziv: <b>Cijev <5mm></b>",
        )
        summary = ValidationSummary.from_findings("invoice", [finding])

        html = render_summary_html(summary)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html
