"""
Testovi za services/agent/chat/draft_aggregation_service.py.

Reprodukuju konkretne upite iz docs/agent/AGENT_TOOL_COVERAGE_AUDIT.md — upiti gdje je
LLM ranije morao sam da racuna/filtrira iz sirovog teksta (ista klasa greske kao SUSSINA
bug, agent_reports/2026-08-05_agent-pretraga-stavki-po-nazivu.md).
"""
from core.draft.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
from services.agent.chat.draft_aggregation_service import agregiraj, filtriraj


def _draft_sa_naimenovanjima():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1", ordinal_no=1, tariff_code="94054000",
            origin_country_code="RS", item_value=100.0, gross_mass_kg=50.0,
        ),
        NaimenovanjeDraft(
            item_id="2", ordinal_no=2, tariff_code="94054000",
            origin_country_code="DE", item_value=200.0, gross_mass_kg=245.3,
        ),
        NaimenovanjeDraft(
            item_id="3", ordinal_no=3, tariff_code="84019000",
            origin_country_code="", item_value=50.0, gross_mass_kg=10.0,
        ),
    ]
    return draft


def test_agregiraj_sum_sa_filterom_po_tarifi():
    """Reprodukcija upita #1: 'ukupna vrijednost svih stavki sa tarifom 94054000'."""
    draft = _draft_sa_naimenovanjima()
    rezultat = agregiraj(
        draft, "sum", "vrijednost", target="items",
        uslovi=[{"polje": "tarifa", "operator": "=", "vrijednost": "94054000"}],
    )
    assert rezultat["rezultat"] == 300.0
    assert rezultat["broj_stavki"] == 2
    # Reprodukcija korisnikovog nalaza: SUM mora vratiti I listu stavki, ne samo broj
    assert {e["row"].ordinal_no for e in rezultat["stavke"]} == {1, 2}


def test_agregiraj_max_top_n():
    """Reprodukcija upita #2/#12: 'koja stavka ima najveću bruto masu' / 'top 3'."""
    draft = _draft_sa_naimenovanjima()
    rezultat = agregiraj(draft, "max", "bruto_masa", target="items", top_n=2)
    assert rezultat["broj_stavki"] == 3
    assert [e["vrijednost"] for e in rezultat["top"]] == [245.3, 50.0]
    assert rezultat["top"][0]["row"].ordinal_no == 2


def test_agregiraj_count_bez_polja():
    draft = _draft_sa_naimenovanjima()
    rezultat = agregiraj(draft, "count", target="items")
    assert rezultat["broj"] == 3


def test_agregiraj_avg():
    draft = _draft_sa_naimenovanjima()
    rezultat = agregiraj(draft, "avg", "vrijednost", target="items")
    assert round(rezultat["rezultat"], 2) == round((100.0 + 200.0 + 50.0) / 3, 2)


def test_agregiraj_nepoznato_polje_vraca_error_ne_exception():
    draft = _draft_sa_naimenovanjima()
    rezultat = agregiraj(draft, "sum", "nepostojece_polje", target="items")
    assert "error" in rezultat


def test_filtriraj_prazno_operator():
    """Reprodukcija upita #7 (dio): 'koje stavke nemaju zemlju porijekla'."""
    draft = _draft_sa_naimenovanjima()
    rezultat = filtriraj(
        draft, target="items",
        uslovi=[{"polje": "zemlja", "operator": "prazno"}],
    )
    assert rezultat["broj"] == 1
    assert rezultat["rows"][0].ordinal_no == 3


def test_filtriraj_grupisanje_po_tarifi():
    """Reprodukcija upita #14: 'da li se neki tarifni broj ponavlja u više naimenovanja'."""
    draft = _draft_sa_naimenovanjima()
    rezultat = filtriraj(draft, target="items", grupisi_po="tarifa")
    assert rezultat["grupe"]["94054000"].__len__() == 2
    assert rezultat["grupe"]["84019000"].__len__() == 1


def test_filtriraj_invoice_lines_kombinovani_uslovi():
    """Reprodukcija upita #7 (puna verzija): 'koliko fakturnih linija nema ni tarifu ni zemlju'."""
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(line_no=1, naziv_robe="A", tarifni_broj="", zemlja_porijekla=""),
        InvoiceLine(line_no=2, naziv_robe="B", tarifni_broj="12345678", zemlja_porijekla=""),
        InvoiceLine(line_no=3, naziv_robe="C", tarifni_broj="", zemlja_porijekla="RS"),
    ]
    rezultat = filtriraj(
        draft, target="invoice",
        uslovi=[
            {"polje": "tarifa", "operator": "prazno"},
            {"polje": "zemlja", "operator": "prazno"},
        ],
    )
    assert rezultat["broj"] == 1
    assert rezultat["rows"][0].line_no == 1


def test_agregiraj_bez_stavki_vraca_none_ne_baca_gresku():
    draft = DeclarationDraft()
    rezultat = agregiraj(draft, "sum", "vrijednost", target="items")
    assert rezultat["rezultat"] is None
    assert rezultat["broj_stavki"] == 0


