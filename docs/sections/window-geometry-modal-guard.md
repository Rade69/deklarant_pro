# Window geometry modal guard

## Problem

Qt može promijeniti veličinu glavnog prozora nakon zatvaranja modalnog dijaloga ako je dijalog otvoren iz child taba ili ako se poslije potvrde pokrene reload većeg dijela UI-ja.

U praksi se problem pojavio u:
- Zaglavlje XML import/validacija/export tokovima
- Faktura kreiranje naimenovanja poslije potvrde
- direktnim `QMessageBox(self, ...)` i `QDialog.exec()` pozivima iz child widgeta

## Rješenje

`gui/utils/safe_message_box.py` centralizuje:
- parent za poruke preko top-level `window()`
- čuvanje i vraćanje geometrije oko `QMessageBox`
- zaštitu oko `QDialog.exec()` i `QDialog.show()`
- queued restore poslije Qt relayout tick-a

Guard ne smije forsirati geometriju ako je prozor minimiziran ili ako je korisnik u međuvremenu promijenio maximize state. To sprečava kvarenje normalnog maximize/minimize ponašanja.

## Pravilo za novi kod

Za poruke koristi:
```python
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox
```

Za modalne dijaloge koji rade `exec()` iz taba koristi:
```python
from gui.utils.safe_message_box import exec_dialog_preserving_geometry

result = exec_dialog_preserving_geometry(dialog, self)
```

Za ne-modalni `show()` koristi:
```python
from gui.utils.safe_message_box import show_dialog_preserving_geometry

show_dialog_preserving_geometry(dialog, self)
```

Ako akcija poslije potvrde radi veći UI reload, uhvati cijeli tok:
```python
from gui.utils.safe_message_box import capture_window_geometry, restore_window_geometry_queued

state = capture_window_geometry(self)
try:
    ...
finally:
    restore_window_geometry_queued(state)
```
