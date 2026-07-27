"""
Testovi za services/agent/chat/tool_policy.py — Faza A sigurnosna kapija.

Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §5
"""
from __future__ import annotations

from services.agent.chat.tool_policy import ToolEffect, effect_for, is_known_tool, TOOL_EFFECTS


def test_nepoznat_alat_vraca_none_fail_closed():
    assert effect_for("nepostojeci_alat_xyz") is None
    assert is_known_tool("nepostojeci_alat_xyz") is False


def test_upisi_u_kolonu_je_mutate():
    assert effect_for("upisi_u_kolonu") is ToolEffect.MUTATE


def test_read_only_alati_su_ispravno_klasifikovani():
    read_only_alati = [
        "pregled_stanja_aplikacije", "provjeri_tarife", "pretrazi_tarifu",
        "pretrazi_porijeklo", "validuj_deklaraciju", "prikazi_naimenovanja",
        "provjeri_naimenovanja", "analiziraj_tarifne", "pronadji_slicne_proizvode",
    ]
    for naziv in read_only_alati:
        assert effect_for(naziv) is ToolEffect.READ_ONLY, f"{naziv} bi trebao biti READ_ONLY"


def test_propose_alati_su_ispravno_klasifikovani():
    for naziv in ("predlozi_tarife", "spoji_naimenovanja"):
        assert effect_for(naziv) is ToolEffect.PROPOSE, f"{naziv} bi trebao biti PROPOSE"


def test_registry_ne_sadrzi_prazna_imena():
    assert "" not in TOOL_EFFECTS
    for naziv in TOOL_EFFECTS:
        assert naziv.strip() == naziv and naziv, "Ime alata ne smije biti prazno/sa razmacima"


def test_svaki_efekat_je_toolEffect_instanca():
    for naziv, effect in TOOL_EFFECTS.items():
        assert isinstance(effect, ToolEffect), f"{naziv}: efekat mora biti ToolEffect enum"


def test_imena_alata_su_ascii():
    """Plan §8.3 pravilo 1: imena alata moraju biti ^[a-z0-9_]{1,64}$.
    Groq/OpenAI function-name schema odbacuje non-ASCII karaktere."""
    import re
    pattern = re.compile(r'^[a-z0-9_]{1,64}$')
    from services.agent.chat.tool_definitions import TOOLS
    for t in TOOLS:
        name = t["function"]["name"]
        assert pattern.match(name), (
            f"Ime alata '{name}' nije ASCII. "
            f"Dozvoljeno: ^[a-z0-9_]{{1,64}}$"
        )
