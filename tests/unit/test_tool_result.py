from services.agent.chat.tool_result import (
    TOOL_RESULT_PROMPT_RULE,
    ToolResult,
    ToolResultStatus,
    render_tool_result_html,
)
from services.agent.chat.tool_policy import ToolEffect


def test_tool_result_unknown_ne_dozvoljava_llm_inferencu():
    result = ToolResult.unknown(
        "pretrazi_porijeklo",
        "Nema potvrđenog podatka o porijeklu.",
        "lokalni XML indeks",
    )

    assert result.status == ToolResultStatus.UNKNOWN
    assert result.can_llm_infer is False


def test_render_tool_result_prikazuje_status_i_izvor():
    result = ToolResult.needs_review(
        "upisi_u_kolonu",
        "Navedi kolonu i vrijednost za upis.",
        "lokalni tool router",
    )

    html = render_tool_result_html(result)

    assert "Navedi kolonu" in html
    assert "lokalni tool router" in html
    assert "needs_review" in html


def test_tool_result_prompt_rule_zabranjuje_promjenu_znacenja():
    assert "Ne mijenjaj status" in TOOL_RESULT_PROMPT_RULE
    assert "unknown ili needs_review" in TOOL_RESULT_PROMPT_RULE


def test_ok_klasa_metoda_postavlja_status_ok():
    result = ToolResult.ok("provjeri_tarife", "Sve tarife su ispravne.", "TariffValidator")

    assert result.status == ToolResultStatus.OK
    assert result.can_llm_infer is True


def test_default_faza_d_polja_su_neutralna():
    result = ToolResult.ok("provjeri_tarife", "poruka", "izvor")

    assert result.effect is None
    assert result.confirmation_required is False
    assert result.operation_id == ""


def test_effect_i_operation_id_se_mogu_postaviti_nakon_konstrukcije():
    result = ToolResult.needs_review("upisi_u_kolonu", "poruka", "izvor")
    result.effect = ToolEffect.MUTATE
    result.confirmation_required = True
    result.operation_id = "abc123"

    assert result.effect == ToolEffect.MUTATE
    assert result.confirmation_required is True
    assert result.operation_id == "abc123"
