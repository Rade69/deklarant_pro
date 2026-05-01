from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

# Docs: docs/sections/window-geometry-modal-guard.md


def _message_parent(parent: QWidget | None) -> QWidget | None:
    if parent is None:
        return None
    win = parent.window()
    return win if win else parent


def _preserve_geometry(parent: QWidget | None, callback: Callable[[], Any]) -> Any:
    state = capture_window_geometry(parent)
    if state is None:
        return callback()

    try:
        return callback()
    finally:
        restore_window_geometry(state)


def capture_window_geometry(parent: QWidget | None) -> tuple[QWidget, bool, Any, Any] | None:
    win = _message_parent(parent)
    if win is None:
        return None
    return win, win.isMaximized(), win.geometry(), win.windowState()


def restore_window_geometry(state: tuple[QWidget, bool, Any, Any] | None) -> None:
    if state is None:
        return
    win, was_maximized, geom, captured_state = state
    if win.isMinimized() or win.windowState() & Qt.WindowState.WindowMinimized:
        return
    current_maximized = bool(win.windowState() & Qt.WindowState.WindowMaximized)
    captured_maximized = bool(captured_state & Qt.WindowState.WindowMaximized)
    if current_maximized != captured_maximized:
        return
    if was_maximized:
        return
    else:
        win.setGeometry(geom)


def restore_window_geometry_queued(state: tuple[QWidget, bool, Any, Any] | None) -> None:
    restore_window_geometry(state)
    for delay_ms in (0, 50):
        QTimer.singleShot(delay_ms, lambda state=state: restore_window_geometry(state))


def exec_dialog_preserving_geometry(dialog: Any, parent: QWidget | None = None) -> int:
    state = capture_window_geometry(parent or dialog.parentWidget())
    try:
        return dialog.exec()
    finally:
        restore_window_geometry_queued(state)


def show_dialog_preserving_geometry(dialog: Any, parent: QWidget | None = None) -> None:
    state = capture_window_geometry(parent or dialog.parentWidget())
    dialog.show()
    restore_window_geometry_queued(state)


class SafeMessageBox(QMessageBox):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args and isinstance(args[0], QWidget):
            args = (_message_parent(args[0]), *args[1:])
        elif "parent" in kwargs:
            kwargs["parent"] = _message_parent(kwargs["parent"])
        super().__init__(*args, **kwargs)

    def exec(self) -> int:
        return _preserve_geometry(self.parentWidget(), super().exec)

    @staticmethod
    def information(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> QMessageBox.StandardButton:
        return _preserve_geometry(
            parent,
            lambda: QMessageBox.information(_message_parent(parent), title, text, *args, **kwargs),
        )

    @staticmethod
    def warning(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> QMessageBox.StandardButton:
        return _preserve_geometry(
            parent,
            lambda: QMessageBox.warning(_message_parent(parent), title, text, *args, **kwargs),
        )

    @staticmethod
    def critical(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> QMessageBox.StandardButton:
        return _preserve_geometry(
            parent,
            lambda: QMessageBox.critical(_message_parent(parent), title, text, *args, **kwargs),
        )

    @staticmethod
    def question(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> QMessageBox.StandardButton:
        return _preserve_geometry(
            parent,
            lambda: QMessageBox.question(_message_parent(parent), title, text, *args, **kwargs),
        )

    @staticmethod
    def about(parent: QWidget | None, title: str, text: str) -> None:
        return _preserve_geometry(
            parent,
            lambda: QMessageBox.about(_message_parent(parent), title, text),
        )
