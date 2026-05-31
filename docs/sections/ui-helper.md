# UIHelper

## Svrha
Factory za UI komponente sa dosljednim stilom kroz cijelu aplikaciju.
Kreira dugmad sa QtAwesome ikonicama i objectName-ima koji se mapiraju
na unified_color_system.qss paletu.

## Zavisnosti i pretpostavke
- PySide6 (QtWidgets, QtCore, QtGui)
- QtAwesome (optional) — bez njega dugmad nemaju ikonice ali rade
- `unified_color_system.qss` mora biti učitan u aplikaciji

## Pravila i granice
- `BUTTON_OBJECT_NAMES` mapira style_class → QSS objectName
  - `success` → `btnDodaj` (zelena)
  - `danger` → `btnObrisi` (crvena)
  - `default` → `btnSnimi` (zelena)
  - `primary` → prazan string (default plava)
- `create_action_buttons()` uvijek kreira par (✏️ Uredi, 🗑️ Obriši)
- Ne mijenjati objectName-ve bez ažuriranja QSS fajla
- `create_styled_button` dodaje razmak ispred teksta ako ima ikonicu

## Zašto ovako
Dugmad su bila inline u svakom View-u sa dupliciranim stilovima.
Izdvajanjem je osigurano da svi tabovi koriste iste boje i ikonice.
Alternativa: QSS samo bez helper-a — odbijeno jer bi zahtijevalo
ručno setovanje objectName na svakom dugmetu.
Provjera: dugme "Novi" mora biti zeleno sa ikonicom plus.
