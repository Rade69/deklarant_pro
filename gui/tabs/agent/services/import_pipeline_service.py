"""
Import Pipeline Service

Pipeline logika za sve tri procesne rute agenta:
  - Analiza mode (prikaži izvještaj, ponudi akcije)
  - Uvezi u deklaraciju mode (dijalozi, ručna potvrda)
  - Puna automatizacija mode (auto-koraci uz obaveznu deklarantsku potvrdu)

Premješteno iz agent_controller.py radi smanjenja veličine controllera.
"""

import logging
import re
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gui.utils.safe_message_box import SafeMessageBox as QMessageBox

logger = logging.getLogger("deklarant_pro.agent.import_pipeline")

EUR1_THRESHOLD = 6000.0  # EUR — iznad ovog iznosa standardna izjava ne važi
_PE_DOC_CODES = {"PE1", "PE2", "PE3"}


def _normalize_pe_document_text(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    parts = text.split(" ", 1)
    code = parts[0].upper() if parts else ""
    if code not in _PE_DOC_CODES:
        return text
    rest = parts[1].strip() if len(parts) > 1 else ""
    while rest.upper().startswith(f"{code} "):
        rest = rest[len(code):].strip()
    if rest.upper() == code:
        rest = ""
    return f"{code} {rest}".strip()


def _pe_doc_code(value: str) -> str:
    code = (value or "").strip().split(" ", 1)[0].upper()
    return code if code in _PE_DOC_CODES else ""


def _clear_secondary_pe_documents(item) -> bool:
    doc4 = _normalize_pe_document_text(getattr(item, "attached_document4", "") or "")
    if doc4 != (getattr(item, "attached_document4", "") or "").strip():
        item.attached_document4 = doc4
    if not _pe_doc_code(doc4):
        return False

    changed = False
    for field_name in (
        "attached_document1",
        "attached_document2",
        "attached_document3",
        "attached_document5",
    ):
        if _pe_doc_code(getattr(item, field_name, "") or ""):
            setattr(item, field_name, "")
            changed = True
    return changed


def _origin_dialog_type(lines: list, has_origin_statement: bool,
                        is_authorized_exporter: bool) -> str:
    """
    Odredi koji dijalog prikazati za porijeklo robe.

    Vraća:
      'pe3'  — izjava ovlaštenog izvoznika (PE3, bez ograničenja vrijednosti)
      'pe2'  — standardna izjava na fakturi, vrijednost ≤ 6.000 EUR (PE2)
      'eur1' — EUR.1 obrazac potreban (PE1):
               • standardna izjava + vrijednost > 6.000 EUR, ILI
               • nema izjave ali stavke imaju zemlja_porijekla
      'none' — nema ništa za rješavati
    """
    if has_origin_statement:
        if is_authorized_exporter:
            return 'pe3'
        # Standardna izjava — provjeri ukupnu vrijednost robe s porijeklom
        val = sum(l.iznos or 0 for l in lines if getattr(l, 'zemlja_porijekla', None))
        if val == 0:
            val = sum(l.iznos or 0 for l in lines)
        return 'pe2' if val <= EUR1_THRESHOLD else 'eur1'
    # Nema izjave — EUR.1 potreban ako stavke imaju zemlja_porijekla
    has_pending = any(
        getattr(l, 'zemlja_porijekla', None)
        and not getattr(l, 'has_origin_statement', False)
        and not getattr(l, 'eur1_number', None)
        for l in lines
    )
    return 'eur1' if has_pending else 'none'


class ImportPipelineService:
    """Upravljanje pipeline modovima i pomoćnim koracima uvoza."""

    def __init__(self, controller):
        self._ctrl = controller

    # ── Javni API ────────────────────────────────────────────────────

    def analiza_pipeline(self, completed: list, chat) -> None:
        _analiza_pipeline(self._ctrl, completed, chat)

    def analiza_uvezi_action(self) -> None:
        _analiza_uvezi_action(self._ctrl)

    def analiza_auto_action(self) -> None:
        _analiza_auto_action(self._ctrl)

    def puna_auto_pipeline(self, fw, chat, all_lines: list) -> None:
        _puna_auto_pipeline(self._ctrl, fw, chat, all_lines)

    def get_preference_by_country(self, country_code: str, exporter_name: str = "") -> str:
        return _get_preference_by_country(self._ctrl, country_code, exporter_name)

    def auto_handle_povlastice(self, invoice_lines: list, chat,
                                has_origin_statement: bool = False) -> dict:
        return _auto_handle_povlastice(self._ctrl, invoice_lines, chat, has_origin_statement)

    def apply_eur1_to_naimenovanja(self, eur1_data: dict, chat) -> None:
        _apply_eur1_to_naimenovanja(self._ctrl, eur1_data, chat)

    def validiraj_prije_uvoza(self, invoice_lines: list, chat) -> tuple:
        return _validiraj_prije_uvoza(invoice_lines, chat)

    def generisi_izvjestaj(self, chat) -> bool:
        return _generisi_izvjestaj(self._ctrl, chat)



    def otvori_faktura_tab_nakon_uvoza(self, chat) -> None:
        _otvori_faktura_tab_nakon_uvoza(self._ctrl, chat)


# ── Implementacija (slobodne funkcije — lakše testirati) ─────────────


def _analiza_pipeline(ctrl, completed: list, chat) -> None:
    from services.agent.invoice_analysis_service import InvoiceAnalysisService
    from ..workflow_state import WorkflowState

    svc = InvoiceAnalysisService()
    ctrl._pending_import_files = completed

    chat.add_activity(f"🔍 Analiza {len(completed)} faktura...")

    for file_item in completed:
        lines = file_item.invoice_lines or []
        if not lines:
            continue

        invoice_name = file_item.invoice_number or Path(file_item.filepath).stem
        chat.add_activity(f"📋 Analiziram: {invoice_name} ({len(lines)} stavki)")
        QApplication.processEvents()

        try:
            result = svc.analyse(
                lines=lines,
                bruto_kg=file_item.bruto_kg,
                neto_kg=file_item.neto_kg,
                invoice_name=invoice_name,
                has_origin_statement=file_item.has_origin_statement,
                currency="EUR",
            )
            report_html = svc.format_report(result)
            chat.add_agent_message(report_html)
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri analizi {invoice_name}: {e}")

    ctrl.workflow.transition(WorkflowState.COMPLETED)

    chat.show_action_buttons([
        ("📥 Uvezi u deklaraciju", ctrl._analiza_uvezi_action),
        ("🤖 Automatski uvoz",     ctrl._analiza_auto_action),
    ])


def _analiza_uvezi_action(ctrl) -> None:
    if not ctrl._pending_import_files:
        ctrl.view.get_chat_panel().add_agent_message("⚠️ Nema keširanih fajlova za uvoz.")
        return
    ctrl._current_mode = "Uvezi u deklaraciju"
    chat = ctrl.view.get_chat_panel()
    chat.add_activity("📥 Pokretam uvoz iz analize...")
    ctrl._on_all_completed(ctrl._pending_import_files)
    ctrl._pending_import_files = []


def _analiza_auto_action(ctrl) -> None:
    if not ctrl._pending_import_files:
        ctrl.view.get_chat_panel().add_agent_message("⚠️ Nema keširanih fajlova za uvoz.")
        return
    ctrl._current_mode = "Puna automatizacija"
    chat = ctrl.view.get_chat_panel()
    chat.add_activity("🤖 Pokretam automatski uvoz iz analize...")
    ctrl._on_all_completed(ctrl._pending_import_files)
    ctrl._pending_import_files = []


def _wait_for_historical_validation(fw, timeout_ms: int = 30000) -> bool:
    """Sačekaj da FakturaView.historical_validation_worker (ako radi) završi.

    _run_historical_tariff_validation pokreće HistoricalValidationWorker kao
    fire-and-forget QThread i vraća se odmah — rezultati (auto-primijenjeni
    tarifni brojevi) stižu tek kasnije preko finished_validation signala.
    Ovo pumpa Qt event loop dok worker stvarno ne završi (ili istekne
    timeout kao sigurnosna kočnica protiv beskonačnog čekanja).

    Returns:
        True ako je worker postojao i čekanje izvršeno, False ako nije bilo
        aktivnog worker-a (ništa za čekati).
    """
    from PySide6.QtCore import QEventLoop, QThread, QTimer

    worker = getattr(fw, "historical_validation_worker", None)
    if not isinstance(worker, QThread) or not worker.isRunning():
        return False
    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return True


def _puna_auto_pipeline(ctrl, fw, chat, all_lines: list) -> None:
    """
    Puna automatizacija — svaka faza vraća PipelineStageResult; kritična
    greška (FAILED) zaustavlja pipeline prije sljedeće faze umjesto starog
    obrasca "except -> upozorenje -> nastavi". Finalna poruka odražava stvaran
    ishod (COMPLETED/PARTIAL/FAILED/CANCELLED), ne bezuslovno "završeno".

    Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §7
    """
    from gui.tabs.agent.services.pipeline_stage_result import (
        PipelineStageResult, PipelineStageStatus,
    )

    QApplication.processEvents()
    results: list[PipelineStageResult] = []

    # 1. Izračunaj mase — KRITIČNO, zaustavlja pipeline ako ne uspije.
    # Preskoči ako SVE linije već imaju obje težine (npr. parser koji
    # ekstraktuje bruto/neto direktno po stavci, bez potrebe za toolbar-total
    # redistribucijom) — isti obrazac kao provjera "bez_tarife" ispod za
    # auto-popunu tarifa. _on_calculate_masses(auto=True) vraća False i kad
    # NEMA šta da se preračuna (sve već popunjeno, "updated_count == 0" —
    # faktura_view.py:5180) — to nije greška, ali _puna_auto_pipeline je to
    # tretirala kao fatalan pad i lažno zaustavljala cijelu automatizaciju
    # (korisnička primjedba 2026-07-28: mase su ispravno prikazane u tabeli,
    # a pipeline ipak javlja "Izračun masa nije uspio").
    bez_mase = sum(
        1 for l in ctrl.draft.invoice_lines
        if not getattr(l, 'bruto_kg', None) or not getattr(l, 'neto_kg', None)
    )
    if bez_mase > 0:
        chat.add_activity("⚖️ [Auto] Izračunavam mase...")
        try:
            ok = bool(fw and hasattr(fw, '_on_calculate_masses') and fw._on_calculate_masses(auto=True))
        except Exception as e:
            logger.error("[Puna automatizacija] Izračun masa — neočekivan izuzetak: %s", e, exc_info=True)
            ok = False
        if not ok:
            chat.add_activity("❌ Izračun masa nije uspio — automatizacija zaustavljena")
            results.append(PipelineStageResult(
                "mase", PipelineStageStatus.FAILED,
                message="Izračun masa nije uspio (provjeri unesene bruto/neto vrijednosti).",
                can_continue=False,
            ))
            return _finish_puna_auto_pipeline(ctrl, chat, results)
        chat.add_activity("✅ Mase izračunate")
        results.append(PipelineStageResult("mase", PipelineStageStatus.SUCCESS))
    else:
        chat.add_activity("✅ [Auto] Sve stavke već imaju izračunatu masu — preskačem")
        results.append(PipelineStageResult("mase", PipelineStageStatus.SUCCESS))
    QApplication.processEvents()

    # 2. Auto-popuni tarifne — WARNING ako ostanu neriješene, ne zaustavlja.
    bez_tarife = sum(1 for l in ctrl.draft.invoice_lines if not getattr(l, 'tarifni_broj', None))
    if bez_tarife > 0:
        chat.add_activity(f"🤖 [Auto] Popunjavam tarifne brojeve ({bez_tarife} stavki bez tarife)...")
        try:
            mapping_result = (
                fw._on_auto_fill(auto=True) if fw and hasattr(fw, '_on_auto_fill') else None
            )
        except Exception as e:
            logger.error("[Puna automatizacija] Auto-popuna — neočekivan izuzetak: %s", e, exc_info=True)
            mapping_result = None
        preostalo = sum(1 for l in ctrl.draft.invoice_lines if not getattr(l, 'tarifni_broj', None))
        if mapping_result is None:
            chat.add_activity("⚠️ Auto-popuni nije uspio ili nema prijedloga")
            results.append(PipelineStageResult(
                "auto_popuna", PipelineStageStatus.WARNING,
                message="Auto-popuna tarifa nije uspjela ili nije bilo prijedloga.",
                stats={"bez_tarife": preostalo},
            ))
        elif preostalo > 0:
            chat.add_activity(f"⚠️ Auto-popuni završen — {preostalo} stavki i dalje bez tarife")
            results.append(PipelineStageResult(
                "auto_popuna", PipelineStageStatus.WARNING,
                message=f"{preostalo} stavki ostaje bez tarifnog broja nakon auto-popune.",
                stats={"bez_tarife": preostalo},
            ))
        else:
            chat.add_activity("✅ Auto-popuni završen")
            results.append(PipelineStageResult("auto_popuna", PipelineStageStatus.SUCCESS))
        QApplication.processEvents()
    else:
        chat.add_activity("✅ [Auto] Sve stavke imaju tarifni broj — preskačem Auto-popuni")
        results.append(PipelineStageResult("auto_popuna", PipelineStageStatus.SUCCESS))

    # 3. Validacija — KRITIČNO ako postoje greške (RED), WARNING za upozorenja (YELLOW).
    # Koristi postojeći validation_cache (isti izvor kao ručna validacija u Faktura tabu) —
    # ne izmišlja novu poslovnu logiku za "šta je kritično".
    chat.add_activity("🔍 [Auto] Validacija stavki...")
    try:
        if fw and hasattr(fw, '_on_validate_all'):
            ok, error_count, warning_count = fw._on_validate_all(auto=True)
        else:
            ok, error_count, warning_count = False, -1, -1
    except Exception as e:
        logger.error("[Puna automatizacija] Validacija — neočekivan izuzetak: %s", e, exc_info=True)
        ok, error_count, warning_count = False, -1, -1

    if not ok:
        chat.add_activity("❌ Validacija nije mogla biti izvršena — automatizacija zaustavljena")
        results.append(PipelineStageResult(
            "validacija", PipelineStageStatus.FAILED,
            message="Validacija nije mogla biti izvršena.", can_continue=False,
        ))
        return _finish_puna_auto_pipeline(ctrl, chat, results)
    if error_count > 0:
        chat.add_activity(f"❌ Validacija: {error_count} grešaka — automatizacija zaustavljena")
        results.append(PipelineStageResult(
            "validacija", PipelineStageStatus.FAILED,
            message=f"{error_count} kritičnih grešaka u validaciji stavki.",
            can_continue=False, stats={"errors": error_count, "warnings": warning_count},
        ))
        return _finish_puna_auto_pipeline(ctrl, chat, results)
    if warning_count > 0:
        chat.add_activity(f"⚠️ Validacija završena — {warning_count} upozorenja")
        results.append(PipelineStageResult(
            "validacija", PipelineStageStatus.WARNING,
            message=f"{warning_count} upozorenja u validaciji stavki.",
            stats={"warnings": warning_count},
        ))
    else:
        chat.add_activity("✅ Validacija završena")
        results.append(PipelineStageResult("validacija", PipelineStageStatus.SUCCESS))
    QApplication.processEvents()

    # 3b. _on_validate_all (auto=True) iznutra pokreće HistoricalValidationWorker
    # kao fire-and-forget QThread (docs/CONTEXT.md §59 — DB upiti po stavci su
    # prespori za UI thread) i vraća se ODMAH, prije nego worker stvarno završi.
    # Bez ovog čekanja, "Puna automatizacija" je nastavljala na EUR.1/PE potvrdu
    # i kreiranje naimenovanja dok je taj worker još radio — korisnička
    # primjedba 2026-07-27: "Nije završen proces u tabu faktura, tek kad se tu
    # sve završi proces može ići dalje."
    if _wait_for_historical_validation(fw):
        chat.add_activity("✅ Istorijska tarifna provjera završena")
    QApplication.processEvents()

    # 4. Deklarant mora potvrditi porijeklo i preferencijalne dokumente prije naimenovanja.
    chat.add_activity("🧾 [Auto] Čekam potvrdu deklaranta za porijeklo i EUR.1/PE dokumente...")
    reply = QMessageBox.question(
        ctrl.view,
        "Potvrda prije kreiranja naimenovanja",
        "Prije kreiranja naimenovanja deklarant mora provjeriti:\n\n"
        "• zemlju porijekla za stavke\n"
        "• da li postoji izjava o porijeklu na fakturi\n"
        "• da li je potreban EUR.1 obrazac\n"
        "• da li su PE1/PE2/PE3 dokumenti ispravno postavljeni\n\n"
        "Da li je ova provjera završena i smije li se nastaviti sa kreiranjem naimenovanja?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if reply != QMessageBox.Yes:
        chat.add_agent_message(
            "⏸️ <b>Puna automatizacija pauzirana.</b><br>"
            "Provjeri porijeklo i EUR.1/PE dokumente u Faktura tabu, "
            "pa kreiraj naimenovanja kada budeš siguran."
        )
        chat.add_activity("⏸️ Kreiranje naimenovanja zaustavljeno — čeka se deklarantska provjera")
        results.append(PipelineStageResult(
            "deklarantska_potvrda", PipelineStageStatus.CANCELLED,
            message="Deklarant nije potvrdio provjeru porijekla/EUR.1/PE dokumenata.",
            can_continue=False,
        ))
        return _finish_puna_auto_pipeline(ctrl, chat, results)
    results.append(PipelineStageResult("deklarantska_potvrda", PipelineStageStatus.SUCCESS))

    # 5. Kreiraj naimenovanja — KRITIČNO.
    chat.add_activity("📋 [Auto] Kreiram naimenovanja...")
    try:
        ok = bool(
            fw and hasattr(fw, '_on_create_naimenovanja') and fw._on_create_naimenovanja(auto=True)
        )
    except Exception as e:
        logger.error("[Puna automatizacija] Kreiranje naimenovanja — neočekivan izuzetak: %s", e, exc_info=True)
        ok = False
    if not ok:
        chat.add_activity("❌ Kreiranje naimenovanja nije uspjelo — automatizacija zaustavljena")
        results.append(PipelineStageResult(
            "naimenovanja", PipelineStageStatus.FAILED,
            message="Kreiranje naimenovanja nije uspjelo.", can_continue=False,
        ))
        return _finish_puna_auto_pipeline(ctrl, chat, results)
    chat.add_activity("✅ Naimenovanja kreirana")
    results.append(PipelineStageResult("naimenovanja", PipelineStageStatus.SUCCESS))
    QApplication.processEvents()

    _finish_puna_auto_pipeline(ctrl, chat, results)


def _finish_puna_auto_pipeline(ctrl, chat, results: list) -> None:
    """Izračunaj finalni ishod iz svih faza i ispiši TAČNU poruku — nikad
    bezuslovno "završeno" ako neka faza nije stvarno uspjela."""
    from gui.tabs.agent.services.pipeline_stage_result import (
        PipelineStageStatus, overall_outcome,
    )
    from services.agent.chat.audit_log import AuditEvent, record as record_audit

    outcome = overall_outcome(results)
    for r in results:
        record_audit(AuditEvent(
            routing_layer="pipeline",
            tool="_puna_auto_pipeline",
            status=r.status.value,
            pipeline_stage=r.stage,
            extra={"outcome": outcome} if r is results[-1] else {},
        ))

    if outcome == "CANCELLED":
        return  # Poruka je već ispisana u koraku 4 (deklarantska_potvrda)

    if outcome == "FAILED":
        failed = next((r for r in results if r.status == PipelineStageStatus.FAILED), None)
        chat.add_agent_message(
            f"❌ <b>Puna automatizacija zaustavljena.</b><br>"
            f"Faza: <b>{failed.stage if failed else '?'}</b><br>"
            f"{failed.message if failed else ''}<br><br>"
            f"💡 Ispravi problem u Faktura tabu i pokreni ponovo, ili nastavi ručno."
        )
        return

    bez_tarife = sum(1 for l in ctrl.draft.invoice_lines if not l.tarifni_broj)
    n_naim = len(getattr(ctrl.draft, 'items', []))

    if outcome == "PARTIAL":
        warnings = [r for r in results if r.status == PipelineStageStatus.WARNING and r.message]
        warn_lines = "<br>".join(f"⚠️ {r.stage}: {r.message}" for r in warnings)
        chat.add_agent_message(
            f"⚠️ <b>Puna automatizacija završena djelimično.</b><br>"
            f"Stavki: {len(ctrl.draft.invoice_lines)} | Bez tarifnog: <b>{bez_tarife}</b><br>"
            f"Naimenovanja: <b>{n_naim}</b><br>"
            f"Zaglavlje: <b>nije automatski popunjeno</b><br><br>"
            f"{warn_lines}<br><br>"
            f"💡 Provjeri upozorenja i naimenovanja, ručno provjeri/popuni zaglavlje, zatim izvezi XML."
        )
        return

    chat.add_agent_message(
        f"🎉 <b>Puna automatizacija završena!</b><br>"
        f"Stavki: {len(ctrl.draft.invoice_lines)} | Bez tarifnog: <b>{bez_tarife}</b><br>"
        f"Naimenovanja: <b>{n_naim}</b><br>"
        f"Zaglavlje: <b>nije automatski popunjeno</b><br><br>"
        f"💡 Provjeri naimenovanja, ručno provjeri/popuni zaglavlje, zatim izvezi XML."
    )


def _get_preference_by_country(ctrl, country_code: str, exporter_name: str = "") -> str:
    if exporter_name and exporter_name.strip():
        try:
            historical_pref = ctrl.historical_svc.get_preference_safe(exporter_name, country_code)
            if historical_pref:
                return historical_pref
        except Exception:
            pass

    eu_countries = {
        'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
        'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
        'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
    }
    cefta_countries = {'RS', 'BA', 'ME', 'MK', 'AL', 'XK', 'MD'}
    c = (country_code or '').upper()
    if c in eu_countries:
        return 'EUPR'
    if c in cefta_countries:
        return 'CEFTAR'
    if c == 'TR':
        return 'TRPR'
    if c == 'IR':
        return 'IRP'
    if c in {'CH', 'LI'}:
        return 'EFTA1R'
    if c == 'IS':
        return 'EFTA2R'
    if c == 'NO':
        return 'EFTA3R'
    return ''


def _auto_handle_povlastice(ctrl, invoice_lines: list, chat,
                             has_origin_statement: bool = False) -> dict:
    updated_pe2 = 0
    updated_eur1 = 0
    eur1_pending = 0

    for line in invoice_lines:
        country = getattr(line, 'zemlja_porijekla', None)
        if not country:
            continue

        pov = _get_preference_by_country(ctrl, country)
        if not pov:
            continue

        line_has_stmt = has_origin_statement or getattr(line, 'has_origin_statement', False)

        if line_has_stmt:
            updated_pe2 += 1
        else:
            if not getattr(line, 'eur1_number', None):
                eur1_pending += 1

    result = {'pe2': updated_pe2, 'eur1': updated_eur1, 'eur1_pending': eur1_pending}

    lines_with_country = sum(1 for l in invoice_lines if getattr(l, 'zemlja_porijekla', None))
    if updated_pe2 > 0:
        chat.add_activity(
            f"🌍 PE2/PE3 kandidati: {updated_pe2} stavki ceka potvrdu deklaranta"
            + (f" (has_origin_statement={has_origin_statement})" if has_origin_statement else "")
        )
    elif lines_with_country > 0:
        chat.add_activity(f"ℹ️ {lines_with_country} stavki ima zemlja_porijekla — povlastice se primjenjuju tek nakon potvrde deklaranta")
    else:
        chat.add_activity(f"⚠️ Povlastice: 0 stavki ima zemlja_porijekla — nije moguće auto-postavljanje")

    if eur1_pending > 0:
        chat.add_activity(f"⚠️ {eur1_pending} stavki čeka ručni unos EUR1 broja")

    return result


def _apply_eur1_to_naimenovanja(ctrl, eur1_data: dict, chat) -> None:
    if not ctrl.draft or not getattr(ctrl.draft, 'items', None):
        return

    updated = 0
    doc44 = ""
    for country, data in eur1_data.items():
        eur1_num = (data.get('eur1_number') or '').strip()
        preference = (data.get('preference') or '').strip()
        has_stmt = data.get('has_origin_statement', False)
        doc_code = (data.get('code') or '').strip().upper()
        if doc_code not in {"PE1", "PE2", "PE3"}:
            doc_code = "PE2" if has_stmt else "PE1"
        doc44 = _normalize_pe_document_text(f"{doc_code} {eur1_num}".strip())

        for item in ctrl.draft.items:
            pov = (getattr(item, 'preference_code', '') or '').strip()
            origin = (getattr(item, 'origin_country_code', '') or '').strip()
            if pov == preference or origin.upper() == country.upper():
                item.attached_document4 = doc44
                # Rub.36 mora biti popunjena ako je Rub.44 popunjena
                if not pov and preference:
                    item.preference_code = preference
                updated += 1

    if updated:
        chat.add_activity(f"📋 Rb.44 ažuriran na {updated} naimenovanja ({doc44})")

        # Sinhronizuj PE1/PE2/PE3 u header_attached_documents
        # Vidi docs/sections/pe-rub44-4.md
        _sync_pe_docs_to_header(ctrl)


def _sync_pe_docs_to_header(ctrl) -> None:
    """Sinhronizuj PE1/PE2/PE3 iz attached_document4 u header_attached_documents."""
    header_docs = getattr(ctrl.draft, "header_attached_documents", None)
    if header_docs is None:
        return

    pe_entries: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in ctrl.draft.items:
        _clear_secondary_pe_documents(item)
        raw_doc4 = (getattr(item, 'attached_document4', '') or '').strip()
        doc4 = _normalize_pe_document_text(raw_doc4)
        if doc4 != raw_doc4:
            item.attached_document4 = doc4
        if not doc4:
            continue
        parts = doc4.split(' ', 1)
        sifra = parts[0].strip()
        broj = parts[1].strip() if len(parts) > 1 else ''
        if sifra in _PE_DOC_CODES:
            key = (sifra, broj)
            if key not in seen:
                seen.add(key)
                pe_entries.append(key)

    header_docs[:] = [d for d in header_docs if d.code not in _PE_DOC_CODES]

    if pe_entries:
        from core.draft.draft import AttachedDocument
        naziv_map = {
            "PE1": "EUR.1 obrazac",
            "PE2": "Izjava na fakturi",
            "PE3": "Izjava ovlaštenog izvoznika",
        }
        for sifra, broj in pe_entries:
            naziv = naziv_map.get(sifra, f"Dokument {sifra}")
            header_docs.append(AttachedDocument(
                code=sifra,
                name=naziv,
                number=broj,
                from_rule=sifra == "PE1",
            ))

        ctrl.draft.mark_dirty()


def _validiraj_prije_uvoza(invoice_lines: list, chat) -> tuple:
    errors = []
    warnings = []

    chat.add_activity("🔍 Validacija podataka...")

    # 1. Provjera duplikata
    try:
        from services.zaglavlje_service import ZaglavljeService
        zaglavlje_svc = ZaglavljeService()
        brojevi_faktura = set()
        for line in invoice_lines:
            if hasattr(line, 'broj_fakture') and line.broj_fakture:
                brojevi_faktura.add(line.broj_fakture)
        for broj in brojevi_faktura:
            if zaglavlje_svc.postoji_broj_fakture(broj):
                errors.append(f"❌ Faktura br. '{broj}' već postoji u bazi!")
            else:
                chat.add_activity(f"  ✅ Faktura {broj}: Nije duplikat")
    except Exception as _e:
        logger.warning("Provjera duplikata fakture neuspješna: %s", _e)

    # 2. Provjera partnera
    try:
        from services.sifarnici_service import SifarniciService
        sifarnici_svc = SifarniciService()
        partneri = set()
        for line in invoice_lines:
            if hasattr(line, 'dobavljac') and line.dobavljac:
                partneri.add(line.dobavljac)
            if hasattr(line, 'primalac') and line.primalac:
                partneri.add(line.primalac)
        for partner in partneri:
            found = sifarnici_svc.search_partneri(partner)
            if not found or len(found) == 0:
                warnings.append(f"⚠️ Partner '{partner}' nije u šifrarniku")
            else:
                chat.add_activity(f"  ✅ Partner {partner}: Nađen u šifrarniku")
    except Exception as _e:
        logger.warning("Provjera partnera u šifrarniku neuspješna: %s", _e)

    # 3. Provjera formata tarifnih
    try:
        for line in invoice_lines:
            if hasattr(line, 'tarifni_broj') and line.tarifni_broj:
                tarif = line.tarifni_broj.strip()
                if len(tarif) >= 4 and '.' in tarif:
                    chat.add_activity(f"  ✅ Tarifni {tarif}: Format ispravan")
    except Exception as _e:
        logger.warning("Provjera formata tarifnih neuspješna: %s", _e)

    for w in warnings:
        chat.add_activity(w)

    if errors:
        chat.add_activity(f"❌ Validacija NIJE uspješna: {len(errors)} grešaka")
        return (False, errors + warnings)
    else:
        chat.add_activity(f"✅ Validacija uspješna ({len(warnings)} upozorenja)")
        return (True, warnings)


def _generisi_izvjestaj(ctrl, chat) -> bool:
    from services.faktura.validation_service import FakturaItemValidator

    chat.add_activity("📊 Generisanje izvještaja...")

    errors = []
    warnings = []
    suggestions = []

    FakturaItemValidator()

    for i, line in enumerate(ctrl.draft.invoice_lines):
        row_num = i + 1

        if not line.tarifni_broj:
            errors.append(f"Stavka {row_num}: Nema tarifni broj")
            suggestions.append(f"  → Klikni 'Auto-popuni tarifne' za stavku {row_num}")
        else:
            try:
                from services.naimenovanja.tariff_service import TariffService
                tariff_svc = TariffService()
                if not tariff_svc.validate_tariff(line.tarifni_broj):
                    errors.append(f"Stavka {row_num}: Nevažeći tarifni '{line.tarifni_broj}'")
                    suggestions.append(f"  → Ručno provjeri tarifni za stavku {row_num}")
            except Exception as _e:
                logger.debug("Validacija tarifnog broja stavke %s: %s", row_num, _e)

        if not line.zemlja_porijekla:
            warnings.append(f"Stavka {row_num}: Nema zemlju porijekla")

        if not line.bruto_kg and not line.neto_kg:
            warnings.append(f"Stavka {row_num}: Nema mase (bruto/neto)")
            suggestions.append(f"  → Unesi mase za stavku {row_num}")
        elif line.bruto_kg and line.neto_kg and line.bruto_kg < line.neto_kg:
            errors.append(f"Stavka {row_num}: Bruto ({line.bruto_kg}) < Neto ({line.neto_kg})")
            suggestions.append(f"  → Ispravi mase za stavku {row_num}")

        if not line.jm or line.jm.strip() == "":
            warnings.append(f"Stavka {row_num}: Nema jedinicu mjere")

    if errors:
        chat.add_agent_message(
            f"⚠️ <b>Uočio sam {len(errors)} problema:</b><br><br>"
            f"❌ <b>Greške ({len(errors)}):</b><br>"
            f"{'<br>'.join(errors[:5])}" + (f"<br>... i još {len(errors)-5}" if len(errors) > 5 else "") +
            f"<br><br>"
            f"💡 <b>Prijedlozi:</b><br>"
            f"{'<br>'.join(suggestions[:5])}" + (f"<br>... i još {len(suggestions)-5}" if len(suggestions) > 5 else "")
        )
    elif warnings:
        chat.add_agent_message(
            f"✅ <b>Sve stavke su ispravne!</b><br><br>"
            f"⚠️ <b>Upozorenja ({len(warnings)}):</b><br>"
            f"{'<br>'.join(warnings[:5])}" + (f"<br>... i još {len(warnings)-5}" if len(warnings) > 5 else "")
        )
    else:
        chat.add_agent_message(
            f"✅ <b>Sve je savršeno!</b><br>"
            f"Nema grešaka ni upozorenja."
        )

    return len(errors) == 0


def _otvori_faktura_tab_nakon_uvoza(ctrl, chat) -> None:
    chat.add_activity("🔄 Otvaranje Faktura taba...")

    parent = ctrl.view.parent()
    while parent:
        if 'MainWindow' in str(type(parent)):
            break
        parent = parent.parent()

    faktura_tab_widget = ctrl.faktura_tab
    if hasattr(ctrl.faktura_tab, 'view'):
        faktura_tab_widget = ctrl.faktura_tab.view

    if parent and faktura_tab_widget:
        try:
            from PySide6.QtWidgets import QTabWidget
            tabs_widgets = parent.findChildren(QTabWidget)
            if tabs_widgets:
                tabs = tabs_widgets[0]
                tabs.setCurrentWidget(ctrl.faktura_tab)
                chat.add_activity("✅ Prebačeno na Faktura tab")
                if hasattr(faktura_tab_widget, '_load_data_from_draft'):
                    faktura_tab_widget._load_data_from_draft()
                    chat.add_activity("✅ Podaci učitani u Faktura tab")
                else:
                    chat.add_activity("⚠️ _load_data_from_draft nije dostupan")
            else:
                chat.add_activity("⚠️ Tabs widget nije pronađen")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri otvaranju Faktura taba: {e}")
    else:
        chat.add_activity("⚠️ Parent window nije pronađen")

