"""
XML Workflow Service

Logika za pronalaženje i primjenu XML templatea na zaglavlje deklaracije,
te za izvoz deklaracije u ASYCUDA XML fajl.

Premješteno iz agent_controller.py radi smanjenja veličine controllera.
"""

import re
import logging
from html import escape
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

logger = logging.getLogger("deklarant_pro.agent.xml_workflow")


class XmlWorkflowService:
    """Upravljanje XML templateima i exportom deklaracije."""

    def __init__(self, controller):
        self._ctrl = controller

    # ── Javni API ────────────────────────────────────────────────────

    def primjeni_xml_template(self, all_lines: list, chat, silent: bool = False) -> str:
        return _primjeni_xml_template(self._ctrl, all_lines, chat, silent)

    def izvezi_xml(self, chat, confirm_fn=None) -> None:
        _izvezi_xml(self._ctrl, chat, confirm_fn=confirm_fn)


# ── Implementacija (slobodne funkcije — lakše testirati) ─────────────


def _primjeni_xml_template(ctrl, all_lines: list, chat, silent: bool = False) -> str:
    """
    Pronađi stari XML sa istim pošiljaocem i primijeni whitelist polja na draft zaglavlje.

    Redosljed pretrage:
    1. Par (exporter+importer) — kad parser izvuče izvoznika iz fakture
    2. Consignee-only — fallback kad nema izvoznika
    3. Filename hint
    4. Lokalni XML fajlovi (fallback)
    """
    if not ctrl.draft:
        return "⚠️ Draft nije inicijalizovan"

    chat.add_activity("🔍 Tražim XML template za zaglavlje...")

    # ── Tip deklaracije iz drafta (IM/EX) ───────────────────────────
    draft_decl_type = (getattr(ctrl.draft, 'deklaracija_tip', '') or '').upper().strip()
    is_import = draft_decl_type.startswith("IM") or not draft_decl_type

    # ── JIB i naziv uvoznika (Rb.8) ─────────────────────────────────
    consignee_jib  = getattr(ctrl.draft, 'primalac_id', '') or ''
    consignee_name = getattr(ctrl.draft, 'primalac_naziv', '') or ''

    if not consignee_name:
        for line in all_lines:
            name = getattr(getattr(line, 'importer', None), 'name', None)
            if name and name.strip():
                consignee_name = name.strip()
                break

    # ── Hint za stranog dobavljača (Rb.2) ───────────────────────────
    exporter_hint    = ""
    hint_from_invoice = False
    for line in all_lines:
        name = getattr(getattr(line, 'exporter', None), 'name', None)
        if name and name.strip():
            exporter_hint     = name.strip()
            hint_from_invoice = True
            break

    # ── Hint iz naziva fajla ─────────────────────────────────────────
    filename_hint = ""
    doc = ctrl.view.get_document_panel()
    candidates = []
    for file_item in doc.get_files():
        stem = Path(file_item).stem if isinstance(file_item, str) else Path(file_item.filepath).stem
        if re.match(r'^DOC\d+', stem, re.IGNORECASE):
            continue
        if re.match(r'^[\d\-_]+$', stem):
            continue
        clean = re.sub(r'[-_\s]*[\d/\\-]+$', '', stem).strip()
        if len(clean) >= 3:
            candidates.append(clean)
    if candidates:
        filename_hint = max(candidates, key=len)

    if not exporter_hint:
        exporter_hint = filename_hint

    chat.add_activity(
        f"🔍 Tražim template — strani dobavljač: '{exporter_hint}'"
        + (f", uvoznik JIB: {consignee_jib}" if consignee_jib else "")
        + (f" (tip: {draft_decl_type})" if draft_decl_type else "")
    )

    from services.agent.validation.xml_template_service import XmlTemplateService, TemplateMatch
    svc   = XmlTemplateService()
    match = None

    def _build_match(db_result):
        xml_path = Path(db_result['xml_filepath'])
        if not xml_path.exists():
            return None
        exporter_from_xml, fields = svc._parse_xml(xml_path)
        xml_decl_type = (fields.get("deklaracija_tip") or "").upper().strip()
        if draft_decl_type and xml_decl_type and not xml_decl_type.startswith(draft_decl_type):
            chat.add_activity(
                f"⚠️ '{xml_path.name}' je tip {xml_decl_type}, "
                f"a deklaracija je {draft_decl_type} — preskačem"
            )
            return None
        match_type = db_result.get('match_type', 'db')
        score = (1.0 if 'jib'  in match_type else
                 0.90 if 'name' in match_type else 0.75)
        chat.add_activity(
            f"✅ Nađen u bazi: '{xml_path.name}' "
            f"(tip: {xml_decl_type or '?'}, match: {match_type}, "
            f"uvoznik: {db_result.get('consignee_original', '—')})"
        )
        return TemplateMatch(
            filepath=str(xml_path),
            filename=xml_path.name,
            exporter_name=db_result.get('exporter_original') or exporter_from_xml,
            match_score=score,
            fields=fields,
            declaration_type=xml_decl_type,
        )

    # 1a. Par (exporter + importer) — najtačnije
    if not match and exporter_hint and hint_from_invoice:
        try:
            from services.agent.learning.exporter_xml_indexer import find_xml_for_pair
            db_result = find_xml_for_pair(
                exporter_hint,
                consignee_jib=consignee_jib,
                consignee_hint=consignee_name,
            )
            if db_result:
                match = _build_match(db_result)
                if match:
                    chat.add_activity(
                        f"✅ Template nađen po paru: "
                        f"{db_result.get('exporter_original')} → {db_result.get('consignee_original')}"
                    )
        except Exception as e:
            chat.add_activity(f"⚠️ Pair DB lookup greška: {e}")

    # 1b. Consignee-only — SAMO kad nemamo info o izvozniku iz fakture.
    # Ako znamo ko je izvoznik (hint_from_invoice=True), preskačemo ovaj korak —
    # vratio bi XML od pogrešnog dobavljača za istog uvoznika.
    if not match and is_import and not hint_from_invoice and (consignee_jib or consignee_name):
        try:
            from services.agent.learning.exporter_xml_indexer import find_xml_by_consignee
            db_result = find_xml_by_consignee(
                consignee_jib=consignee_jib,
                consignee_hint=consignee_name,
            )
            if db_result:
                match = _build_match(db_result)
                if match:
                    chat.add_activity("✅ Template nađen po uvozniku (consignee)")
        except Exception as e:
            chat.add_activity(f"⚠️ Consignee lookup greška: {e}")

    # 1c. Filename hint
    if not match and filename_hint and not hint_from_invoice:
        try:
            if is_import:
                from services.agent.learning.exporter_xml_indexer import find_xml_by_consignee
                db_result = find_xml_by_consignee(consignee_jib="", consignee_hint=filename_hint)
            else:
                from services.agent.learning.exporter_xml_indexer import find_xml_for_pair
                db_result = find_xml_for_pair(
                    filename_hint,
                    consignee_jib=consignee_jib,
                    consignee_hint=consignee_name,
                )
            if db_result:
                match = _build_match(db_result)
        except Exception as e:
            chat.add_activity(f"⚠️ Filename DB lookup greška: {e}")

    # 2. Fallback — lokalni XML fajlovi
    if not match:
        try:
            match = svc.find_template(exporter_hint, declaration_type=draft_decl_type)
            if match:
                chat.add_activity(
                    f"✅ Nađen lokalno: '{match.filename}' "
                    f"(pošiljalac: '{match.exporter_name}', "
                    f"tip: {match.declaration_type}, poklapanje: {int(match.match_score * 100)}%)"
                )
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri pretrazi XML templatea: {e}")

    if not match:
        chat.add_activity(f"ℹ️ Nema XML templatea za '{exporter_hint}' — popuni zaglavlje ručno")
        return f"ℹ️ Nema prethodnog XML-a za '{exporter_hint}'"

    # ── Primijeni template na draft ──────────────────────────────────
    applied = svc.apply_to_draft(ctrl.draft, match.fields)

    if not applied:
        chat.add_activity("ℹ️ Sva zaglavlje polja već popunjena — template nije primijenjen")
        return "ℹ️ Zaglavlje već popunjeno"

    chat.add_activity(f"✅ Primijenjeno {len(applied)} zaglavlje polja iz templatea")

    # ── Provjeri aktuelni kurs od CBBH (non-EUR valute) ─────────────
    try:
        from services.agent.cbbh_exchange_service import update_draft_kurs
        update_draft_kurs(ctrl.draft, chat=chat)
    except Exception as e:
        chat.add_activity(f"⚠️ CBBH kurs provjera neuspješna: {e}")

    # ── Osvježi Zaglavlje tab ────────────────────────────────────────
    if ctrl.zaglavlje_tab:
        try:
            if hasattr(ctrl.zaglavlje_tab, 'load_from_draft'):
                ctrl.zaglavlje_tab.load_from_draft(ctrl.draft)
            elif hasattr(ctrl.zaglavlje_tab, 'reload_data'):
                ctrl.zaglavlje_tab.reload_data()
            elif hasattr(ctrl.zaglavlje_tab, 'refresh'):
                ctrl.zaglavlje_tab.refresh()
            chat.add_activity("✅ Zaglavlje tab osvježen")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri osvježavanju Zaglavlje taba: {e}")

    if silent:
        chat.add_activity(
            f"✅ Zaglavlje popunjeno iz: <b>{match.filename}</b> "
            f"(pošiljalac: {match.exporter_name})"
        )
        return f"✅ Popunjeno iz {match.filename}"

    # ── Prikaži dijalog sa rezimeom (interaktivni modovi) ────────────
    try:
        from gui.dialogs.zaglavlje_template_dialog import ZaglavljeTemplateDialog
        dialog = ZaglavljeTemplateDialog(match, applied, parent=ctrl.view)
        result = dialog.exec()
        if result != 1:
            for field_name in applied:
                try:
                    setattr(ctrl.draft, field_name, "")
                except Exception:
                    pass
            if ctrl.zaglavlje_tab and hasattr(ctrl.zaglavlje_tab, 'load_from_draft'):
                ctrl.zaglavlje_tab.load_from_draft(ctrl.draft)
            chat.add_activity("ℹ️ Template odbačen — zaglavlje polja resetovana")
        else:
            chat.add_activity("✅ Template prihvaćen — popuni preostala polja u Zaglavlje tabu")
    except Exception as e:
        chat.add_activity(f"⚠️ Greška pri prikazu dijaloga: {e}")

    return f"✅ Popunjeno iz {match.filename}"


