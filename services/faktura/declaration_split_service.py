"""
Dijeli jedan DeclarationDraft na više draftova po grupama zemalja porijekla.

Poslovni razlog: Carinska praksa zahtijeva zasebnu deklaraciju po zemlji
porijekla robe. EU zemlja idu zajedno kao jedna grupa ("EU").
"""

from __future__ import annotations

import copy
from collections import defaultdict
from typing import Dict, List, Tuple

from core.draft.draft import DeclarationDraft, InvoiceLine

# Sve EU države idu u jednu deklaraciju
EU_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}

# Prikazni nazivi grupa za navigator
_GROUP_LABELS: Dict[str, str] = {
    "EU": "EU",
    "RS": "Srbija (RS)",
    "TR": "Turska (TR)",
    "CN": "Kina (CN)",
    "BR": "Brazil (BR)",
    "BA": "BiH (BA)",
    "ME": "Crna Gora (ME)",
    "MK": "S. Makedonija (MK)",
    "AL": "Albanija (AL)",
    "XK": "Kosovo (XK)",
    "": "Nepoznato",
}


def declaration_country_group(zemlja: str) -> str:
    """Vraća ključ grupe deklaracije. EU zemlja → 'EU', ostalo → šifra ili ''."""
    z = (zemlja or "").strip().upper()
    if z in EU_COUNTRIES:
        return "EU"
    return z


def group_label(group_key: str) -> str:
    """Čitljivi naziv grupe za prikaz u navigatoru."""
    return _GROUP_LABELS.get(group_key, group_key or "Nepoznato")


def split_draft_by_country(draft: DeclarationDraft) -> List[DeclarationDraft]:
    """
    Dijeli draft po grupama zemalja porijekla.

    Vraća listu draftova sortiranih po ključu grupe.
    Ako sve stavke imaju istu grupu, vraća [draft] (bez kopiranja).

    Svaki rezultujući draft:
      - ima isto zaglavlje kao original
      - sadrži samo invoice_lines za svoju grupu
      - sadrži samo invoice_weights za fakture te grupe
      - ima _country_group attr setovan na ključ grupe
    """
    if not draft.invoice_lines:
        return [draft]

    # Grupiši linije po grupi zemalja
    buckets: Dict[str, List[InvoiceLine]] = defaultdict(list)
    for line in draft.invoice_lines:
        group = declaration_country_group(line.zemlja_porijekla)
        buckets[group].append(line)

    if len(buckets) == 1:
        # Samo jedna grupa — nema smisla dijeliti
        only_key = next(iter(buckets))
        draft._country_group = only_key  # type: ignore[attr-defined]
        return [draft]

    # Izračunaj invoice_weights po grupi (faktura može biti u više grupa ako
    # ima mixed C/O — tada se težina dijeli proporcionalno po vrijednosti)
    group_weights = _split_invoice_weights(draft, buckets)

    result: List[DeclarationDraft] = []
    for group_key in sorted(buckets.keys()):
        lines = buckets[group_key]
        new_draft = _copy_header(draft)
        new_draft.invoice_lines = lines
        new_draft.invoice_weights = group_weights.get(group_key, {})
        new_draft._country_group = group_key  # type: ignore[attr-defined]
        result.append(new_draft)

    return result


def _copy_header(draft: DeclarationDraft) -> DeclarationDraft:
    """Shallow kopija drafta — zaglavlje, bez invoice_lines/items/weights."""
    new = copy.copy(draft)
    new._data_change_callbacks = []  # type: ignore[attr-defined]
    new.invoice_lines = []
    new.items = []
    new.invoice_weights = {}
    new.warnings = list(draft.warnings)
    new.dirty = False
    return new


def _split_invoice_weights(
    draft: DeclarationDraft,
    buckets: Dict[str, List[InvoiceLine]],
) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """
    Raspodjeljuje invoice_weights iz drafta na grupe.

    Za fakture čije sve stavke idu u jednu grupu — cijela težina ide toj grupi.
    Za mixed fakture — težina se dijeli proporcionalno fakturnoj vrijednosti.
    """
    from services.faktura.weight_guards import normalize_invoice_key

    # Mapa: normalized_inv_key → {group → [lines]}
    inv_group_lines: Dict[str, Dict[str, List[InvoiceLine]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for group_key, lines in buckets.items():
        for ln in lines:
            inv_key = normalize_invoice_key(ln.invoice_number)
            inv_group_lines[inv_key][group_key].append(ln)

    result: Dict[str, Dict[str, Tuple[float, float]]] = defaultdict(dict)

    for inv_key, (bruto, neto) in draft.invoice_weights.items():
        if inv_key not in inv_group_lines:
            continue

        groups_for_inv = inv_group_lines[inv_key]

        if len(groups_for_inv) == 1:
            # Cijela faktura ide u jednu grupu
            only_group = next(iter(groups_for_inv))
            result[only_group][inv_key] = (bruto, neto)
        else:
            # Mixed faktura — raspodijeli po vrijednosti
            total_val = sum(
                sum(ln.iznos for ln in lns)
                for lns in groups_for_inv.values()
            ) or 1.0
            for group_key, lns in groups_for_inv.items():
                share = sum(ln.iznos for ln in lns) / total_val
                result[group_key][inv_key] = (
                    round(bruto * share, 3),
                    round(neto * share, 3),
                )

    return dict(result)


def count_country_groups(invoice_lines: List[InvoiceLine]) -> int:
    """Brzo prebrojava koliko bi deklaracija nastalo iz datih stavki."""
    return len({declaration_country_group(ln.zemlja_porijekla) for ln in invoice_lines})
