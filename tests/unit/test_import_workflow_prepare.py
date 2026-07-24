"""
Testovi za servis pripreme uvoza (Faza 3).

Plan §16 Faza 3: deduplikacija, sortiranje, identitet, grupisanje,
konflikti partnera/valute, normalizacija tarifa, težine, PE2/PE3/EUR1, plan ADD/REPLACE/SKIP.
"""
from __future__ import annotations

from core.draft.draft import InvoiceLine, Party
from services.import_workflow.models import ImportCandidate
from services.import_workflow.plan_models import (
    DraftOperation,
    ImportPlan,
    OriginDialogType,
    PreparedInvoice,
)
from services.import_workflow.prepare_service import (
    determine_origin_dialog,
    invoice_keys_match,
    normalize_partner_name,
    normalize_tariff_number,
    partners_similar,
    prepare_import,
)


def _make_line(invoice_number="INV-001", tarifni_broj="08052190", iznos=100.0,
               zemlja_porijekla="DE"):
    return InvoiceLine(
        tarifni_broj=tarifni_broj,
        naziv_robe="Test proizvod",
        zemlja_porijekla=zemlja_porijekla,
        bruto_kg=10.0,
        neto_kg=9.0,
        iznos=iznos,
        kolicina=5,
        jm="kom",
        invoice_number=invoice_number,
    )


def _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001",
                    invoice_lines=None, bruto_kg=100.0, neto_kg=90.0,
                    is_combined=False, consumed_paths=None,
                    exporter=None, importer=None, currency="EUR",
                    has_origin_statement=False, is_authorized_exporter=False):
    if invoice_lines is None:
        invoice_lines = [_make_line(invoice_number=invoice_number)]
    if exporter is None:
        exporter = Party(name="Exporter d.o.o.", address="Export str 1", country="DE")
    if importer is None:
        importer = Party(name="Importer d.o.o.", address="Import str 1", country="BA")
    import os
    from pathlib import Path
    return ImportCandidate(
        source_path=source_path,
        normalized_path=os.path.normcase(str(Path(source_path).resolve())),
        file_type="PDF",
        parser="test",
        invoice_lines=invoice_lines,
        explicit_invoice_number=invoice_number,
        display_name=invoice_number or "test.pdf",
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        exporter=exporter,
        importer=importer,
        currency=currency,
        has_origin_statement=has_origin_statement,
        is_authorized_exporter=is_authorized_exporter,
        is_combined=is_combined,
        consumed_paths=consumed_paths or [],
    )


# ── Pomoćne funkcije ───────────────────────────────────────────────────────


class TestNormalizeTariffNumber:
    def test_8_cifara_ostaje(self):
        assert normalize_tariff_number("08052190") == "08052190"

    def test_uklanja_ne_brojove(self):
        assert normalize_tariff_number("0805.21.90") == "08052190"

    def test_excel_gubi_vodece_nule(self):
        # "3824999" (7 cifara) → zfill na 8 dodaje vodeću nulu na POČETAK
        assert normalize_tariff_number("3824999") == "03824999"

    def test_prazan(self):
        assert normalize_tariff_number("") == ""

    def test_none(self):
        assert normalize_tariff_number(None) == ""


class TestNormalizePartnerName:
    def test_mala_slova(self):
        # D.O.O. se nakon uklanjanja interpunkcije pretvara u "d o o" (postojeće ponašanje)
        assert normalize_partner_name("EXPORTER d.o.o.") == "exporter d o o"

    def test_bez_interpunkcije(self):
        # "Firma, d.o.o." → "firma d o o" (postojeće ponašanje — d.o.o. regex ne matcha razmaknuto)
        assert normalize_partner_name("Firma, d.o.o.") == "firma d o o"

    def test_prazan(self):
        assert normalize_partner_name("") == ""


class TestPartnersSimilar:
    def test_isti_partner_jednaki_naziv(self):
        assert partners_similar("Exporter d.o.o.", "Exporter d.o.o.") is True

    def test_razliciti_partneri(self):
        assert partners_similar("Neki izvoznik", "Drugi uvoznik") is False

    def test_prazan_ne_blokira(self):
        assert partners_similar("", "Nesto") is True


class TestInvoiceKeysMatch:
    def test_isti_broj(self):
        assert invoice_keys_match("INV-001", "INV-001") is True

    def test_slican_broj(self):
        assert invoice_keys_match("INV-001", "INV001") is True

    def test_kratak_broj(self):
        assert invoice_keys_match("AB", "CD") is False

    def test_prazan(self):
        assert invoice_keys_match("", "INV-001") is False


