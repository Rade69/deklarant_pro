"""
Testovi za ImportResult.validate() i ImportValidator servis.

Pokriva:
  1. validate() na ImportResult — parser-level provjere
  2. validate_import_result() iz ImportValidator servisa
  3. Edge case-ovi: prazne stavke, negativne cijene, neto > bruto
"""

import pytest

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult
from services.import_validator import validate_import_result, format_validation_summary


# ---------------------------------------------------------------------------
# Helperi
# ---------------------------------------------------------------------------

def _line(naziv="Roba A", kolicina=10.0, cijena=5.0, iznos=50.0, bruto=1.0, neto=0.9):
    return InvoiceLine(
        naziv_robe=naziv,
        kolicina=kolicina,
        cijena_jed=cijena,
        iznos=iznos,
        bruto_kg=bruto,
        neto_kg=neto,
    )


def _result(*lines, bruto=0.0, neto=0.0, currency="EUR"):
    return ImportResult(
        items=list(lines),
        bruto_kg=bruto,
        neto_kg=neto,
        currency=currency,
    )


# ---------------------------------------------------------------------------
# ImportResult.validate() — ispravni rezultati
# ---------------------------------------------------------------------------

def test_validate_ok_single_line():
    r = _result(_line(), bruto=1.0, neto=0.9)
    ok, errors, warnings = r.validate()
    assert ok
    assert not errors


def test_validate_ok_multiple_lines():
    r = _result(_line("A"), _line("B"), _line("C"), bruto=10.0, neto=8.0)
    ok, errors, warnings = r.validate()
    assert ok
    assert not errors


# ---------------------------------------------------------------------------
# ImportResult.validate() — greške koje blokiraju uvoz
# ---------------------------------------------------------------------------

def test_validate_error_zero_items():
    r = _result()  # nema stavki
    ok, errors, _ = r.validate()
    assert not ok
    assert any("0 stavki" in e for e in errors)


def test_validate_error_negative_bruto():
    r = _result(_line(), bruto=-5.0, neto=0.0)
    ok, errors, _ = r.validate()
    assert not ok
    assert any("bruto" in e.lower() for e in errors)


def test_validate_error_negative_neto():
    r = _result(_line(), bruto=5.0, neto=-1.0)
    ok, errors, _ = r.validate()
    assert not ok
    assert any("neto" in e.lower() for e in errors)


def test_validate_error_neto_gt_bruto():
    r = _result(_line(), bruto=5.0, neto=10.0)
    ok, errors, _ = r.validate()
    assert not ok
    assert any("neto" in e.lower() and "bruto" in e.lower() for e in errors)


def test_validate_error_negative_price():
    r = _result(_line(cijena=-1.0))
    ok, errors, _ = r.validate()
    assert not ok
    assert any("cijena" in e.lower() for e in errors)


