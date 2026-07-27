"""
Test za importers/incoterm_utils.py (2026-07-26).

Korisnički zahtjev: parser mora prepoznati paritet isporuke (Incoterms
2020: EXW, FCA, FAS, FOB, CFR, CIF, CPT, CIP, DAP, DPU, DDP) sa fakture i
popuniti Rb.20 "Uslovi isporuke". Pošto je paritet pravno obavezan podatak
u postupku carinjenja, detekcija je NAMJERNO konzervativna: samo uz jednu
od poznatih oznaka (label + kod), nikad samostalna pretraga koda bez
konteksta — lažan pozitiv je gori od praznog polja.
"""
from __future__ import annotations

import pytest

from importers.incoterm_utils import detect_incoterm, VALID_INCOTERM_CODES


def test_svih_11_sifri_su_validne():
    assert VALID_INCOTERM_CODES == {
        "EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP",
    }


@pytest.mark.parametrize("text,expected", [
    ("Incoterms 2020: CPT", "CPT"),
    ("Incoterms: FCA", "FCA"),
    ("INCOTERM DDP", "DDP"),
    ("Paritet isporuke: FCA", "FCA"),  # Master Frigo formulacija
    ("paritetu: CPT", "CPT"),  # KG Fashion formulacija (bez "isporuke")
    ("Isporuka po paritetu isporuke: EXW", "EXW"),
    ("Uslovi isporuke: DAP", "DAP"),
    ("Delivery terms: EXW", "EXW"),
    ("Delivery term FOB", "FOB"),
    ("Termin isporuke: CIF", "CIF"),
])
def test_prepoznaje_uobicajene_formulacije(text: str, expected: str):
    assert detect_incoterm(text) == expected


def test_studija_slucaja_puna_faktura_sa_vise_linija():
    text = (
        "INVOICE No. 123/2026\n"
        "Datum: 15.07.2026\n"
        "Uslovi isporuke: CPT Sarajevo\n"
        "Ukupno: 1500.00 EUR\n"
    )
    assert detect_incoterm(text) == "CPT"


def test_prazan_string_vraca_prazno():
    assert detect_incoterm("") == ""


def test_bez_poznate_oznake_vraca_prazno():
    # "CPT" se pojavljuje ali BEZ konteksta/oznake — namjerno se ne hvata
    assert detect_incoterm("Roba: CPT model 500, boja crna") == ""


def test_oznaka_prisutna_ali_kod_nije_validan_vraca_prazno():
    assert detect_incoterm("Paritet isporuke: XYZ") == ""


def test_case_insensitive():
    assert detect_incoterm("incoterms 2020: cpt") == "CPT"
