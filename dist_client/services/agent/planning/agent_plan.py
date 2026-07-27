"""
AgentPlan i PlanStep modeli — Faza 7.

Plan §7.7 (v2.1): strukturisan plan za višekoračne workflow ciljeve.
LLM rezultat nikada nije direktno izvršiv dok PlanValidator ne potvrdi.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlanStep:
    """Jedan korak u planu — poziv servisa/alata."""
    id: str
    tool: str                      # ime alata (npr. "provjeri", "prikazi")
    arguments: dict = field(default_factory=dict)
    effect: str = "READ_ONLY"      # ToolEffect
    preconditions: tuple[str, ...] = ()  # id-jevi koraka koji moraju uspjeti prije
    success_condition: str = ""
    failure_policy: str = "BLOCK"  # BLOCK | WARN | SKIP
    requires_confirmation: bool = False


@dataclass
class AgentPlan:
    """Kompletan plan za izvršenje više alata."""
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "pending"         # pending | running | paused | completed | failed | cancelled

    @property
    def current_step_obj(self) -> PlanStep | None:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    @property
    def is_done(self) -> bool:
        return self.status in ("completed", "failed", "cancelled")

    def advance(self) -> None:
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
        else:
            self.status = "completed"


# Kanonski workflow do XML-a (plan §18)
KANONSKI_WORKFLOW = [
    PlanStep(id="validate_invoice", tool="provjeri", arguments={"target": "invoice"},
             effect="READ_ONLY", success_condition="invoice_validated"),
    PlanStep(id="resolve_tariffs", tool="predlozi_tarife", arguments={},
             effect="PROPOSE", requires_confirmation=True),
    PlanStep(id="calculate_masses", tool="kalkulisi_mase", arguments={},
             effect="READ_ONLY"),
    PlanStep(id="create_items", tool="kreiraj_naimenovanja", arguments={},
             effect="MUTATE", requires_confirmation=True),
    PlanStep(id="validate_items", tool="provjeri", arguments={"target": "items"},
             effect="READ_ONLY"),
    PlanStep(id="validate_header", tool="provjeri", arguments={"target": "header"},
             effect="READ_ONLY"),
    PlanStep(id="cross_check", tool="provjeri", arguments={"target": "cross_tab"},
             effect="READ_ONLY"),
    PlanStep(id="xml_preflight", tool="provjeri", arguments={"target": "xml"},
             effect="READ_ONLY"),
    PlanStep(id="export_xml", tool="izvezi_xml", arguments={},
             effect="MUTATE", requires_confirmation=True),
]
