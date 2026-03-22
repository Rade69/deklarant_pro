# AGENT TAB - CORRECTION PROMPT (Ispravi Postojeće)

**Za Claude Code: Modifikuj postojeći Agent Tab da odgovara dizajnu iz novi_gui_agent.png**

---

## CILJ

**NE PRAVI SVE ISPOČETKA!** 

Umjesto toga:
1. ✅ **ZADRŽI** ono što već radi (upload area, file table, header)
2. ➕ **DODAJ** ono što nedostaje (chat panel desno, split view)
3. 🔧 **IZMIJENI** ono što je pogrešno (tabovi na pogrešnom mjestu)

---

## TRENUTNO STANJE (iz screenshot-a)

```
┌─────────────────────────────────────────────────────┐
│ Status | Parser | Sesija                             │
├─────────────────────────────────────────────────────┤
│ Description text                                    │
├─────────────────────────────────────────────────────┤
│ 📋 DOKUMENTI          [Agent][Aktivnosti][?] ← ❌   │
│                                                     │
│  📁 Prevuci fajlove ovdje                           │
│  [Odaberi fajlove] [Pokreni analizu]               │
│                                                     │
│  [File table]                                       │
│                                                     │
│  (Cijeli prostor je samo dokumenti panel!)         │
└─────────────────────────────────────────────────────┘
```

**Problemi:**
- ❌ Tabovi su GORE u dokumenti header-u (pogrešno!)
- ❌ Nema chat panela DESNO
- ❌ Nema split view-a

---

## ŽELJENO STANJE (iz novi_gui_agent.png)

```
┌────────────────────────────────────────────────────────────┐
│ Status | Parser | Sesija                                    │
├────────────────────────────────────────────────────────────┤
│ Description text                                           │
├──────────────────────────────┬─────────────────────────────┤
│ 📋 DOKUMENTI                 │ [Agent][Aktivnosti][Pitanja]│ ← Tabovi OVDJE!
│                              │ ─────────────────────────── │
│  📁 Prevuci fajlove...       │                             │
│  [Buttoni]                   │ 🤖 Agent: 09:21            │
│                              │ Pozdrav! Ja sam AI Agent... │
│  [File table]                │                             │
│                              │ Mogu ti pomoći sa:          │
│  [Inline rezultati]          │ • Automatsko popunjavanje...│
│                              │                             │
│                              │ [Postavi pitanje...] [🚀]  │
└──────────────────────────────┴─────────────────────────────┘
      ↑ 70% lijevo                    ↑ 30% desno
```

---

## MODIFIKACIJE - STEP BY STEP

### ⚠️ KRITIČNO: Čitaj pažljivo svaki step!

---

## STEP 1: PRONAĐI POSTOJEĆE FAJLOVE

Provjeri da li postoje:
```
gui/tabs/agent/agent_view.py          ← Main view (MORA postojati)
gui/tabs/agent/agent_controller.py    ← Controller (možda postoji)
gui/tabs/agent/widgets/               ← Folder sa widgetima
```

**Ako NE POSTOJE ovi fajlovi, onda reci "Fajlovi ne postoje - trebam kreirati sve novo"**

**Ako POSTOJE, nastavi sa modifikacijama:**

---

## STEP 2: MODIFIKUJ agent_view.py - DODAJ SPLIT VIEW

**Fajl:** `gui/tabs/agent/agent_view.py`

### Trenutno ima (vjerovatno):

```python
class AgentView(QWidget):
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        self.header = HeaderBar()
        layout.addWidget(self.header)
        
        # Description
        desc = ...
        layout.addWidget(desc)
        
        # Document panel (samo ovo, bez chat-a!)
        self.document_panel = DocumentPanel()
        layout.addWidget(self.document_panel)  # ← PROBLEM!
```

### ⚠️ IZMIJENI NA OVO:

```python
class AgentView(QWidget):
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header (ZADRŽI postojeći!)
        self.header = HeaderBar()
        layout.addWidget(self.header)
        
        # Description (ZADRŽI postojeći!)
        desc = self._create_description()
        layout.addWidget(desc)
        
        # ═══════════════════════════════════════════════════════
        # KLJUČNA IZMJENA - DODAJ QSPLITTER!
        # ═══════════════════════════════════════════════════════
        
        from PySide6.QtWidgets import QSplitter
        from PySide6.QtCore import Qt
        
        splitter = QSplitter(Qt.Horizontal)  # ← HORIZONTAL = lijevo/desno
        
        # Lijevi panel - Document panel (VEĆ POSTOJI - samo ga preusmjeri!)
        self.document_panel = DocumentPanel()
        splitter.addWidget(self.document_panel)
        
        # Desni panel - Chat panel (NOVI - mora se kreirati!)
        self.chat_panel = self._create_chat_panel()
        splitter.addWidget(self.chat_panel)
        
        # Postavi početne širine: 70% lijevo, 30% desno
        splitter.setStretchFactor(0, 7)  # Document panel
        splitter.setStretchFactor(1, 3)  # Chat panel
        
        # Dodaj splitter u layout (umjesto samo document_panel-a!)
        layout.addWidget(splitter)
        
        # ═══════════════════════════════════════════════════════
```

