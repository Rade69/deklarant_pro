"""
Regresioni test za dugme "Zavrsna provjera" (zaglavlje_view.py:btn_snimi).

Pokriva scenario "XML uvoz direktno u Naimenovanja, bez ATB Faktura uvoza"
(agent_reports/2026-06-15_compliance-check-bez-atb-fakture.md) kroz STVARNI
kod put kontrolera (_get_naimenovanja_data / _get_invoice_lines), ne kroz
rucno konstruisane podatke — ovaj kod put ranije nije bio testiran.
"""
from PySide6.QtWidgets import QPushButton, QTabWidget

from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
from gui.tabs.zaglavlje_controller import ZaglavljeController
from gui.dialogs.enhanced_validation_dialog import EnhancedValidationDialog, DialogConfig
from services.agent.declaration_validator_service import validate_declaration_full


def _build_draft_bez_atb():
    draft = DeclarationDraft()
    draft.invoice_lines = []
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=1,
            goods_trade_name="Testna roba bez tarife",
            tariff_code="",
            procedure_code="",
            origin_country_code="",
        )
    ]
    draft.header_attached_documents = []
    return draft


def test_controller_extraction_feeds_compliance_check_bez_atb():
    draft = _build_draft_bez_atb()
    controller = ZaglavljeController.__new__(ZaglavljeController)
    controller._get_draft_fn = lambda: draft

    naimenovanja_data = controller._get_naimenovanja_data()
    invoice_lines_data = controller._get_invoice_lines(draft)

    assert invoice_lines_data == []
    assert len(naimenovanja_data) == 1
    assert naimenovanja_data[0]["tariff_code"] == ""

    report = validate_declaration_full(
        zaglavlje_data={},
        naimenovanja_data=naimenovanja_data,
        invoice_lines=invoice_lines_data,
        draft=draft,
    )

    assert report.valid is False
    assert report.error_count > 0
    codes = {item.field for item in (report.compliance_items or [])}
    assert codes == {"no_invoice_lines", "naim_no_tariff", "naim_no_procedure", "no_docs"}


def test_enhanced_dialog_shows_kompletnost_tab_without_export_button(qtbot):
    draft = _build_draft_bez_atb()
    controller = ZaglavljeController.__new__(ZaglavljeController)
    controller._get_draft_fn = lambda: draft

    report = validate_declaration_full(
        zaglavlje_data={},
        naimenovanja_data=controller._get_naimenovanja_data(),
        invoice_lines=controller._get_invoice_lines(draft),
        draft=draft,
    )

    config = DialogConfig(show_details=True, show_recommendations=True, show_export_button=False)
    dialog = EnhancedValidationDialog(report, config, None)
    qtbot.addWidget(dialog)

    tabs = dialog.findChild(QTabWidget)
    tab_names = [tabs.tabText(i) for i in range(tabs.count())]
    assert any("Kompletnost" in name for name in tab_names)

    button_labels = [b.text() for b in dialog.findChildren(QPushButton)]
    assert not any("export" in b.lower() or "izvezi" in b.lower() for b in button_labels), (
        "Zavrsna provjera ne smije imati Export dugme — deklarant uvijek "
        "rucno pokrece 'Izvezi XML' odvojeno (poslovno pravilo korisnika)"
    )
