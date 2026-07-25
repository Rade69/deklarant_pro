# tests/integration/test_real_invoice_import_e2e.py

"""
End-to-end integracioni testovi jedinstvenog import workflow-a sa STVARNIM
fakturama (parser -> ImportCandidate -> ImportPlan -> apply_import_plan).

Fakture sadrže stvarne poslovne podatke i NISU u repozitorijumu — testovi se
graciozno PRESKAČU ako arhiva nije dostupna (H:\\New folder\\najavauvoza ili
korisnički Downloads). Očekivane vrijednosti su iz zbirnog sažetka štampanog
na svakoj fakturi (zlatni standard).

Pokretanje sa eksplicitnom putanjom:
    DEKLARANT_INVOICE_DIR="D:\\fakture" python -m pytest tests/integration/test_real_invoice_import_e2e.py -v

Pokriva scenarije koje su import-workflow izvještaji označili kao "potrebna
ručna potvrda":
  1. Jedan uvoz — ispravne stavke/težine/iznos/izvoznik (Master Frigo, Medicopharm).
  2. Ponovni uvoz iste fakture — REPLACE, ne duplikat.
  3. Različit izvoznik — konflikt partnera se detektuje (ne miješa se tiho).
  4. Kombinovani uvoz (faktura + packing lista) — consumed_paths, bez duplikata.
  5. Per-item PE izjava porijekla po rasponima ("1-3; 5-41; ...").
  6. Ista 8-cifrena tarifa iz više zemalja — tačna zemlja po stavci.
"""

import os
from pathlib import Path

import pytest

from services.import_service import ImportService
from services.import_workflow.adapters import from_import_result
from services.import_workflow.prepare_service import prepare_import
from services.import_workflow.apply_service import apply_import_plan
from services.import_workflow.decision_models import (
    UserDecisions,
    InvoiceDecision,
    OriginDialogResponse,
    OriginDialogResolution,
)
from core.draft.draft import DeclarationDraft
from importers.import_result import ImportResult


# ── Lociranje arhive faktura ──────────────────────────────────────────────────

_CANDIDATE_DIRS = [
    os.environ.get("DEKLARANT_INVOICE_DIR", ""),
    r"H:\New folder\najavauvoza",
    str(Path.home() / "Downloads"),
]


def _find(*names: str) -> Path | None:
    """Vrati prvu putanju gdje SVI navedeni fajlovi postoje (isti folder)."""
    for base in _CANDIDATE_DIRS:
        if not base:
            continue
        d = Path(base)
        if all((d / n).exists() for n in names):
            return d
    return None


_MASTER = "R2503394 (16.12.2025.) (E)-MASTER FRIGO, BANJA LUKA (60 DANA)-22.813,00 EUR.pdf"
_PIP = "PIP92.pdf"
_SRECKO_INV = "SRECKO- faktura.pdf"
_SRECKO_PACK = "SRECKO-pack-lista.pdf"
_MEDICO = "1476 BIH.pdf"


# ── Pomoćnici ─────────────────────────────────────────────────────────────────

def _decisions_skip_origin(plan) -> UserDecisions:
    """Simuliraj korisnika: primijeni sve fakture, svaki PE/EUR1 dijalog = SKIPPED."""
    ud = UserDecisions()
    for invoice_key, dialog_type in plan.origin_dialogs_needed:
        ud.invoice_decisions[invoice_key] = InvoiceDecision(
            invoice_key=invoice_key,
            apply=True,
            origin_response=OriginDialogResponse(
                invoice_key=invoice_key,
                dialog_type=dialog_type,
                resolution=OriginDialogResolution.SKIPPED,
            ),
        )
    return ud


def _existing_invoice_keys(draft: DeclarationDraft) -> set[str]:
    """Isti izvor ključeva kao GUI (FakturaView._existing_invoice_keys_for_import_workflow):
    invoice_weights ključevi + normalizovan invoice_number sa svake stavke."""
    from services.faktura.weight_guards import normalize_invoice_key

    keys = set(getattr(draft, "invoice_weights", {}) or {})
    for line in draft.invoice_lines or []:
        key = normalize_invoice_key(getattr(line, "invoice_number", "") or "")
        if key:
            keys.add(key)
    return keys


def _apply(res: ImportResult, source: str, draft: DeclarationDraft):
    cand = from_import_result(res, source_path=source)
    plan = prepare_import(
        [cand],
        existing_invoice_keys=_existing_invoice_keys(draft),
        expected_exporter=draft.izvoznik_naziv or "",
    )
    result = apply_import_plan(draft, plan, _decisions_skip_origin(plan))
    return plan, result


# ── Master Frigo: jedan uvoz + REPLACE ───────────────────────────────────────

@pytest.mark.skipif(_find(_MASTER) is None, reason="Master Frigo faktura nije dostupna")
def test_master_frigo_single_import_and_replace():
    d = _find(_MASTER)
    f = str(d / _MASTER)

    draft = DeclarationDraft()
    res1 = ImportService().import_file(f)
    assert isinstance(res1, ImportResult)
    assert len(res1.items) == 51

    _, r1 = _apply(res1, f, draft)
    assert r1.success, r1.errors
    n1 = len(draft.invoice_lines)
    iz1 = round(sum((l.iznos or 0) for l in draft.invoice_lines), 2)
    assert n1 == 51
    assert iz1 == 22813.00                       # poklapa se sa imenom fajla
    assert draft.izvoznik_naziv == "MASTER FRIGO"

    # Ponovni uvoz iste fakture -> REPLACE, ne duplikat.
    res2 = ImportService().import_file(f)
    _, r2 = _apply(res2, f, draft)
    assert r2.success, r2.errors
    assert len(draft.invoice_lines) == n1        # nije udvostruceno
    assert round(sum((l.iznos or 0) for l in draft.invoice_lines), 2) == iz1


