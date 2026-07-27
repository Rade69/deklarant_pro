from types import SimpleNamespace

from gui.tabs.faktura_view import FakturaView, ValidationDelegate
from gui.tabs.naimenovanja_view import NaimenovanjaView
from gui.tabs.sifarnici_view import SifarniciView
from gui.tabs.zaglavlje_controller import ZaglavljeController


class _Widget:
    def __init__(self):
        self.focused = False
        self.style = ""

    def setFocus(self, reason):
        self.focused = True

    def styleSheet(self):
        return self.style

    def setStyleSheet(self, style):
        self.style = style


class _Cell:
    def __init__(self):
        self.data = {}
        self.tooltip = ""

    def setData(self, role, value):
        self.data[role] = value

    def setToolTip(self, text):
        self.tooltip = text


def test_faktura_missing_tariff_marks_only_tariff_cell():
    cells = [_Cell() for _ in range(12)]
    table = SimpleNamespace(
        columnCount=lambda: 12,
        item=lambda row, col: cells[col],
    )
    result = SimpleNamespace(
        errors=[],
        warnings=[],
        valid=False,
        has_blocking_errors=lambda: True,
    )
    view = SimpleNamespace(
        validator=SimpleNamespace(validate=lambda item: result),
        validation_cache=SimpleNamespace(set=lambda row, value: None),
        table=table,
        _apply_country_confidence_color=lambda row, item: None,
        _apply_preference_confidence_color=lambda row, item: None,
    )
    item = SimpleNamespace(
        tarifni_broj="",
        zemlja_porijekla="CN",
        tariff_similarity=0.0,
    )

    FakturaView._validate_and_color_row(view, 0, item)

    role = ValidationDelegate.ValidationColorRole
    assert cells[4].data[role] == "#F9E4E3"
    assert cells[3].data[role] == "#ffffff"
    assert cells[4].tooltip == "❌ Greška: Nedostaje tarifni broj"


def test_faktura_missing_country_overrides_country_confidence_color():
    cells = [_Cell() for _ in range(12)]
    table = SimpleNamespace(
        columnCount=lambda: 12,
        item=lambda row, col: cells[col],
    )
    result = SimpleNamespace(
        errors=[],
        warnings=[],
        valid=False,
        has_blocking_errors=lambda: True,
    )

    def apply_country(row, item):
        cells[9].setData(ValidationDelegate.ValidationColorRole, "#EAF4EE")

    view = SimpleNamespace(
        validator=SimpleNamespace(validate=lambda item: result),
        validation_cache=SimpleNamespace(set=lambda row, value: None),
        table=table,
        _apply_country_confidence_color=apply_country,
        _apply_preference_confidence_color=lambda row, item: None,
    )
    item = SimpleNamespace(
        tarifni_broj="39269097",
        zemlja_porijekla="",
        tariff_similarity=0.0,
    )

    FakturaView._validate_and_color_row(view, 0, item)

    assert (
        cells[9].data[ValidationDelegate.ValidationColorRole]
        == "#F9E4E3"
    )


def test_naimenovanja_issue_carries_item_and_widget_location():
    item = SimpleNamespace(
        tariff_code="",
        origin_country_code="",
        package_qty=0,
        item_value=0,
        preference_code="",
        attached_document1="",
        attached_document2="",
        attached_document3="",
        attached_document4="",
        attached_document5="",
    )
    view = SimpleNamespace(draft=SimpleNamespace(items=[item]))

    issues = NaimenovanjaView._validation_issues(view)

    assert issues[0]["item_index"] == 0
    assert issues[0]["widget_name"] == "le_rubrika33"
    assert any(issue["widget_name"] == "le_rubrika34_zemlja" for issue in issues)
    assert any(issue["widget_name"] == "le_r31_broj" for issue in issues)


def test_sifarnici_focus_first_required_field():
    jib = _Widget()
    naziv = _Widget()
    view = SimpleNamespace(
        current_category="Pošiljaoci",
        jib_field=jib,
        naziv_field=naziv,
    )

    SifarniciView.focus_first_invalid_field(
        view, {"jib": "", "naziv": ""}
    )

    assert jib.focused is True
    assert naziv.focused is False


def test_zaglavlje_validation_focuses_mapped_widget(monkeypatch):
    widget = _Widget()
    view = SimpleNamespace(
        field_widgets={"iznos": widget},
        show_warning=lambda message: None,
    )
    controller = SimpleNamespace(view=view)
    monkeypatch.setattr(
        "gui.tabs.zaglavlje_controller.QTimer.singleShot",
        lambda delay, callback: None,
    )

    ZaglavljeController._focus_validation_field(
        controller, SimpleNamespace(field="Iznos fakture")
    )

    assert widget.focused is True
    assert "border: 2px solid #c94b45" in widget.style
