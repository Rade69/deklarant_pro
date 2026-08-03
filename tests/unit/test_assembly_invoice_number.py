"""
Karakterizacioni test za AssemblyItem.update_from_invoice() — bug prijavljen
2026-08-02 (korisnik, GUI screenshot): kolona "Faktura" ostaje prazna za
SVE stavke u master-list/Assembly uvozu, iako je cijena/kolicina uspjesno
uparena sa 4 fakture (status bar "100% (4 faktura)").

Uzrok: update_from_invoice() kopira cijena_jed/iznos/kolicina/valuta/
tarifni_broj/zemlja_porijekla/naziv_robe/bruto_kg/neto_kg/jm/povlasticu iz
fakturne linije u master-list stavku, ali NIKAD invoice_number - za razliku
od "obicnog" (non-Assembly) rucnog uvoza gdje apply_service.py:144 i
faktura_view.py:2766 invoice_number redovno postavljaju.
"""
from core.draft import InvoiceLine
from services.naimenovanja.declaration_assembly import AssemblyItem


def _master_item() -> AssemblyItem:
    line = InvoiceLine(
        line_no=1, naziv_robe="", tarifni_broj="", zemlja_porijekla="",
        kolicina=1.0, jm="kom",
    )
    item = AssemblyItem(invoice_line=line, source_master=True)
    item._check_completeness()
    return item


def _pdf_line() -> InvoiceLine:
    return InvoiceLine(
        line_no=1, naziv_robe="Grejac spirala", tarifni_broj="85168020",
        zemlja_porijekla="IT", cijena_jed=10.0, kolicina=1.0, jm="kom",
    )


def test_invoice_number_se_upisuje_kad_faktura_donese_cijenu():
    master = _master_item()
    pdf_line = _pdf_line()

    master.update_from_invoice(pdf_line, "INV-2026-001")

    assert master.invoice_line.invoice_number == "INV-2026-001"


def test_invoice_number_se_ne_dira_ako_faktura_ne_donese_cijenu():
    """Prazna cijena = faktura nije stvarno uparena sa ovom stavkom -
    invoice_number ostaje prazan, isto kao ostala polja (cijena/iznos)."""
    master = _master_item()
    pdf_line = InvoiceLine(line_no=1, naziv_robe="X", cijena_jed=0.0, kolicina=1.0, jm="kom")

    master.update_from_invoice(pdf_line, "INV-2026-002")

    assert master.invoice_line.invoice_number == ""


def test_invoice_number_iz_druge_facture_ne_prepisuje_prvu_bez_nove_cijene():
    """source_invoice prati POSLJEDNJU fakturu koja je donijela cijenu -
    invoice_number mora pratiti isti obrazac kao source_invoice (istorijski
    dokazano ponasanje za cijena_jed/iznos, vidi liniju iznad)."""
    master = _master_item()
    master.update_from_invoice(_pdf_line(), "INV-A")
    assert master.invoice_line.invoice_number == "INV-A"

    no_price = InvoiceLine(line_no=1, naziv_robe="X", cijena_jed=0.0, kolicina=1.0, jm="kom")
    master.update_from_invoice(no_price, "INV-B")
    assert master.invoice_line.invoice_number == "INV-A"
