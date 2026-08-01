"""
Preference Rules Service — pravila za povlastice, porijeklo i partner consistency
"""

from importers.import_result import ImportResult


def similar_partner_names(a: str, b: str) -> bool:
    """Provjeri da li su dva naziva partnera dovoljno slična (>60% token overlap)."""
    from services.faktura.faktura_service import FakturaService

    na = FakturaService.normalize_partner(a)
    nb = FakturaService.normalize_partner(b)
    if not na or not nb:
        return True
    ta = set(na.split())
    tb = set(nb.split())
    if not ta or not tb:
        return True
    overlap = len(ta & tb) / max(len(ta), len(tb))
    return overlap >= 0.6


def suggest_preference_by_country(country_code: str, exporter_name: str = "") -> str:
    """Vrati povlasticu (Rub.36) na osnovu koda zemlje i istorijskog učenja."""
    if exporter_name and exporter_name.strip():
        try:
            from services.agent.learning.historical_learning_service_safe import enhance_preference_logic
            historical_pref = enhance_preference_logic(country_code, exporter_name)
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
        return 'EUP'
    if c in cefta_countries:
        return 'CEFTAP'
    if c == 'TR':
        return 'TRP'
    if c == 'IR':
        return 'IRP'
    return ''


def should_show_eur1_dialog(items) -> bool:
    """Provjeri da li treba pokazati EUR.1 dialog (faktura BEZ izjave o poreklu)."""
    if isinstance(items, ImportResult):
        items = items.items

    has_any_statement = any(
        hasattr(item, 'has_origin_statement') and item.has_origin_statement
        for item in items
    )
    if has_any_statement:
        return False

    return any(
        hasattr(item, 'has_origin_statement')
        and not item.has_origin_statement
        and item.zemlja_porijekla
        for item in items
    )


def should_show_pe2_dialog(items) -> bool:
    """Provjeri da li treba pokazati PE2 dialog (faktura IMA izjavu o poreklu)."""
    if isinstance(items, ImportResult):
        items = items.items

    return any(
        hasattr(item, 'has_origin_statement') and item.has_origin_statement
        for item in items
    )


def auto_handle_povlastice_agent(draft, has_origin_statement: bool) -> dict:
    """Agent mod: evidentiraj PE2/EUR1 kandidate bez primjene povlastice."""
    import logging
    logger = logging.getLogger("deklarant_pro.faktura.preference_rules")

    updated_pe2 = 0
    eur1_pending = 0

    exporter_name = ""
    if hasattr(draft, 'exporter') and draft.exporter:
        exporter_name = draft.exporter
    elif draft.invoice_lines and hasattr(draft.invoice_lines[0], 'exporter'):
        exporter_name = draft.invoice_lines[0].exporter

    for item in draft.invoice_lines:
        item_has_statement = getattr(item, 'has_origin_statement', has_origin_statement)
        if item_has_statement:
            updated_pe2 += 1
        elif item.zemlja_porijekla:
            pov = suggest_preference_by_country(item.zemlja_porijekla, exporter_name)
            if pov and not getattr(item, 'povlastica', None) and not getattr(item, 'eur1_number', None):
                eur1_pending += 1

    logger.info(
        f"🤖 [agent] Auto-povlastice: PE2={updated_pe2}, EUR1_pending={eur1_pending} "
        f"(bez PE dokaza povlastica ostaje neutralna)"
    )
    return {'pe2': updated_pe2, 'eur1_pending': eur1_pending}
