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


def _pdf_line(povlastica="", eur1_number="", has_origin_statement=False,
              country_confidence="", country_source="", country_conflict_details="") -> InvoiceLine:
    """Stavka kao iz PDF fakture, opciono sa POTVRDJENIM dokazom.

    country_confidence/country_source ovdje simuliraju ono sto stvarno
    postavlja _apply_grouped_origin_data() (services/import_workflow/
    apply_service.py:217-223) nakon EUR.1/PE2/PE3 dijaloga - "HIGH" +
    izvor ("EUR1_POTVRDA"/"PDF_IZJAVA"), NIKAD prazno kad je dialog_data
    primijenjen.
    """
    return InvoiceLine(
        line_no=1, naziv_robe="Test", tarifni_broj="84186900",
        zemlja_porijekla="IT", povlastica=povlastica,
        eur1_number=eur1_number, has_origin_statement=has_origin_statement,
        country_confidence=country_confidence, country_source=country_source,
        country_conflict_details=country_conflict_details,
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


class TestCountryConfidencePropagacija:
    """Bug prijavljen 2026-08-02: povlastica/eur1_number su se ispravno
    prepisivali (prva popravka), ali country_confidence NIJE - pa
    ValidationService.country_confidence_style() (Faza 5 pravilo) vraca
    None (nema stila/kvacice) jer 'if not item.country_confidence: return
    None' - CAK I KAD je povlastica stvarno potvrdjena dokazom."""

    def test_country_confidence_se_prepisuje_sa_potvrdjenim_dokazom(self):
        master = _master_item(povlastica="EUP")
        pdf_line = _pdf_line(
            povlastica="EUP", eur1_number="EUR1-1",
            country_confidence="HIGH", country_source="EUR1_POTVRDA",
        )

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.country_confidence == "HIGH"
        assert master.invoice_line.country_source == "EUR1_POTVRDA"

    def test_bez_dokaza_country_confidence_master_liste_ostaje_netaknut(self):
        """Master-liste stavka NIKAD nema country_confidence (Excel ga ne
        postavlja) - bez dokaza ostaje prazan, kao i do sad."""
        master = _master_item(povlastica="EUP")
        pdf_line = _pdf_line(povlastica="CEFTAP")  # bez eur1/izjave

        master.update_from_invoice(pdf_line, "INV-1")

        assert master.invoice_line.country_confidence == ""

    def test_kompletan_scenario_povlastica_i_confidence_zajedno_potvrdjeni(self):
        """End-to-end provjera cijelog lanca koji je korisnik vidio u GUI-ju:
        nakon EUR.1 potvrde, i povlastica I country_confidence moraju biti
        postavljeni - to je jedini nacin da ValidationService.
        country_confidence_style() vrati checkmark."""
        from services.faktura.validation_service import ValidationService

        master = _master_item(povlastica="EUP")  # neconfirmed Excel guess
        pdf_line = _pdf_line(
            povlastica="EUP", eur1_number="EUR1-99",
            country_confidence="HIGH", country_source="EUR1_POTVRDA",
        )

        master.update_from_invoice(pdf_line, "INV-1")

        style = ValidationService.country_confidence_style(master.invoice_line)
        assert style is not None
        assert style["icon"] == "✅"
