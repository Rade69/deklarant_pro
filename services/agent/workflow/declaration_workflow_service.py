"""
Declaration Workflow Service — orkestrator za "jedna komanda vodi cijeli proces" (Faza 7).

Plan §18: RUN_WORKFLOW cilj ("Pripremi deklaraciju") mora proizvesti kontrolisan
tok koji se zaustavlja na kapijama i traži potvrdu, umjesto da izvrši jedan
alat ili padne na plain chat bez tools=.

Prije popravke (2026-07-27) ovaj fajl nije postojao — `declaration_workflow_state.py`
i `automation_levels.py` su bili izgrađeni ali nigdje pozivani, a `_puna_auto_pipeline`
(jedini stvarni automatski tok u aplikaciji) nije bio dodirnut. Vidi
agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md za puno obrazloženje.

Namjerna arhitektonska odluka: ovaj orkestrator NE radi punu inverziju
zavisnosti `_puna_auto_pipeline` (uklanjanje QMessageBox/processEvents iz te
funkcije) — to ostaje veliki, rizičan zahvat koji plan §18 opisuje kao
"polovina obima Faze 7" i traži zaseban project_room prije nego što se dirne.
Umjesto toga: `_puna_auto_pipeline` se PONOVO KORISTI kao provjerena "prva
polovina" (mase → tarife → validacija → potvrda porijekla/PE → naimenovanja),
a ovaj servis dodaje NEDOSTAJUĆU "drugu polovinu" (zaglavlje → cross-tab →
xml preflight → izvoz) koja prije ove popravke nije postojala nigdje.
"""

from __future__ import annotations

from dataclasses import dataclass

import logging

logger = logging.getLogger("deklarant_pro.agent.declaration_workflow")


@dataclass
class WorkflowRunResult:
    """Ishod jednog poziva run_declaration_workflow."""
    completed: bool
    stopped_at: str = ""   # ime kapije gdje je zaustavljeno ("" ako je zavrseno)
    message: str = ""


class AgentBusyError(RuntimeError):
    """Workflow je već aktivan — nova radnja se odbija (plan §7.6.b, single-flight)."""


def run_declaration_workflow(ctrl, chat, fw=None, confirm_fn=None) -> WorkflowRunResult:
    """Pripremi deklaraciju do XML izvoza, uz pauze na svakoj kapiji.

    Kapije (plan §7.5, declaration_workflow_state.GATE_ORDER):
      files_imported → invoice_validated → tariffs_resolved → origin_confirmed
      → masses_calculated → items_created  [_puna_auto_pipeline pokriva do ovdje]
      → items_validated → header_ready → cross_check_passed → xml_preflight_passed
      → (finalni izvoz kroz xml_workflow_service._izvezi_xml, koji sam po sebi
         ponovo provjerava readiness i traži potvrdu — plan §17)

    Prije provjere header_ready: pokušaj auto-popune Izvoznik/Primalac/Deklarant
    iz najbliže istorijske deklaracije istog izvoznika (header_autofill_service,
    isti mehanizam kao dugme "Uvezi XML"). Popunjava samo prazna polja; ako
    nema pogotka ili i dalje nedostaju obavezna polja, kapija se zaustavlja
    normalno i traži ručni unos.

    fw: Faktura tab widget potreban za _puna_auto_pipeline (mase/auto-popuna).
        Ako nije prosljeđen, rezolvira se iz ctrl.faktura_tab.
    confirm_fn: Callable[[str, str], bool] — prosljeđuje se do _izvezi_xml.

    Raises:
        AgentBusyError: ako je workflow već aktivan na ovom controlleru
                        (single-flight brava, plan §5.2/§7.6.b).
    """
    from services.agent.workflow.declaration_workflow_state import compute_state_from_draft
    from services.agent.validation.renderer import render_summary_html, render_xml_readiness_html

    if getattr(ctrl, "_declaration_workflow_running", False):
        chat.add_agent_message(
            "⚠️ Priprema deklaracije je već u toku — sačekaj da se završi prije nove radnje."
        )
        raise AgentBusyError("declaration workflow already running")

    ctrl._declaration_workflow_running = True
    try:
        return _run(ctrl, chat, fw, confirm_fn, compute_state_from_draft,
                    render_summary_html, render_xml_readiness_html)
    finally:
        ctrl._declaration_workflow_running = False


