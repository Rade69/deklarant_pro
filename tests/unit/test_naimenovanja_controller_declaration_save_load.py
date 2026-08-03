from core.draft.draft import DeclarationDraft
from gui.tabs.naimenovanja_controller import NaimenovanjaController


class FakeView:
    def __init__(self, draft):
        self.draft = draft
        self.is_loading = False
        self.current_item_index = 0
        self.errors = []
        self.successes = []

    def read_current_form(self):
        return {}

    def show_error(self, message, title="Greška"):
        self.errors.append((title, message))

    def show_success(self, message="Operacija uspješna", title="Uspjeh"):
        self.successes.append((title, message))


def _make_controller(draft, save_header_calls=None, replace_draft_calls=None):
    return NaimenovanjaController(
        get_draft_fn=lambda: draft,
        save_header_fn=(lambda: save_header_calls.append(True)) if save_header_calls is not None else None,
        replace_draft_fn=(lambda loaded: replace_draft_calls.append(loaded)) if replace_draft_calls is not None else None,
    )


def test_save_declaration_persists_draft_and_notifies_view(tmp_path):
    draft = DeclarationDraft()
    view = FakeView(draft)
    save_header_calls = []
    controller = _make_controller(draft, save_header_calls=save_header_calls)

    target = tmp_path / "nacrt.xml"
    ok = controller.save_declaration(view, str(target))

    assert ok is True
    assert save_header_calls == [True]
    assert draft.dirty is False
    assert draft._persistent_draft_path == str(target)
    assert target.exists()
    assert view.successes and "sačuvana" in view.successes[0][1]
    assert view.successes[0][0] == "Nacrt sačuvan"
    assert not view.errors


def test_save_declaration_reports_error_on_failure(monkeypatch, tmp_path):
    draft = DeclarationDraft()
    view = FakeView(draft)
    controller = _make_controller(draft)

    from services import declaration_draft_service

    def _boom(self, draft, path):
        raise OSError("disk pun")

    monkeypatch.setattr(declaration_draft_service.DeclarationDraftService, "save", _boom)

    ok = controller.save_declaration(view, str(tmp_path / "x.xml"))

    assert ok is False
    assert view.errors
    assert "nije sačuvan" in view.errors[0][1]
    assert view.errors[0][0] == "Greška pri čuvanju"


def test_load_declaration_replaces_draft_via_callback(tmp_path):
    draft = DeclarationDraft()
    view = FakeView(draft)
    replace_calls = []
    controller = _make_controller(draft, replace_draft_calls=replace_calls)

    target = tmp_path / "nacrt.xml"
    controller.save_declaration(view, str(target))
    view.successes.clear()

    ok = controller.load_declaration(view, str(target))

    assert ok is True
    assert len(replace_calls) == 1
    assert replace_calls[0]._persistent_draft_path == str(target)
    assert view.successes and "Otvoren" in view.successes[0][1]


def test_load_declaration_reports_error_when_file_missing(tmp_path):
    draft = DeclarationDraft()
    view = FakeView(draft)
    replace_calls = []
    controller = _make_controller(draft, replace_draft_calls=replace_calls)

    ok = controller.load_declaration(view, str(tmp_path / "nepostojeci.xml"))

    assert ok is False
    assert not replace_calls
    assert view.errors
