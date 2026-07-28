from __future__ import annotations

import sys
from types import SimpleNamespace

from services.process_completion_sound import play_process_completion_sound


def _fake_winsound():
    calls = []
    module = SimpleNamespace(
        SND_ALIAS=1,
        SND_ASYNC=2,
        SND_NODEFAULT=4,
        PlaySound=lambda alias, flags: calls.append((alias, flags)),
    )
    return module, calls


def test_success_sound_is_async_windows_alias(monkeypatch):
    winsound, calls = _fake_winsound()
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    monkeypatch.delenv("PROCESS_COMPLETION_SOUND", raising=False)

    assert play_process_completion_sound("success") is True
    assert calls == [("SystemAsterisk", 7)]


def test_warning_and_error_use_distinct_aliases(monkeypatch):
    winsound, calls = _fake_winsound()
    monkeypatch.setitem(sys.modules, "winsound", winsound)

    assert play_process_completion_sound("warning") is True
    assert play_process_completion_sound("error") is True
    assert calls == [
        ("SystemExclamation", 7),
        ("SystemHand", 7),
    ]


def test_sound_can_be_disabled_from_environment(monkeypatch):
    winsound, calls = _fake_winsound()
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    monkeypatch.setenv("PROCESS_COMPLETION_SOUND", "false")

    assert play_process_completion_sound("success") is False
    assert calls == []


def test_unavailable_windows_sound_never_breaks_process(monkeypatch):
    winsound, _calls = _fake_winsound()

    def fail(_alias, _flags):
        raise RuntimeError("sound device unavailable")

    winsound.PlaySound = fail
    monkeypatch.setitem(sys.modules, "winsound", winsound)

    assert play_process_completion_sound("success") is False
