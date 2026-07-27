from pathlib import Path

import pytest

from services.import_service import ImportService

_FIXTURE_DIR = Path("najavauvoza/blagic-attos")

# Ovi testovi zavise od stvarnih ATTOS faktura koje su privatni podaci van repoa.
# Kad fixture fajlovi nisu prisutni (druga mašina, CI), preskoči umjesto pada.
pytestmark = pytest.mark.skipif(
    not _FIXTURE_DIR.exists(),
    reason="Blagić-Attos fixture fakture nisu dostupne (privatni podaci van repoa)",
)


@pytest.mark.parametrize(
    "invoice_glob, expected_bruto, expected_neto",
    [
        ("Faktura 720*.pdf", 124.26, 112.9),
        ("Faktura 721*.pdf", 1125.295, 1090.005),
        ("Faktura 722*.pdf", 47.01, 42.45),
    ],
)
def test_blagic_attos_bruto_neto_excludes_pallet_weight(
    invoice_glob, expected_bruto, expected_neto
):
    """
    ATTOS dodaje paušalnu težinu EUR palete (~20kg) u finalni "Bruto:" red
    dokumenta, koji se razlikuje od zbira bruto/neto po stavkama iz liste
    pakovanja. Za deklaraciju je relevantan zbir po stavkama (bez palete) —
    vidi agent_reports/2026-07-04_blagic-attos-tezina-palete-fix.md
    """
    faktura = next(_FIXTURE_DIR.glob(invoice_glob))

    svc = ImportService()
    result = svc.import_file(str(faktura))

    assert result.is_combined is True
    assert result.bruto_kg == pytest.approx(expected_bruto, abs=0.01)
    assert result.neto_kg == pytest.approx(expected_neto, abs=0.01)
