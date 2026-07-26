"""
Poslovno stanje deklaracije — kapije (gates), ne enum (Faza 7).

Plan §7.5: modelovati kao kapije koje se izvode iz stvarnog drafta,
ne kao fiksna lista stanja. Svaka kapija je provjera koja vraća prolaz/blokadu.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeclarationGate:
    """Jedna kapija u workflow-u."""
    name: str
    passed: bool = False
    reason: str = ""  # zašto nije prošla (ako nije)


@dataclass
class DeclarationWorkflowState:
    """Trenutno stanje deklaracionog procesa — izvedeno iz drafta."""
    draft_revision: int = 0
    gates: list[DeclarationGate] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def blocked_gates(self) -> list[DeclarationGate]:
        return [g for g in self.gates if not g.passed]

    @staticmethod
    def from_draft(draft) -> DeclarationWorkflowState:
        """Izvedi poslovno stanje iz stvarnog drafta."""
        state = DeclarationWorkflowState(draft_revision=getattr(draft, "revision", 0))
        has_inv = bool(getattr(draft, "invoice_lines", []))
        has_items = bool(getattr(draft, "items", []))
        has_header = bool(getattr(draft, "deklaracija_tip", ""))

        state.gates = [
            DeclarationGate("files_imported", passed=has_inv,
                           reason="" if has_inv else "Nema uvezenih faktura"),
            DeclarationGate("items_created", passed=has_items,
                           reason="" if has_items else "Naimenovanja nisu kreirana"),
            DeclarationGate("header_filled", passed=has_header,
                           reason="" if has_header else "Zaglavlje nije popunjeno"),
        ]
        return state


def compute_state_from_draft(draft) -> DeclarationWorkflowState:
    """Izračunaj trenutno stanje iz drafta — jedan izvor istine."""
    return DeclarationWorkflowState.from_draft(draft)
