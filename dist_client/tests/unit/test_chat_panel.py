from PySide6.QtGui import QGuiApplication

from gui.tabs.agent.widgets.chat_panel import ChatPanel


def test_copy_last_agent_message_strips_html_to_clipboard(qtbot):
    panel = ChatPanel()
    qtbot.addWidget(panel)

    panel.add_agent_message(
        "<b>Tarifa 85168080</b> je jak prijedlog.<br>"
        "Izvor: istorijski XML istog izvoznika PIP FOOD GROUP DOO, korišteno 6x.<br>"
        "Pouzdanost: 91%."
    )

    panel._copy_last_agent_message()

    report = QGuiApplication.clipboard().text()
    assert "<b>" not in report
    assert "Tarifa 85168080" in report
    assert "PIP FOOD GROUP DOO" in report
    assert "Pouzdanost: 91%." in report


def test_copy_last_agent_message_without_messages_does_not_crash(qtbot):
    panel = ChatPanel()
    qtbot.addWidget(panel)

    # Samo welcome poruka je prikazana (ne preko add_agent_message) — nema sta kopirati,
    # ne smije baciti izuzetak.
    panel._copy_last_agent_message()
