"""
Import Pipeline Service

Pipeline logika za sve tri procesne rute agenta:
  - Analiza mode (prikaÅ¾i izvjeÅ¡taj, ponudi akcije)
  - Uvezi u deklaraciju mode (dijalozi, ruÄna potvrda)
  - Puna automatizacija mode (auto-koraci uz obaveznu deklarantsku potvrdu)

PremjeÅ¡teno iz agent_controller.py radi smanjenja veliÄine controllera.
"""

import logging
import re
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gui.utils.safe_message_box import SafeMessageBox as QMessageBox

logger = logging.getLogger("deklarant_pro.agent.import_pipeline")

EUR1_THRESHOLD = 6000.0  # EUR â€” iznad ovog iznosa standardna izjava ne vaÅ¾i
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

    VraÄ‡a:
      'pe3'  â€” izjava ovlaÅ¡tenog izvoznika (PE3, bez ograniÄenja vrijednosti)
      'pe2'  â€” standardna izjava na fakturi, vrijednost â‰¤ 6.000 EUR (PE2)
      'eur1' â€” EUR.1 obrazac potreban (PE1):
               â€¢ standardna izjava + vrijednost > 6.000 EUR, ILI
               â€¢ nema izjave ali stavke imaju zemlja_porijekla
      'none' â€” nema niÅ¡ta za rjeÅ¡avati
    """
    if has_origin_statement:
        if is_authorized_exporter:
            return 'pe3'
        # Standardna izjava â€” provjeri ukupnu vrijednost robe s porijeklom
        val = sum(l.iznos or 0 for l in lines if getattr(l, 'zemlja_porijekla', None))
        if val == 0:
            val = sum(l.iznos or 0 for l in lines)
        return 'pe2' if val <= EUR1_THRESHOLD else 'eur1'
    # Nema izjave â€” EUR.1 potreban ako stavke imaju zemlja_porijekla
    has_pending = any(
        getattr(l, 'zemlja_porijekla', None)
        and not getattr(l, 'has_origin_statement', False)
        and not getattr(l, 'eur1_number', None)
        for l in lines
    )
    return 'eur1' if has_pending else 'none'


class ImportPipelineService:
    """Upravljanje pipeline modovima i pomoÄ‡nim koracima uvoza."""

    def __init__(self, controller):
        self._ctrl = controller

    # â”€â”€ Javni API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ Implementacija (slobodne funkcije â€” lakÅ¡e testirati) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _analiza_pipeline(ctrl, completed: list, chat) -> None:
    from services.agent.invoice_analysis_service import InvoiceAnalysisService
    from ..workflow_state import WorkflowState

    svc = InvoiceAnalysisService()
    ctrl._pending_import_files = completed

    chat.add_activity(f"ðŸ” Analiza {len(completed)} faktura...")

    for file_item in completed:
        lines = file_item.invoice_lines or []
        if not lines:
            continue

        invoice_name = file_item.invoice_number or Path(file_item.filepath).stem
        chat.add_activity(f"ðŸ“‹ Analiziram: {invoice_name} ({len(lines)} stavki)")
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
            chat.add_activity(f"âš ï¸ GreÅ¡ka pri analizi {invoice_name}: {e}")

    ctrl.workflow.transition(WorkflowState.COMPLETED)

    chat.show_action_buttons([
        ("ðŸ“¥ Uvezi u deklaraciju", ctrl._analiza_uvezi_action),
        ("ðŸ¤– Automatski uvoz",     ctrl._analiza_auto_action),
    ])


def _analiza_uvezi_action(ctrl) -> None:
    if not ctrl._pending_import_files:
        ctrl.view.get_chat_panel().add_agent_message("âš ï¸ Nema keÅ¡iranih fajlova za uvoz.")
        return
    ctrl._current_mode = "Uvezi u deklaraciju"
    chat = ctrl.view.get_chat_panel()
    chat.add_activity("ðŸ“¥ Pokretam uvoz iz analize...")
    ctrl._on_all_completed(ctrl._pending_import_files)
    ctrl._pending_import_files = []


def _analiza_auto_action(ctrl) -> None:
    if not ctrl._pending_import_files:
        ctrl.view.get_chat_panel().add_agent_message("âš ï¸ Nema keÅ¡iranih fajlova za uvoz.")
        return
    ctrl._current_mode = "Puna automatizacija"
    chat = ctrl.view.get_chat_panel()
    chat.add_activity("ðŸ¤– Pokretam automatski uvoz iz analize...")
    ctrl._on_all_completed(ctrl._pending_import_files)
    ctrl._pending_import_files = []


def _puna_auto_pipeline(ctrl, fw, chat, all_lines: list) -> None:
    QApplication.processEvents()

    # 1. IzraÄunaj mase
    chat.add_activity("âš–ï¸ [Auto] IzraÄunavam mase...")
    try:
        if fw and hasattr(fw, '_on_calculate_masses'):
            fw._on_calculate_masses(auto=True)
            chat.add_activity("âœ… Mase izraÄunate")
    except Exception as e:
        chat.add_activity(f"âš ï¸ GreÅ¡ka pri izraÄunu masa: {e}")
    QApplication.processEvents()

    # 2. Auto-popuni tarifne (preskaÄi ako su sve tarife veÄ‡ popunjene)
    bez_tarife = sum(1 for l in ctrl.draft.invoice_lines if not getattr(l, 'tarifni_broj', None))
    if bez_tarife > 0:
        chat.add_activity(f"ðŸ¤– [Auto] Popunjavam tarifne brojeve ({bez_tarife} stavki bez tarife)...")
        try:
            if fw and hasattr(fw, '_on_auto_fill'):
                fw._on_auto_fill(auto=True)
                chat.add_activity("âœ… Auto-popuni zavrÅ¡en")
        except Exception as e:
            chat.add_activity(f"âš ï¸ GreÅ¡ka pri auto-popuni: {e}")
        QApplication.processEvents()
    else:
        chat.add_activity("âœ… [Auto] Sve stavke imaju tarifni broj â€” preskaÄem Auto-popuni")

    # 3. Validacija
    chat.add_activity("ðŸ” [Auto] Validacija stavki...")
    try:
        if fw and hasattr(fw, '_on_validate_all'):
            fw._on_validate_all(auto=True)
            chat.add_activity("âœ… Validacija zavrÅ¡ena")
    except Exception as e:
        chat.add_activity(f"âš ï¸ GreÅ¡ka pri validaciji: {e}")
    QApplication.processEvents()

    # 4. Deklarant mora potvrditi porijeklo i preferencijalne dokumente prije naimenovanja
    chat.add_activity("ðŸ§¾ [Auto] ÄŒekam potvrdu deklaranta za porijeklo i EUR.1/PE dokumente...")
    reply = QMessageBox.question(
        ctrl.view,
        "Potvrda prije kreiranja naimenovanja",
        "Prije kreiranja naimenovanja deklarant mora provjeriti:\n\n"
        "â€¢ zemlju porijekla za stavke\n"
        "â€¢ da li postoji izjava o porijeklu na fakturi\n"
        "â€¢ da li je potreban EUR.1 obrazac\n"
        "â€¢ da li su PE1/PE2/PE3 dokumenti ispravno postavljeni\n\n"
        "Da li je ova provjera zavrÅ¡ena i smije li se nastaviti sa kreiranjem naimenovanja?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if reply != QMessageBox.Yes:
        chat.add_agent_message(
            "â¸ï¸ <b>Puna automatizacija pauzirana.</b><br>"
            "Provjeri porijeklo i EUR.1/PE dokumente u Faktura tabu, "
            "pa kreiraj naimenovanja kada budeÅ¡ siguran."
        )
        chat.add_activity("â¸ï¸ Kreiranje naimenovanja zaustavljeno â€” Äeka se deklarantska provjera")
        return

    # 5. Kreiraj naimenovanja
    chat.add_activity("ðŸ“‹ [Auto] Kreiram naimenovanja...")
    try:
        if fw and hasattr(fw, '_on_create_naimenovanja'):
            fw._on_create_naimenovanja(auto=True)
            chat.add_activity("âœ… Naimenovanja kreirana")
    except Exception as e:
        chat.add_activity(f"âš ï¸ GreÅ¡ka pri kreiranju naimenovanja: {e}")
    QApplication.processEvents()

    bez_tarife = sum(1 for l in ctrl.draft.invoice_lines if not l.tarifni_broj)
    n_naim = len(getattr(ctrl.draft, 'items', []))
    chat.add_agent_message(
        f"ðŸŽ‰ <b>Puna automatizacija zavrÅ¡ena!</b><br>"
        f"Stavki: {len(ctrl.draft.invoice_lines)} | Bez tarifnog: <b>{bez_tarife}</b><br>"
        f"Naimenovanja: <b>{n_naim}</b><br>"
        f"Zaglavlje: <b>nije automatski popunjeno</b><br><br>"
        f"ðŸ’¡ Provjeri naimenovanja, ruÄno provjeri/popuni zaglavlje, zatim izvezi XML."
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

        existing_pov = getattr(line, 'povlastica', None)
        line_has_stmt = has_origin_statement or getattr(line, 'has_origin_statement', False)

        if line_has_stmt:
            if not existing_pov:
                line.povlastica = pov
            updated_pe2 += 1
        else:
            if not existing_pov:
                line.povlastica = pov
                updated_eur1 += 1
            if not getattr(line, 'eur1_number', None):
                eur1_pending += 1

    result = {'pe2': updated_pe2, 'eur1': updated_eur1, 'eur1_pending': eur1_pending}

    lines_with_country = sum(1 for l in invoice_lines if getattr(l, 'zemlja_porijekla', None))
    if updated_pe2 > 0 or updated_eur1 > 0:
        chat.add_activity(
            f"ðŸŒ Povlastice auto-postavljene: PE2={updated_pe2}, EUR1={updated_eur1}"
            + (f" (has_origin_statement={has_origin_statement})" if has_origin_statement else "")
        )
    elif lines_with_country > 0:
        chat.add_activity(f"â„¹ï¸ {lines_with_country} stavki ima zemlja_porijekla â€” povlastice veÄ‡ postavljene")
    else:
        chat.add_activity(f"âš ï¸ Povlastice: 0 stavki ima zemlja_porijekla â€” nije moguÄ‡e auto-postavljanje")

    if eur1_pending > 0:
        chat.add_activity(f"âš ï¸ {eur1_pending} stavki Äeka ruÄni unos EUR1 broja")

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
        chat.add_activity(f"ðŸ“‹ Rb.44 aÅ¾uriran na {updated} naimenovanja ({doc44})")

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
            "PE3": "Izjava ovlaÅ¡tenog izvoznika",
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

    chat.add_activity("ðŸ” Validacija podataka...")

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
                errors.append(f"âŒ Faktura br. '{broj}' veÄ‡ postoji u bazi!")
            else:
                chat.add_activity(f"  âœ… Faktura {broj}: Nije duplikat")
    except Exception as _e:
        logger.warning("Provjera duplikata fakture neuspjeÅ¡na: %s", _e)

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
                warnings.append(f"âš ï¸ Partner '{partner}' nije u Å¡ifrarniku")
            else:
                chat.add_activity(f"  âœ… Partner {partner}: NaÄ‘en u Å¡ifrarniku")
    except Exception as _e:
        logger.warning("Provjera partnera u Å¡ifrarniku neuspjeÅ¡na: %s", _e)

    # 3. Provjera formata tarifnih
    try:
        for line in invoice_lines:
            if hasattr(line, 'tarifni_broj') and line.tarifni_broj:
                tarif = line.tarifni_broj.strip()
                if len(tarif) >= 4 and '.' in tarif:
                    chat.add_activity(f"  âœ… Tarifni {tarif}: Format ispravan")
    except Exception as _e:
        logger.warning("Provjera formata tarifnih neuspjeÅ¡na: %s", _e)

    for w in warnings:
        chat.add_activity(w)

    if errors:
        chat.add_activity(f"âŒ Validacija NIJE uspjeÅ¡na: {len(errors)} greÅ¡aka")
        return (False, errors + warnings)
    else:
        chat.add_activity(f"âœ… Validacija uspjeÅ¡na ({len(warnings)} upozorenja)")
        return (True, warnings)


def _generisi_izvjestaj(ctrl, chat) -> bool:
    from services.faktura.validation_service import FakturaItemValidator

    chat.add_activity("ðŸ“Š Generisanje izvjeÅ¡taja...")

    errors = []
    warnings = []
    suggestions = []

    FakturaItemValidator()

    for i, line in enumerate(ctrl.draft.invoice_lines):
        row_num = i + 1

        if not line.tarifni_broj:
            errors.append(f"Stavka {row_num}: Nema tarifni broj")
            suggestions.append(f"  â†’ Klikni 'Auto-popuni tarifne' za stavku {row_num}")
        else:
            try:
                from services.naimenovanja.tariff_service import TariffService
                tariff_svc = TariffService()
                if not tariff_svc.validate_tariff(line.tarifni_broj):
                    errors.append(f"Stavka {row_num}: NevaÅ¾eÄ‡i tarifni '{line.tarifni_broj}'")
                    suggestions.append(f"  â†’ RuÄno provjeri tarifni za stavku {row_num}")
            except Exception as _e:
                logger.debug("Validacija tarifnog broja stavke %s: %s", row_num, _e)

        if not line.zemlja_porijekla:
            warnings.append(f"Stavka {row_num}: Nema zemlju porijekla")

        if not line.bruto_kg and not line.neto_kg:
            warnings.append(f"Stavka {row_num}: Nema mase (bruto/neto)")
            suggestions.append(f"  â†’ Unesi mase za stavku {row_num}")
        elif line.bruto_kg and line.neto_kg and line.bruto_kg < line.neto_kg:
            errors.append(f"Stavka {row_num}: Bruto ({line.bruto_kg}) < Neto ({line.neto_kg})")
            suggestions.append(f"  â†’ Ispravi mase za stavku {row_num}")

        if not line.jm or line.jm.strip() == "":
            warnings.append(f"Stavka {row_num}: Nema jedinicu mjere")

    if errors:
        chat.add_agent_message(
            f"âš ï¸ <b>UoÄio sam {len(errors)} problema:</b><br><br>"
            f"âŒ <b>GreÅ¡ke ({len(errors)}):</b><br>"
            f"{'<br>'.join(errors[:5])}" + (f"<br>... i joÅ¡ {len(errors)-5}" if len(errors) > 5 else "") +
            f"<br><br>"
            f"ðŸ’¡ <b>Prijedlozi:</b><br>"
            f"{'<br>'.join(suggestions[:5])}" + (f"<br>... i joÅ¡ {len(suggestions)-5}" if len(suggestions) > 5 else "")
        )
    elif warnings:
        chat.add_agent_message(
            f"âœ… <b>Sve stavke su ispravne!</b><br><br>"
            f"âš ï¸ <b>Upozorenja ({len(warnings)}):</b><br>"
            f"{'<br>'.join(warnings[:5])}" + (f"<br>... i joÅ¡ {len(warnings)-5}" if len(warnings) > 5 else "")
        )
    else:
        chat.add_agent_message(
            f"âœ… <b>Sve je savrÅ¡eno!</b><br>"
            f"Nema greÅ¡aka ni upozorenja."
        )

    return len(errors) == 0


def _otvori_faktura_tab_nakon_uvoza(ctrl, chat) -> None:
    chat.add_activity("ðŸ”„ Otvaranje Faktura taba...")

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
                chat.add_activity("âœ… PrebaÄeno na Faktura tab")
                if hasattr(faktura_tab_widget, '_load_data_from_draft'):
                    faktura_tab_widget._load_data_from_draft()
                    chat.add_activity("âœ… Podaci uÄitani u Faktura tab")
                else:
                    chat.add_activity("âš ï¸ _load_data_from_draft nije dostupan")
            else:
                chat.add_activity("âš ï¸ Tabs widget nije pronaÄ‘en")
        except Exception as e:
            chat.add_activity(f"âš ï¸ GreÅ¡ka pri otvaranju Faktura taba: {e}")
    else:
        chat.add_activity("âš ï¸ Parent window nije pronaÄ‘en")


