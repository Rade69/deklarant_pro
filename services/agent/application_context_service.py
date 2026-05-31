from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
from typing import Any


def _s(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _short(value: Any, limit: int = 80) -> str:
    text = _s(value)
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


class ApplicationContextService:
    def __init__(self, draft=None):
        self.draft = draft

    def snapshot(self) -> dict[str, Any]:
        draft = self.draft
        invoice_lines = list(getattr(draft, "invoice_lines", []) or []) if draft else []
        naimenovanja = list(getattr(draft, "items", []) or []) if draft else []
        return {
            "status": self._status(draft, invoice_lines, naimenovanja),
            "header": self._header(draft),
            "invoice_lines": self._invoice_lines(invoice_lines),
            "naimenovanja": self._naimenovanja(naimenovanja),
        }

    def format_html(self, scope: str = "all") -> str:
        data = self.snapshot()
        scope = (scope or "all").lower()
        parts = ["<b>Trenutno stanje aplikacije</b>"]

        status = data["status"]
        parts.append(
            "Status: "
            f"faktura stavki <b>{status['invoice_line_count']}</b>, "
            f"naimenovanja <b>{status['naimenovanje_count']}</b>, "
            f"dirty=<b>{'da' if status['dirty'] else 'ne'}</b>"
        )

        if scope in {"all", "header", "zaglavlje"}:
            parts.append(self._format_header(data["header"]))
        if scope in {"all", "faktura", "invoice", "invoice_lines"}:
            parts.append(self._format_invoice(data["invoice_lines"]))
        if scope in {"all", "naimenovanja", "naim"}:
            parts.append(self._format_naimenovanja(data["naimenovanja"]))

        return "<br>".join(part for part in parts if part)

    def _status(self, draft, invoice_lines: list, naimenovanja: list) -> dict[str, Any]:
        return {
            "has_draft": draft is not None,
            "invoice_line_count": len(invoice_lines),
            "naimenovanje_count": len(naimenovanja),
            "dirty": bool(getattr(draft, "dirty", False)) if draft else False,
            "source_files": list(getattr(draft, "source_files", []) or []) if draft else [],
            "warnings": list(getattr(draft, "warnings", []) or []) if draft else [],
        }

    def _header(self, draft) -> dict[str, Any]:
        if not draft:
            return {}
        return {
            "declaration": " ".join(
                part for part in [
                    _s(getattr(draft, "deklaracija_tip", "")),
                    _s(getattr(draft, "deklaracija_oznaka", "")),
                    _s(getattr(draft, "deklaracija_a", "")),
                ] if part
            ),
            "exporter": _s(getattr(draft, "izvoznik_naziv", "")),
            "importer": _s(getattr(draft, "primalac_naziv", "")),
            "declarant": _s(getattr(draft, "deklarant_naziv", "")),
            "currency": _s(getattr(draft, "valuta", "")),
            "invoice_total": _f(getattr(draft, "iznos", 0.0)),
            "exchange_rate": _f(getattr(draft, "kurs", 0.0)),
            "delivery": " ".join(
                part for part in [
                    _s(getattr(draft, "uslovi_kod", "")),
                    _s(getattr(draft, "uslovi_mjesto", "")),
                ] if part
            ),
            "gross_from_lines": 0.0,
            "net_from_lines": 0.0,
            "previous_document": " ".join(
                part for part in [
                    _s(getattr(draft, "rb40_skracenica", "")),
                    _s(getattr(draft, "rb40_broj", "")),
                ] if part
            ),
            "attached_documents": [
                {
                    "code": _s(getattr(doc, "code", "")),
                    "number": _s(getattr(doc, "number", "")),
                    "name": _s(getattr(doc, "name", "")),
                }
                for doc in list(getattr(draft, "header_attached_documents", []) or [])
            ],
        }

    def _invoice_lines(self, lines: list) -> dict[str, Any]:
        invoices: dict[str, dict[str, Any]] = {}
        tariff_counter = Counter()
        country_counter = Counter()
        preference_counter = Counter()
        missing_tariff = []
        missing_country = []
        missing_amount = []

        for idx, line in enumerate(lines, start=1):
            invoice = _s(getattr(line, "invoice_number", "")) or "(bez broja)"
            bucket = invoices.setdefault(invoice, {
                "invoice_number": invoice,
                "count": 0,
                "amount": 0.0,
                "gross": 0.0,
                "net": 0.0,
                "countries": Counter(),
                "tariffs": Counter(),
                "preferences": Counter(),
                "samples": [],
            })
            tariff = _s(getattr(line, "tarifni_broj", ""))
            country = _s(getattr(line, "zemlja_porijekla", ""))
            preference = _s(getattr(line, "povlastica", ""))
            amount = _f(getattr(line, "iznos", 0.0))

            bucket["count"] += 1
            bucket["amount"] += amount
            bucket["gross"] += _f(getattr(line, "bruto_kg", 0.0))
            bucket["net"] += _f(getattr(line, "neto_kg", 0.0))
            if country:
                bucket["countries"][country] += 1
                country_counter[country] += 1
            if tariff:
                bucket["tariffs"][tariff] += 1
                tariff_counter[tariff] += 1
            if preference:
                bucket["preferences"][preference] += 1
                preference_counter[preference] += 1
            if len(bucket["samples"]) < 3:
                bucket["samples"].append({
                    "rb": idx,
                    "name": _s(getattr(line, "naziv_robe", "")),
                    "tariff": tariff,
                    "country": country,
                    "amount": amount,
                })

            if not tariff:
                missing_tariff.append(idx)
            if not country:
                missing_country.append(idx)
            if amount <= 0:
                missing_amount.append(idx)

        invoice_list = []
        for bucket in invoices.values():
            invoice_list.append({
                **{k: v for k, v in bucket.items() if k not in {"countries", "tariffs", "preferences"}},
                "countries": dict(bucket["countries"]),
                "tariffs": dict(bucket["tariffs"]),
                "preferences": dict(bucket["preferences"]),
            })

        return {
            "count": len(lines),
            "invoice_count": len(invoice_list),
            "total_amount": sum(_f(getattr(line, "iznos", 0.0)) for line in lines),
            "total_gross": sum(_f(getattr(line, "bruto_kg", 0.0)) for line in lines),
            "total_net": sum(_f(getattr(line, "neto_kg", 0.0)) for line in lines),
            "invoices": sorted(invoice_list, key=lambda row: row["invoice_number"]),
            "tariffs": dict(tariff_counter),
            "countries": dict(country_counter),
            "preferences": dict(preference_counter),
            "missing": {
                "tariff": missing_tariff,
                "country": missing_country,
                "amount": missing_amount,
            },
        }

    def _naimenovanja(self, items: list) -> dict[str, Any]:
        rows = []
        missing = defaultdict(list)
        for idx, item in enumerate(items, start=1):
            rb = getattr(item, "ordinal_no", idx) or idx
            row = {
                "rb": rb,
                "tariff": _s(getattr(item, "tariff_code", "")),
                "suffix": _s(getattr(item, "tariff_suffix", "")),
                "country": _s(getattr(item, "origin_country_code", "")),
                "preference": _s(getattr(item, "preference_code", "")),
                "gross": _f(getattr(item, "gross_mass_kg", 0.0)),
                "net": _f(getattr(item, "net_mass_kg", 0.0)),
                "value": _f(getattr(item, "item_value", 0.0)),
                "statistical_value": _f(getattr(item, "statistical_value", 0.0)),
                "rub31": _s(getattr(item, "goods_description", "")),
                "rub40": " ".join(
                    part for part in [
                        _s(getattr(item, "previous_document", "")),
                        _s(getattr(item, "previous_document2", "")),
                        _s(getattr(item, "previous_document3", "")),
                    ] if part
                ),
                "rub44": " ".join(
                    part for part in [
                        _s(getattr(item, "attached_document1", "")),
                        _s(getattr(item, "attached_document2", "")),
                        _s(getattr(item, "attached_document3", "")),
                        _s(getattr(item, "attached_document4", "")),
                        _s(getattr(item, "attached_document5", "")),
                    ] if part
                ),
            }
            if not row["tariff"]:
                missing["tariff"].append(rb)
            if not row["country"]:
                missing["country"].append(rb)
            if not row["rub31"]:
                missing["rub31"].append(rb)
            rows.append(row)

        return {
            "count": len(rows),
            "total_gross": sum(row["gross"] for row in rows),
            "total_net": sum(row["net"] for row in rows),
            "total_value": sum(row["value"] for row in rows),
            "items": rows,
            "missing": dict(missing),
        }

    def _format_header(self, header: dict[str, Any]) -> str:
        if not header:
            return "<br><b>Zaglavlje</b>: nema drafta."
        docs = ", ".join(
            f"{escape(doc['code'])} {escape(doc['number'])}".strip()
            for doc in header.get("attached_documents", [])
            if doc.get("code") or doc.get("number")
        )
        return (
            "<br><b>Zaglavlje</b><br>"
            f"Pošiljalac: {escape(header.get('exporter') or '-')}; "
            f"Primalac: {escape(header.get('importer') or '-')}; "
            f"Valuta: {escape(header.get('currency') or '-')}; "
            f"Ukupno: {header.get('invoice_total', 0):.2f}; "
            f"Uslovi: {escape(header.get('delivery') or '-')}; "
            f"Rb.40: {escape(header.get('previous_document') or '-')}; "
            f"Prilozi: {escape(docs or '-')}"
        )

    def _format_invoice(self, data: dict[str, Any]) -> str:
        if data["count"] == 0:
            return "<br><b>Faktura</b>: nema učitanih stavki."
        parts = [
            "<br><b>Faktura tab</b>",
            f"Stavki: <b>{data['count']}</b>; faktura: <b>{data['invoice_count']}</b>; "
            f"iznos: <b>{data['total_amount']:.2f}</b>; "
            f"bruto/neto: <b>{data['total_gross']:.2f}/{data['total_net']:.2f} kg</b>",
            "Fakture:",
        ]
        for inv in data["invoices"][:12]:
            countries = ", ".join(f"{k}:{v}" for k, v in inv["countries"].items()) or "-"
            tariffs = ", ".join(f"{k}:{v}" for k, v in list(inv["tariffs"].items())[:5]) or "-"
            sample = "; ".join(_short(s["name"], 35) for s in inv["samples"] if s["name"])
            parts.append(
                f"• <b>{escape(inv['invoice_number'])}</b>: {inv['count']} stavki, "
                f"{inv['amount']:.2f}, zemlje {escape(countries)}, tarife {escape(tariffs)}"
                + (f"<br><small>{escape(sample)}</small>" if sample else "")
            )
        missing = data["missing"]
        parts.append(
            "Nedostaje: "
            f"tarifa {len(missing['tariff'])}, "
            f"zemlja {len(missing['country'])}, "
            f"iznos {len(missing['amount'])}"
        )
        return "<br>".join(parts)

    def _format_naimenovanja(self, data: dict[str, Any]) -> str:
        if data["count"] == 0:
            return "<br><b>Naimenovanja</b>: nema kreiranih naimenovanja."
        parts = [
            "<br><b>Naimenovanja tab</b>",
            f"Naimenovanja: <b>{data['count']}</b>; "
            f"vrijednost: <b>{data['total_value']:.2f}</b>; "
            f"bruto/neto: <b>{data['total_gross']:.2f}/{data['total_net']:.2f} kg</b>",
        ]
        for row in data["items"][:20]:
            parts.append(
                f"• Rb.{row['rb']}: {escape(row['tariff'] or '-')}, "
                f"zemlja {escape(row['country'] or '-')}, "
                f"povl. {escape(row['preference'] or '-')}, "
                f"rub.31 {escape(_short(row['rub31'], 60) or '-')}, "
                f"rub.44 {escape(_short(row['rub44'], 45) or '-')}"
            )
        missing = data["missing"]
        parts.append(
            "Nedostaje: "
            f"tarifa {len(missing.get('tariff', []))}, "
            f"zemlja {len(missing.get('country', []))}, "
            f"rub.31 {len(missing.get('rub31', []))}"
        )
        return "<br>".join(parts)