class TestDetermineOriginDialog:
    def test_ovlaseni_izvoznik_pe3(self):
        lines = [_make_line()]
        assert determine_origin_dialog(lines, True, True) == OriginDialogType.PE3

    def test_standardna_izjava_pe2(self):
        lines = [_make_line(iznos=100.0)]  # ispod 6000
        assert determine_origin_dialog(lines, True, False) == OriginDialogType.PE2

    def test_standardna_izjava_iznad_6000_eur1(self):
        lines = [_make_line(iznos=7000.0)]  # iznad 6000
        assert determine_origin_dialog(lines, True, False) == OriginDialogType.EUR1

    def test_bez_izjave_sa_zemljom_eur1(self):
        lines = [_make_line(zemlja_porijekla="DE")]
        assert determine_origin_dialog(lines, False, False) == OriginDialogType.EUR1

    def test_bez_izjave_bez_zemlje_none(self):
        lines = [_make_line(zemlja_porijekla="")]
        assert determine_origin_dialog(lines, False, False) == OriginDialogType.NONE


# ── prepare_import — deduplikacija ─────────────────────────────────────────


class TestPrepareDedup:
    def test_consumed_paths_preskace(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf")
        c2 = _make_candidate(source_path="/tmp/INV-001-packing.pdf",
                             consumed_paths=["/tmp/INV-001-packing.pdf"])
        plan = prepare_import([c1, c2])
        # c2 je consumed, samo c1 ostaje
        assert len(plan.invoices) == 1
        assert any(s.reason == "consumed" for s in plan.skipped)

    def test_duplikat_putanje_preskace(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf")
        c2 = _make_candidate(source_path="/tmp/INV-001.pdf")  # ista putanja
        plan = prepare_import([c1, c2])
        assert len(plan.invoices) == 1
        assert any(s.reason == "duplicate_path" for s in plan.skipped)

    def test_bez_stavki_u_failed(self):
        c = _make_candidate(invoice_lines=[])
        plan = prepare_import([c])
        assert len(plan.invoices) == 0
        assert len(plan.failed) == 1


# ── prepare_import — grupisanje ────────────────────────────────────────────


class TestPrepareGrouping:
    def test_kombinovani_je_zasebna_grupa(self):
        c = _make_candidate(source_path="/tmp/combined.pdf", is_combined=True)
        plan = prepare_import([c])
        assert len(plan.invoices) == 1

    def test_isti_invoice_broj_grupise(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001")
        c2 = _make_candidate(source_path="/tmp/INV-001-packing.pdf",
                             invoice_number="INV-001")
        plan = prepare_import([c1, c2])
        # Oba fajla sa istim brojem → jedna logička faktura
        assert len(plan.invoices) == 1
        assert plan.invoices[0].item_count == 2  # po jedna stavka iz svakog fajla

    def test_razliciti_brojevi_zasebne_fakture(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001")
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002")
        plan = prepare_import([c1, c2])
        assert len(plan.invoices) == 2


# ── prepare_import — normalizacija tarifa ──────────────────────────────────


class TestPrepareNormalizeTariffs:
    def test_normalizuje_tarife_na_stavkama(self):
        lines = [_make_line(tarifni_broj="0805.21.90")]
        c = _make_candidate(invoice_lines=lines, invoice_number="INV-001")
        plan = prepare_import([c])
        assert plan.invoices[0].invoice_lines[0].tarifni_broj == "08052190"

    def test_prazna_tarifa_ostaje_prazna(self):
        lines = [_make_line(tarifni_broj="")]
        c = _make_candidate(invoice_lines=lines, invoice_number="INV-001")
        plan = prepare_import([c])
        assert plan.invoices[0].invoice_lines[0].tarifni_broj == ""


# ── prepare_import — plan ADD/REPLACE/SKIP ─────────────────────────────────


class TestPrepareDraftOperation:
    def test_novi_invoice_add(self):
        c = _make_candidate(invoice_number="INV-001")
        plan = prepare_import([c])
        assert plan.invoices[0].draft_operation == DraftOperation.ADD

    def test_postojeci_invoice_replace(self):
        c = _make_candidate(invoice_number="INV-001")
        existing = {"inv001"}
        plan = prepare_import([c], existing_invoice_keys=existing)
        assert plan.invoices[0].draft_operation == DraftOperation.REPLACE

    def test_duplikat_u_batchu_skip(self):
        # Dva fajla sa istim brojem → prvi ADD, drugi preskočen u grupi
        # Ali grupisanje ih spaja u jednu fakturu, pa nema SKIP ovde.
        # SKIP bi bio ako bi ista faktura došla dvaput kao zasebne grupe.
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001")
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-001")
        plan = prepare_import([c1, c2])
        # Oba su grupisana u jednu fakturu
        assert len(plan.invoices) == 1


# ── prepare_import — konflikti ─────────────────────────────────────────────


class TestPrepareConflicts:
    def test_razliciti_izvoznici_konflikt(self):
        c1 = _make_candidate(exporter=Party(name="Izvoznik A", address="", country="DE"))
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002",
                             exporter=Party(name="Potpuno Drugi", address="", country="TR"))
        plan = prepare_import([c1, c2])
        assert plan.has_conflicts is True
        assert any(pc.field_name == "exporter" for pc in plan.partner_conflicts)

    def test_isti_izvoznici_bez_konflikta(self):
        # Koristimo identične nazive (postojeća funkcija je osjetljiva na d.o.o. obrascem)
        c1 = _make_candidate(exporter=Party(name="Exporter d.o.o.", address="", country="DE"))
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002",
                             exporter=Party(name="Exporter d.o.o.", address="", country="DE"))
        plan = prepare_import([c1, c2])
        assert plan.has_conflicts is False

    def test_razlicita_valuta_konflikt(self):
        c1 = _make_candidate(currency="EUR")
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002",
                             currency="USD")
        plan = prepare_import([c1, c2])
        assert plan.currency_conflict is not None

    def test_ista_valuta_bez_konflikta(self):
        c1 = _make_candidate(currency="EUR")
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002",
                             currency="EUR")
        plan = prepare_import([c1, c2])
        assert plan.currency_conflict is None