def _draft_faktura_bez_naimenovanja():
    """Stanje odmah nakon uvoza fakture — invoice_lines postoje, items (naimenovanja)
    jos nisu kreirana. Reprodukuje stvaran bug: korisnik pitao 'Pronadji mi sve
    proizvode bez tarifnog broja' dok je Faktura status bedz pokazivao '19 bez
    tarife' (invoice_lines nivo); agent je (target default 'items') odgovorio
    '1 naimenovanje' jer draft.items tada prakticno ne postoji."""
    draft = DeclarationDraft()
    draft.items = []
    draft.invoice_lines = [
        InvoiceLine(line_no=i, naziv_robe=f"Roba {i}", tarifni_broj="", zemlja_porijekla="RS")
        for i in range(1, 20)
    ]
    draft.invoice_lines.append(
        InvoiceLine(line_no=20, naziv_robe="Roba 20", tarifni_broj="12345678", zemlja_porijekla="RS")
    )
    return draft


def test_filtriraj_bez_eksplicitnog_targeta_prebacuje_na_invoice_kad_su_items_prazni():
    """Reprodukcija prijavljenog bug-a: target nije naveden, items prazan → invoice."""
    draft = _draft_faktura_bez_naimenovanja()
    rezultat = filtriraj(
        draft, uslovi=[{"polje": "tarifa", "operator": "prazno"}],
    )
    assert rezultat["target"] == "invoice"
    assert rezultat["broj"] == 19
    assert "napomena" in rezultat


def test_filtriraj_prebacuje_i_kad_je_target_eksplicitno_items_a_prazan():
    """LLM-ov izbor target parametra NIJE pouzdan signal stvarne namjere
    korisnika (potvrdjeno uzivo: LLM salje target='items' bez obzira na
    SYSTEM_PROMPT uputstvo da ga izostavi kad naimenovanja jos ne postoje).
    Zato se fallback aktivira i kad je target eksplicitno 'items', ako je
    prazan a invoice_lines ima podatke — nema legitimnog razloga da se
    vrati '0 naimenovanja' kad naimenovanja uopste ne postoje."""
    draft = _draft_faktura_bez_naimenovanja()
    rezultat = filtriraj(
        draft, target="items", uslovi=[{"polje": "tarifa", "operator": "prazno"}],
    )
    assert rezultat["target"] == "invoice"
    assert rezultat["broj"] == 19
    assert "napomena" in rezultat


def test_filtriraj_kad_su_oba_prazna_vraca_trazeni_target_bez_napomene():
    """Ako NEMA podataka ni u items ni u invoice, fallback nema kud da
    prebaci — vraca trazeni target sa praznim rezultatom, bez napomene
    (nema alternative koju bi ponudio)."""
    draft = DeclarationDraft()
    rezultat = filtriraj(
        draft, target="items", uslovi=[{"polje": "tarifa", "operator": "prazno"}],
    )
    assert rezultat["target"] == "items"
    assert rezultat["broj"] == 0
    assert "napomena" not in rezultat


def test_filtriraj_prebacuje_na_items_kad_je_target_invoice_a_invoice_prazan():
    """Simetrican slucaj: target='invoice' (eksplicitno ili default), ali
    invoice_lines je prazan dok items ima podatke — prebacuje na items."""
    draft = DeclarationDraft()
    draft.invoice_lines = []
    draft.items = _draft_sa_naimenovanjima().items
    rezultat = filtriraj(
        draft, target="invoice", uslovi=[{"polje": "zemlja", "operator": "prazno"}],
    )
    assert rezultat["target"] == "items"
    assert rezultat["broj"] == 1
    assert "napomena" in rezultat


def test_agregiraj_bez_eksplicitnog_targeta_prebacuje_na_invoice_kad_su_items_prazni():
    draft = _draft_faktura_bez_naimenovanja()
    rezultat = agregiraj(draft, "count", uslovi=[{"polje": "tarifa", "operator": "prazno"}])
    assert rezultat["target"] == "invoice"
    assert rezultat["broj"] == 19
    assert "napomena" in rezultat


def test_agregiraj_prebacuje_i_kad_je_target_eksplicitno_items_a_prazan():
    draft = _draft_faktura_bez_naimenovanja()
    rezultat = agregiraj(
        draft, "count", target="items", uslovi=[{"polje": "tarifa", "operator": "prazno"}],
    )
    assert rezultat["target"] == "invoice"
    assert rezultat["broj"] == 19
    assert "napomena" in rezultat


def test_resolve_target_kad_items_postoje_ostaje_items_bez_napomene():
    """Kad naimenovanja VEC postoje, default (bez eksplicitnog targeta) ostaje items,
    kao i ranije — fallback se aktivira SAMO kad je items prazan."""
    draft = _draft_sa_naimenovanjima()
    rezultat = filtriraj(draft, uslovi=[{"polje": "zemlja", "operator": "prazno"}])
    assert rezultat["target"] == "items"
    assert "napomena" not in rezultat
