"""
Legacy import service — poruke za Assembly/master-list uvoz put.

"Legacy" ovdje NE znači "zastarjelo, treba obrisati". PROBE
(project_rooms/2026-08-02_faza6-probe-legacy-uvoz-status.md) je potvrdio da
je ovaj put (aktivan kad je `assembly.master_list_loaded=True`, ili kad
`_finish_import_legacy_path` dobije rezultat koji nije `ImportResult`)
TRAJNA, namjerna arhitektonska odluka iz odobrenog master plana
(docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md) —
Assembly/master-list tok se namjerno NE spaja sa unified import putem.

Ovaj modul sadrži samo čiste funkcije za građenje poruka (bez Qt zavisnosti)
izdvojene iz `FakturaView._finish_import_legacy_path` i
`FakturaView._process_batch_records_legacy`. Kontrolni tok, redoslijed
dijaloga i mutacija drafta ostaju namjerno u View-u — to je legitimna
Controller/View orkestracija (poziv Assembly servisa, odluka koji dijalog
prikazati), ne poslovna logika koja treba biti u servisu.
"""

from typing import Optional, Tuple


def build_assembly_match_message(
    invoice_name: str,
    matched: int,
    unmatched: int,
    bruto_kg: float,
    neto_kg: float,
    status: dict,
    current_weights: Optional[Tuple[float, float]] = None,
) -> str:
    """Poruka nakon Assembly matching-a (master-list tok). Poziva se PRIJE
    `_append_imported_files_message` — taj sufiks View dodaje sam."""
    message = f"Faktura '{invoice_name}' dodana u assembly.\n\n"
    message += f"Match rezultati:\n"
    message += f"- Matched: {matched} stavki\n"
    message += f"- Unmatched: {unmatched} stavki\n\n"

    if bruto_kg > 0 or neto_kg > 0:
        message += f"Težine sa fakture '{invoice_name}':\n"
        message += f"- Bruto: {bruto_kg:.3f} kg\n"
        message += f"- Neto: {neto_kg:.3f} kg\n\n"

    if current_weights is not None:
        current_bruto, current_neto = current_weights
        message += f"Ukupno u draft-u (nakon matching-a):\n"
        message += f"- Bruto: {current_bruto:.3f} kg\n"
        message += f"- Neto: {current_neto:.3f} kg\n\n"

    if unmatched > 0:
        message += "⚠️ Nepodudarajuće stavke su dodane u tabelu i označene CRVENOM bojom.\n"
        message += "Provjerite ih i ručno popunite nedostajuća polja (tarifni broj, zemlja).\n\n"

    message += f"Status:\n"
    message += f"- Ukupno stavki: {status['total']}\n"
    message += f"- Kompletno: {status['complete']} ({status['completion_percentage']:.1f}%)\n"
    message += f"- Uvezene fakture: {status['imported_invoices_count']}\n\n"

    return message


def build_manual_import_prefix_message(
    invoice_name: str,
    item_count: int,
    previous_count: int,
    total_count: int,
    bruto_kg: float,
    neto_kg: float,
    accumulated_bruto_kg: float,
    accumulated_neto_kg: float,
) -> str:
    """Prefiks poruke za obični (non-Assembly) uvoz. View poziva
    `_append_imported_files_message(message, min_files=2)` nakon ovoga, pa
    dodaje sufiks preko `build_manual_import_suffix_message`."""
    message = f"Uspješno uvezeno {item_count} stavki iz '{invoice_name}'.\n\n"

    if previous_count > 0:
        message += f"📊 Akumulirano:\n"
        message += f"- Prethodno: {previous_count} stavki\n"
        message += f"- Nova faktura: {item_count} stavki\n"
        message += f"- Ukupno: {total_count} stavki\n\n"

    if bruto_kg > 0 or neto_kg > 0:
        message += f"Težine sa fakture '{invoice_name}':\n"
        message += f"- Bruto: {bruto_kg:.3f} kg\n"
        message += f"- Neto: {neto_kg:.3f} kg\n\n"
        message += f"Akumulirano ukupno:\n"
        message += f"- Bruto: {accumulated_bruto_kg:.3f} kg\n"
        message += f"- Neto: {accumulated_neto_kg:.3f} kg\n\n"

    return message


def build_manual_import_suffix_message(is_combined: bool, import_type: str) -> str:
    """Sufiks poruke za obični (non-Assembly) uvoz — dodaje se NAKON
    `_append_imported_files_message` poziva u View-u."""
    if is_combined:
        return "🔗 Redoslijed stavki održan iz PDF fakture."
    if import_type == "loren_excel":
        return (
            "⚠️  LOREN EXCEL: Iznosi (cijene) dolaze iz PDF-a!\n"
            "   Uvezite PDF fajl sa istim brojem fakture da biste dobili\n"
            "   ispravne iznose. Trenutno su svi iznosi = 0."
        )
    return (
        "💡 Možete nastaviti sa uvozom dodatnih faktura.\n"
        "   Svaka faktura će biti dodana u draft održavajući svoj redoslijed."
    )


def build_legacy_batch_import_message(
    records_count: int,
    final_records_count: int,
    all_items_count: int,
    total_bruto_kg: float,
    total_neto_kg: float,
    failed_imports: list,
    parser_warnings: list,
) -> str:
    """Poruka za grupni Assembly/master-list uvoz (`_process_batch_records_legacy`)."""
    from services.faktura.faktura_service import FakturaService

    skipped_count = records_count - final_records_count
    message = "📦 Grupni uvoz završen!\n\n"
    message += f"✅ Uspješno faktura: {final_records_count}\n"
    if skipped_count:
        message += f"🔗 Spojeno/preskočeno parova: {skipped_count}\n"
    message += f"📋 Ukupno stavki: {all_items_count}\n"
    message += f"⚖️  Bruto: {FakturaService.format_weight(total_bruto_kg)} kg\n"
    message += f"⚖️  Neto: {FakturaService.format_weight(total_neto_kg)} kg\n"

    if failed_imports:
        message += f"\n❌ Neuspješno: {len(failed_imports)}\n"
        for fname, err in failed_imports[:3]:
            message += f"   • {fname}: {err[:80]}\n"
        if len(failed_imports) > 3:
            message += f"   ... i još {len(failed_imports) - 3}\n"

    if parser_warnings:
        message += f"\n⚠️ Upozorenja parsera ({len(parser_warnings)}):\n"
        for w in parser_warnings[:5]:
            message += f"   • {w}\n"
        if len(parser_warnings) > 5:
            message += f"   ... i još {len(parser_warnings) - 5}\n"

    return message
