"""
Tool Policy — klasifikacija efekta poznatih agent alata.

Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §5

Registry je namjerno whitelist (eksplicitan popis) — alat koji nije u
TOOL_EFFECTS je NEPOZNAT i nikad se ne izvršava (fail-closed), bez obzira
da li ga LLM Tool Use ili regex fallback prepoznaju kao ime.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class ToolEffect(str, Enum):
    """
    READ_ONLY — čita/prikazuje, izvršava se odmah bez potvrde.
    PROPOSE   — računa/prikazuje prijedlog (npr. proposal karticu ili
                pending action), ali sam poziv ne mijenja draft.
    MUTATE    — mijenja draft; uvijek mora proći kroz eksplicitnu potvrdu
                korisnika prije nego se izmjena primijeni.
    """
    READ_ONLY = "read_only"
    PROPOSE = "propose"
    MUTATE = "mutate"


# Mora ostati usklađen sa services/agent/chat/tool_definitions.py:TOOLS —
# vidi tests/unit/test_tool_policy.py::test_svaki_definisani_alat_ima_effect
TOOL_EFFECTS: dict[str, ToolEffect] = {
    # ── Nova parametrizovana imena (Faza 1 konsolidacija) ──
    "prikazi": ToolEffect.READ_ONLY,
    "provjeri": ToolEffect.READ_ONLY,
    "pretrazi_tarifu": ToolEffect.READ_ONLY,
    "pretrazi_porijeklo": ToolEffect.READ_ONLY,
    "pretrazi_stavke": ToolEffect.READ_ONLY,
    "agregiraj_stavke": ToolEffect.READ_ONLY,
    "filtriraj_stavke": ToolEffect.READ_ONLY,
    "pronadji_slicne_proizvode": ToolEffect.READ_ONLY,
    "analiziraj_tarifne": ToolEffect.READ_ONLY,
    "predlozi_tarife": ToolEffect.PROPOSE,
    "spoji_naimenovanja": ToolEffect.PROPOSE,
    "upisi_u_kolonu": ToolEffect.MUTATE,
    # ── Stara imena (aliasi) — zadržana radi kompatibilnosti ──
    "pregled_stanja_aplikacije": ToolEffect.READ_ONLY,
    "prikazi_naimenovanja": ToolEffect.READ_ONLY,
    "provjeri_naimenovanja": ToolEffect.READ_ONLY,
    "provjeri_tarife": ToolEffect.READ_ONLY,
    "validuj_deklaraciju": ToolEffect.READ_ONLY,
    # ── Workflow alati (Faza 7) ──
    "kalkulisi_mase": ToolEffect.READ_ONLY,
    "kreiraj_naimenovanja": ToolEffect.MUTATE,
    "izvezi_xml": ToolEffect.MUTATE,
}


def effect_for(tool_name: str) -> Optional[ToolEffect]:
    """Vrati ToolEffect za poznat alat, ili None za nepoznat (fail-closed)."""
    return TOOL_EFFECTS.get(tool_name)


def is_known_tool(tool_name: str) -> bool:
    return tool_name in TOOL_EFFECTS
