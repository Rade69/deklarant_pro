"""
AgentContextAdapter — jedina tačka kroz koju draft podaci postaju
AgentSafeContext, sa maskiranjem partner imena na JEDNOM mjestu.

Faza 1 iz project_rooms/2026-07-25_agent-safe-input-schema-plan.md.
Trenutno nekorišten od strane ChatWorker-a (Faza 2 migrira Zone B/B2 da
koriste ovo umjesto ručnog "if send_sensitive:" po polju u svakoj zoni —
tačno taj obrazac je uzrokovao propust popravljen u §61/commit 223d543).
"""
from __future__ import annotations

from services.agent.chat.safe_context_schema import (
    AttachedDocument,
    DeclarationHeaderSummary,
    DraftSummary,
    PartnerInfo,
)


class AgentContextAdapter:
    def __init__(self, draft, allow_sensitive: bool):
        self.draft = draft
        self.allow_sensitive = allow_sensitive

    def build_partner_info(self) -> list[PartnerInfo]:
        pairs = [
            ("izvoznik", getattr(self.draft, "izvoznik_naziv", "") or ""),
            ("primalac", getattr(self.draft, "primalac_naziv", "") or ""),
            ("deklarant", getattr(self.draft, "deklarant_naziv", "") or ""),
        ]
        result = []
        for role, name in pairs:
            if not name:
                continue
            result.append(PartnerInfo(
                role=role,
                name=name if self.allow_sensitive else None,
                masked=not self.allow_sensitive,
            ))
        return result

    @staticmethod
    def build_draft_summary(invoice_lines: list) -> DraftSummary:
        bez_tarife = sum(1 for l in invoice_lines if not getattr(l, "tarifni_broj", None))
        bez_zemlje = sum(1 for l in invoice_lines if not getattr(l, "zemlja_porijekla", None))
        sa_povlasticom = sum(1 for l in invoice_lines if getattr(l, "povlastica", None))
        ceka_eur1 = sum(
            1 for l in invoice_lines
            if getattr(l, "povlastica", None)
            and not getattr(l, "has_origin_statement", False)
            and not getattr(l, "eur1_number", None)
        )
        zemlja_distribucija: dict[str, int] = {}
        for l in invoice_lines:
            c = getattr(l, "zemlja_porijekla", None) or "(nepoznato)"
            zemlja_distribucija[c] = zemlja_distribucija.get(c, 0) + 1

        return DraftSummary(
            total_items=len(invoice_lines),
            bez_tarife=bez_tarife,
            bez_zemlje=bez_zemlje,
            sa_povlasticom=sa_povlasticom,
            ceka_eur1=ceka_eur1,
            zemlja_distribucija=zemlja_distribucija,
        )

    def build_header(self) -> DeclarationHeaderSummary | None:
        d = self.draft
        if not d:
            return None

        vrsta = f"{getattr(d,'deklaracija_tip','')} {getattr(d,'deklaracija_oznaka','')} {getattr(d,'deklaracija_a','')}".strip()
        troskovi = []
        for i, attr in enumerate(["trosak_1", "trosak_2", "trosak_3", "trosak_4", "trosak_5"], 1):
            v = getattr(d, attr, "0,00") or "0,00"
            if v not in ("0,00", "0", "", "0.00"):
                troskovi.append(f"T{i}={v}")

        prilozene_isprave = [
            AttachedDocument(name=getattr(doc, "name", "") or "", number=getattr(doc, "number", "") or "")
            for doc in (getattr(d, "header_attached_documents", []) or [])
        ]

        return DeclarationHeaderSummary(
            vrsta_deklaracije=vrsta,
            carinska_ispostava=getattr(d, "ured_odredista", "") or "",
            valuta=getattr(d, "valuta", "") or "",
            iznos=getattr(d, "iznos", 0.0) or 0.0,
            kurs=getattr(d, "kurs", 1.0) or 1.0,
            uslovi_isporuke=f"{getattr(d,'uslovi_kod','')} {getattr(d,'uslovi_mjesto','')}".strip(),
            vid_transporta=f"unutra={getattr(d,'vid_unutra','') or '?'} granica={getattr(d,'vid_granica','') or '?'}",
            drzava_izvoza=getattr(d, "drzava_izvoza_naziv", "") or getattr(d, "drzava_izvoza_sifra", "") or "",
            troskovi=troskovi,
            prilozene_isprave=prilozene_isprave,
        )
