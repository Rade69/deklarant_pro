import logging

from services.faktura.models import (
    CreateNaimenovanjaDraftResult,
    CreateNaimenovanjaPostActionPlan,
    CreateNaimenovanjaPreparationResult,
    CreateNaimenovanjaUserMessage,
    CreateNaimenovanjaWorkflowResult,
)

logger = logging.getLogger("deklarant_pro.faktura.create_naimenovanja_workflow")


class CreateNaimenovanjaWorkflowService:
    def prepare(self, draft, multi_drafts: list, auto: bool = False) -> CreateNaimenovanjaPreparationResult:
        from services.faktura.declaration_split_service import count_declaration_groups

        drafts_to_process = multi_drafts if len(multi_drafts) > 1 else [draft]
        all_lines = [line for current_draft in drafts_to_process for line in current_draft.invoice_lines]
        should_offer_split = (
            len(multi_drafts) <= 1
            and bool(getattr(draft, "invoice_lines", []))
            and not auto
            and count_declaration_groups(draft.invoice_lines) > 1
        )
        return CreateNaimenovanjaPreparationResult(
            drafts_to_process=drafts_to_process,
            all_lines=all_lines,
            should_offer_split=should_offer_split,
        )

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

    def build_success_message(
        self,
        result: CreateNaimenovanjaWorkflowResult,
        all_lines_count: int,
    ) -> CreateNaimenovanjaUserMessage:
        from services.faktura.declaration_split_service import group_label

        display_results = [
            (draft_result.draft, draft_result.count, draft_result.split_info)
            for draft_result in result.draft_results
        ]
        overflow_drafts = [
            (draft, count, split_info)
            for draft, count, split_info in display_results
            if split_info and split_info.overflow_count > 0
        ]
        if overflow_drafts:
            _, _, split_info = overflow_drafts[0]
            return CreateNaimenovanjaUserMessage(
                level="warning",
                title="ASYCUDA limit — 99 naimenovanja",
                message=(
                    "ASYCUDA World u BiH podržava najviše 99 naimenovanja po deklaraciji.\n\n"
                    f"Ukupno je formirano {split_info.total_count} naimenovanja.\n"
                    f"Trenutna deklaracija je ograničena na prvih {split_info.current_count}.\n"
                    f"Preostalih {split_info.overflow_count} naimenovanja je pripremljeno za sljedeću deklaraciju.\n\n"
                    "Završite i izvezite ovu deklaraciju, pa će aplikacija ponuditi nastavak sa ostatkom."
                ),
            )
        if len(display_results) > 1:
            lines = "\n".join(
                f"  • {group_label(getattr(draft, '_country_group', ''), getattr(draft, '_currency_group', ''))}: {count} naimenovanja"
                for draft, count, _ in display_results
            )
            return CreateNaimenovanjaUserMessage(
                title="Uspjeh!",
                message=(
                    f"✅ Kreirano naimenovanja za {len(display_results)} deklaracije:\n\n"
                    f"{lines}\n\n"
                    "Koristite navigator ◀ ▶ za pregled svake deklaracije."
                ),
            )

        _, count, _ = display_results[0]
        return CreateNaimenovanjaUserMessage(
            title="Uspjeh!",
            message=(
                f"✅ Kreirano {count} naimenovanja iz {all_lines_count} stavki!\n\n"
                "Naimenovanja su grupisana po tarifi, zemlji porijekla i povlastici.\n\n"
                "Možete ih pregledati i editovati u tabu 'Naimenovanja'."
            ),
        )

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
