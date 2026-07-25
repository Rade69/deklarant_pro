"""
AgentSafeContext — validirana struktura koja opisuje šta smije proći
prema agentu/LLM-u.

Faza 1 iz project_rooms/2026-07-25_agent-safe-input-schema-plan.md — novi,
izolovani fajl, ne mijenja postojeći ChatWorker (Faza 2 migrira Zone B/B2
da koriste AgentContextAdapter, vidi context_adapter.py).

PartnerInfo.name je None ako je maskirano — masking se radi PRIJE
popunjavanja modela (u AgentContextAdapter), model nikad ne nosi i puno
ime i masku istovremeno.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DraftSummary(BaseModel):
    total_items: int = Field(ge=0)
    bez_tarife: int = Field(ge=0)
    bez_zemlje: int = Field(ge=0)
    sa_povlasticom: int = Field(ge=0)
    ceka_eur1: int = Field(ge=0)
    zemlja_distribucija: dict[str, int] = {}


class PartnerInfo(BaseModel):
    role: str  # "izvoznik" | "primalac" | "deklarant"
    name: str | None = None
    masked: bool = False


class AttachedDocument(BaseModel):
    """Rb.44 priložene isprave — brojevi dokumenata nisu osjetljivi
    (korisnička potvrda 2026-07-25), ne maskira se."""
    name: str = ""
    number: str = ""


class DeclarationHeaderSummary(BaseModel):
    vrsta_deklaracije: str = ""
    carinska_ispostava: str = ""
    valuta: str = ""
    iznos: float = 0.0
    kurs: float = 1.0
    uslovi_isporuke: str = ""
    vid_transporta: str = ""
    drzava_izvoza: str = ""
    troskovi: list[str] = []
    prilozene_isprave: list[AttachedDocument] = []


class AgentSafeContext(BaseModel):
    draft_summary: DraftSummary
    partners: list[PartnerInfo] = []
    header: DeclarationHeaderSummary | None = None
    # knowledge/tariff_val/declarations zone ostaju slobodan tekst u Fazi 1 —
    # vidi plan §6 Faza 5 za eventualnu daljnju strukturizaciju.
    knowledge_context: list[str] = []
    tariff_validation_context: list[str] = []
    declarations_context: list[str] = []
