"""Testovi za DeclarationSplitService — podjela drafta po grupama zemalja i valuta."""

import pytest

from core.draft.draft import DeclarationDraft, InvoiceLine
from services.faktura.declaration_split_service import (
    EU_COUNTRIES,
    count_declaration_groups,
    count_country_groups,
    declaration_country_group,
    declaration_split_key,
    group_label,
    split_draft_by_country,
)


# ---------------------------------------------------------------------------
# Helperi
# ---------------------------------------------------------------------------

def _line(zemlja: str, iznos: float = 100.0, invoice: str = "FA-1",
          valuta: str = "EUR") -> InvoiceLine:
    return InvoiceLine(
        zemlja_porijekla=zemlja, iznos=iznos,
        invoice_number=invoice, valuta=valuta,
    )


def _draft_with_lines(*lines: InvoiceLine) -> DeclarationDraft:
    d = DeclarationDraft()
    d.invoice_lines = list(lines)
    return d


# ---------------------------------------------------------------------------
# declaration_country_group
# ---------------------------------------------------------------------------

def test_eu_country_maps_to_eu():
    for c in ("PT", "DE", "SI", "HR", "IT", "FR"):
        assert declaration_country_group(c) == "EU", f"{c} treba biti EU"


def test_non_eu_country_maps_to_itself():
    assert declaration_country_group("RS") == "RS"
    assert declaration_country_group("TR") == "TR"
    assert declaration_country_group("CN") == "CN"
    assert declaration_country_group("BR") == "BR"


def test_empty_country_maps_to_empty():
    assert declaration_country_group("") == ""
    assert declaration_country_group(None) == ""  # type: ignore[arg-type]


def test_lowercase_country_normalized():
    assert declaration_country_group("de") == "EU"
    assert declaration_country_group("rs") == "RS"


# ---------------------------------------------------------------------------
# declaration_split_key
# ---------------------------------------------------------------------------

def test_split_key_country_and_currency():
    line = _line("TR", valuta="EUR")
    assert declaration_split_key(line) == ("TR", "EUR")


def test_split_key_eu_merge():
    line = _line("PT", valuta="EUR")
    assert declaration_split_key(line) == ("EU", "EUR")


def test_split_key_currency_normalized_uppercase():
    line = _line("BR", valuta="usd")
    assert declaration_split_key(line) == ("BR", "USD")


def test_split_key_same_country_different_currency():
    eur = _line("BR", valuta="EUR")
    usd = _line("BR", valuta="USD")
    assert declaration_split_key(eur) != declaration_split_key(usd)


# ---------------------------------------------------------------------------
# count_declaration_groups (uključuje valutu)
# ---------------------------------------------------------------------------

def test_count_groups_single_country_single_currency():
    lines = [_line("TR"), _line("TR"), _line("TR")]
    assert count_declaration_groups(lines) == 1


def test_count_groups_eu_merges():
    lines = [_line("PT"), _line("DE"), _line("TR")]
    assert count_declaration_groups(lines) == 2


def test_count_groups_same_country_different_currency():
    lines = [_line("BR", valuta="EUR"), _line("BR", valuta="USD")]
    assert count_declaration_groups(lines) == 2


def test_count_groups_multiple():
    lines = [_line("TR"), _line("RS"), _line("CN"), _line("BR")]
    assert count_declaration_groups(lines) == 4


def test_count_country_groups_alias():
    # Backwards compat alias
    lines = [_line("TR"), _line("RS")]
    assert count_country_groups(lines) == count_declaration_groups(lines)


# ---------------------------------------------------------------------------
# split_draft_by_country — osnov
# ---------------------------------------------------------------------------

def test_split_single_country_returns_original():
    draft = _draft_with_lines(_line("TR"), _line("TR"))
    result = split_draft_by_country(draft)
    assert len(result) == 1
    assert result[0] is draft


def test_split_two_countries():
    draft = _draft_with_lines(_line("TR"), _line("RS"), _line("TR"))
    result = split_draft_by_country(draft)
    assert len(result) == 2
    groups = {getattr(d, "_country_group", None) for d in result}
    assert groups == {"TR", "RS"}


def test_split_eu_merged():
    draft = _draft_with_lines(_line("PT"), _line("DE"), _line("TR"))
    result = split_draft_by_country(draft)
    assert len(result) == 2
    groups = {getattr(d, "_country_group", None) for d in result}
    assert groups == {"EU", "TR"}


def test_split_eu_stavke_count():
    draft = _draft_with_lines(_line("PT"), _line("DE"), _line("SI"), _line("TR"))
    result = split_draft_by_country(draft)
    eu_draft = next(d for d in result if getattr(d, "_country_group") == "EU")
    tr_draft = next(d for d in result if getattr(d, "_country_group") == "TR")
    assert len(eu_draft.invoice_lines) == 3
    assert len(tr_draft.invoice_lines) == 1


def test_split_preserves_header():
    draft = _draft_with_lines(_line("TR"), _line("RS"))
    draft.izvoznik_naziv = "KG Fashion"
    draft.primalac_naziv = "Pret a Porter"
    result = split_draft_by_country(draft)
    for d in result:
        assert d.izvoznik_naziv == "KG Fashion"
        assert d.primalac_naziv == "Pret a Porter"


def test_split_does_not_share_invoice_lines():
    draft = _draft_with_lines(_line("TR"), _line("RS"))
    result = split_draft_by_country(draft)
    for d in result:
        assert d.invoice_lines is not draft.invoice_lines


# ---------------------------------------------------------------------------
# Split po valuti (Brazil EUR vs USD — ključni slučaj)
# ---------------------------------------------------------------------------

