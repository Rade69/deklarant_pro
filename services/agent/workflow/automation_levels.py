"""
Nivoi automatizacije i korisničke kapije — Faza 8.

Plan §19: 3 režima (Asistirani, Kontrolisana automatizacija, Priprema do XML-a).
Obavezne ljudske kapije za sva tri režima.
"""

from __future__ import annotations

from enum import Enum


class AutomationLevel(str, Enum):
    ASSISTED = "assisted"           # Sve analize automatske, svaka mutacija traži potvrdu
    CONTROLLED = "controlled"       # Bezbjedne tehničke operacije automatske, carinski rizične traže potvrdu
    PREPARE_TO_XML = "prepare"      # Workflow vodi cijeli proces, obavezne ljudske kapije ostaju


# Kapije koje zahtijevaju eksplicitnu ljudsku potvrdu u SVA tri režima
REQUIRED_HUMAN_GATES = frozenset({
    "unconfirmed_tariff",      # Nepouzdana ili konfliktna tarifa
    "unconfirmed_origin",      # Porijeklo bez potvrđenog dokaza
    "unconfirmed_preference",  # PE1/PE2/PE3 i EUR.1 povlastica
    "severe_value_mismatch",   # Ozbiljan mismatch vrijednosti/mase
    "readiness_warning",       # Readiness warning koji politika označi za obavezni review
    "final_xml_export",        # Finalni XML izvoz — uvijek traži potvrdu
})


def requires_human_confirmation(gate_name: str, level: AutomationLevel = AutomationLevel.ASSISTED) -> bool:
    """Da li data kapija zahtijeva ljudsku potvrdu na datom nivou automatizacije?

    U ASSISTED režimu SVAKA mutacija traži potvrdu (ne samo navedene kapije).
    U CONTROLLED i PREPARE_TO_XML, samo kapije iz REQUIRED_HUMAN_GATES.
    """
    if level == AutomationLevel.ASSISTED:
        return True  # Sve mutacije traže potvrdu
    return gate_name in REQUIRED_HUMAN_GATES
