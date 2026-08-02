"""
Karakterizacioni testovi za AssemblyItem.update_from_invoice() prioritet
povlastice — Faza "Assembly EUR.1 dialog parity" (2026-08-02,
project_rooms/2026-08-02_assembly-eur1-dialog-parity.md).

Korisnicka odluka: Assembly/master-list uvoz mora raditi identicno kao
Agent mod - povlastica POTVRDJENA PE1/PE2/PE3 dokazom (EUR.1 dijalog)
mora UVIJEK nadjacati "predlog" iz master-liste Excel "preferential"
kolone (koji nema nikakav dokaz, samo pretpostavku po zemlji).

Bez dokaza (dialog_type == NONE, npr. stavka bez zemlje porijekla),
staro ponasanje ostaje: master lista pobjedjuje ako vec ima povlasticu.
"""
from core.draft import InvoiceLine
from services.naimenovanja.declaration_assembly import AssemblyItem


def _master_item(povlastica="", zemlja="IT") -> AssemblyItem:
    """Stavka kao iz master liste Excel-a - ima povlasticu BEZ dokaza."""
    line = InvoiceLine(
        line_no=1, naziv_robe="Test", tarifni_broj="84186900",
        zemlja_porijekla=zemlja, povlastica=povlastica,
        kolicina=1.0, jm="kom",
    )
    item = AssemblyItem(invoice_line=line, source_master=True)
    item._check_completeness()
    return item


def _pdf_line(povlastica="", eur1_number="", has_origin_statement=False) -> InvoiceLine:
    """Stavka kao iz PDF fakture, opciono sa POTVRDJENIM dokazom."""
    return InvoiceLine(
        line_no=1, naziv_robe="Test", tarifni_broj="84186900",
        zemlja_porijekla="IT", povlastica=povlastica,
        eur1_number=eur1_number, has_origin_statement=has_origin_statement,
        cijena_jed=10.0, kolicina=1.0, jm="kom",
    )


class TestBezDokaza_StaroPonasanjeOstajeIsto:
    def test_master_lista_pobjedjuje_ako_vec_ima_povlasticu(self):
        master = _master_item(povlastica="EUP")
        pdf_line = _pdf_line(povlastica="CEFTAP")  # bez eur1/izjave

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.povlastica == "EUP"  # master lista pobjedjuje

    def test_pdf_popunjava_prazno_polje_master_liste(self):
        master = _master_item(povlastica="")
        pdf_line = _pdf_line(povlastica="EUP")

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.povlastica == "EUP"


class TestSaDokazom_PotvrdaUvijekPobjedjuje:
    def test_eur1_broj_nadjacava_master_listu(self):
        master = _master_item(povlastica="EUP")
        pdf_line = _pdf_line(povlastica="EUP", eur1_number="EUR1-12345")

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.povlastica == "EUP"
        assert master.invoice_line.eur1_number == "EUR1-12345"

    def test_has_origin_statement_nadjacava_master_listu(self):
        master = _master_item(povlastica="EUP")
        pdf_line = _pdf_line(povlastica="EUP", has_origin_statement=True)

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.has_origin_statement is True

    def test_potvrdjena_drugacija_povlastica_stvarno_prepisuje_master_listu(self):
        """Kljucan slucaj: master lista je pogodila POGRESNO (CEFTAP), PDF
        dokaz potvrdjuje EUP - dokaz mora pobijediti, ne masking."""
        master = _master_item(povlastica="CEFTAP")
        pdf_line = _pdf_line(povlastica="EUP", eur1_number="EUR1-1")

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.povlastica == "EUP"

    def test_dokaz_bez_povlastice_ne_brise_postojecu_povlasticu(self):
        """Ako je PE dijalog potvrdjen ali povlastica polje prazno (edge
        case), ne smije obrisati vec postojecu vrijednost."""
        master = _master_item(povlastica="EUP")
        pdf_line = _pdf_line(povlastica="", eur1_number="EUR1-1")

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.povlastica == "EUP"
