"""
Dijeli jedan DeclarationDraft na više draftova po grupama zemalja i valuta.

Poslovni razlog:
  - Carinska praksa zahtijeva zasebnu deklaraciju po zemlji porijekla.
  - EU zemlja idu zajedno kao jedna grupa ("EU").
  - Roba iste zemlje ali različite valute ide u zasebne deklaracije
    (ASYCUDA deklaracija ima jednu valutu za cijelu deklaraciju).
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
    "IN": "Indija (IN)",
    "VN": "Vijetnam (VN)",
    "BA": "BiH (BA)",
    "ME": "Crna Gora (ME)",
    "MK": "S. Makedonija (MK)",
    "AL": "Albanija (AL)",
    "XK": "Kosovo (XK)",
    "": "Nepoznato",
}

# Tip ključa grupe: (country_group, currency)
SplitKey = Tuple[str, str]


def declaration_country_group(zemlja: str) -> str:
    """Vraća ključ grupe deklaracije. EU zemlja → 'EU', ostalo → šifra ili ''."""
    z = (zemlja or "").strip().upper()
    if z in EU_COUNTRIES:
        return "EU"
    return z


def declaration_split_key(line: InvoiceLine) -> SplitKey:
    """
    Vraća ključ za grupisanje u deklaraciju: (country_group, valuta).

    Primjeri:
      line(zemlja="TR", valuta="EUR") → ("TR", "EUR")
      line(zemlja="BR", valuta="USD") → ("BR", "USD")
      line(zemlja="PT", valuta="EUR") → ("EU", "EUR")  ← EU merge
    """
    country = declaration_country_group(line.zemlja_porijekla)
    currency = (line.valuta or "EUR").strip().upper()
    return (country, currency)


def group_label(country_group: str, currency: str = "") -> str:
    """Čitljivi naziv grupe za prikaz u navigatoru."""
    country_part = _GROUP_LABELS.get(country_group, country_group or "Nepoznato")
    if currency:
        return f"{country_part} • {currency}"
    return country_part


def split_draft_by_country(draft: DeclarationDraft) -> List[DeclarationDraft]:
    """
    Dijeli draft po kombinaciji (zemlja porijekla, valuta).

    Vraća listu draftova sortiranih po ključu.
    Ako sve stavke imaju isti ključ, vraća [draft] (bez kopiranja).

    Svaki rezultujući draft:
      - ima isto zaglavlje kao original
      - ima postavljenu valutu (draft.valuta) na valutu grupe
      - sadrži samo invoice_lines za svoju grupu
      - sadrži samo invoice_weights za fakture te grupe
      - ima _country_group i _currency_group attr setovane
    """
    if not draft.invoice_lines:
        return [draft]

    # Grupiši linije po (zemlja, valuta)
    buckets: Dict[SplitKey, List[InvoiceLine]] = defaultdict(list)
    for line in draft.invoice_lines:
        key = declaration_split_key(line)
        buckets[key].append(line)

    if len(buckets) == 1:
        only_key = next(iter(buckets))
        draft._country_group = only_key[0]   # type: ignore[attr-defined]
        draft._currency_group = only_key[1]  # type: ignore[attr-defined]
        return [draft]

    group_weights = _split_invoice_weights(draft, buckets)

    result: List[DeclarationDraft] = []
    for split_key in sorted(buckets.keys()):
        country, currency = split_key
        lines = buckets[split_key]
        new_draft = _copy_header(draft)
        new_draft.invoice_lines = lines
        new_draft.invoice_weights = group_weights.get(split_key, {})
        new_draft.valuta = currency
        new_draft._country_group = country   # type: ignore[attr-defined]
        new_draft._currency_group = currency  # type: ignore[attr-defined]
        result.append(new_draft)

    return result


def count_declaration_groups(invoice_lines: List[InvoiceLine]) -> int:
    """Brzo prebrojava koliko bi deklaracija nastalo iz datih stavki."""
    return len({declaration_split_key(ln) for ln in invoice_lines})


# Backwards-compatible alias
count_country_groups = count_declaration_groups


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
    buckets: Dict[SplitKey, List[InvoiceLine]],
) -> Dict[SplitKey, Dict[str, Tuple[float, float]]]:
    """
    Raspodjeljuje invoice_weights iz drafta na grupe.

    Za fakture čije sve stavke idu u jednu grupu — cijela težina ide toj grupi.
    Za mixed fakture — težina se dijeli proporcionalno fakturnoj vrijednosti.
    """
    from services.faktura.weight_guards import normalize_invoice_key

    # Mapa: normalized_inv_key → {split_key → [lines]}
    inv_group_lines: Dict[str, Dict[SplitKey, List[InvoiceLine]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for split_key, lines in buckets.items():
        for ln in lines:
            inv_key = normalize_invoice_key(ln.invoice_number)
            inv_group_lines[inv_key][split_key].append(ln)

    result: Dict[SplitKey, Dict[str, Tuple[float, float]]] = defaultdict(dict)

    for inv_key, (bruto, neto) in draft.invoice_weights.items():
        if inv_key not in inv_group_lines:
            continue

        groups_for_inv = inv_group_lines[inv_key]

        if len(groups_for_inv) == 1:
            only_key = next(iter(groups_for_inv))
            result[only_key][inv_key] = (bruto, neto)
        else:
            # Mixed faktura — raspodijeli po vrijednosti
            total_val = sum(
                sum(ln.iznos for ln in lns)
                for lns in groups_for_inv.values()
            ) or 1.0
            for split_key, lns in groups_for_inv.items():
                share = sum(ln.iznos for ln in lns) / total_val
                result[split_key][inv_key] = (
                    round(bruto * share, 3),
                    round(neto * share, 3),
                )

    return dict(result)
