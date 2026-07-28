from __future__ import annotations

import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

ProcessOutcome = Literal["success", "warning", "error"]

_ALIASES: dict[ProcessOutcome, str] = {
    "success": "SystemAsterisk",
    "warning": "SystemExclamation",
    "error": "SystemHand",
}
_FALSE_VALUES = {"0", "false", "no", "off"}


def play_process_completion_sound(outcome: ProcessOutcome = "success") -> bool:
    enabled = os.getenv("PROCESS_COMPLETION_SOUND", "true").strip().lower()
    if enabled in _FALSE_VALUES:
        return False

    alias = _ALIASES.get(outcome, _ALIASES["success"])
    try:
        import winsound

        flags = winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        winsound.PlaySound(alias, flags)
        return True
    except (ImportError, RuntimeError, OSError, AttributeError):
        logger.debug("Windows process completion sound is unavailable", exc_info=True)
        return False
