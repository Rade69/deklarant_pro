from unittest.mock import MagicMock

from gui.tabs.admin.admin_controller import AdminController
from gui.tabs.admin.panels.settings_panel import SettingsPanel
from services.admin.settings_service import SettingsService


def test_sound_setting_is_enabled_by_default():
    service = SettingsService.__new__(SettingsService)

    assert service.get_default_settings()["completion_sound_enabled"] is True
    assert service.validate_settings({"completion_sound_enabled": True}) is True
    assert service.validate_settings({"completion_sound_enabled": "yes"}) is False


def test_settings_panel_emits_sound_setting(qtbot):
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.completion_sound_check.setChecked(False)

    with qtbot.waitSignal(panel.save_requested) as signal:
        panel.btn_save.click()

    assert signal.args[0]["completion_sound_enabled"] is False


def test_settings_panel_exposes_test_sound_action(qtbot):
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.test_sound_requested):
        panel.btn_test_sound.click()


def test_admin_controller_connects_and_loads_settings():
    controller = AdminController.__new__(AdminController)
    controller.view = MagicMock()
    controller.service = MagicMock()
    settings_panel = controller.view.get_settings_panel.return_value
    controller.service.get_settings.return_value = {"completion_sound_enabled": False}

    controller._connect_signals()
    controller._load_initial_data()

    settings_panel.save_requested.connect.assert_called_once_with(
        controller._on_save_settings
    )
    settings_panel.reset_requested.connect.assert_called_once_with(
        controller._on_reset_settings
    )
    settings_panel.test_sound_requested.connect.assert_called_once_with(
        controller._on_test_sound
    )
    settings_panel.set_settings.assert_called_once_with(
        {"completion_sound_enabled": False}
    )