def test_validate_error_negative_iznos():
    r = _result(_line(iznos=-50.0))
    ok, errors, _ = r.validate()
    assert not ok
    assert any("iznos" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# ImportResult.validate() — upozorenja (ne blokiraju)
# ---------------------------------------------------------------------------

def test_validate_warning_empty_naziv():
    r = _result(_line(naziv=""))
    ok, errors, warnings = r.validate()
    assert ok  # warning, ne error
    assert not errors
    assert any("naziv" in w.lower() for w in warnings)


def test_validate_warning_zero_kolicina():
    r = _result(_line(kolicina=0.0))
    ok, _, warnings = r.validate()
    assert ok
    assert any("količina" in w.lower() for w in warnings)


def test_validate_warning_unknown_currency():
    r = _result(_line(), currency="XYZ")
    ok, _, warnings = r.validate()
    assert ok
    assert any("XYZ" in w for w in warnings)


def test_validate_warning_item_neto_gt_bruto():
    line = _line(bruto=1.0, neto=2.0)
    r = _result(line, bruto=5.0, neto=4.0)
    ok, _, warnings = r.validate()
    assert ok
    assert any("neto" in w.lower() for w in warnings)


def test_validate_warnings_deduped_in_result_warnings():
    """validate() dodaje warnings u result.warnings bez duplikata."""
    r = _result(_line(naziv=""), _line(naziv=""))
    r.validate()
    r.validate()  # drugi poziv ne smije duplicirati
    prazan_naziv_warnings = [w for w in r.warnings if "naziv" in w.lower()]
    # Mogu biti 2 (jedan po stavci) ali ne 4
    assert len(prazan_naziv_warnings) <= 2


# ---------------------------------------------------------------------------
# ImportValidator servis
# ---------------------------------------------------------------------------

def test_validate_import_result_ok():
    r = _result(_line(), bruto=1.0, neto=0.9)
    vr = validate_import_result(r, "test.pdf")
    assert vr.ok
    assert vr.filename == "test.pdf"
    assert not vr.errors


def test_validate_import_result_error_zero_items():
    r = _result()
    vr = validate_import_result(r, "prazan.xlsx")
    assert not vr.ok
    assert vr.errors


def test_validate_import_result_summary_line_ok():
    r = _result(_line())
    vr = validate_import_result(r, "faktura.pdf")
    assert "✅" in vr.summary_line()


def test_validate_import_result_summary_line_error():
    r = _result()
    vr = validate_import_result(r, "prazan.pdf")
    assert "❌" in vr.summary_line()


def test_validate_import_result_summary_line_warning():
    r = _result(_line(naziv=""))
    vr = validate_import_result(r, "nepotpuna.pdf")
    assert "⚠️" in vr.summary_line() or "✅" in vr.summary_line()
    # Warning ne blokira — ok=True


def test_format_validation_summary_empty():
    assert format_validation_summary([]) == ""


def test_format_validation_summary_all_ok():
    r1 = _result(_line())
    r2 = _result(_line())
    vr_list = [
        validate_import_result(r1, "a.pdf"),
        validate_import_result(r2, "b.pdf"),
    ]
    summary = format_validation_summary(vr_list)
    assert summary == ""  # nema grešaka ni upozorenja


def test_format_validation_summary_with_error():
    good = _result(_line())
    bad = _result()  # 0 stavki
    vr_list = [
        validate_import_result(good, "ok.pdf"),
        validate_import_result(bad, "bad.pdf"),
    ]
    summary = format_validation_summary(vr_list)
    assert "❌" in summary
    assert "bad.pdf" in summary


# ---------------------------------------------------------------------------
# ImportService — validacija u import_file() pokriva sve tokove
# ---------------------------------------------------------------------------

def test_import_service_raises_on_zero_items(tmp_path, monkeypatch):
    """ImportService.import_file() mora baciti ImportException ako parser vrati 0 stavki."""
    from importers.import_result import ImportResult
    from importers.exceptions import ImportError as ImportException
    from services.import_service import ImportService

    fake_file = tmp_path / "faktura.pdf"
    fake_file.write_bytes(b"%PDF-1.4 fake")

    empty_result = ImportResult(items=[], bruto_kg=0.0, neto_kg=0.0)

    svc = ImportService()
    monkeypatch.setattr(svc, "_try_combine_with_previous", lambda fp: None)
    monkeypatch.setattr(svc, "_try_import_as_packing_list", lambda fp: None)
    monkeypatch.setattr(svc.registry, "import_file", lambda fp, **kw: empty_result)

    with pytest.raises(ImportException, match="0 stavki"):
        svc.import_file(str(fake_file))


def test_import_service_packing_list_allows_empty_but_blocks_negative_weight(tmp_path, monkeypatch):
    """Packing lista sa 0 stavki prolazi, ali negativna težina i dalje blokira."""
    from importers.import_result import ImportResult
    from importers.exceptions import ImportError as ImportException
    from services.import_service import ImportService

    fake_file = tmp_path / "packing.pdf"
    fake_file.write_bytes(b"%PDF-1.4 fake")

    bad_packing = ImportResult(items=[], bruto_kg=-10.0, neto_kg=0.0)

    svc = ImportService()
    monkeypatch.setattr(svc, "_try_combine_with_previous", lambda fp: None)
    monkeypatch.setattr(svc, "_try_import_as_packing_list", lambda fp: bad_packing)

    with pytest.raises(ImportException, match="bruto"):
        svc.import_file(str(fake_file))


def test_validate_allow_empty_skips_zero_items_error():
    """validate(allow_empty=True) ne baca grešku za 0 stavki, ali hvata negativnu težinu."""
    r_empty = _result(bruto=0.0, neto=0.0)
    ok, errors, _ = r_empty.validate(allow_empty=True)
    assert ok
    assert not errors

    r_neg = _result(bruto=-5.0, neto=0.0)
    ok2, errors2, _ = r_neg.validate(allow_empty=True)
    assert not ok2
    assert any("bruto" in e.lower() for e in errors2)