### ➕ DODAJ NOVU METODU - _create_chat_panel:

```python
def _create_chat_panel(self) -> QWidget:
    """
    Kreiraj chat panel sa tabovima.
    
    ⚠️ VAŽNO: Tabovi moraju biti OVDJE, ne u document panelu!
    """
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QTabWidget, QTextEdit,
        QLineEdit, QPushButton, QHBoxLayout, QLabel
    )
    from PySide6.QtCore import QDateTime
    import qtawesome as qta
    
    # Main widget
    chat_widget = QWidget()
    layout = QVBoxLayout(chat_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    
    # ═══════════════════════════════════════════════════════
    # TAB WIDGET - OVDJE su tabovi [Agent][Aktivnosti][Pitanja]
    # ═══════════════════════════════════════════════════════
    
    tabs = QTabWidget()
    tabs.setStyleSheet("""
        QTabWidget::pane {
            border: 1px solid #ddd;
            background-color: white;
        }
        QTabBar::tab {
            background-color: #f8f9fa;
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid #ddd;
            border-bottom: none;
            min-width: 80px;
        }
        QTabBar::tab:selected {
            background-color: white;
            color: #0078d4;
            font-weight: bold;
        }
        QTabBar::tab:hover {
            background-color: #e9ecef;
        }
    """)
    
    # Agent tab - glavni chat
    agent_view = QTextEdit()
    agent_view.setReadOnly(True)
    agent_view.setStyleSheet("""
        QTextEdit {
            background-color: white;
            border: none;
            padding: 10px;
            font-size: 13px;
        }
    """)
    
    # Welcome message
    timestamp = QDateTime.currentDateTime().toString("HH:mm")
    welcome_msg = f"""
    <div style="margin: 10px 0; padding: 10px; background-color: #e3f2fd; 
                border-left: 3px solid #0078d4; border-radius: 4px;">
        <div style="font-size: 11px; color: #666; margin-bottom: 5px;">
            🤖 <b>Agent</b> · {timestamp}
        </div>
        <div>
            Pozdrav! Ja sam AI Agent za procesiranje faktura.<br><br>
            Mogu ti pomoći sa:<br>
            • Automatsko popunjavanje tarifnih brojeva<br>
            • Identifikacijom proizvoda<br>
            • Validacijom podataka<br><br>
            Pošaljite pitanja ili prevucite fakture u upload panel.
        </div>
    </div>
    """
    agent_view.setHtml(welcome_msg)
    
    tabs.addTab(agent_view, qta.icon('fa5s.robot', color='#0078d4'), " Agent")
    
    # Aktivnosti tab - activity log
    aktivnosti_view = QTextEdit()
    aktivnosti_view.setReadOnly(True)
    aktivnosti_view.setStyleSheet("""
        QTextEdit {
            background-color: #f8f9fa;
            border: none;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
        }
    """)
    tabs.addTab(aktivnosti_view, qta.icon('fa5s.list', color='#0078d4'), " Aktivnosti")
    
    # Pitanja tab - FAQ
    pitanja_widget = QWidget()
    pitanja_layout = QVBoxLayout(pitanja_widget)
    faq_label = QLabel("""
    <h3>Često postavljana pitanja</h3>
    
    <p><b>Q: Koliko fajlova mogu uploadovati?</b><br>
    A: Do 50 faktura odjednom.</p>
    
    <p><b>Q: Koje formate podržava?</b><br>
    A: PDF, Excel (.xlsx, .xls) i XML.</p>
    
    <p><b>Q: Šta znači "Potrebna potvrda"?</b><br>
    A: Agent nije siguran (< 80% confidence).</p>
    """)
    faq_label.setWordWrap(True)
    faq_label.setTextFormat(Qt.RichText)
    faq_label.setStyleSheet("padding: 10px; color: #333;")
    pitanja_layout.addWidget(faq_label)
    pitanja_layout.addStretch()
    
    tabs.addTab(pitanja_widget, qta.icon('fa5s.question-circle', color='#0078d4'), " Pitanja")
    
    layout.addWidget(tabs)
    
    # ═══════════════════════════════════════════════════════
    # INPUT AREA - chat input field sa send buttonom
    # ═══════════════════════════════════════════════════════
    
    input_widget = QWidget()
    input_layout = QHBoxLayout(input_widget)
    input_layout.setContentsMargins(10, 5, 10, 10)
    
    input_field = QLineEdit()
    input_field.setPlaceholderText("Postavi pitanje...")
    input_field.setStyleSheet("""
        QLineEdit {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 13px;
        }
        QLineEdit:focus {
            border-color: #0078d4;
        }
    """)
    
    send_btn = QPushButton(qta.icon('fa5s.paper-plane', color='white'), "")
    send_btn.setFixedSize(36, 36)
    send_btn.setToolTip("Pošalji (Enter)")
    send_btn.setStyleSheet("""
        QPushButton {
            background-color: #0078d4;
            border: none;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #0056b3;
        }
    """)
    
    input_layout.addWidget(input_field)
    input_layout.addWidget(send_btn)
    
    layout.addWidget(input_widget)
    
    # Store references za kasnije
    self.chat_agent_view = agent_view
    self.chat_aktivnosti_view = aktivnosti_view
    self.chat_input_field = input_field
    self.chat_tabs = tabs
    
    return chat_widget
```

