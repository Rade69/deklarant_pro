"""
Karakterizacioni testovi za services/faktura/legacy_import_service.py.

Poruke izdvojene iz FakturaView._finish_import_legacy_path i
_process_batch_records_legacy (Faza 6 ekstrakcije, 2026-08-02). Test-ovi
zakljucavaju tacan format postojecih poruka prije nego sto se View
prekopira da ih koristi.
"""
from services.faktura.legacy_import_service import (
    build_assembly_match_message,
    build_manual_import_prefix_message,
    build_manual_import_suffix_message,
    build_legacy_batch_import_message,
)


class TestAssemblyMatchMessage:
    def test_sadrzi_naziv_fakture_i_match_rezultate(self):
        status = {"total": 10, "complete": 8, "completion_percentage": 80.0, "imported_invoices_count": 2}
        msg = build_assembly_match_message("1476/26", matched=5, unmatched=2, bruto_kg=10.0, neto_kg=9.0, status=status)
        assert "1476/26" in msg
        assert "Matched: 5 stavki" in msg
        assert "Unmatched: 2 stavki" in msg
        assert "Ukupno stavki: 10" in msg
        assert "Kompletno: 8 (80.0%)" in msg

    def test_bez_tezina_ne_prikazuje_tezinu_sekciju(self):
        status = {"total": 1, "complete": 1, "completion_percentage": 100.0, "imported_invoices_count": 1}
        msg = build_assembly_match_message("X", matched=1, unmatched=0, bruto_kg=0.0, neto_kg=0.0, status=status)
        assert "Težine sa fakture" not in msg

    def test_unmatched_dodaje_upozorenje_o_crvenoj_boji(self):
        status = {"total": 1, "complete": 0, "completion_percentage": 0.0, "imported_invoices_count": 1}
        msg = build_assembly_match_message("X", matched=0, unmatched=3, bruto_kg=0.0, neto_kg=0.0, status=status)
        assert "CRVENOM bojom" in msg

    def test_nula_unmatched_ne_dodaje_upozorenje(self):
        status = {"total": 1, "complete": 1, "completion_percentage": 100.0, "imported_invoices_count": 1}
        msg = build_assembly_match_message("X", matched=1, unmatched=0, bruto_kg=0.0, neto_kg=0.0, status=status)
        assert "CRVENOM bojom" not in msg

    def test_current_weights_none_ne_prikazuje_draft_ukupno(self):
        status = {"total": 1, "complete": 1, "completion_percentage": 100.0, "imported_invoices_count": 1}
        msg = build_assembly_match_message("X", 1, 0, 5.0, 4.0, status, current_weights=None)
        assert "nakon matching-a" not in msg

    def test_current_weights_prisutne_prikazuje_draft_ukupno(self):
        status = {"total": 1, "complete": 1, "completion_percentage": 100.0, "imported_invoices_count": 1}
        msg = build_assembly_match_message("X", 1, 0, 5.0, 4.0, status, current_weights=(12.5, 11.5))
        assert "nakon matching-a" in msg
        assert "12.500" in msg
        assert "11.500" in msg


class TestManualImportMessages:
    def test_prefix_bez_prethodnih_stavki(self):
        msg = build_manual_import_prefix_message(
            "1476/26", item_count=5, previous_count=0, total_count=5,
            bruto_kg=0.0, neto_kg=0.0, accumulated_bruto_kg=0.0, accumulated_neto_kg=0.0,
        )
        assert "Uspješno uvezeno 5 stavki iz '1476/26'" in msg
        assert "Akumulirano" not in msg

    def test_prefix_sa_prethodnim_stavkama_prikazuje_akumulaciju(self):
        msg = build_manual_import_prefix_message(
            "1476/26", item_count=5, previous_count=10, total_count=15,
            bruto_kg=0.0, neto_kg=0.0, accumulated_bruto_kg=0.0, accumulated_neto_kg=0.0,
        )
        assert "Prethodno: 10 stavki" in msg
        assert "Ukupno: 15 stavki" in msg

    def test_prefix_sa_tezinom_prikazuje_akumulirano_ukupno(self):
        msg = build_manual_import_prefix_message(
            "X", 1, 0, 1, bruto_kg=3.0, neto_kg=2.5,
            accumulated_bruto_kg=30.0, accumulated_neto_kg=25.0,
        )
        assert "Akumulirano ukupno" in msg
        assert "30.000" in msg
        assert "25.000" in msg

    def test_suffix_kombinovan_import(self):
        assert "Redoslijed stavki održan" in build_manual_import_suffix_message(True, "")

    def test_suffix_loren_excel(self):
        msg = build_manual_import_suffix_message(False, "loren_excel")
        assert "LOREN EXCEL" in msg
        assert "iznosi = 0" in msg

    def test_suffix_default(self):
        msg = build_manual_import_suffix_message(False, "")
        assert "Možete nastaviti sa uvozom" in msg


class TestLegacyBatchImportMessage:
    def test_osnovna_poruka(self):
        msg = build_legacy_batch_import_message(
            records_count=5, final_records_count=5, all_items_count=50,
            total_bruto_kg=100.0, total_neto_kg=90.0,
            failed_imports=[], parser_warnings=[],
        )
        assert "Uspješno faktura: 5" in msg
        assert "Ukupno stavki: 50" in msg
        assert "Spojeno/preskočeno" not in msg

    def test_skipped_count_prikazan_kad_ima_razlike(self):
        msg = build_legacy_batch_import_message(
            records_count=7, final_records_count=5, all_items_count=50,
            total_bruto_kg=100.0, total_neto_kg=90.0,
            failed_imports=[], parser_warnings=[],
        )
        assert "Spojeno/preskočeno parova: 2" in msg

    def test_failed_imports_prikazani_max_3_sa_brojem_ostatka(self):
        failed = [("a.pdf", "err1"), ("b.pdf", "err2"), ("c.pdf", "err3"), ("d.pdf", "err4")]
        msg = build_legacy_batch_import_message(
            records_count=5, final_records_count=1, all_items_count=1,
            total_bruto_kg=1.0, total_neto_kg=1.0,
            failed_imports=failed, parser_warnings=[],
        )
        assert "Neuspješno: 4" in msg
        assert "a.pdf" in msg and "c.pdf" in msg
        assert "d.pdf" not in msg
        assert "i još 1" in msg

    def test_parser_warnings_prikazane_max_5(self):
        warnings = [f"upozorenje {i}" for i in range(7)]
        msg = build_legacy_batch_import_message(
            records_count=1, final_records_count=1, all_items_count=1,
            total_bruto_kg=1.0, total_neto_kg=1.0,
            failed_imports=[], parser_warnings=warnings,
        )
        assert "Upozorenja parsera (7)" in msg
        assert "upozorenje 0" in msg
        assert "upozorenje 4" in msg
        assert "upozorenje 5" not in msg
        assert "i još 2" in msg