# ── Konflikt partnera (različit izvoznik) ────────────────────────────────────

@pytest.mark.skipif(_find(_PIP) is None, reason="PIP faktura nije dostupna")
def test_different_exporter_triggers_partner_conflict():
    d = _find(_PIP)
    f = str(d / _PIP)
    res = ImportService().import_file(f)
    cand = from_import_result(res, source_path=f)
    # Draft "već ima" MASTER FRIGO kao izvoznika:
    plan = prepare_import([cand], existing_invoice_keys=set(), expected_exporter="MASTER FRIGO")
    assert len(plan.partner_conflicts) >= 1
    pc = plan.partner_conflicts[0]
    assert pc.field_name == "exporter"
    assert pc.expected == "MASTER FRIGO"
    assert "PIP" in pc.actual.upper()


# ── Kombinovani uvoz (faktura + packing) ─────────────────────────────────────

@pytest.mark.skipif(_find(_SRECKO_INV, _SRECKO_PACK) is None, reason="SRECKO par nije dostupan")
def test_combined_invoice_plus_packing_sets_consumed_paths():
    d = _find(_SRECKO_INV, _SRECKO_PACK)
    svc = ImportService()
    r_inv = svc.import_file(str(d / _SRECKO_INV))
    assert isinstance(r_inv, ImportResult)
    n_inv = len(r_inv.items)

    r_comb = svc.import_file(str(d / _SRECKO_PACK))
    assert isinstance(r_comb, ImportResult)
    assert r_comb.is_combined
    assert r_comb.consumed_paths                 # faktura označena kao potrošena
    # Kombinovanje ne duplira stavke (isti broj kao sama faktura).
    assert len(r_comb.items) == n_inv


# ── Medicopharm 1476: najzahtjevniji format ──────────────────────────────────

@pytest.mark.skipif(_find(_MEDICO) is None, reason="Medicopharm 1476 faktura nije dostupna")
class TestMedicopharm1476:
    """94 stavke, per-item PE izjava po rasponima, ista tarifa iz više zemalja."""

    @pytest.fixture(scope="class")
    def result(self) -> ImportResult:
        d = _find(_MEDICO)
        res = ImportService().import_file(str(d / _MEDICO))
        assert isinstance(res, ImportResult)
        return res

    def test_totals_match_invoice_summary(self, result):
        assert len(result.items) == 94
        assert round(sum((it.iznos or 0) for it in result.items), 2) == 22662.72
        assert result.bruto_kg == 310.0          # "BRUTO TEŽINA: 310KG"
        assert result.neto_kg == 284.94          # zbirni sažetak "Total 284.94"
        assert result.invoice_name == "1476/26"
        assert "MEDICO PHARM" in (getattr(result.exporter, "name", "") or "").upper()

    def test_per_item_preferential_origin_ranges(self, result):
        # Faktura: "Ova izjava se odnosi na stavke: 1-3; 5-41; 43-51; 53-85; 87;88; 92-94"
        # Komplement (BEZ PE) su tačno: 4, 42, 52, 86, 89, 90, 91.
        without_pe = [
            i + 1 for i, it in enumerate(result.items)
            if not getattr(it, "has_origin_statement", False)
        ]
        assert without_pe == [4, 42, 52, 86, 89, 90, 91]

    def test_same_tariff_different_countries_split_correctly(self, result):
        from collections import defaultdict
        g: dict = defaultdict(float)
        for it in result.items:
            t8 = (it.tarifni_broj or "")[:8]
            g[(t8, it.zemlja_porijekla or "?")] += it.kolicina or 0

        # Ista 8-cifrena tarifa iz više zemalja — količine po zemlji iz sažetka fakture:
        assert g[("21069098", "PT")] == 20      # 21069098/9080 PORTUGAL
        assert g[("21069098", "PL")] == 132     # 210690989080 POLJSKA
        assert g[("33049900", "FR")] == 1302    # 1182+10+10+100
        assert g[("33049900", "DE")] == 1003    # 248+755
        assert g[("33049900", "GB")] == 18      # 330499000080 VELIKA BRITANIJA
        assert g[("33059000", "FR")] == 10
        assert g[("33059000", "US")] == 10      # 3305900000 SJEDINJENE AM.

    def test_full_workflow_apply_preserves_totals(self, result):
        d = _find(_MEDICO)
        draft = DeclarationDraft()
        _, r = _apply(result, str(d / _MEDICO), draft)
        assert r.success, r.errors
        assert len(draft.invoice_lines) == 94
        assert round(sum((l.iznos or 0) for l in draft.invoice_lines), 2) == 22662.72
        assert round(sum((l.bruto_kg or 0) for l in draft.invoice_lines), 2) == 310.0
        assert round(sum((l.neto_kg or 0) for l in draft.invoice_lines), 2) == 284.94