def _run(ctrl, chat, fw, confirm_fn, compute_state_from_draft,
         render_summary_html, render_xml_readiness_html) -> WorkflowRunResult:
    state = compute_state_from_draft(ctrl.draft)

    files_gate = state.gate("files_imported")
    if files_gate is None or not files_gate.passed:
        msg = "Nema uvezenih faktura — prvo uvezi dokumente prije pripreme deklaracije."
        chat.add_agent_message(f"ℹ️ {msg}")
        return WorkflowRunResult(completed=False, stopped_at="files_imported", message=msg)

    # ── Prva polovina: mase → tarife → validacija → naimenovanja ──────
    # Ponovo koristi provjeren _puna_auto_pipeline umjesto da ga prepisuje.
    pre_item_gates = (
        "invoice_validated", "tariffs_resolved", "origin_confirmed",
        "masses_calculated", "items_created",
    )
    if any(not _passed(state, g) for g in pre_item_gates):
        chat.add_activity("🤖 Pokrećem pripremu fakture i naimenovanja...")
        resolved_fw = fw if fw is not None else _resolve_faktura_widget(ctrl)
        from gui.tabs.agent.services.import_pipeline_service import ImportPipelineService
        all_lines = list(getattr(ctrl.draft, "invoice_lines", []) or [])
        ImportPipelineService(ctrl).puna_auto_pipeline(resolved_fw, chat, all_lines)
        state = compute_state_from_draft(ctrl.draft)

    if not _passed(state, "items_created"):
        msg = "Naimenovanja nisu kreirana — pogledaj poruke iznad za razlog zaustavljanja."
        chat.add_agent_message(f"⚠️ {msg}")
        return WorkflowRunResult(completed=False, stopped_at="items_created", message=msg)

    # ── Druga polovina: nedostajala prije ove popravke ────────────────
    if not _passed(state, "items_validated"):
        from services.agent.validation.items_review_service import provjeri_naimenovanja
        summary = provjeri_naimenovanja(ctrl.draft)
        chat.add_agent_message(render_summary_html(summary))
        msg = "Naimenovanja imaju blokirajuće nalaze — ispravi ih prije nastavka."
        chat.add_agent_message(f"⚠️ {msg}")
        return WorkflowRunResult(completed=False, stopped_at="items_validated", message=msg)

    if not _passed(state, "header_ready"):
        from services.agent.workflow.header_autofill_service import auto_fill_header_from_history
        try:
            if auto_fill_header_from_history(ctrl, chat):
                state = compute_state_from_draft(ctrl.draft)
        except Exception:
            logger.warning("Auto-popuna zaglavlja iz istorije nije uspjela", exc_info=True)

    if not _passed(state, "header_ready"):
        from services.agent.validation.header_review_service import provjeri_zaglavlje
        summary = provjeri_zaglavlje(ctrl.draft)
        chat.add_agent_message(render_summary_html(summary))
        msg = "Zaglavlje nije spremno — popuni nedostajuća polja prije nastavka."
        chat.add_agent_message(f"⚠️ {msg}")
        return WorkflowRunResult(completed=False, stopped_at="header_ready", message=msg)

    if not _passed(state, "cross_check_passed"):
        from services.agent.validation.header_review_service import provjeri_usklađenost_tabova
        summary = provjeri_usklađenost_tabova(ctrl.draft)
        chat.add_agent_message(render_summary_html(summary))
        msg = "Tabovi nisu međusobno usklađeni — vidi nalaze iznad."
        chat.add_agent_message(f"⚠️ {msg}")
        return WorkflowRunResult(completed=False, stopped_at="cross_check_passed", message=msg)

    if not _passed(state, "xml_preflight_passed"):
        from services.agent.validation.xml_readiness_service import provjeri_spremnost_za_xml
        result = provjeri_spremnost_za_xml(ctrl.draft)
        chat.add_agent_message(render_xml_readiness_html(result))
        msg = "XML preflight nije prošao — vidi blokade iznad."
        chat.add_agent_message(f"⚠️ {msg}")
        return WorkflowRunResult(completed=False, stopped_at="xml_preflight_passed", message=msg)

    # ── Sve kapije zadovoljene — finalni izvoz ────────────────────────
    # _izvezi_xml sam po sebi ponovo provjerava readiness (zaštita od
    # zastarjelog rezultata ako se draft promijenio između ovog trenutka i
    # klika/potvrde) i traži eksplicitnu potvrdu prije pisanja fajla — plan §17.
    chat.add_agent_message("✅ <b>Svi preduslovi zadovoljeni.</b> Priprema za XML izvoz...")
    from gui.tabs.agent.services.xml_workflow_service import XmlWorkflowService
    XmlWorkflowService(ctrl).izvezi_xml(chat, confirm_fn=confirm_fn)
    return WorkflowRunResult(completed=True, message="Workflow završen — vidi ishod izvoza iznad.")


def _passed(state, gate_name: str) -> bool:
    gate = state.gate(gate_name)
    return gate is not None and gate.passed


def _resolve_faktura_widget(ctrl):
    """Isti obrazac kao import_pipeline_service._otvori_faktura_tab_nakon_uvoza."""
    faktura_tab = getattr(ctrl, "faktura_tab", None)
    if faktura_tab is not None and hasattr(faktura_tab, "view"):
        return faktura_tab.view
    return faktura_tab
