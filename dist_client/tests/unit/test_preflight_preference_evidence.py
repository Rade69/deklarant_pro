from core.draft.draft import InvoiceLine
from gui.dialogs.preflight_naimenovanja_dialog import analyse_preflight


def test_preflight_ne_trazi_eur1_kad_je_pe2_potvrdjen():
    line = InvoiceLine(
        tarifni_broj="33051000",
        naziv_robe="Sampon",
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
        has_origin_statement=True,
        eur1_number="108VP-2026",
    )

    result = analyse_preflight([line])

    assert result.povlastica_bez_eur1 == []


def test_preflight_upozorava_kad_povlastica_nema_pe_dokaz():
    line = InvoiceLine(
        tarifni_broj="33051000",
        naziv_robe="Sampon",
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
        has_origin_statement=False,
        eur1_number="",
    )

    result = analyse_preflight([line])

    assert len(result.povlastica_bez_eur1) == 1
    assert "bez PE1/PE2/PE3 dokaza" in result.povlastica_bez_eur1[0].problem
