"""
Plan Validator — Faza 7.

Provjerava da li je AgentPlan validan prije izvršenja:
- svi alati su poznati (whitelist)
- ToolPolicy dozvoljava effect
- preconditions su zadovoljene
- nema MUTATE koraka bez confirmation gate
"""

from __future__ import annotations

from services.agent.planning.agent_plan import AgentPlan, PlanStep
from services.agent.chat.tool_policy import is_known_tool, effect_for


def validate_plan(plan: AgentPlan) -> list[str]:
    """Validiraj plan. Vraća listu grešaka (prazna = validno)."""
    errors: list[str] = []

    if not plan.steps:
        errors.append("Plan nema definisane korake")
        return errors

    step_ids = {s.id for s in plan.steps}

    for step in plan.steps:
        # 1. Alat je poznat
        if not is_known_tool(step.tool):
            errors.append(f"Korak '{step.id}': nepoznat alat '{step.tool}'")

        # 2. Effect je dozvoljen
        expected = effect_for(step.tool)
        if expected is None:
            errors.append(f"Korak '{step.id}': alat '{step.tool}' nije u TOOL_EFFECTS")

        # 3. Preconditions reference stvarne korake
        for pre in step.preconditions:
            if pre not in step_ids:
                errors.append(f"Korak '{step.id}': precondition '{pre}' ne postoji u planu")

        # 4. MUTATE koraci moraju imati confirmation gate
        if step.effect == "MUTATE" and not step.requires_confirmation:
            errors.append(f"Korak '{step.id}': MUTATE efekt zahtijeva requires_confirmation=True")

    return errors


def build_workflow_plan(goal: str) -> AgentPlan:
    """Sastavi plan za poznate workflow ciljeve."""
    from services.agent.planning.agent_plan import KANONSKI_WORKFLOW
    plan = AgentPlan(goal=goal, steps=list(KANONSKI_WORKFLOW))
    errs = validate_plan(plan)
    if errs:
        plan.status = "failed"
    return plan
