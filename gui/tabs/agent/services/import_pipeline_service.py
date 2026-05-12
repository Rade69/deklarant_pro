"""
Import Pipeline Service

Pipeline logika za sve tri procesne rute agenta:
  - Analiza mode (prikaži izvještaj, ponudi akcije)
  - Uvezi u deklaraciju mode (dijalozi, ručna potvrda)
  - Puna automatizacija mode (auto-koraci uz obaveznu deklarantsku potvrdu)

Premješteno iz agent_controller.py radi smanjenja veličine controllera.
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gui.utils.safe_message_box import SafeMessageBox as QMessageBox

logger = logging.getLogger("deklarant_pro.agent.import_pipeline")

EUR1_THRESHOLD = 6000.0  # EUR — iznad ovog iznosa standardna izjava ne važi


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

    def izracunaj_tezine_interno(self, invoice_lines: list, chat) -> int:
        return _izracunaj_tezine_interno(self._ctrl, invoice_lines, chat)

    def validiraj_prije_uvoza(self, invoice_lines: list, chat) -> tuple:
        return _validiraj_prije_uvoza(invoice_lines, chat)

    def generisi_izvjestaj(self, chat) -> bool:
        return _generisi_izvjestaj(self._ctrl, chat)

    def uvezi_u_deklaraciju(self, invoice_lines: list, chat,
                             total_bruto: float = 0.0, total_neto: float = 0.0,
                             has_origin_statement: bool = False,
                             is_authorized_exporter: bool = False,
                             completed: list = None) -> None:
        _uvezi_u_deklaraciju(self._ctrl, invoice_lines, chat,
                             total_bruto, total_neto, has_origin_statement,
                             is_authorized_exporter, completed)

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


def _puna_auto_pipeline(ctrl, fw, chat, all_lines: list) -> None:
    QApplication.processEvents()

    # 1. Izračunaj mase
    chat.add_activity("⚖️ [Auto] Izračunavam mase...")
    try:
        if fw and hasattr(fw, '_on_calculate_masses'):
            fw._on_calculate_masses(auto=True)
            chat.add_activity("✅ Mase izračunate")
    except Exception as e:
        chat.add_activity(f"⚠️ Greška pri izračunu masa: {e}")
    QApplication.processEvents()

    # 2. Auto-popuni tarifne (preskači ako su sve tarife već popunjene)
    bez_tarife = sum(1 for l in ctrl.draft.invoice_lines if not getattr(l, 'tarifni_broj', None))
    if bez_tarife > 0:
        chat.add_activity(f"🤖 [Auto] Popunjavam tarifne brojeve ({bez_tarife} stavki bez tarife)...")
        try:
            if fw and hasattr(fw, '_on_auto_fill'):
                fw._on_auto_fill(auto=True)
                chat.add_activity("✅ Auto-popuni završen")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri auto-popuni: {e}")
        QApplication.processEvents()
    else:
        chat.add_activity("✅ [Auto] Sve stavke imaju tarifni broj — preskačem Auto-popuni")

    # 3. Validacija
    chat.add_activity("🔍 [Auto] Validacija stavki...")
    try:
        if fw and hasattr(fw, '_on_validate_all'):
            fw._on_validate_all(auto=True)
            chat.add_activity("✅ Validacija završena")
    except Exception as e:
        chat.add_activity(f"⚠️ Greška pri validaciji: {e}")
    QApplication.processEvents()

    # 4. Deklarant mora potvrditi porijeklo i preferencijalne dokumente prije naimenovanja
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
        return

    # 5. Kreiraj naimenovanja
    chat.add_activity("📋 [Auto] Kreiram naimenovanja...")
    try:
        if fw and hasattr(fw, '_on_create_naimenovanja'):
            fw._on_create_naimenovanja(auto=True)
            chat.add_activity("✅ Naimenovanja kreirana")
    except Exception as e:
        chat.add_activity(f"⚠️ Greška pri kreiranju naimenovanja: {e}")
    QApplication.processEvents()

    bez_tarife = sum(1 for l in ctrl.draft.invoice_lines if not l.tarifni_broj)
    n_naim = len(getattr(ctrl.draft, 'items', []))
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
            f"🌍 Povlastice auto-postavljene: PE2={updated_pe2}, EUR1={updated_eur1}"
            + (f" (has_origin_statement={has_origin_statement})" if has_origin_statement else "")
        )
    elif lines_with_country > 0:
        chat.add_activity(f"ℹ️ {lines_with_country} stavki ima zemlja_porijekla — povlastice već postavljene")
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
        doc44 = f"{doc_code} {eur1_num}".strip()

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
        doc4 = (getattr(item, 'attached_document4', '') or '').strip()
        if not doc4:
            continue
        parts = doc4.split(' ', 1)
        sifra = parts[0].strip()
        broj = parts[1].strip() if len(parts) > 1 else ''
        if sifra in ("PE1", "PE2", "PE3"):
            key = (sifra, broj)
            if key not in seen:
                seen.add(key)
                pe_entries.append(key)

    header_docs[:] = [d for d in header_docs if d.code not in ("PE1", "PE2", "PE3")]

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


def _izracunaj_tezine_interno(ctrl, invoice_lines: list, chat) -> int:
    bruto_total = 0.0
    neto_total = 0.0

    if ctrl.faktura_tab:
        try:
            bruto_text = ctrl.faktura_tab.input_bruto.text().strip()
            neto_text = ctrl.faktura_tab.input_neto.text().strip()
            bruto_total = float(bruto_text.replace(",", "") or "0")
            neto_total = float(neto_text.replace(",", "") or "0")
            print(f"[WeightCalc] Toolbar težine: bruto={bruto_total:.2f} kg, neto={neto_total:.2f} kg")
        except Exception as e:
            print(f"[WeightCalc] Greška pri čitanju težina: {e}")
            bruto_total = 0.0
            neto_total = 0.0

    items_to_update = [
        line for line in invoice_lines
        if (not line.bruto_kg or line.bruto_kg == 0)
        or (not line.neto_kg or line.neto_kg == 0)
    ]

    if not items_to_update:
        print("[WeightCalc] Sve stavke već imaju težine - preskačem izračun")
        return 0

    print(f"[WeightCalc] {len(items_to_update)} stavki za izračun težina")

    neto_bruto_ratio = neto_total / bruto_total if (bruto_total > 0 and neto_total > 0) else 0.95
    print(f"[WeightCalc] Odnos neto/bruto: {neto_bruto_ratio:.6f}")

    total_qty = sum(line.kolicina or 0.0 for line in items_to_update if not (line.bruto_kg and line.bruto_kg > 0))

    izracunato = 0
    for line in items_to_update:
        has_bruto = line.bruto_kg and line.bruto_kg > 0
        has_neto = line.neto_kg and line.neto_kg > 0

        if not has_bruto and not has_neto:
            qty = line.kolicina or 0.0
            if qty > 0 and total_qty > 0:
                proportion = qty / total_qty
                line.bruto_kg = round(bruto_total * proportion, 3) if bruto_total > 0 else 0.0
                line.neto_kg = round(neto_total * proportion, 3) if neto_total > 0 else round(line.bruto_kg * neto_bruto_ratio, 3)
            else:
                avg_weight = (bruto_total / len(invoice_lines)) if bruto_total > 0 else 0.0
                line.bruto_kg = round(avg_weight, 3)
                line.neto_kg = round(avg_weight * neto_bruto_ratio, 3)
            izracunato += 1
            print(f"  [PDF] {line.naziv_robe[:30]}: bruto={line.bruto_kg:.3f}, neto={line.neto_kg:.3f}")

        elif has_bruto and not has_neto:
            line.neto_kg = round(line.bruto_kg * neto_bruto_ratio, 3)
            izracunato += 1
            print(f"  [Excel] {line.naziv_robe[:30]}: bruto={line.bruto_kg:.3f} → neto={line.neto_kg:.3f}")

    print(f"[WeightCalc] ✅ Izračunato {izracunato} težina")
    return izracunato


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


def _uvezi_u_deklaraciju(ctrl, invoice_lines: list, chat,
                          total_bruto: float = 0.0, total_neto: float = 0.0,
                          has_origin_statement: bool = False,
                          is_authorized_exporter: bool = False,
                          completed: list = None) -> None:
    print(f"[ImportPipeline] _uvezi_u_deklaraciju: {len(invoice_lines)} stavki")

    if not ctrl.draft:
        chat.add_activity("⚠️ Draft nije dostupan")
        return

    # 0. Validacija PRIJE uvoza
    chat.add_activity("🔍 Validacija prije uvoza...")
    valid, greske = _validiraj_prije_uvoza(invoice_lines, chat)
    if not valid:
        chat.add_agent_message(
            f"❌ <b>Validacija nije uspješna!</b><br><br>"
            f"{'<br>'.join(greske)}<br><br>"
            f"Uvoz je obustavljen."
        )
        return

    # 1. Uvezi podatke u draft
    # Važno: ne prepisuj globalno invoice_number sa "prvim" fajlom.
    # Svaka stavka mora zadržati broj fakture koji je parser već postavio.
    
    chat.add_activity(f"📥 Uvoz {len(invoice_lines)} stavki...")
    ctrl.draft.invoice_lines.clear()
    ctrl.draft.invoice_lines.extend(invoice_lines)
    chat.add_activity(f"✅ Uvezeno {len(invoice_lines)} stavki")

    QApplication.processEvents()

    # 2. Otvori Faktura tab
    faktura_widget = ctrl.faktura_tab
    if hasattr(ctrl.faktura_tab, 'view'):
        faktura_widget = ctrl.faktura_tab.view

    if faktura_widget:
        if total_bruto > 0 or total_neto > 0:
            if hasattr(faktura_widget, 'weight_manager') and hasattr(faktura_widget, '_accumulate_weights'):
                faktura_widget.weight_manager.accumulated_bruto_kg = 0.0
                faktura_widget.weight_manager.accumulated_neto_kg = 0.0
                faktura_widget._accumulate_weights(total_bruto, total_neto)
                chat.add_activity(f"⚖️ Težine postavljene: Bruto={total_bruto:.2f}kg, Neto={total_neto:.2f}kg")

        if hasattr(faktura_widget, '_load_data_from_draft'):
            faktura_widget._load_data_from_draft()

        chat.add_activity("🤖 Izračunavam mase...")
        try:
            from services.faktura.mass_calculator import MassCalculator
            mass_calc = MassCalculator()
            if hasattr(faktura_widget, 'input_bruto') and hasattr(faktura_widget, 'input_neto'):
                bruto_total = float(faktura_widget.input_bruto.text().replace(",", "") or "0")
                neto_total = float(faktura_widget.input_neto.text().replace(",", "") or "0")
                if bruto_total > 0 or neto_total > 0:
                    result = mass_calc.calculate_masses(ctrl.draft.invoice_lines, bruto_total, neto_total)
                    chat.add_activity(f"✅ Mase izračunate: {result['updated']} stavki ažurirano")
                else:
                    chat.add_activity("ℹ️ Nema težina za izračun")
        except Exception as e:
            chat.add_activity(f"⚠️ Greška pri izračunu masa: {e}")

        if hasattr(faktura_widget, '_load_data_from_draft'):
            faktura_widget._load_data_from_draft()

    # 3. Broj fakture za dijalog i za N380 u zaglavlju
    # Skupljamo SVE eksplicitno parsirane brojeve (bez stem fallbacka)
    brojevi_faktura = []
    if completed:
        for f in completed:
            if f.status == 'Completed' and f.invoice_number:
                if f.invoice_number not in brojevi_faktura:
                    brojevi_faktura.append(f.invoice_number)
    invoice_number = " | ".join(brojevi_faktura) if brojevi_faktura else ""

    # 4. Dijalog za porijeklo (PE2 / PE3 / EUR.1)
    dialog_tip = _origin_dialog_type(ctrl.draft.invoice_lines, has_origin_statement,
                                     is_authorized_exporter)

    if dialog_tip in ('pe2', 'pe3'):
        doc_code = 'PE3' if dialog_tip == 'pe3' else 'PE2'
        lbl = "PE3 (ovlašteni izvoznik)" if dialog_tip == 'pe3' else "PE2 (izjava na fakturi)"
        chat.add_activity(f"📄 Faktura ima izjavu o porijeklu — otvaram {lbl} dijalog...")
        chat.add_agent_message(
            f"📄 <b>Faktura ima izjavu o preferencijalnom porijeklu ({doc_code}).</b><br>"
            + (f"Ovlašteni izvoznik — EUR.1 nije potreban.<br>" if dialog_tip == 'pe3' else
               f"Vrijednost je ispod 6.000 EUR — EUR.1 nije potreban.<br>")
            + f"<br>⚠️ <b>Ništa se ne upisuje automatski — ti odlučuješ.</b>"
        )
        try:
            from gui.dialogs.pe2_quick_dialog import PE2QuickDialog
            dialog = PE2QuickDialog(ctrl.draft.invoice_lines, ctrl.view,
                                    invoice_number=invoice_number, doc_code=doc_code)
            result_dlg = dialog.exec()
            if result_dlg == 1:
                pe2_data = dialog.get_data()
                if pe2_data:
                    updated_count = PE2QuickDialog.apply_pe2_data(ctrl.draft.invoice_lines, pe2_data)
                    chat.add_activity(f"✅ {doc_code} primijenjen na {updated_count} stavki")
                    if faktura_widget and hasattr(faktura_widget, '_load_data_from_draft'):
                        faktura_widget._load_data_from_draft()
            else:
                chat.add_activity(f"ℹ️ {doc_code} dijalog preskočen — uredi ručno u Faktura tabu")
        except Exception as e:
            chat.add_activity(f"⚠️ {doc_code} dijalog greška: {e}")

    elif dialog_tip == 'eur1':
        razlog = ("Standardna izjava na fakturi, ali vrijednost prelazi 6.000 EUR"
                  if has_origin_statement else "Faktura nema izjavu o porijeklu")
        chat.add_activity(f"📋 EUR.1 obrazac potreban — otvaram dijalog...")
        chat.add_agent_message(
            f"⚠️ <b>Potreban EUR.1 obrazac.</b><br>"
            f"{razlog}.<br><br>"
            f"📄 <b>Unesi EUR.1 broj za svaku zemlju.</b><br>"
            f"Ako nemaš EUR.1, ostavi prazno i uredi kasnije ručno."
        )
        try:
            from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog
            dialog = Eur1QuickDialog(ctrl.draft.invoice_lines, ctrl.view, invoice_number=invoice_number)
            result_dlg = dialog.exec()
            if result_dlg == 1:
                eur1_data = dialog.get_data()
                if eur1_data:
                    updated_count = Eur1QuickDialog.apply_eur1_data(ctrl.draft.invoice_lines, eur1_data)
                    chat.add_activity(f"✅ EUR.1 primijenjen na {updated_count} stavki")
                    _apply_eur1_to_naimenovanja(ctrl, eur1_data, chat)
                    if faktura_widget and hasattr(faktura_widget, '_load_data_from_draft'):
                        faktura_widget._load_data_from_draft()
            else:
                chat.add_activity("ℹ️ EUR.1 dijalog preskočen — unesi broj ručno u Faktura tabu")
        except Exception as e:
            chat.add_activity(f"⚠️ EUR.1 dijalog greška: {e}")

    else:
        chat.add_activity("ℹ️ Nema stavki koje zahtijevaju EUR.1 — nastavi ručno uređivanje")

    # 5. Rezime
    bez_tarife = sum(1 for l in ctrl.draft.invoice_lines if not l.tarifni_broj)
    chat.add_agent_message(
        f"✅ <b>Uvoz završen!</b><br>"
        f"Uvezeno <b>{len(invoice_lines)}</b> stavki.<br><br>"
        f"📊 <b>Stanje:</b><br>"
        f"  • Bez tarifnog broja: <b>{bez_tarife}</b><br>"
        f"  • Mase: izračunate<br>"
        f"  • Povlastice: {'PE2/EUR.1 potvrđeno' if has_origin_statement else 'Čeka unos'}<br><br>"
        f"💡 <b>Šta dalje?</b><br>"
        f"  • Reci <i>'popuni tarifne'</i> za prijedloge tarifnih brojeva<br>"
        f"  • Pregledaj tablicu i ručno dopuni podatke<br>"
        f"  • Kad si spreman, reci <i>'kreiraj naimenovanja'</i>"
    )


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
