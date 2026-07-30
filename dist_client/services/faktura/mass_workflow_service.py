import logging

from services.faktura.mass_calculator import MassCalculator
from services.faktura.models import CalculateMassesRequest, CalculateMassesResult
from services.faktura.weight_guards import (
    find_mass_total_mismatches,
    group_lines_by_invoice,
    is_suspicious_fallback,
    normalized_invoice_weights,
)

logger = logging.getLogger("deklarant_pro.faktura.mass_workflow")


class MassWorkflowService:
    def calculate(self, draft, request: CalculateMassesRequest) -> CalculateMassesResult:
        lines = getattr(draft, "invoice_lines", []) or []
        invoice_groups, no_invoice_lines, invoice_labels = group_lines_by_invoice(lines)
        invoice_weights = normalized_invoice_weights(getattr(draft, "invoice_weights", {}) or {})
        invoice_weights = self._with_toolbar_neto_fallback(
            invoice_weights,
            request.neto_total,
        )

        total_updated = 0
        total_skipped = 0
        no_weight_invoices = []

        for inv_key, group_lines in invoice_groups.items():
            if inv_key in invoice_weights:
                inv_bruto, inv_neto = invoice_weights[inv_key]
                stats = MassCalculator.calculate_masses(group_lines, inv_bruto, inv_neto)
                total_updated += stats["updated"]
                total_skipped += stats["skipped"]
                label = invoice_labels.get(inv_key, inv_key)
                logger.debug(
                    "   ⚖️ [%s]: %s ažurirano, %s preskočeno (%.3f/%.3f kg)",
                    label,
                    stats["updated"],
                    stats["skipped"],
                    inv_bruto,
                    inv_neto,
                )
            else:
                no_weight_invoices.append(inv_key)
                total_skipped += len(group_lines)
                label = invoice_labels.get(inv_key, inv_key)
                logger.debug("   ⚠️ [%s]: nema sačuvane težine — preskočeno", label)

        fallback_skipped = 0
        suspicious_fallback = is_suspicious_fallback(invoice_groups, no_invoice_lines)
        if no_invoice_lines:
            if suspicious_fallback and not request.allow_suspicious_fallback:
                fallback_skipped = len(no_invoice_lines)
                total_skipped += fallback_skipped
                logger.debug(
                    "   ⚠️ [bez fakture]: %s preskočeno zbog sumnjivog fallback-a",
                    fallback_skipped,
                )
            else:
                stats = MassCalculator.calculate_masses(
                    no_invoice_lines,
                    request.bruto_total,
                    request.neto_total,
                )
                total_updated += stats["updated"]
                total_skipped += stats["skipped"]
                logger.debug(
                    "   ⚖️ [bez fakture]: %s ažurirano koristeći toolbar total",
                    stats["updated"],
                )

        mass_mismatches = find_mass_total_mismatches(
            invoice_groups,
            invoice_weights,
            invoice_labels,
        )
        reason = self._reason(
            total_updated,
            fallback_skipped,
            no_weight_invoices,
            no_invoice_lines,
            mass_mismatches,
        )

        return CalculateMassesResult(
            success=total_updated > 0,
            updated_count=total_updated,
            skipped_count=total_skipped,
            fallback_skipped=fallback_skipped,
            no_weight_invoices=no_weight_invoices,
            mass_mismatches=mass_mismatches,
            suspicious_fallback=suspicious_fallback,
            no_invoice_count=len(no_invoice_lines),
            reason=reason,
            invoice_labels=invoice_labels,
        )

    def _with_toolbar_neto_fallback(self, invoice_weights: dict, neto_total: float) -> dict:
        if neto_total <= 0 or not invoice_weights:
            return invoice_weights
        stored_neto_sum = sum(n for _, n in invoice_weights.values())
        if stored_neto_sum != 0:
            return invoice_weights
        total_stored_bruto = sum(b for b, _ in invoice_weights.values())
        if total_stored_bruto <= 0:
            return invoice_weights
        adjusted = dict(invoice_weights)
        for key, (inv_bruto, _) in adjusted.items():
            proportion = inv_bruto / total_stored_bruto
            adjusted[key] = (inv_bruto, round(neto_total * proportion, 3))
        logger.debug(
            "   ℹ️ Neto iz toolbar-a (%.3f kg) raspoređen proporcionalno na %s faktura(e)",
            neto_total,
            len(adjusted),
        )
        return adjusted

    def _reason(
        self,
        updated_count: int,
        fallback_skipped: int,
        no_weight_invoices: list,
        no_invoice_lines: list,
        mass_mismatches: list,
    ) -> str:
        if updated_count > 0:
            return "updated"
        if fallback_skipped:
            return "fallback_skipped"
        if no_weight_invoices and not no_invoice_lines:
            return "missing_invoice_weights"
        if mass_mismatches:
            return "mass_mismatch"
        return "nothing_to_update"