---

## STEP 3: UKLONI TABOVE IZ DOCUMENT PANELA

**Fajl:** `gui/tabs/agent/widgets/document_panel.py` (ili gdje god je definisan)

### Pronađi ovaj kod:

```python
# Možda ima nešto kao:
header_layout.addWidget(QLabel("📋 DOKUMENTI"))
header_layout.addWidget(tabs)  # ← PROBLEM! Tabovi su ovdje!
```

### ⚠️ UKLONI tabove iz document panel header-a:

```python
# Samo label, BEZ tabova!
header = QLabel("📋 DOKUMENTI")
header.setStyleSheet("""
    font-size: 15px;
    font-weight: bold;
    color: #333;
    padding: 10px;
    background-color: white;
    border-bottom: 1px solid #ddd;
""")

# NE DODAVAJ tabove ovdje! Oni su sada u chat panelu!
```

---

## STEP 4: (OPCIONO) DODAJ RESULTS VIEWER

**Ako već ne postoji inline rezultat viewer:**

**Fajl:** `gui/tabs/agent/widgets/document_panel.py`

### Dodaj na dno document_panel layout-a:

```python
# U _setup_ui metodi DocumentPanel-a:

# ... nakon file_table ...

# Results viewer (inline)
from PySide6.QtWidgets import QGroupBox, QGridLayout

self.results_group = QGroupBox("📋 Rezultati obrade za:")
self.results_group.setStyleSheet("""
    QGroupBox {
        font-weight: bold;
        border: 1px solid #ddd;
        border-radius: 4px;
        margin-top: 10px;
        padding-top: 10px;
        background-color: white;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: #0078d4;
    }
""")

results_layout = QGridLayout()

# Labels
lbl_faktura = QLabel("Faktura br.:")
lbl_faktura.setStyleSheet("font-weight: bold; color: #666;")
val_faktura = QLabel("12345")

lbl_datum = QLabel("Datum:")
lbl_datum.setStyleSheet("font-weight: bold; color: #666;")
val_datum = QLabel("23.04.2024")

lbl_tarif = QLabel("Tarif broj:")
lbl_tarif.setStyleSheet("font-weight: bold; color: #666;")
val_tarif = QLabel("1209.2900 ⚠️ Potrebna potvrda")
val_tarif.setStyleSheet("color: #ffc107; font-weight: bold;")

lbl_iznos = QLabel("Iznos:")
lbl_iznos.setStyleSheet("font-weight: bold; color: #666;")
val_iznos = QLabel("1,250.00 HRK")

# Grid layout
results_layout.addWidget(lbl_faktura, 0, 0)
results_layout.addWidget(val_faktura, 0, 1)
results_layout.addWidget(lbl_tarif, 0, 3)
results_layout.addWidget(val_tarif, 0, 4)

results_layout.addWidget(lbl_datum, 1, 0)
results_layout.addWidget(val_datum, 1, 1)

results_layout.addWidget(lbl_iznos, 2, 0)
results_layout.addWidget(val_iznos, 2, 1)

self.results_group.setLayout(results_layout)
self.results_group.hide()  # Sakriven dok ne odabereš fajl

# Dodaj u main layout
layout.addWidget(self.results_group)
```

