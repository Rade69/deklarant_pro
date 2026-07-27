import logging
import sys
from enum import Enum

logger = logging.getLogger(__name__)


class CompletionSound(str, Enum):
    SUCCESS = "success"
    ATTENTION = "attention"
    ERROR = "error"


_WINDOWS_ALIASES = {
    CompletionSound.SUCCESS: "SystemAsterisk",
    CompletionSound.ATTENTION: "SystemExclamation",
    CompletionSound.ERROR: "SystemHand",
}


def play_completion_sound(sound: CompletionSound = CompletionSound.SUCCESS) -> bool:
    from services.admin.settings_service import SettingsService

    if not SettingsService().get_setting("completion_sounds_enabled", True):
        return False

    try:
        if sys.platform == "win32":
            import winsound

            winsound.PlaySound(
                _WINDOWS_ALIASES[sound],
                winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        else:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                return False
            app.beep()
        return True
    except Exception as exc:
        logger.warning("⚠️ Zvuk završetka procesa nije moguće reprodukovati: %s", exc)
        return False
