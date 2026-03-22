# 🎨 Nerd Font Instalacija - ASYCUDA Pro

**Datum:** 2026-03-22  
**Status:** ✅ Završeno

---

## 📦 Instalirani Font

**JetBrainsMono Nerd Font** - verzija 3.3.0

### Lokacije:
- **Korisnički fontovi:** `~/.fonts/` (kopirani .ttf fajlovi)
- **Original:** `~/.local/share/fonts/jetbrains-mono-nerd/`

---

## ⚙️ Konfiguracija Terminala

### GNOME Terminal (Trenutni)
```bash
# Postavi font
gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrainsMono Nerd Font 11'

# Provjeri trenutni font
gsettings get org.gnome.desktop.interface monospace-font-name
```

**Trenutna postavka:** `JetBrainsMono Nerd Font 11`

---

## 🧪 Testiranje Ikonica

### Emoji Test
```
📁 📂 📄 ✅ ❌ ⚠️ 🔍 📝 🎯 🚀
```

### Nerd Font Glyphs Test
```bash
# Pokreni u terminalu
echo "         "
```

### Dostupni Font Varijanti
- `JetBrainsMono Nerd Font` - Standardna verzija
- `JetBrainsMono Nerd Font Mono` - Fiksna širina
- `JetBrainsMono Nerd Font Propo` - Proporcionalna

---

## 🔧 Ručna Konfiguracija po Terminalima

### GNOME Terminal
```bash
gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrainsMono Nerd Font 11'
```

### Konsole (KDE)
1. Settings → Edit Current Profile → Font
2. Izaberi: `JetBrainsMono Nerd Font`
3. Veličina: 11

### Alacritty
```yaml
# ~/.config/alacritty/alacritty.yml
font:
  normal:
    family: JetBrainsMono Nerd Font
    style: Regular
  size: 11.0
```

### Kitty
```conf
# ~/.config/kitty/kitty.conf
font_family      JetBrainsMono Nerd Font
bold_font        JetBrainsMono Nerd Font Bold
italic_font      JetBrainsMono Nerd Font Italic
font_size        11.0
```

### WezTerm
```lua
-- ~/.wezterm.lua
return {
  font = font 'JetBrainsMono Nerd Font',
  font_size = 11.0,
}
```

---

## 🛠️ Troubleshooting

### Font se ne prikazuje
```bash
# Osvježi font cache
fc-cache -fv ~/.fonts/

# Provjeri da li je font dostupan
fc-list | grep "JetBrainsMono Nerd"
```

### Ikonice se i dalje ne prikazuju
1. **Restartuj terminal** - Neki terminali zahtijevaju restart
2. **Provjeri encoding** - Postavi na UTF-8
3. **Provjeri locale**:
   ```bash
   locale  # Treba biti en_US.UTF-8 ili slično
   ```

### VSCode Terminal
1. File → Preferences → Settings
2. Search: `terminal font`
3. Postavi: `Terminal › Integrated: Font Family`
   ```
   'JetBrainsMono Nerd Font', Consolas, 'Courier New', monospace
   ```

---

## 📊 Dostupne Veličine

Preporučene veličine:
- **Mali ekrani:** 10-11pt
- **Standardni:** 11-12pt
- **Veliki/HiDPI:** 12-14pt

---

## 🎯 Preporuke za ASYCUDA Pro

Za najbolje iskustvo sa ASYCUDA Pro projektom:

1. **Terminal Font:** JetBrainsMono Nerd Font 11
2. **VSCode Font:** JetBrainsMono Nerd Font 11
3. **Encoding:** UTF-8
4. **Locale:** en_US.UTF-8 ili bs_BA.UTF-8

Ovo osigurava pravilno prikazivanje:
- ✅ Emojija u outputu
- ✅ FontAwesome ikonica
- ✅ ASCII/Unicode arta
- ✅ Simbola iz MCP memorije

---

*Kreirao: Qwen | 2026-03-22 | Nerd Font Instalacija*
