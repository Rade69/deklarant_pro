"""
Draft Aggregation Service — determinisitička agregacija/filtriranje stavki drafta.

Qt-independent, čiste funkcije nad `DeclarationDraft.invoice_lines`/`items`.
Postoji da agent (LLM) NIKAD ne mora sam da broji/sabira/poredi iz sirovog teksta —
vidi agent_reports/2026-08-05_agent-pretraga-stavki-po-nazivu.md i
docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md za puno objašnjenje ove klase buga.

NAMJERNO nema "all" target opcije koja bi miješala invoice_lines i items u istoj
agregaciji — AGENTS.md eksplicitno zabranjuje miješanje ta dva koncepta (potpuno
različite jedinice/značenje).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

FIELD_MAP: Dict[str, Dict[str, str]] = {
    "invoice": {
        "vrijednost": "iznos",
        "kolicina": "kolicina",
        "bruto_masa": "bruto_kg",
        "neto_masa": "neto_kg",
        "cijena": "cijena_jed",
        "tarifa": "tarifni_broj",
        "zemlja": "zemlja_porijekla",
        "povlastica": "povlastica",
        "faktura": "invoice_number",
        "naziv": "naziv_robe",
    },
    "items": {
        "vrijednost": "item_value",
        "bruto_masa": "gross_mass_kg",
        "neto_masa": "net_mass_kg",
        "tarifa": "tariff_code",
        "zemlja": "origin_country_code",
        "povlastica": "preference_code",
        "naziv": "goods_description",
    },
}


def _rows_for(draft, target: str) -> List[Any]:
    if target == "items":
        return list(draft.items or [])
    return list(draft.invoice_lines or [])


def _primijeni_uslove(rows: List[Any], uslovi: Optional[List[dict]], fields: Dict[str, str]) -> List[Any]:
    if not uslovi:
        return list(rows)

    out = []
    for row in rows:
        match = True
        for uslov in uslovi:
            polje = uslov.get("polje", "")
            operator = uslov.get("operator", "=")
            vrijednost = uslov.get("vrijednost", "")
            attr = fields.get(polje)
            if not attr:
                match = False
                break
            val = getattr(row, attr, "")
            val_s = str(val).strip() if val is not None else ""

            if operator == "prazno":
                ok = val_s == ""
            elif operator == "nije_prazno":
                ok = val_s != ""
            elif operator == "!=":
                ok = val_s.casefold() != str(vrijednost).strip().casefold()
            else:  # "="
                ok = val_s.casefold() == str(vrijednost).strip().casefold()

            if not ok:
                match = False
                break
        if match:
            out.append(row)
    return out


def agregiraj(
    draft,
    operacija: str,
    polje: str = "",
    target: str = "items",
    uslovi: Optional[List[dict]] = None,
    top_n: Optional[int] = None,
) -> Dict[str, Any]:
    """SUM/AVG/MAX/MIN/COUNT nad numeričkim poljem, opciono filtrirano."""
    fields = FIELD_MAP.get(target)
    if fields is None:
        return {"error": f"Nepoznat target: {target}"}

    rows = _primijeni_uslove(_rows_for(draft, target), uslovi, fields)

    if operacija == "count":
        return {"operacija": "count", "target": target, "broj": len(rows)}

    attr = fields.get(polje)
    if not attr:
        return {
            "error": (
                f"Nepoznato ili nepodržano polje '{polje}' za target '{target}'. "
                f"Dostupno: {sorted(fields)}"
            )
        }

    parovi = [(row, getattr(row, attr, 0.0) or 0.0) for row in rows]
    if not parovi:
        return {
            "operacija": operacija, "target": target, "polje": polje,
            "broj_stavki": 0, "rezultat": None,
        }

    if operacija in ("max", "min"):
        sortirano = sorted(parovi, key=lambda rv: rv[1], reverse=(operacija == "max"))
        n = max(1, top_n or 1)
        return {
            "operacija": operacija, "target": target, "polje": polje,
            "broj_stavki": len(parovi),
            "top": [{"row": row, "vrijednost": v} for row, v in sortirano[:n]],
        }

    if operacija == "sum":
        rezultat = sum(v for _, v in parovi)
    elif operacija == "avg":
        rezultat = sum(v for _, v in parovi) / len(parovi)
    else:
        return {"error": f"Nepoznata operacija: {operacija}"}

    return {
        "operacija": operacija, "target": target, "polje": polje,
        "broj_stavki": len(parovi), "rezultat": rezultat,
    }


def filtriraj(
    draft,
    target: str = "items",
    uslovi: Optional[List[dict]] = None,
    grupisi_po: Optional[str] = None,
) -> Dict[str, Any]:
    """Filtriraj i/ili grupiši stavke po bilo kom podržanom polju."""
    fields = FIELD_MAP.get(target)
    if fields is None:
        return {"error": f"Nepoznat target: {target}"}

    rows = _primijeni_uslove(_rows_for(draft, target), uslovi, fields)

    if grupisi_po:
        attr = fields.get(grupisi_po)
        if not attr:
            return {"error": f"Nepoznato polje za grupisanje: {grupisi_po}"}
        grupe: Dict[str, List[Any]] = {}
        for row in rows:
            key = str(getattr(row, attr, "") or "—")
            grupe.setdefault(key, []).append(row)
        return {"target": target, "grupisano_po": grupisi_po, "grupe": grupe, "broj": len(rows)}

    return {"target": target, "rows": rows, "broj": len(rows)}
