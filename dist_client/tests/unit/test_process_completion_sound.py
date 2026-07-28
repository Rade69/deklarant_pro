from __future__ import annotations

import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import services.process_completion_sound as sound_service


def _fake_winsound():
    calls = []
    module = SimpleNamespace(
        SND_FILENAME=1,
        SND_ASYNC=2,
        SND_NODEFAULT=4,
        PlaySound=lambda filename, flags: calls.append((filename, flags)),
    )
    return module, calls


def test_success_sound_uses_async_wav_file(monkeypatch, tmp_path):
    winsound, calls = _fake_winsound()
    sound_path = tmp_path / "success.wav"
    sound_path.write_bytes(b"RIFF-test")
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    monkeypatch.setattr(sound_service, "_settings_enabled", lambda: True)
    monkeypatch.setattr(sound_service, "_ensure_sound_file", lambda _outcome: sound_path)
    monkeypatch.delenv("PROCESS_COMPLETION_SOUND", raising=False)

    assert sound_service.play_process_completion_sound("success") is True
    assert calls == [(str(sound_path), 7)]


def test_generated_outcomes_use_distinct_valid_wav_files(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    paths = [
        sound_service._ensure_sound_file(outcome)
        for outcome in ("success", "warning", "error")
    ]

    assert len(set(paths)) == 3
    for path in paths:
        with wave.open(str(path), "rb") as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getframerate() == 44100
            assert wav_file.getnframes() > 0


def test_sound_can_be_disabled_from_admin_setting(monkeypatch):
    winsound, calls = _fake_winsound()
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    monkeypatch.setattr(sound_service, "_settings_enabled", lambda: False)
    monkeypatch.delenv("PROCESS_COMPLETION_SOUND", raising=False)

    assert sound_service.play_process_completion_sound("success") is False
    assert calls == []


def test_forced_test_sound_bypasses_disabled_setting(monkeypatch, tmp_path):
    winsound, calls = _fake_winsound()
    sound_path = tmp_path / "success.wav"
    sound_path.write_bytes(b"RIFF-test")
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    monkeypatch.setattr(sound_service, "_settings_enabled", lambda: False)
    monkeypatch.setattr(sound_service, "_ensure_sound_file", lambda _outcome: sound_path)

    assert sound_service.play_process_completion_sound("success", force=True) is True
    assert calls == [(str(sound_path), 7)]


def test_unavailable_windows_sound_never_breaks_process(monkeypatch, tmp_path):
    winsound, _calls = _fake_winsound()
    sound_path = tmp_path / "success.wav"
    sound_path.write_bytes(b"RIFF-test")

    def fail(_filename, _flags):
        raise RuntimeError("sound device unavailable")

    winsound.PlaySound = fail
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    monkeypatch.setattr(sound_service, "_settings_enabled", lambda: True)
    monkeypatch.setattr(sound_service, "_ensure_sound_file", lambda _outcome: sound_path)

    assert sound_service.play_process_completion_sound("success") is False
