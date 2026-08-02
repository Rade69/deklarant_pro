# tests/integration/test_assembly_master_list_import_e2e.py

"""
End-to-end test Assembly/master-list uvoz puta (DeclarationAssembly.add_invoice)
sa STVARNIM fakturama — popunjava rupu koju je PROBE za Fazu 6 identifikovao
(project_rooms/2026-08-02_faza6-probe-legacy-uvoz-status.md): unified put ima
test_real_invoice_import_e2e.py, Assembly put do sad nije imao ekvivalent.

Fakture i master lista sadrže stvarne poslovne podatke i NISU u repozitorijumu
— test se graciozno PRESKAČE ako arhiva nije dostupna (H:\\New folder\\najavauvoza
ili DEKLARANT_INVOICE_DIR).

Ovo je isti scenario koji je korisnik ručno testirao u GUI-ju 2026-08-02
("Učitaj glavnu listu" sa Podela po poreklu.xlsx, zatim pojedinačni PDF uvoz)
— test dokazuje da FakturaView._finish_import_legacy_path-ova Assembly grana
(services/naimenovanja/declaration_assembly.py, NETAKNUTO u Fazi 6) i
services/faktura/legacy_import_service.py (IZDVOJENO u Fazi 6) rade ispravno
sa stvarnim podacima, bez GUI-ja.
"""

import os
from pathlib import Path

import pytest

from services.import_service import ImportService
from services.naimenovanja.declaration_assembly import DeclarationAssembly
from services.faktura.legacy_import_service import build_assembly_match_message
from importers.import_result import ImportResult


_CANDIDATE_DIRS = [
    os.environ.get("DEKLARANT_INVOICE_DIR", ""),
    r"H:\New folder\najavauvoza",
    str(Path.home() / "Downloads"),
]

_MASTER_LIST = "Podela po poreklu.xlsx 18,12,2025.xlsx"
_INV_2503393 = "R2503393 (16.12.2025.) (E)-MASTER FRIGO, BANJA LUKA  (AVANSNO)-23.503,15 EUR.pdf"
_INV_2503394 = "R2503394 (16.12.2025.) (E)-MASTER FRIGO, BANJA LUKA (60 DANA)-22.813,00 EUR.pdf"


def _find(*names: str) -> Path | None:
    for base in _CANDIDATE_DIRS:
        if not base:
            continue
        d = Path(base)
        if all((d / n).exists() for n in names):
            return d
    return None


@pytest.mark.skipif(
    _find(_MASTER_LIST, _INV_2503393, _INV_2503394) is None,
    reason="Master lista/fakture nisu dostupne",
)
class TestAssemblyMasterListRealImport:
    """Master lista (88 stavki, IT/EUP dobavljač) + dvije stvarne fakture
    istog dobavljača (Master Frigo) — isti scenario kao GUI screenshot
    2026-08-02."""

    @pytest.fixture(scope="class")
    def base_dir(self) -> Path:
        return _find(_MASTER_LIST, _INV_2503393, _INV_2503394)

    @pytest.fixture()
    def assembly(self, base_dir) -> DeclarationAssembly:
        a = DeclarationAssembly()
        count = a.load_master_list(str(base_dir / _MASTER_LIST))
        assert count == 88
        return a

    def test_master_list_loaded_all_incomplete_before_any_invoice(self, assembly):
        status = assembly.get_completion_status()
        assert status["total"] == 88
        assert status["complete"] == 0
        assert status["completion_percentage"] == 0
        assert status["imported_invoices_count"] == 0

    def test_single_invoice_matches_against_master_list(self, assembly, base_dir):
        res = ImportService().import_file(str(base_dir / _INV_2503393))
        assert isinstance(res, ImportResult)

        matched, unmatched, unmatched_names = assembly.add_invoice(res.items, "2503393")

        assert matched == len(res.items)
        assert unmatched == 0
        assert unmatched_names == []

        status = assembly.get_completion_status()
        assert status["complete"] == matched
        assert status["imported_invoices_count"] == 1
        assert status["imported_invoices"] == ["2503393"]

    def test_two_invoices_accumulate_without_losing_first_matches(self, assembly, base_dir):
        res1 = ImportService().import_file(str(base_dir / _INV_2503393))
        m1, u1, _ = assembly.add_invoice(res1.items, "2503393")

        res2 = ImportService().import_file(str(base_dir / _INV_2503394))
        m2, u2, _ = assembly.add_invoice(res2.items, "2503394")

        status = assembly.get_completion_status()
        assert status["imported_invoices_count"] == 2
        assert status["imported_invoices"] == ["2503393", "2503394"]
        # Prva faktura ostaje matched i nakon druge (ne prepisuje se).
        assert status["complete"] >= m1
        assert status["complete"] >= m2

    def test_create_draft_after_matching_preserves_master_list_order(self, assembly, base_dir):
        res = ImportService().import_file(str(base_dir / _INV_2503393))
        assembly.add_invoice(res.items, "2503393")

        draft = assembly.create_draft()
        assert len(draft.invoice_lines) == 88  # cijela master lista, ne samo matched

    def test_faza6_message_builder_renders_sensibly_with_real_data(self, assembly, base_dir):
        """Direktna provjera services/faktura/legacy_import_service.py
        (Faza 6 ekstrakcija) protiv STVARNIH matched/unmatched/status
        vrijednosti — ne samo sintetičkih test fixture-a."""
        res = ImportService().import_file(str(base_dir / _INV_2503393))
        matched, unmatched, _ = assembly.add_invoice(res.items, "2503393")
        status = assembly.get_completion_status()

        message = build_assembly_match_message(
            "2503393", matched, unmatched, res.bruto_kg or 0.0, res.neto_kg or 0.0, status,
        )

        assert "2503393" in message
        assert f"Matched: {matched} stavki" in message
        assert f"Unmatched: {unmatched} stavki" in message
        assert f"Ukupno stavki: {status['total']}" in message
        # Sa stvarnim podacima (0 unmatched) upozorenje o crvenoj boji se NE prikazuje.
        if unmatched == 0:
            assert "CRVENOM bojom" not in message
