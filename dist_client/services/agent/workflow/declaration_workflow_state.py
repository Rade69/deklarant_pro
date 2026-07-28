"""
Poslovno stanje deklaracije — kapije (gates), ne enum (Faza 7).

Plan §7.5: modelovati kao kapije koje se izvode iz stvarnog drafta,
ne kao fiksna lista stanja. Svaka kapija je provjera koja vraća prolaz/blokadu.

Prije popravke (2026-07-27) kapije su bile plitke provjere tipa "lista nije
prazna" i nisu pozivale nijedan review servis iz Faza 3-6 — items_created i
header_filled su bile jedine dvije poslovne kapije. Sada svaka kapija koja
ima odgovarajući review servis (Faza 3-6) poziva ga, i kapija prolazi samo
ako servis vrati ready=True (nema blokirajućih nalaza) — ne samo "podaci
postoje". Vidi agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Redoslijed kapija = redoslijed provjere (plan §7.5, 10 kapija)
GATE_ORDER = (
    "files_imported", "invoice_validated", "tariffs_resolved",
    "origin_confirmed", "masses_calculated", "items_created",
    "items_validated", "header_ready", "cross_check_passed",
    "xml_preflight_passed",
)


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
        return bool(self.gates) and all(g.passed for g in self.gates)

    @property
    def blocked_gates(self) -> list[DeclarationGate]:
        return [g for g in self.gates if not g.passed]

    def gate(self, name: str) -> DeclarationGate | None:
        return next((g for g in self.gates if g.name == name), None)

    @staticmethod
    def from_draft(draft) -> "DeclarationWorkflowState":
        """Izvedi poslovno stanje iz stvarnog drafta — poziva stvarne review servise.

        Kapije se procjenjuju redoslijedom iz GATE_ORDER; kad ranija strukturna
        kapija (files_imported, items_created) ne prođe, kasnije kapije koje
        zavise od tih podataka se ne pokušavaju (nema smisla validirati
        naimenovanja koja ne postoje).
        """
        state = DeclarationWorkflowState(draft_revision=getattr(draft, "revision", 0))
        gates: list[DeclarationGate] = []

        invoice_lines = list(getattr(draft, "invoice_lines", []) or [])
        items = list(getattr(draft, "items", []) or [])

        has_inv = bool(invoice_lines)
        gates.append(DeclarationGate(
            "files_imported", passed=has_inv,
            reason="" if has_inv else "Nema uvezenih faktura",
        ))
        if not has_inv:
            state.gates = gates
            return state

        gates.append(_run_summary_gate(
            "invoice_validated", draft,
            "services.agent.validation.invoice_review_service", "provjeri_fakturu",
            "blokirajućih nalaza u fakturi",
        ))

        bez_tarife = sum(1 for l in invoice_lines if not getattr(l, "tarifni_broj", None))
        gates.append(DeclarationGate(
            "tariffs_resolved", passed=bez_tarife == 0,
            reason="" if bez_tarife == 0 else f"{bez_tarife} stavki bez tarifnog broja",
        ))

        bez_zemlje = sum(1 for l in invoice_lines if not getattr(l, "zemlja_porijekla", None))
        gates.append(DeclarationGate(
            "origin_confirmed", passed=bez_zemlje == 0,
            reason="" if bez_zemlje == 0 else f"{bez_zemlje} stavki bez zemlje porijekla",
        ))

        bez_mase = sum(
            1 for l in invoice_lines
            if not getattr(l, "bruto_kg", None) or not getattr(l, "neto_kg", None)
        )
        gates.append(DeclarationGate(
            "masses_calculated", passed=bez_mase == 0,
            reason="" if bez_mase == 0 else f"{bez_mase} stavki bez izračunate mase",
        ))

        # NE provjeravati samo bool(items) — draft.items može sadržati
        # ZASTARJELA naimenovanja iz vraćene/prekinute prethodne sesije
        # (session restore) koja nemaju veze sa TRENUTNIM invoice_lines.
        # bool(items)==True bi tada lažno "prošao" ovu kapiju i preskočio
        # _puna_auto_pipeline (koja bi inače pozvala create_smart_group() i
        # ispravno prvo obrisala stara items), pa bi items_validated kapija
        # dole provjeravala stare, nepovezane naimenovanje umjesto stvarnih —
        # korisnička primjedba 2026-07-27/28 ("agent ne okida aktivnost kad
        # klikne Provjeri/Kreiraj Naimenovanja, samo nastavlja i udara u
        # zid"). Ispravan uslov: SVAKA invoice_lines stavka mora imati
        # assigned_naimenovanje_id koji pokazuje na POSTOJEĆI item.
        item_ids = {getattr(it, "item_id", None) for it in items}
        unmapped = sum(
            1 for l in invoice_lines
            if not getattr(l, "assigned_naimenovanje_id", None)
            or getattr(l, "assigned_naimenovanje_id", None) not in item_ids
        )
        has_items = bool(items) and unmapped == 0
        gates.append(DeclarationGate(
            "items_created", passed=has_items,
            reason="" if has_items else (
                "Naimenovanja nisu kreirana" if not items
                else f"{unmapped} stavki nije povezano sa trenutnim naimenovanjima (moguće zastarjela iz prethodne sesije)"
            ),
        ))
        if not has_items:
            state.gates = gates
            return state

        gates.append(_run_summary_gate(
            "items_validated", draft,
            "services.agent.validation.items_review_service", "provjeri_naimenovanja",
            "blokirajućih nalaza u naimenovanjima",
        ))
        gates.append(_run_summary_gate(
            "header_ready", draft,
            "services.agent.validation.header_review_service", "provjeri_zaglavlje",
            "blokirajućih nalaza u zaglavlju",
        ))
        gates.append(_run_summary_gate(
            "cross_check_passed", draft,
            "services.agent.validation.header_review_service", "provjeri_usklađenost_tabova",
            "međutabnih neusklađenosti",
        ))
        gates.append(_run_readiness_gate(draft))

        state.gates = gates
        return state


def _run_summary_gate(name: str, draft, module: str, func: str, opis: str) -> DeclarationGate:
    """Pozovi review servis koji vraća ValidationSummary i pretvori u kapiju."""
    try:
        import importlib
        mod = importlib.import_module(module)
        summary = getattr(mod, func)(draft)
        reason = "" if summary.ready else f"{summary.blocking_count} {opis}"
        return DeclarationGate(name, passed=summary.ready, reason=reason)
    except Exception as e:
        return DeclarationGate(name, passed=False, reason=f"Provjera nije izvršena: {e}")


def _run_readiness_gate(draft) -> DeclarationGate:
    try:
        from services.agent.validation.xml_readiness_service import provjeri_spremnost_za_xml
        result = provjeri_spremnost_za_xml(draft)
        reason = "" if result.is_ready else f"{result.blocking_count} blokada prije XML izvoza"
        return DeclarationGate("xml_preflight_passed", passed=result.is_ready, reason=reason)
    except Exception as e:
        return DeclarationGate("xml_preflight_passed", passed=False, reason=f"Provjera nije izvršena: {e}")


def compute_state_from_draft(draft) -> DeclarationWorkflowState:
    """Izračunaj trenutno stanje iz drafta — jedan izvor istine."""
    return DeclarationWorkflowState.from_draft(draft)
