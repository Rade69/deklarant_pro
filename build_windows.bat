@echo off
REM =========================================================
REM  Deklarant Pro — Windows Build Skripta
REM  Pokretati na Windows mašini sa Python 3.11+
REM =========================================================

echo ============================================
echo  Deklarant Pro - Windows Build
echo ============================================
echo.

REM Provjeri Python
python --version >nul 2>&1
if errorlevel 1 (
    echo GRESKA: Python nije pronadjen u PATH-u.
    echo Instaliraj Python 3.11+ sa https://python.org
    pause
    exit /b 1
)

REM Provjeri PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Instaliram PyInstaller...
    pip install pyinstaller
)

REM Provjeri UPX (opciono, smanjuje velicinu EXE-a)
where upx >nul 2>&1
if errorlevel 1 (
    echo NAPOMENA: UPX nije pronadjen - build ce raditi ali EXE ce biti veci.
    echo          Preuzmi sa https://upx.github.io i dodaj u PATH.
)

echo.
echo [1/4] Cistim prethodne build-ove...
if exist dist\DeklarantPro rmdir /s /q dist\DeklarantPro
if exist build rmdir /s /q build

echo.
echo [2/4] Instaliram zavisnosti...
pip install -r requirements.txt --quiet

echo.
echo [3/4] Gradim EXE...
pyinstaller deklarant_pro.spec --noconfirm

if errorlevel 1 (
    echo.
    echo GRESKA: Build nije uspio. Pogledaj log iznad.
    pause
    exit /b 1
)

echo.
echo [4/4] Kopiram dodatne fajlove...

REM .env.example u dist folder (korisnik treba napraviti .env)
copy .env.example dist\DeklarantPro\.env.example

REM Provjeri da li postoji NOVA ASIKUDA XML arhiv
if exist "data\knowledge_base\NOVA ASIKUDA" (
    echo NAPOMENA: XML arhiv (NOVA ASIKUDA) je prevelik za bundling.
    echo          Kopiraj ga rucno u: dist\DeklarantPro\data\knowledge_base\NOVA ASIKUDA
) else (
    echo NAPOMENA: XML arhiv nije pronadjen lokalno - dodaj ga rucno u dist folder.
)

echo.
echo ============================================
echo  Build USPJESAN!
echo  Folder: dist\DeklarantPro\
echo.
echo  PRIJE DISTRIBUCIJE:
echo  1. Kopiraj XML arhiv (NOVA ASIKUDA) u dist\DeklarantPro\data\knowledge_base\
echo  2. Testiraj pokretanjem: dist\DeklarantPro\DeklarantPro.exe
echo  3. Pokreni Inno Setup sa: installer\setup.iss
echo ============================================
echo.
pause
