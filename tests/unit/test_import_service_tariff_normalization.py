# tests/unit/test_import_service_tariff_normalization.py

"""
Testovi za ImportService._normalize_tariffs_in_result().

Regresija (2026-07-25, otkriveno na Medicopharm fakturi 1476/26 Rb.78):
zfill(8) je lijevo-dopunjavao SVAKI 4-7-cifreni kod nulama, pod
pretpostavkom da je uvijek izostavljena vodeća nula poglavlja 01-09. Za
"3304990" (7 cifara, poglavlje 33, izostavljena ZADNJA cifra) to je
proizvodilo "03304990" — nepostojeće poglavlje 03 (riba) umjesto stvarnog
poglavlja 33 (kozmetika). Smjer dopune nije odrediv bez pogađanja, pa se
4-7-cifreni kod sada NE dopunjava — ostaje nepotpun (uhvati ga
declaration_validator_service ERROR provjera protiv zvanične tarife).
"""
from types import SimpleNamespace

from services.import_service import ImportService
from importers.import_result import ImportResult


def _result_with_tariff(code: str) -> ImportResult:
    item = SimpleNamespace(tarifni_broj=code)
    return ImportResult(items=[item])


def test_7digit_code_ostaje_nepromijenjen_ne_fabrikuje_poglavlje():
    """Regresija: '3304990' NE smije postati '03304990'."""
    svc = ImportService()
    result = _result_with_tariff("3304990")
    svc._normalize_tariffs_in_result(result)
    assert result.items[0].tarifni_broj == "3304990"


def test_4_do_7_cifara_ostaje_nepromijenjeno():
    svc = ImportService()
    for code in ("8516", "85166", "851660", "8516609"):
        result = _result_with_tariff(code)
        svc._normalize_tariffs_in_result(result)
        assert result.items[0].tarifni_broj == code, f"kod {code} je promijenjen"


def test_10_cifara_sa_trailing_00_skracuje_na_8():
    svc = ImportService()
    result = _result_with_tariff("8511800000")
    svc._normalize_tariffs_in_result(result)
    assert result.items[0].tarifni_broj == "85118000"


def test_10_cifara_bez_trailing_00_skracuje_na_internih_8():
    svc = ImportService()
    result = _result_with_tariff("8511800010")
    svc._normalize_tariffs_in_result(result)
    assert result.items[0].tarifni_broj == "85118000"


def test_vise_od_10_cifara_skracuje_na_8():
    svc = ImportService()
    result = _result_with_tariff("851180001099")
    svc._normalize_tariffs_in_result(result)
    assert result.items[0].tarifni_broj == "85118000"


def test_tarife_iz_glavne_liste_skracuje_na_internih_8():
    svc = ImportService()
    for raw, expected in (
        ("8516802090", "85168020"),
        ("8421298090", "84212980"),
        ("8415900090", "84159000"),
        ("8413608090", "84136080"),
    ):
        result = _result_with_tariff(raw)
        svc._normalize_tariffs_in_result(result)
        assert result.items[0].tarifni_broj == expected


def test_kod_sa_kosom_crtom_uzima_dio_prije_crte():
    svc = ImportService()
    result = _result_with_tariff("21069098/9080")
    svc._normalize_tariffs_in_result(result)
    assert result.items[0].tarifni_broj == "21069098"


def test_vec_8_cifreni_kod_ostaje_nepromijenjen():
    svc = ImportService()
    result = _result_with_tariff("38249993")
    svc._normalize_tariffs_in_result(result)
    assert result.items[0].tarifni_broj == "38249993"


def test_prazan_kod_ne_puca():
    svc = ImportService()
    result = _result_with_tariff("")
    svc._normalize_tariffs_in_result(result)
    assert result.items[0].tarifni_broj == ""


def test_ne_import_result_je_no_op():
    svc = ImportService()
    svc._normalize_tariffs_in_result([SimpleNamespace(tarifni_broj="1234")])  # ne puca
