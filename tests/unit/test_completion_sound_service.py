import sys
from types import SimpleNamespace
from unittest.mock import Mock

from services.admin.settings_service import SettingsService
from services.completion_sound_service import CompletionSound, play_completion_sound


def test_completion_sound_default_and_validation():
    defaults = SettingsService.DEFAULT_SETTINGS

    assert defaults["completion_sounds_enabled"] is True
    assert SettingsService.validate_settings(
        object.__new__(SettingsService),
        {**defaults, "completion_sounds_enabled": False},
    )
    assert not SettingsService.validate_settings(
        object.__new__(SettingsService),
        {**defaults, "completion_sounds_enabled": "da"},
    )


def test_disabled_setting_ne_pusta_zvuk(monkeypatch):
    play_sound = Mock()
    fake_winsound = SimpleNamespace(
        PlaySound=play_sound,
        SND_ALIAS=1,
        SND_ASYNC=2,
        SND_NODEFAULT=4,
    )
    monkeypatch.setitem(sys.modules, "winsound", fake_winsound)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(SettingsService, "get_setting", lambda *args: False)

    assert play_completion_sound(CompletionSound.SUCCESS) is False
    play_sound.assert_not_called()


def test_windows_koristi_razlicite_sistemske_zvukove(monkeypatch):
    play_sound = Mock()
    fake_winsound = SimpleNamespace(
        PlaySound=play_sound,
        SND_ALIAS=1,
        SND_ASYNC=2,
        SND_NODEFAULT=4,
    )
    monkeypatch.setitem(sys.modules, "winsound", fake_winsound)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(SettingsService, "get_setting", lambda *args: True)

    assert play_completion_sound(CompletionSound.SUCCESS)
    assert play_completion_sound(CompletionSound.ATTENTION)
    assert play_completion_sound(CompletionSound.ERROR)

    aliases = [call.args[0] for call in play_sound.call_args_list]
    assert aliases == ["SystemAsterisk", "SystemExclamation", "SystemHand"]
    assert all(call.args[1] == 7 for call in play_sound.call_args_list)


def test_greska_zvuka_ne_prekida_proces(monkeypatch):
    fake_winsound = SimpleNamespace(
        PlaySound=Mock(side_effect=RuntimeError("audio nije dostupan")),
        SND_ALIAS=1,
        SND_ASYNC=2,
        SND_NODEFAULT=4,
    )
    monkeypatch.setitem(sys.modules, "winsound", fake_winsound)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(SettingsService, "get_setting", lambda *args: True)

    assert play_completion_sound(CompletionSound.ERROR) is False


def test_settings_panel_ucitava_i_emituje_postavku(qtbot):
    from gui.tabs.admin.panels.settings_panel import SettingsPanel

    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.set_settings({"completion_sounds_enabled": False})
    emitted = []
    panel.save_requested.connect(emitted.append)

    panel._on_save_clicked()

    assert panel.completion_sounds_check.isChecked() is False
    assert emitted[0]["completion_sounds_enabled"] is False
