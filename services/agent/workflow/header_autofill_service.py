"""
Header Auto-fill Service — popuni Izvoznik/Primalac/Deklarant iz istorijskog XML-a.

Isti mehanizam kao dugme "Uvezi XML" u Zaglavlju (ZaglavljeService.load_from_xml)
i "Prethodna deklaracija" u Fakturi (find_xml_for_pair), ali headless — bez
QFileDialog/QMessageBox — da bi mogao da se pozove iz run_declaration_workflow
prije header_ready kapije. Popunjava SAMO prazna polja, nikad ne prepisuje
ono što je korisnik (ili raniji uvoz) već unio — isti obrazac kao
faktura_view.py::_apply_import_result_to_header.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("deklarant_pro.agent.header_autofill")


def auto_fill_header_from_history(ctrl, chat) -> bool:
    """Pokušaj popuniti prazna header polja drafta iz najbliže istorijske deklaracije.

    Vraća True ako je bar jedno polje popunjeno.
    """
    draft = getattr(ctrl, "draft", None)
    if draft is None:
        return False

    izvoznik = (getattr(draft, "izvoznik_naziv", "") or "").strip()
    if not izvoznik:
        for line in getattr(draft, "invoice_lines", None) or []:
            cand = (getattr(getattr(line, "exporter", None), "name", "") or "").strip()
            if cand:
                izvoznik = cand.split("\n")[0].strip()
                break

    if not izvoznik:
        return False

    try:
        from services.agent.learning.exporter_xml_indexer import find_xml_for_pair
        consignee_jib = (getattr(draft, "primalac_id", "") or "").strip()
        consignee_hint = (getattr(draft, "primalac_naziv", "") or "").strip()
        result = find_xml_for_pair(izvoznik, consignee_jib, consignee_hint)
    except Exception as exc:
        logger.warning("find_xml_for_pair greška u auto-popuni zaglavlja: %s", exc)
        return False

    xml_path = result.get("xml_filepath") if result else None
    if not xml_path:
        return False

    try:
        from services.zaglavlje_service import ZaglavljeService
        header_data = ZaglavljeService().load_from_xml(xml_path)
    except Exception as exc:
        logger.warning("load_from_xml greška u auto-popuni zaglavlja (%s): %s", xml_path, exc)
        return False

    filled = []
    for field, value in (header_data or {}).items():
        if not value or not hasattr(draft, field):
            continue
        current = getattr(draft, field, "")
        if isinstance(current, str) and current.strip():
            continue
        setattr(draft, field, value)
        filled.append(field)

    if not filled:
        return False

    logger.info(
        "Zaglavlje auto-popunjeno iz istorijskog XML-a (%s): %d polja (%s)",
        xml_path, len(filled), ", ".join(filled),
    )
    chat.add_activity(
        f"📥 Zaglavlje auto-popunjeno iz prethodne deklaracije "
        f"({result.get('exporter_original') or izvoznik}): {len(filled)} polja"
    )

    zaglavlje_tab = getattr(ctrl, "zaglavlje_tab", None)
    if zaglavlje_tab is not None and hasattr(zaglavlje_tab, "load_from_draft"):
        try:
            zaglavlje_tab.load_from_draft(draft)
        except Exception as exc:
            logger.warning("Zaglavlje tab reload greška nakon auto-popune: %s", exc)

    return True
