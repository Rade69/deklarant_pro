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


def _resolve_target(draft, target: Optional[str]) -> tuple[str, Optional[str]]:
    """Odredi stvaran target kad LLM ne navede jedan eksplicitno.

    Naimenovanja (items) se kreiraju TEK nakon fakturnih linija — odmah
    nakon uvoza fakture `draft.items` je prazan. Ako LLM ne navede target
    i items je prazan dok invoice_lines nije, "items" default bi tiho
    pretražio praktično prazan skup i vratio lažno nizak/pogrešan broj
    (potvrđen stvaran bug: "19 bez tarife" na Faktura status bedžu, agent
    odgovorio "1 naimenovanje" jer je default bio items). Vraća
    (rezolutovan_target, napomena_za_korisnika_ili_None).
    """
    if target:
        return target, None
    if not (draft.items or []):
        return "invoice", (
            "Naimenovanja još nisu kreirana za ovu deklaraciju — "
            "pretraženo je po fakturnim linijama."
        )
    return "items", None


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
    target: Optional[str] = None,
    uslovi: Optional[List[dict]] = None,
    top_n: Optional[int] = None,
) -> Dict[str, Any]:
    """SUM/AVG/MAX/MIN/COUNT nad numeričkim poljem, opciono filtrirano.

    target=None (LLM ga nije naveo) → vidi _resolve_target().
    """
    target, napomena = _resolve_target(draft, target)
    fields = FIELD_MAP.get(target)
    if fields is None:
        return {"error": f"Nepoznat target: {target}"}

    rows = _primijeni_uslove(_rows_for(draft, target), uslovi, fields)

    if operacija == "count":
        rez = {"operacija": "count", "target": target, "broj": len(rows)}
        if napomena:
            rez["napomena"] = napomena
        return rez

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
        rez = {
            "operacija": operacija, "target": target, "polje": polje,
            "broj_stavki": 0, "rezultat": None,
        }
        if napomena:
            rez["napomena"] = napomena
        return rez

    if operacija in ("max", "min"):
        sortirano = sorted(parovi, key=lambda rv: rv[1], reverse=(operacija == "max"))
        n = max(1, top_n or 1)
        rez = {
            "operacija": operacija, "target": target, "polje": polje,
            "broj_stavki": len(parovi),
            "top": [{"row": row, "vrijednost": v} for row, v in sortirano[:n]],
        }
        if napomena:
            rez["napomena"] = napomena
        return rez

    if operacija == "sum":
        rezultat = sum(v for _, v in parovi)
    elif operacija == "avg":
        rezultat = sum(v for _, v in parovi) / len(parovi)
    else:
        return {"error": f"Nepoznata operacija: {operacija}"}

    rez = {
        "operacija": operacija, "target": target, "polje": polje,
        "broj_stavki": len(parovi), "rezultat": rezultat,
        "stavke": [{"row": row, "vrijednost": v} for row, v in parovi],
    }
    if napomena:
        rez["napomena"] = napomena
    return rez


def filtriraj(
    draft,
    target: Optional[str] = None,
    uslovi: Optional[List[dict]] = None,
    grupisi_po: Optional[str] = None,
) -> Dict[str, Any]:
    """Filtriraj i/ili grupiši stavke po bilo kom podržanom polju.

    target=None (LLM ga nije naveo) → vidi _resolve_target().
    """
    target, napomena = _resolve_target(draft, target)
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
        rez = {"target": target, "grupisano_po": grupisi_po, "grupe": grupe, "broj": len(rows)}
        if napomena:
            rez["napomena"] = napomena
        return rez

    rez = {"target": target, "rows": rows, "broj": len(rows)}
    if napomena:
        rez["napomena"] = napomena
    return rez
