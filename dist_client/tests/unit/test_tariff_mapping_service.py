"""
Testovi za TariffMappingService dry_run/commit_proposals (Fix Set A,
project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md).

Ključni regresioni test: preview (dry_run=True) i stvarni upis
(commit_proposals) MORAJU dati IDENTIČAN rezultat — prije ovog fix-a,
preview (suggest_fast, bez dobavljača) i upis (auto_populate_tariffs, sa
dobavljačem i istorijom) su bila dva nezavisna proračuna koja su se mogla
razići.

NAPOMENA o mockovanju: `find_mapping()`/`HybridMatchingService` su mockovani
na nivou METODE (ne DB konekcije) da se izoluje NOVA dry_run/commit_proposals
kontrolna logika. Ovo NIJE "mock za SQLite/PostgreSQL" (AGENTS.md zabrana) —
SQL korektnost find_mapping() je pokrivena zasebnim, DB-backed
karakterizacionim testovima (test_decision_characterization.py).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.draft.draft import InvoiceLine, Party
from services.tariff.tariff_mapping_service import (
    MappingResult,
    TariffMapping,
    TariffMappingService,
    TariffProposal,
)


def _line(line_no: int, naziv: str, tarifni_broj: str = "") -> InvoiceLine:
    return InvoiceLine(
        line_no=line_no,
        naziv_robe=naziv,
        product_code="",
        tarifni_broj=tarifni_broj,
        zemlja_porijekla="",
        exporter=Party(name="MEDICOPHARM"),
    )


def _mapping(tarifni_broj: str = "84149000", similarity: float = 0.95) -> TariffMapping:
    return TariffMapping(
        product_code="",
        naziv_robe="Neka roba",
        tarifni_broj=tarifni_broj,
        precision_1="000",
        zemlja_porijekla="",
        povlastica="",
        usage_count=5,
        similarity=similarity,
    )


@pytest.fixture
def service():
    return TariffMappingService()


def test_dry_run_ne_upisuje_u_liniju(service):
    """dry_run=True MORA vratiti proposals bez ijedne mutacije invoice_lines."""
    line = _line(1, "GREJAC KVARCNI 1000W")

    with patch.object(service, "find_mapping", return_value=_mapping()) as mock_find:
        result = service.auto_populate_tariffs([line], dry_run=True)

    assert line.tarifni_broj == ""  # NIJE upisano
    assert result.matched_items == 1
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.line_no == 1
    assert proposal.tarifni_broj == "84149000"
    assert proposal.source == "baza_znanja"
    mock_find.assert_called_once()


def test_dry_run_koristi_min_similarity_092_default(service):
    """Projektni kanon (AGENTS.md) — fuzzy prag ne smije ostati na 0.70."""
    line = _line(1, "GREJAC KVARCNI 1000W")

    with patch.object(service, "find_mapping", return_value=None) as mock_find:
        service.auto_populate_tariffs([line], dry_run=True)

    _, kwargs = mock_find.call_args
    assert kwargs["min_similarity"] == 0.92


def test_preview_i_commit_proposals_daju_isti_tarifni_broj(service):
    """
    Regresioni test za glavni bug: ono što je izračunato u preview-u (dry_run)
    MORA biti tačno ono što commit_proposals stvarno upiše — bez ponovnog
    računanja koje bi moglo dati drugačiji rezultat.
    """
    line = _line(5, "PINCETA RAVNA 8CM")
    mapping = _mapping(tarifni_broj="82032000", similarity=0.93)

    with patch.object(service, "find_mapping", return_value=mapping):
        preview = service.auto_populate_tariffs([line], dry_run=True)

    assert line.tarifni_broj == ""  # preview nije upisao ništa

    # Simuliraj da find_mapping sad vraća NEŠTO DRUGO (npr. baza se promijenila
    # između preview-a i potvrde) — commit_proposals NE SMIJE ponovo pitati
    # find_mapping, mora upisati baš ono iz preview-a.
    with patch.object(service, "find_mapping", return_value=_mapping(tarifni_broj="99999999")) as mock_find:
        result = service.commit_proposals([line], preview.proposals)

    mock_find.assert_not_called()  # commit_proposals se NE oslanja na find_mapping
    assert line.tarifni_broj == "82032000"  # baš ono iz preview-a, ne "99999999"
    assert result.matched_items == 1


def test_commit_proposals_preskace_stavke_bez_proposala(service):
    """Linija koja nije u proposals listi (npr. već imala tarifu) ostaje netaknuta."""
    line1 = _line(1, "STAVKA A")
    line2 = _line(2, "STAVKA B", tarifni_broj="11112222")  # već ima tarifu, nema proposal

    proposal = TariffProposal(
        line_no=1,
        naziv_ili_kod="STAVKA A",
        tarifni_broj="33334444",
        precision_1="000",
        source="baza_znanja",
        confidence=0.95,
        mapping=_mapping(tarifni_broj="33334444"),
    )

    result = service.commit_proposals([line1, line2], [proposal])

    assert line1.tarifni_broj == "33334444"
    assert line2.tarifni_broj == "11112222"  # netaknuto
    assert result.matched_items == 1


def test_commit_proposals_ne_kolidira_po_line_no_kroz_vise_faktura(service):
    """
    Regresioni test za Codex nalaz #2: svaki importer numeriše line_no od 1
    PO FAKTURI, pa dvije stavke iz različitih faktura mogu imati isti
    line_no. Kad se auto-popuni pokrene nad cijelim draft.invoice_lines
    (npr. "Auto-popuni" bez selekcije), by_line_no bi kolizijom prepisao
    prijedlog za prvu stavku prijedlogom za drugu — commit_proposals MORA
    upisati tačno onu tarifu koja je izračunata ZA TU stavku (po poziciji),
    ne po (neispravno pretpostavljenom jedinstvenom) line_no.
    """
    # Dvije "fakture" u istom draftu, obje počinju numeraciju od 1.
    faktura1_l1 = _line(1, "PINCETA RAVNA 8CM")
    faktura2_l1 = _line(1, "GREJAC KVARCNI 1000W")
    target_lines = [faktura1_l1, faktura2_l1]

    mapping1 = _mapping(tarifni_broj="82032000", similarity=0.95)
    mapping2 = _mapping(tarifni_broj="85167990", similarity=0.95)

    with patch.object(service, "find_mapping", side_effect=[mapping1, mapping2]):
        preview = service.auto_populate_tariffs(target_lines, dry_run=True)

    assert len(preview.proposals) == 2
    assert faktura1_l1.tarifni_broj == ""  # dry_run ne upisuje
    assert faktura2_l1.tarifni_broj == ""

    with patch.object(service, "find_mapping") as mock_find:
        result = service.commit_proposals(target_lines, preview.proposals)

    mock_find.assert_not_called()
    assert faktura1_l1.tarifni_broj == "82032000"  # ispravan prijedlog za PRVU stavku
    assert faktura2_l1.tarifni_broj == "85167990"  # ispravan prijedlog za DRUGU stavku
    assert result.matched_items == 2


def test_dry_run_ne_povecava_usage_count(service):
    """usage_count se ne smije inkrementirati na preview — samo na stvaran upis."""
    line = _line(1, "GREJAC KVARCNI 1000W")

    with patch.object(service, "find_mapping", return_value=_mapping()), \
         patch.object(service, "_increment_usage") as mock_incr:
        service.auto_populate_tariffs([line], dry_run=True)

    mock_incr.assert_not_called()

    with patch.object(service, "find_mapping", return_value=_mapping()), \
         patch.object(service, "_increment_usage") as mock_incr:
        service.auto_populate_tariffs([line], dry_run=False)

    mock_incr.assert_called_once()


def test_bez_mappinga_dry_run_ne_dira_country_confidence(service):
    """Ako nema mapiranja, dry_run NE SMIJE mijenjati country_confidence (mutacija)."""
    line = _line(1, "NEPOZNAT PROIZVOD XYZ")
    line.zemlja_porijekla = "RS"

    with patch.object(service, "find_mapping", return_value=None):
        result = service.auto_populate_tariffs([line], dry_run=True)

    assert line.country_confidence == ""  # netaknuto
    assert result.unmatched_items == 1
