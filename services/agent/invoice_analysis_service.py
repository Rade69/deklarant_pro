# services/agent/invoice_analysis_service.py

"""
InvoiceAnalysisService — analiza fakture bez uvoza u draft.

Razdvaja stavke na poznate (u bazi znanja) i nepoznate,
provjerava uslove za EUR.1, i formatira izvještaj za agenta.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional
from core.draft.draft import InvoiceLine

logger = logging.getLogger("asycuda_pro.agent.analysis")

EUR1_THRESHOLD = 6000.0  # EUR


@dataclass
class ItemAnalysis:
    line: InvoiceLine
    known: bool               # True = u bazi znanja
    proposed_tariff: str = ""
    confidence: float = 0.0
    source: str = ""          # "baza_znanja" | "llm" | ""


@dataclass
class AnalysisResult:
    total_items: int = 0
    known_items: List[ItemAnalysis] = field(default_factory=list)
    unknown_items: List[ItemAnalysis] = field(default_factory=list)
    total_value_eur: float = 0.0
    currency: str = "EUR"
    has_origin_statement: bool = False
    eur1_warning: bool = False
    supplier_hint: str = ""
    invoice_name: str = ""
    bruto_kg: float = 0.0
    neto_kg: float = 0.0


class InvoiceAnalysisService:
    """
    Analizira parsirane invoice stavke bez uvoza u draft.
    Vraća AnalysisResult koji agent formatira u chat poruku.
    """

    def __init__(self):
        from services.tariff_mapping_service import TariffMappingService
        self._mapping_svc = TariffMappingService()

    def analyse(
        self,
        lines: List[InvoiceLine],
        bruto_kg: float = 0.0,
        neto_kg: float = 0.0,
        invoice_name: str = "",
        has_origin_statement: bool = False,
        currency: str = "EUR",
    ) -> AnalysisResult:
        """
        Analizira listu InvoiceLine-ova:
        - Provjerava svaku stavku u bazi znanja
        - Računa ukupnu vrijednost
        - Provjerava uslov za EUR.1 upozorenje
        """
        result = AnalysisResult(
            total_items=len(lines),
            bruto_kg=bruto_kg,
            neto_kg=neto_kg,
            invoice_name=invoice_name,
            has_origin_statement=has_origin_statement,
            currency=currency,
        )

        # Ukupna vrijednost
        result.total_value_eur = sum(
            (l.iznos or 0.0) for l in lines
        )

        # Provjeri svaku stavku u bazi znanja
        for line in lines:
            already_has = bool(getattr(line, 'tarifni_broj', None))

            if already_has:
                # Stavka već ima tarifni broj (uvezeno iz XLS npr.)
                item = ItemAnalysis(
                    line=line,
                    known=True,
                    proposed_tariff=line.tarifni_broj,
                    confidence=1.0,
                    source="faktura",
                )
                result.known_items.append(item)
                continue

            mapping = self._mapping_svc.find_mapping(
                product_code=getattr(line, 'product_code', ''),
                naziv_robe=getattr(line, 'naziv_robe', ''),
                min_similarity=0.85,
            )

            if mapping:
                item = ItemAnalysis(
                    line=line,
                    known=True,
                    proposed_tariff=mapping.tarifni_broj,
                    confidence=getattr(mapping, 'similarity', 1.0),
                    source="baza_znanja",
                )
                result.known_items.append(item)
            else:
                item = ItemAnalysis(
                    line=line,
                    known=False,
                    proposed_tariff="",
                    confidence=0.0,
                    source="",
                )
                result.unknown_items.append(item)

        # EUR.1 upozorenje: izjava o porijeklu + vrijednost > praga
        if has_origin_statement and result.total_value_eur > EUR1_THRESHOLD:
            result.eur1_warning = True

        # Supplier hint iz prve stavke
        for line in lines:
            name = getattr(getattr(line, 'exporter', None), 'name', None)
            if name and name.strip():
                result.supplier_hint = name.strip()
                break

        logger.info(
            f"[Analiza] {result.total_items} stavki | "
            f"poznate={len(result.known_items)} | "
            f"nepoznate={len(result.unknown_items)} | "
            f"vrijednost={result.total_value_eur:.2f} {currency} | "
            f"EUR1={result.eur1_warning}"
        )
        return result

    def format_report(self, result: AnalysisResult) -> str:
        """
        Formatira AnalysisResult u HTML poruku za agent chat.
        """
        n_known   = len(result.known_items)
        n_unknown = len(result.unknown_items)
        pct_known = int(n_known / result.total_items * 100) if result.total_items else 0

        # ── Zaglavlje ──
        lines = [
            f"<b>📦 Analiza fakture: {result.invoice_name or '—'}</b><br>",
            f"Stavki: <b>{result.total_items}</b> | "
            f"Vrijednost: <b>{result.total_value_eur:,.2f} {result.currency}</b> | "
            f"Bruto: <b>{result.bruto_kg:,.1f} kg</b><br>",
        ]

        # ── Tarifna pokrivenost ──
        lines.append("<br>")
        if pct_known == 100:
            lines.append(f"✅ <b>Sve stavke poznate u bazi ({n_known}/{result.total_items})</b> — auto-popuni će raditi bez problema.<br>")
        elif pct_known >= 70:
            lines.append(
                f"🟡 <b>{n_known}/{result.total_items} stavki poznato ({pct_known}%)</b> — "
                f"<b>{n_unknown}</b> stavki treba ručnu provjeru tarife.<br>"
            )
        else:
            lines.append(
                f"🔴 <b>{n_known}/{result.total_items} stavki poznato ({pct_known}%)</b> — "
                f"mnogo novih stavki, preporučuje se ručna provjera tarife.<br>"
            )

        # ── Nepoznate stavke ──
        if result.unknown_items:
            lines.append("<br><b>❓ Nepoznate stavke (nema u bazi znanja):</b><br>")
            for ia in result.unknown_items[:15]:
                code = ia.line.product_code or "—"
                name = (ia.line.naziv_robe or "—")[:55]
                izn  = ia.line.iznos or 0.0
                zem  = ia.line.zemlja_porijekla or "—"
                lines.append(
                    f"&nbsp;&nbsp;• <b>{code}</b> — {name} "
                    f"({izn:,.2f} EUR, {zem})<br>"
                )
            if len(result.unknown_items) > 15:
                lines.append(f"&nbsp;&nbsp;<i>... i još {len(result.unknown_items) - 15} stavki</i><br>")

        # ── EUR.1 upozorenje ──
        if result.eur1_warning:
            lines.append(
                f"<br>⚠️ <b>Provjeri EUR.1 obrazac!</b><br>"
                f"Faktura ima izjavu o porijeklu robe i vrijednost "
                f"<b>{result.total_value_eur:,.2f} EUR</b> "
                f"prelazi prag od <b>6.000 EUR</b> — "
                f"pošiljku mora pratiti fizički EUR.1 obrazac.<br>"
            )
        elif result.has_origin_statement:
            lines.append(
                f"<br>ℹ️ Faktura ima izjavu o porijeklu robe. "
                f"Vrijednost ({result.total_value_eur:,.2f} EUR) "
                f"je ispod praga od 6.000 EUR — EUR.1 nije potreban.<br>"
            )

        return "".join(lines)
