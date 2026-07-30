import logging

from services.faktura.models import (
    CreateNaimenovanjaDraftResult,
    CreateNaimenovanjaPostActionPlan,
    CreateNaimenovanjaWorkflowResult,
)

logger = logging.getLogger("deklarant_pro.faktura.create_naimenovanja_workflow")


class CreateNaimenovanjaWorkflowService:
    def create_for_drafts(self, drafts: list) -> CreateNaimenovanjaWorkflowResult:
        results = []
        try:
            from services.naimenovanja.create_naimenovanja_service import (
                CreateNaimenovanjaService,
            )

            for draft in drafts:
                svc = CreateNaimenovanjaService(draft)
                count = svc.create_smart_group()
                split_info = getattr(svc, "last_split_info", None)
                learning_count, learning_error = self._learn_from_draft(draft)
                results.append(
                    CreateNaimenovanjaDraftResult(
                        draft=draft,
                        count=count,
                        split_info=split_info,
                        learning_count=learning_count,
                        learning_error=learning_error,
                    )
                )
            return CreateNaimenovanjaWorkflowResult(draft_results=results)
        except Exception as e:
            logger.error("Kreiranje naimenovanja nije uspjelo: %s", e, exc_info=True)
            return CreateNaimenovanjaWorkflowResult(draft_results=results, error=e)

    def clear_import_memory(self) -> None:
        try:
            from services.import_service import get_import_service
            get_import_service().clear_memory()
        except Exception:
            logger.debug("Import service memory cleanup preskočen", exc_info=True)

    def build_post_action_plan(self) -> CreateNaimenovanjaPostActionPlan:
        return CreateNaimenovanjaPostActionPlan()

    def _learn_from_draft(self, draft) -> tuple[int, str]:
        try:
            from services.tariff_facade import TariffFacade
            count = TariffFacade.get_instance().learn_from_draft(
                draft.invoice_lines,
                draft_uid=getattr(draft, "draft_uid", "") or "",
            )
            return count or 0, ""
        except Exception as e:
            logger.warning("Auto-učenje tarifa nije uspjelo: %s", e)
            return 0, str(e)