def test_split_same_country_different_currency():
    draft = _draft_with_lines(
        _line("BR", valuta="EUR", invoice="RAC-285"),
        _line("BR", valuta="USD", invoice="RAC-287"),
    )
    result = split_draft_by_country(draft)
    assert len(result) == 2
    currencies = {getattr(d, "_currency_group") for d in result}
    assert currencies == {"EUR", "USD"}


def test_split_currency_sets_draft_valuta():
    draft = _draft_with_lines(
        _line("BR", valuta="EUR"),
        _line("BR", valuta="USD"),
    )
    result = split_draft_by_country(draft)
    eur_d = next(d for d in result if getattr(d, "_currency_group") == "EUR")
    usd_d = next(d for d in result if getattr(d, "_currency_group") == "USD")
    assert eur_d.valuta == "EUR"
    assert usd_d.valuta == "USD"


def test_split_brazil_eur_usd_stavke():
    draft = _draft_with_lines(
        _line("BR", valuta="EUR", invoice="RAC-285"),
        _line("BR", valuta="EUR", invoice="RAC-285"),
        _line("BR", valuta="USD", invoice="RAC-287"),
    )
    result = split_draft_by_country(draft)
    eur_d = next(d for d in result if getattr(d, "_currency_group") == "EUR")
    usd_d = next(d for d in result if getattr(d, "_currency_group") == "USD")
    assert len(eur_d.invoice_lines) == 2
    assert len(usd_d.invoice_lines) == 1


def test_split_kg_fashion_scenario():
    # Scenarij koji odgovara realnim KG Fashion fakturama
    lines = [
        _line("BR", valuta="EUR"),   # Petite Jolie
        _line("BR", valuta="EUR"),   # Petite Jolie
        _line("BR", valuta="USD"),   # Vizzano
        _line("TR", valuta="EUR"),   # Bueno
        _line("RS", valuta="EUR"),   # Jagger
        _line("CN", valuta="EUR"),   # Vizzano torbe
        _line("PT", valuta="EUR"),   # Ambitious (EU)
    ]
    draft = _draft_with_lines(*lines)
    result = split_draft_by_country(draft)
    assert len(result) == 6  # BR/EUR, BR/USD, TR/EUR, RS/EUR, CN/EUR, EU/EUR
    keys = {(getattr(d, "_country_group"), getattr(d, "_currency_group")) for d in result}
    assert ("BR", "EUR") in keys
    assert ("BR", "USD") in keys
    assert ("TR", "EUR") in keys
    assert ("RS", "EUR") in keys
    assert ("CN", "EUR") in keys
    assert ("EU", "EUR") in keys


# ---------------------------------------------------------------------------
# Raspodjela težina — invoice_weights
# ---------------------------------------------------------------------------

def test_split_weights_single_invoice_per_group():
    draft = _draft_with_lines(
        _line("TR", invoice="RAC-296"),
        _line("RS", invoice="RAC-298"),
    )
    draft.invoice_weights = {
        "rac-296": (265.0, 165.0),
        "rac-298": (40.0, 33.0),
    }
    result = split_draft_by_country(draft)
    tr = next(d for d in result if getattr(d, "_country_group") == "TR")
    rs = next(d for d in result if getattr(d, "_country_group") == "RS")
    assert tr.invoice_weights == {"rac-296": (265.0, 165.0)}
    assert rs.invoice_weights == {"rac-298": (40.0, 33.0)}


def test_split_weights_by_currency():
    draft = _draft_with_lines(
        _line("BR", valuta="EUR", iznos=500.0, invoice="RAC-285"),
        _line("BR", valuta="USD", iznos=100.0, invoice="RAC-287"),
    )
    draft.invoice_weights = {
        "rac-285": (833.0, 528.0),
        "rac-287": (61.0, 52.0),
    }
    result = split_draft_by_country(draft)
    eur = next(d for d in result if getattr(d, "_currency_group") == "EUR")
    usd = next(d for d in result if getattr(d, "_currency_group") == "USD")
    assert eur.invoice_weights == {"rac-285": (833.0, 528.0)}
    assert usd.invoice_weights == {"rac-287": (61.0, 52.0)}


def test_split_weights_mixed_invoice_proportional():
    draft = _draft_with_lines(
        _line("TR", iznos=300.0, invoice="FA-1"),
        _line("RS", iznos=100.0, invoice="FA-1"),
    )
    draft.invoice_weights = {"fa-1": (400.0, 300.0)}
    result = split_draft_by_country(draft)
    tr = next(d for d in result if getattr(d, "_country_group") == "TR")
    rs = next(d for d in result if getattr(d, "_country_group") == "RS")
    assert tr.invoice_weights["fa-1"][0] == pytest.approx(300.0, abs=0.01)
    assert tr.invoice_weights["fa-1"][1] == pytest.approx(225.0, abs=0.01)
    assert rs.invoice_weights["fa-1"][0] == pytest.approx(100.0, abs=0.01)
    assert rs.invoice_weights["fa-1"][1] == pytest.approx(75.0, abs=0.01)


# ---------------------------------------------------------------------------
# group_label
# ---------------------------------------------------------------------------

def test_group_label_without_currency():
    assert "Turska" in group_label("TR")
    assert "Srbija" in group_label("RS")
    assert group_label("EU") == "EU"


def test_group_label_with_currency():
    assert group_label("TR", "EUR") == "Turska (TR) • EUR"
    assert group_label("BR", "USD") == "Brazil (BR) • USD"
    assert group_label("EU", "EUR") == "EU • EUR"


def test_group_label_unknown_returns_key():
    assert group_label("JP") == "JP"
    assert group_label("") == "Nepoznato"
