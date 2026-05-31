@echo off
chcp 65001 >nul
REM ================================================================
REM  Deklarant Pro — Build distribucijskog paketa
REM  Kompajlira .pyd module i kreira dist_client/ za isporuku
REM  Pokretati na Windows 11 mašini sa Nuitka instaliranom
REM ================================================================

echo.
echo ============================================================
echo   Deklarant Pro — Build distribucijskog paketa
echo ============================================================
echo.

cd /d "%~dp0.."

REM ── Provjeri okruženje ─────────────────────────────────────
echo [1/5] Provjera okruzenja...
python --version >nul 2>&1
if errorlevel 1 ( echo GRESKA: Python nije pronadjen! & pause & exit /b 1 )
python -m nuitka --version >nul 2>&1
if errorlevel 1 (
    echo Nuitka nije instalirana. Instaliram...
    pip install nuitka
)
echo   OK.
echo.

REM ── Kompajliraj module ─────────────────────────────────────
echo [2/5] Kompajliram zasticene module u .pyd...
if exist nuitka_output rmdir /s /q nuitka_output

REM Pojedinacni fajlovi
for %%f in (
    services\export_service.py
    services\declaration_assembly.py
    services\tariff_controls_service.py
    services\tariff_doc_history_service.py
    services\tariff_facade.py
    services\tariff_mapping_service.py
    services\tariff_tree_service.py
) do (
    echo   Kompajliram: %%f
    python -m nuitka --module --output-dir=nuitka_output %%f >nul 2>&1
    if errorlevel 1 ( echo   GRESKA: %%f & pause & exit /b 1 )
)

REM Paketi (folderi)
echo   Kompajliram: core\licensing
python -m nuitka --module --include-package=core.licensing --output-dir=nuitka_output core\licensing >nul 2>&1
if errorlevel 1 ( echo   GRESKA: core\licensing & pause & exit /b 1 )

echo   Kompajliram: core\validation
python -m nuitka --module --include-package=core.validation --output-dir=nuitka_output core\validation >nul 2>&1
if errorlevel 1 ( echo   GRESKA: core\validation & pause & exit /b 1 )

echo   Kompajliram: services\faktura
python -m nuitka --module --include-package=services.faktura --output-dir=nuitka_output services\faktura >nul 2>&1
if errorlevel 1 ( echo   GRESKA: services\faktura & pause & exit /b 1 )

echo   Kompajliram: services\tariff
python -m nuitka --module --include-package=services.tariff --output-dir=nuitka_output services\tariff >nul 2>&1
if errorlevel 1 ( echo   GRESKA: services\tariff & pause & exit /b 1 )

echo   Kompajliranje zavrseno.
echo.

REM ── Kreiraj dist_client ────────────────────────────────────
echo [3/5] Kreiram dist_client/ folder...
if exist dist_client rmdir /s /q dist_client

robocopy . dist_client /E ^
    /XD dist_client dist nuitka_output .venv .git __pycache__ .gitnexus ^
        .claude .github .vscode .pytest_cache tests tools memory ^
        agent_reports agent_tasks build installer najavauvoza logs temp ^
        .qodo .qwen .roo .crush .agent_memory ^
    /XF *.pyc *.log .env deklarant_sistem.db build_log.txt ^
    /NFL /NDL /NJH /NJS >nul 2>&1

REM Kopiraj .pyd fajlove na ispravne lokacije
copy /y nuitka_output\licensing.cp314-win_amd64.pyd      dist_client\core\  >nul
copy /y nuitka_output\validation.cp314-win_amd64.pyd     dist_client\core\  >nul
copy /y nuitka_output\faktura.cp314-win_amd64.pyd        dist_client\services\ >nul
copy /y nuitka_output\tariff.cp314-win_amd64.pyd         dist_client\services\ >nul
copy /y nuitka_output\export_service*.pyd                dist_client\services\ >nul
copy /y nuitka_output\declaration_assembly*.pyd          dist_client\services\ >nul
copy /y nuitka_output\tariff_controls_service*.pyd       dist_client\services\ >nul
copy /y nuitka_output\tariff_doc_history_service*.pyd    dist_client\services\ >nul
copy /y nuitka_output\tariff_facade*.pyd                 dist_client\services\ >nul
copy /y nuitka_output\tariff_mapping_service*.pyd        dist_client\services\ >nul
copy /y nuitka_output\tariff_tree_service*.pyd           dist_client\services\ >nul

REM Ukloni originalne .py koji su zamijenjeni .pyd
for %%d in (
    dist_client\core\licensing
    dist_client\core\validation
    dist_client\services\faktura
    dist_client\services\tariff
) do ( if exist %%d rmdir /s /q %%d )

for %%f in (
    dist_client\services\export_service.py
    dist_client\services\declaration_assembly.py
    dist_client\services\tariff_controls_service.py
    dist_client\services\tariff_doc_history_service.py
    dist_client\services\tariff_facade.py
    dist_client\services\tariff_mapping_service.py
    dist_client\services\tariff_tree_service.py
) do ( if exist %%f del /f %%f )

echo   dist_client/ kreiran.
echo.

REM ── Import testovi ─────────────────────────────────────────
echo [4/5] Import testovi...
pushd dist_client
python -c "from core import licensing; from core import validation; from services import faktura; from services import tariff; import services.export_service; print('  Svi import testovi: OK')" 2>&1
if errorlevel 1 ( echo   GRESKA: import test pao! & popd & pause & exit /b 1 )
popd
echo.

REM ── Zapakuj ZIP ────────────────────────────────────────────
echo [5/5] Pakujem u ZIP...
for /f "tokens=2 delims==" %%d in ('wmic os get LocalDateTime /value') do set dt=%%d
set DATUM=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%

powershell -NoProfile -Command "Compress-Archive -Path 'dist_client\*' -DestinationPath 'DeklarantPro_v1.0_%DATUM%.zip' -Force"
echo   Kreiran: DeklarantPro_v1.0_%DATUM%.zip
echo.

echo ============================================================
echo   BUILD USPJESAN!
echo.
echo   dist_client/   — folder za direktnu instalaciju
echo   DeklarantPro_v1.0_%DATUM%.zip — ZIP za isporuku
echo.
echo   Klijent radi:
echo     1. Raspakiraj ZIP
echo     2. Pokreni setup_windows_venv.bat
echo     3. Dvostruki klik na start_silent.vbs
echo ============================================================
echo.
pause
