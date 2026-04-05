# services/agent/compliance_check_service.py
"""
ComplianceCheckService — provjera kompletnosti deklaracije.

Provjerava:
  1. Tarifni brojevi postoje u tarifi 2026
  2. Zemlja porijekla popunjena za sve stavke
  3. Težine su logične (bruto > 0, neto <= bruto)
  4. EUR.1 ili izjava o porijeklu prisutna kad postoji povlastica

Vraća listu Issue objekata sa severity: 'error' | 'warning' | 'info'
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Literal, List

logger = logging.getLogger("asycuda_pro.compliance_check")


@dataclass
class Issue:
    severity: Literal['error', 'warning', 'info']
    code: str           # kratki identifikator: 'no_tariff', 'no_country', ...
    message: str        # opis za korisnika
    item_index: int = -1  # -1 = globalno; >= 0 = konkretna stavka


@dataclass
class ComplianceResult:
    issues: List[Issue] = field(default_factory=list)

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == 'error']

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == 'warning']

    @property
    def is_ok(self) -> bool:
        return len(self.errors) == 0

    def summary_html(self) -> str:
        if not self.issues:
            return "✅ <b>Deklaracija je kompletna</b> — nisu pronađeni problemi."

        lines = []
        if self.errors:
            lines.append(f"<b style='color:#b05050;'>❌ Greške ({len(self.errors)}):</b>")
            for iss in self.errors:
                loc = f" [stavka {iss.item_index}]" if iss.item_index >= 0 else ""
                lines.append(f"&nbsp;&nbsp;• {iss.message}{loc}")

        if self.warnings:
            lines.append(f"<b style='color:#b8963a;'>⚠️ Upozorenja ({len(self.warnings)}):</b>")
            for iss in self.warnings:
                loc = f" [stavka {iss.item_index}]" if iss.item_index >= 0 else ""
                lines.append(f"&nbsp;&nbsp;• {iss.message}{loc}")

        info_issues = [i for i in self.issues if i.severity == 'info']
        if info_issues:
            lines.append(f"<b style='color:#4a7890;'>ℹ️ Napomene ({len(info_issues)}):</b>")
            for iss in info_issues:
                lines.append(f"&nbsp;&nbsp;• {iss.message}")

        return "<br>".join(lines)


class ComplianceCheckService:
    """
    Provjerava kompletnost i konzistentnost stavki fakture/deklaracije.

    Upotreba:
        svc = ComplianceCheckService()
        result = svc.check(draft)
        html = result.summary_html()
    """

    def check(self, draft) -> ComplianceResult:
        result = ComplianceResult()

        lines = getattr(draft, 'invoice_lines', []) or []
        if not lines:
            result.issues.append(Issue('warning', 'empty', "Nema uvezenih stavki fakture."))
            return result

        self._check_tariff_codes(lines, result)
        self._check_zemlja_porijekla(lines, result)
        self._check_tezine(lines, result)
        self._check_eur1_povlastica(lines, result)
        self._check_naimenovanja(draft, result)

        return result

    # ─────────────────────────────────────────────────
    # 1. Tarifni brojevi
    # ─────────────────────────────────────────────────

    def _check_tariff_codes(self, lines, result: ComplianceResult):
        bez_tarife = [i for i, l in enumerate(lines, 1)
                      if not getattr(l, 'tarifni_broj', None)]
        if bez_tarife:
            if len(bez_tarife) <= 5:
                indices = ", ".join(str(i) for i in bez_tarife)
                result.issues.append(Issue(
                    'error', 'no_tariff',
                    f"Stavke bez tarifnog broja: {indices}"
                ))
            else:
                result.issues.append(Issue(
                    'error', 'no_tariff',
                    f"{len(bez_tarife)} stavki nema tarifni broj."
                ))

        # Provjeri postoje li tarifni brojevi u tarifi 2026
        invalid_codes = []
        try:
            from services.tarifa_service import trazi_po_kodu
            seen = set()
            for i, l in enumerate(lines, 1):
                kod = (getattr(l, 'tarifni_broj', '') or '').strip()
                if kod and kod not in seen:
                    seen.add(kod)
                    if not trazi_po_kodu(kod):
                        invalid_codes.append((i, kod))
        except Exception as e:
            logger.warning("Greška pri provjeri tarife: %s", e)

        for item_idx, kod in invalid_codes[:10]:
            result.issues.append(Issue(
                'error', 'invalid_tariff',
                f"Tarifni broj '{kod}' nije pronađen u Carinskoj tarifi 2026.",
                item_index=item_idx
            ))

    # ─────────────────────────────────────────────────
    # 2. Zemlja porijekla
    # ─────────────────────────────────────────────────

    def _check_zemlja_porijekla(self, lines, result: ComplianceResult):
        bez_zemlje = [i for i, l in enumerate(lines, 1)
                      if not getattr(l, 'zemlja_porijekla', None)]
        if bez_zemlje:
            if len(bez_zemlje) <= 5:
                indices = ", ".join(str(i) for i in bez_zemlje)
                result.issues.append(Issue(
                    'error', 'no_country',
                    f"Stavke bez zemlje porijekla: {indices}"
                ))
            else:
                result.issues.append(Issue(
                    'error', 'no_country',
                    f"{len(bez_zemlje)} stavki nema zemlju porijekla."
                ))

    # ─────────────────────────────────────────────────
    # 3. Težine
    # ─────────────────────────────────────────────────

    def _check_tezine(self, lines, result: ComplianceResult):
        ukupno_bruto = sum(getattr(l, 'bruto_kg', 0) or 0 for l in lines)
        ukupno_neto = sum(getattr(l, 'neto_kg', 0) or 0 for l in lines)

        if ukupno_bruto <= 0:
            result.issues.append(Issue(
                'warning', 'no_weight',
                "Ukupna bruto težina je 0 — provjeri da li su težine učitane."
            ))
        elif ukupno_neto > ukupno_bruto:
            result.issues.append(Issue(
                'warning', 'weight_inconsistent',
                f"Neto ({ukupno_neto:.3f} kg) je veći od bruto ({ukupno_bruto:.3f} kg)."
            ))
        elif ukupno_neto <= 0:
            result.issues.append(Issue(
                'info', 'no_neto',
                "Neto težina je 0 — biće jednaka bruto pri kreiranju naimenovanja."
            ))

    # ─────────────────────────────────────────────────
    # 4. EUR.1 / izjava o porijeklu
    # ─────────────────────────────────────────────────

    def _check_eur1_povlastica(self, lines, result: ComplianceResult):
        needs_doc = [
            i for i, l in enumerate(lines, 1)
            if getattr(l, 'povlastica', None)
            and not getattr(l, 'has_origin_statement', False)
            and not getattr(l, 'eur1_number', None)
        ]
        if needs_doc:
            if len(needs_doc) <= 5:
                indices = ", ".join(str(i) for i in needs_doc)
                result.issues.append(Issue(
                    'warning', 'no_eur1',
                    f"Stavke sa povlasticom ali bez EUR.1/izjave: {indices}"
                ))
            else:
                result.issues.append(Issue(
                    'warning', 'no_eur1',
                    f"{len(needs_doc)} stavki ima povlasticu ali nema EUR.1 ni izjavu o porijeklu."
                ))

    # ─────────────────────────────────────────────────
    # 5. Naimenovanja (ako su kreirana)
    # ─────────────────────────────────────────────────

    def _check_naimenovanja(self, draft, result: ComplianceResult):
        items = getattr(draft, 'items', []) or []
        if not items:
            return

        bez_tarife_naim = [
            i for i, it in enumerate(items, 1)
            if not getattr(it, 'tariff_code', None)
        ]
        if bez_tarife_naim:
            result.issues.append(Issue(
                'error', 'naim_no_tariff',
                f"{len(bez_tarife_naim)} naimenovanja bez tarifnog broja."
            ))

        bez_procedure = [
            i for i, it in enumerate(items, 1)
            if not getattr(it, 'procedure_code', None)
        ]
        if bez_procedure:
            result.issues.append(Issue(
                'warning', 'naim_no_procedure',
                f"{len(bez_procedure)} naimenovanja bez šifre postupka (Rub.37)."
            ))
