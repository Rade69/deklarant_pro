from __future__ import annotations

import logging
import math
import os
import struct
import wave
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

ProcessOutcome = Literal["success", "warning", "error"]

_TONE_PATTERNS: dict[ProcessOutcome, tuple[int, ...]] = {
    "success": (660, 880),
    "warning": (740, 520),
    "error": (440, 300),
}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _settings_enabled() -> bool:
    try:
        from services.admin.settings_service import SettingsService

        return bool(SettingsService().get_setting("completion_sound_enabled", True))
    except Exception:
        logger.debug("Sound setting is unavailable", exc_info=True)
        return True


def _ensure_sound_file(outcome: ProcessOutcome) -> Path:
    sound_dir = Path.home() / ".deklarant_pro" / "sounds"
    sound_dir.mkdir(parents=True, exist_ok=True)
    path = sound_dir / f"process_{outcome}.wav"
    if path.exists() and path.stat().st_size > 44:
        return path

    sample_rate = 44100
    tone_duration = 0.16
    pause_duration = 0.035
    frames = bytearray()
    pattern = _TONE_PATTERNS[outcome]
    for index, frequency in enumerate(pattern):
        sample_count = int(sample_rate * tone_duration)
        for sample_index in range(sample_count):
            fade = min(sample_index / 500, (sample_count - sample_index) / 500, 1.0)
            value = int(
                18000 * 0.35
                * max(fade, 0.0)
                * math.sin(2 * math.pi * frequency * sample_index / sample_rate)
            )
            frames.extend(struct.pack("<h", value))
        if index < len(pattern) - 1:
            frames.extend(b"\x00\x00" * int(sample_rate * pause_duration))

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
    return path


def play_process_completion_sound(
    outcome: ProcessOutcome = "success",
    *,
    force: bool = False,
) -> bool:
    enabled = os.getenv("PROCESS_COMPLETION_SOUND", "true").strip().lower()
    if not force and (enabled in _FALSE_VALUES or not _settings_enabled()):
        return False

    normalized_outcome = outcome if outcome in _TONE_PATTERNS else "success"
    try:
        import winsound

        sound_path = _ensure_sound_file(normalized_outcome)
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        winsound.PlaySound(str(sound_path), flags)
        return True
    except (ImportError, RuntimeError, OSError, AttributeError, wave.Error):
        logger.debug("Windows process completion sound is unavailable", exc_info=True)
        return False