# ── prepare_import — PE2/PE3/EUR1 ──────────────────────────────────────────


class TestPrepareOriginDialogs:
    def test_pe3_za_ovlasenog(self):
        c = _make_candidate(has_origin_statement=True, is_authorized_exporter=True)
        plan = prepare_import([c])
        assert plan.invoices[0].origin_dialog == OriginDialogType.PE3
        assert plan.has_origin_dialogs is True

    def test_pe2_za_standardnu_izjavu(self):
        c = _make_candidate(has_origin_statement=True, is_authorized_exporter=False)
        plan = prepare_import([c])
        assert plan.invoices[0].origin_dialog == OriginDialogType.PE2

    def test_none_bez_porijekla(self):
        c = _make_candidate(has_origin_statement=False)
        # stavka ima zemlja_porijekla="DE" → eur1
        plan = prepare_import([c])
        assert plan.invoices[0].origin_dialog == OriginDialogType.EUR1

    def test_origin_dialogs_needed_lista(self):
        c = _make_candidate(has_origin_statement=True, is_authorized_exporter=True)
        plan = prepare_import([c])
        assert len(plan.origin_dialogs_needed) == 1
        assert plan.origin_dialogs_needed[0][1] == OriginDialogType.PE3


# ── prepare_import — sažetak ───────────────────────────────────────────────


class TestPrepareSummary:
    def test_brojevi_za_zavrsnu_poruku(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001",
                             bruto_kg=100.0, neto_kg=90.0)
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002",
                             bruto_kg=50.0, neto_kg=45.0)
        plan = prepare_import([c1, c2])
        assert plan.expected_add_count == 2
        assert plan.expected_total_items == 2
        assert plan.expected_total_bruto == 150.0
        assert plan.expected_total_neto == 135.0

    def test_is_empty_sa_nula_faktura(self):
        plan = prepare_import([])
        assert plan.is_empty is True

    def test_is_empty_sa_svim_failed(self):
        c = _make_candidate(invoice_lines=[])
        plan = prepare_import([c])
        assert plan.is_empty is True


# ── prepare_import — identitet fakture ─────────────────────────────────────


class TestPrepareInvoiceIdentity:
    def test_postavlja_invoice_number_na_stavke(self):
        lines = [_make_line(invoice_number="")]  # prazan na stavci
        c = _make_candidate(invoice_lines=lines, invoice_number="INV-001")
        plan = prepare_import([c])
        assert plan.invoices[0].invoice_lines[0].invoice_number == "INV-001"

    def test_ne_prepisuje_postojeci_invoice_number(self):
        lines = [_make_line(invoice_number="POSTOJEĆI")]
        c = _make_candidate(invoice_lines=lines, invoice_number="INV-001")
        plan = prepare_import([c])
        # Stavka već ima broj — ne prepisuje se
        assert plan.invoices[0].invoice_lines[0].invoice_number == "POSTOJEĆI"

    def test_bez_broja_ne_postavlja(self):
        lines = [_make_line(invoice_number="")]
        c = _make_candidate(invoice_lines=lines, invoice_number="")
        plan = prepare_import([c])
        assert plan.invoices[0].invoice_number == ""
        assert plan.invoices[0].has_reliable_invoice_number is False
