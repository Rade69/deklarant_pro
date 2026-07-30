import logging

from services.faktura.auto_fill_service import AutoFillService
from services.faktura.models import AutoFillWorkflowRequest, AutoFillWorkflowResult

logger = logging.getLogger("deklarant_pro.faktura.auto_fill_workflow")


class AutoFillWorkflowService:
    def __init__(self, auto_fill_service=None, facade=None):
        self.auto_fill_service = auto_fill_service or AutoFillService()
        self.facade = facade

    def supplier_name_for(self, target_lines: list) -> str:
        if not target_lines:
            return ""
        exporter = getattr(target_lines[0], "exporter", None)
        return getattr(exporter, "name", "") or ""

    def skipped_details_for(self, target_lines: list) -> list[tuple[int, str, str]]:
        return [
            (
                line.line_no,
                line.product_code or line.naziv_robe[:30],
                line.tarifni_broj,
            )
            for line in target_lines
            if line.tarifni_broj
        ]

    def prepare_preview(self, request: AutoFillWorkflowRequest):
        try:
            return self._facade().auto_populate_tariffs(
                request.target_lines,
                min_similarity=request.min_similarity,
                overwrite_existing=False,
                supplier=request.supplier_name,
                dry_run=True,
            )
        except Exception as e:
            logger.warning("Auto-popuni preview greška: %s", e, exc_info=True)
            return None

    def run(self, request: AutoFillWorkflowRequest) -> AutoFillWorkflowResult:
        skipped_details = self.skipped_details_for(request.target_lines)
        supplier_name = request.supplier_name or self.supplier_name_for(request.target_lines)
        try:
            basic_filled_count = (
                request.basic_filled_count
                if request.basic_filled_count is not None
                else self.auto_fill_service.fill_basic_fields(request.target_lines)
            )
            if request.confirmed_proposals is not None:
                result = self._facade().commit_proposals(
                    request.target_lines,
                    request.confirmed_proposals,
                )
            else:
                result = self._facade().auto_populate_tariffs(
                    request.target_lines,
                    min_similarity=request.min_similarity,
                    overwrite_existing=False,
                    supplier=supplier_name,
                )
            result.skipped_items = len(skipped_details)
            result.skipped_details = skipped_details
            return AutoFillWorkflowResult(
                mapping_result=result,
                basic_filled_count=basic_filled_count,
                supplier_name=supplier_name,
                skipped_details=skipped_details,
            )
        except Exception as e:
            logger.error("Auto-popuni greška: %s", e, exc_info=True)
            return AutoFillWorkflowResult(
                basic_filled_count=0,
                supplier_name=supplier_name,
                skipped_details=skipped_details,
                error=e,
            )

    def empty_result(self, total_items: int, skipped_details: list):
        from services.tariff.tariff_mapping_service import MappingResult
        empty = MappingResult(
            total_items=total_items,
            matched_items=0,
            unmatched_items=total_items - len(skipped_details),
        )
        empty.skipped_items = len(skipped_details)
        empty.skipped_details = skipped_details
        return empty

    def sync_decision_state(self, target_lines: list, supplier_name: str) -> None:
        try:
            from services.decision.integration import sync_decision_state_after_autofill
            sync_decision_state_after_autofill(
                target_lines,
                supplier=supplier_name,
                action_type="auto_fill_clicked",
            )
        except Exception:
            logger.warning("Decision sync autofill nije uspio", exc_info=True)

    def _facade(self):
        if self.facade is None:
            from services.tariff_facade import TariffFacade
            self.facade = TariffFacade.get_instance()
        return self.facade