---

## STEP 5: TESTIRANJE - ⚠️ KRITIČNO!

### Nakon modifikacija, pokreni app:

```bash
python __main__.py
```

### ✅ PROVJERI DA LI VIDIŠ:

```
□ Split view (lijevo | desno)?
□ Dokumenti panel LIJEVO?
□ Chat panel DESNO?
□ Tabove [Agent][Aktivnosti][Pitanja] UNUTAR chat panela (desno gore)?
□ Welcome message u Agent tab-u?
□ Input field sa send buttonom u chat panelu?
□ Upload area i file table LIJEVO?
□ Možeš li drag-ovati splitter (resize između panela)?
```

### ❌ Ako NE vidiš split view:

**Debug:**
```python
# Dodaj print statements u agent_view.py
print(f"Document panel created: {self.document_panel}")
print(f"Chat panel created: {self.chat_panel}")
print(f"Splitter children: {splitter.count()}")  # Mora biti 2!
```

---

## STEP 6: FIX SIGNALI (ako trebaju)

### Ako chat input field treba da šalje poruke:

**U agent_controller.py:**

```python
def _connect_signals(self):
    # ... postojeći signali ...
    
    # Chat input
    if hasattr(self.view, 'chat_input_field'):
        self.view.chat_input_field.returnPressed.connect(self._on_chat_message)

def _on_chat_message(self):
    """Handle chat message."""
    message = self.view.chat_input_field.text().strip()
    
    if not message:
        return
    
    # Add user message to chat
    timestamp = QDateTime.currentDateTime().toString("HH:mm")
    user_msg = f"""
    <div style="margin: 10px 0; padding: 10px; background-color: #f0f0f0; 
                border-left: 3px solid #28a745; border-radius: 4px;">
        <div style="font-size: 11px; color: #666; margin-bottom: 5px;">
            👤 <b>Vi</b> · {timestamp}
        </div>
        <div>{message}</div>
    </div>
    """
    self.view.chat_agent_view.append(user_msg)
    
    # Clear input
    self.view.chat_input_field.clear()
    
    # TODO: Send to AI agent
    # For now - echo back
    agent_msg = f"""
    <div style="margin: 10px 0; padding: 10px; background-color: #e3f2fd; 
                border-left: 3px solid #0078d4; border-radius: 4px;">
        <div style="font-size: 11px; color: #666; margin-bottom: 5px;">
            🤖 <b>Agent</b> · {timestamp}
        </div>
        <div>Razumijem: "{message}". Trenutno učim kako odgovoriti! 🤖</div>
    </div>
    """
    self.view.chat_agent_view.append(agent_msg)
```

---

## COMMIT

```bash
git add gui/tabs/agent/agent_view.py
git add gui/tabs/agent/widgets/document_panel.py
git add gui/tabs/agent/agent_controller.py
git commit -m "Agent Tab: Fix layout - add split view with chat panel

Changes:
- Added QSplitter horizontal layout (70% documents, 30% chat)
- Moved tabs FROM document header TO chat panel
- Created chat panel with Agent/Aktivnosti/Pitanja tabs
- Added welcome message in Agent tab
- Added chat input field with send button
- Added inline results viewer (optional)

Fixed issues:
- Tabs were in wrong location (document header instead of chat)
- Chat panel was missing entirely
- No split view layout

Now matches design from novi_gui_agent.png!
"
```

---

## FINALNA PROVJERA - SLIKAJ I UPOREDI!

### Tvoj screenshot SADA treba izgledati:

```
┌──────────────────────────────┬─────────────────────┐
│ 📋 DOKUMENTI                 │ [Agent][Akt.][Pit.] │ ← Tabovi OVDJE!
│                              │ ─────────────────── │
│  📁 Prevuci fajlove...       │ 🤖 Agent: ...       │
│  [Buttoni]                   │ Pozdrav!...         │
│                              │                     │
│  [File table]                │ [Pitanje...] [🚀]  │
└──────────────────────────────┴─────────────────────┘
```

### Uporedi sa novi_gui_agent.png!

---

## NAPOMENE

1. **ZADRŽI SVE ŠTO RADI** - ne diraj upload area, file table, header ako rade!
2. **DODAJ samo chat panel** sa QSplitter-om
3. **PREMJESTI tabove** iz document panela u chat panel
4. **TESTIRAJ nakon svake izmjene!**

---

**KRAJ CORRECTION PROMPT-A!** 🚀

**Ovo je MNOGO SIGURNIJI pristup** - modifikuješ postojeće umjesto pravljenja svega novo! 💯