def _izvezi_xml(ctrl, chat, confirm_fn=None) -> None:
    """Izvezi deklaraciju u ASYCUDA XML fajl.

    Prije popravke ova funkcija nije pozivala nijednu provjeru spremnosti —
    izvoz je bio moguć i za blokiran draft, a otkazan file dialog i uspjeh
    nisu bili razlučivi (oboje tiho, bez poruke). Sada: readiness → (BLOCKED
    odbija izvoz) → eksplicitna potvrda → file dialog → export, sa jasnom
    porukom za svaki mogući ishod. Vidi
    agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.

    confirm_fn: Callable[[str, str], bool] — (naslov, pitanje) -> bool.
    Default (None) koristi QMessageBox.question (GUI). Testovi prosljeđuju
    lambdu bez GUI zavisnosti (plan §7.6.c).
    """
    if not ctrl.draft:
        return

    from services.agent.validation.xml_readiness_service import (
        ReadinessStatus,
        provjeri_spremnost_za_xml,
    )
    from services.agent.validation.renderer import render_summary_html

    result = provjeri_spremnost_za_xml(ctrl.draft)

    if result.status == ReadinessStatus.BLOCKED:
        chat.add_activity(f"❌ Izvoz blokiran — {result.blocking_count} kritičnih nalaza")
        for summary in result.summaries:
            if summary.blocking_count:
                chat.add_agent_message(render_summary_html(summary))
        chat.add_agent_message(
            "❌ <b>XML izvoz nije moguć.</b><br>"
            "Deklaracija ima kritične nalaze koji moraju biti ispravljeni prije izvoza. "
            "Pokreni <b>provjeri deklaraciju</b> za detalje."
        )
        return

    if result.warning_count:
        chat.add_activity(f"⚠️ {result.warning_count} upozorenja prije izvoza")

    if confirm_fn is None:
        def confirm_fn(title: str, question: str) -> bool:
            from PySide6.QtWidgets import QMessageBox
            return QMessageBox.question(
                ctrl.view, title, question,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            ) == QMessageBox.Yes

    warn_note = f" ({result.warning_count} upozorenja — provjeri prije nastavka)" if result.warning_count else ""
    confirmed = confirm_fn(
        "Potvrda XML izvoza",
        f"Deklaracija je spremna za izvoz{warn_note}. Nastaviti sa izvozom?",
    )
    if not confirmed:
        chat.add_activity("ℹ️ Izvoz otkazan — potvrda nije data")
        chat.add_agent_message("ℹ️ Izvoz otkazan. Fajl nije kreiran.")
        return
    if getattr(ctrl.draft, "revision", 0) != result.draft_revision:
        chat.add_activity("❌ Izvoz blokiran — deklaracija je promijenjena nakon provjere")
        chat.add_agent_message(
            "❌ Deklaracija je promijenjena nakon provjere spremnosti. "
            "Ponovi provjeru prije XML izvoza."
        )
        return

    try:
        from exporters.asycuda_xml_builder import export_to_xml

        filepath, _ = QFileDialog.getSaveFileName(
            ctrl.view,
            "Sačuvaj ASYCUDA XML",
            "",
            "XML Files (*.xml)"
        )
        if not filepath:
            chat.add_activity("ℹ️ Izvoz otkazan — fajl nije izabran")
            return
        if getattr(ctrl.draft, "revision", 0) != result.draft_revision:
            chat.add_activity("❌ Izvoz blokiran — deklaracija je promijenjena")
            chat.add_agent_message(
                "❌ Deklaracija je promijenjena tokom izvoza. "
                "Ponovi provjeru prije kreiranja XML fajla."
            )
            return

        export_to_xml(ctrl.draft, filepath)
        chat.add_activity(f"✅ XML exportovan: {Path(filepath).name}")
        chat.add_agent_message(
            f"✅ <b>XML izvezen.</b><br>Fajl sačuvan: <b>{Path(filepath).name}</b>"
        )
    except Exception as e:
        logger.error(f"Greška pri XML exportu: {e}", exc_info=True)
        chat.add_activity(f"❌ Greška pri XML exportu: {e}")
        chat.add_agent_message(f"❌ Greška pri izvozu XML-a: {escape(str(e))}")
