from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from core.draft import InvoiceLine, NaimenovanjeDraft


def _s(v: object) -> str:
    return "" if v is None else str(v).strip()


def _best_currency(lines: Iterable[InvoiceLine], default: str = "EUR") -> str:
    for ln in lines:
        if _s(ln.valuta):
            return _s(ln.valuta)
    return default


def _sum(lines: Iterable[InvoiceLine], attr: str) -> float:
    total = 0.0
    for ln in lines:
        total += float(getattr(ln, attr, 0.0) or 0.0)
    return total


def group_invoice_lines(
    invoice_lines: List[InvoiceLine],
    *,
    total_gross_kg: float = 0.0,
    total_net_kg: float = 0.0,
) -> List[NaimenovanjeDraft]:
    """
    KLJUČNA POSLOVNA LOGIKA (zakonski kriterijum):

      Grupisanje po:
        ✅ tarifni broj + zemlja porijekla + povlastica

    Težine:
      - Ako linije imaju bruto/neto -> sumiraj.
      - Ako nemaju -> raspodijeli proporcionalno vrijednosti (iznos).

    Napomena:
      Ovdje pravimo NaimenovanjeDraft (item-level agregat) koje UI edituje.
    """

    buckets: Dict[Tuple[str, str, str], List[InvoiceLine]] = defaultdict(list)
    for ln in invoice_lines:
        key = (_s(ln.tarifni_broj), _s(ln.zemlja_porijekla), _s(ln.povlastica))
        buckets[key].append(ln)

    items: List[NaimenovanjeDraft] = []
    for i, (key, lines) in enumerate(sorted(buckets.items(), key=lambda kv: kv[0])):
        tariff, origin, pref = key
        currency = _best_currency(lines)

        value = _sum(lines, "iznos")

        desc_lines = [_s(ln.naziv_robe) for ln in lines if _s(ln.naziv_robe)]
        rub31 = "\n".join(dict.fromkeys(desc_lines))  # uniq + zadrži redoslijed

        gross = _sum(lines, "bruto_kg")
        net = _sum(lines, "neto_kg")

        # Rb.44 dokument porijekla: PE2 = izjava na fakturi, PE1 = EUR.1 obrazac
        first_ln = lines[0]
        eur1_nums = {getattr(ln, 'eur1_number', '') or '' for ln in lines}
        eur1_nums.discard('')
        eur1_num = eur1_nums.pop() if len(eur1_nums) == 1 else ''
        has_stmt = getattr(first_ln, 'has_origin_statement', False)
        doc44 = ""
        if pref:
            doc_code = "PE2" if has_stmt else "PE1"
            doc44 = f"{doc_code} {eur1_num}".strip()

        it = NaimenovanjeDraft(
            item_id=f"{i+1}-{tariff}-{origin}-{pref}",
            ordinal_no=i + 1,
            goods_description=rub31,
            tariff_code=tariff,
            origin_country_code=origin,
            preference_code=pref,
            item_value=value,
            currency=currency or "EUR",
            gross_mass_kg=gross,
            net_mass_kg=net,
            source_invoice_refs=[str(ln.line_no or 0) for ln in lines],
            attached_document4=doc44,
        )
        items.append(it)

    has_any_mass = any((it.gross_mass_kg > 0 or it.net_mass_kg > 0) for it in items)
    if not has_any_mass and (total_gross_kg > 0 or total_net_kg > 0):
        total_value = sum(it.item_value for it in items) or 0.0
        for it in items:
            share = (
                (it.item_value / total_value)
                if total_value > 0
                else (1.0 / max(1, len(items)))
            )
            if total_gross_kg > 0:
                it.gross_mass_kg = round(total_gross_kg * share, 3)
            if total_net_kg > 0:
                it.net_mass_kg = round(total_net_kg * share, 3)

    return items
