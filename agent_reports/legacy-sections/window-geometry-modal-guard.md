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
- `QMessageBox` API koji ne koristi child tab kao parent
- wrapper-e za `QDialog.exec()` i `QDialog.show()` da novi kod ima jedno mjesto za modalne tokove

Top-level prozor (`MainWindow`) mora imati razuman `setMinimumSize(...)`. To je stabilniji guard od nasilnog `setGeometry()` poslije modala, jer ne kvari normalno maximize/minimize ponašanje.

Ne forsirati `setGeometry()` ili `showMaximized()` poslije modala. Taj pristup može pregaziti window state ako korisnik u međuvremenu minimizira ili maksimizira prozor.

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

Ovi helperi su zadržani radi postojećih poziva, ali ne smiju agresivno vraćati geometriju. Primarni guard je top-level parent za modal + minimum size glavnog prozora.
