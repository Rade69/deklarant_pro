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
echo [4/5] Digitalno potpisivanje EXE-a (opciono)...

REM Code signing sertifikat je odlozen do daljnjeg (odluka 2026-07-27 —
REM ne isplati se u ovoj fazi). Ako WINDOWS_SIGNING_CERT_SHA1 nije postavljen,
REM build prolazi BEZ potpisivanja umjesto da stane — takav EXE Windows
REM SmartScreen prikazuje kao "Nepoznat izdavac" i NIJE za siru distribuciju,
REM samo za internu/kontrolisanu upotrebu (npr. dm promet klijent).
REM Cim se WINDOWS_SIGNING_CERT_SHA1 postavi, potpisivanje se automatski
REM vraca bez izmjene ove skripte.

if "%WINDOWS_SIGNING_CERT_SHA1%"=="" (
    echo NAPOMENA: WINDOWS_SIGNING_CERT_SHA1 nije postavljen — EXE ostaje NEPOTPISAN.
    echo          Windows ce prikazati "Nepoznat izdavac" upozorenje pri pokretanju.
    echo          Ovo je namjerno za internu/test upotrebu — NE distribuirati siroko.
    goto :skip_signing
)

where signtool >nul 2>&1
if errorlevel 1 (
    echo GRESKA: signtool nije pronadjen u PATH-u.
    echo Instaliraj Windows SDK i dodaj signtool u PATH.
    exit /b 1
)

if "%SIGN_TIMESTAMP_URL%"=="" set SIGN_TIMESTAMP_URL=http://timestamp.digicert.com

signtool sign /sha1 %WINDOWS_SIGNING_CERT_SHA1% /fd SHA256 /tr %SIGN_TIMESTAMP_URL% /td SHA256 dist\DeklarantPro\DeklarantPro.exe
if errorlevel 1 (
    echo GRESKA: Digitalno potpisivanje EXE-a nije uspjelo.
    exit /b 1
)

signtool verify /pa /v dist\DeklarantPro\DeklarantPro.exe
if errorlevel 1 (
    echo GRESKA: Authenticode provjera potpisanog EXE-a nije prosla.
    exit /b 1
)

:skip_signing

echo.
echo [5/5] Kopiram dodatne fajlove...

REM .env.example u dist folder (korisnik treba napraviti .env)
copy .env.example dist\DeklarantPro\.env.example

REM Provjeri da li postoji NOVA ASIKUDA XML arhiv
if exist "data\knowledge_base\NOVA ASIKUDA" (
    echo NAPOMENA: XML arhiv NOVA ASIKUDA je prevelik za bundling.
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
