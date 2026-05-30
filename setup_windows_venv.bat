@echo off
chcp 65001 >nul
REM ================================================================
REM  Deklarant Pro — Windows venv postavljanje
REM  Pokrenuti JEDNOM na novom računaru kao Administrator
REM  Nakon toga koristiti start_debug.bat ili start_silent.vbs
REM ================================================================

echo.
echo ============================================================
echo   Deklarant Pro — Postavljanje okruzenja (venv)
echo ============================================================
echo.

REM ── 1. Provjeri Python ──────────────────────────────────────
echo [1/5] Provjera Python instalacije...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo GRESKA: Python nije pronadjen!
    echo Instaliraj Python 3.11+ sa: https://python.org/downloads/
    echo VAZNO: Pri instalaciji oznaci "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo   Pronadjen: %%i
echo.

REM ── 2. Napravi virtualno okruzenje ──────────────────────────
echo [2/5] Kreiranje virtualnog okruzenja (.venv)...
if exist .venv (
    echo   .venv vec postoji - preskacam kreiranje.
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo GRESKA: Nije moguce kreirati .venv!
        pause
        exit /b 1
    )
    echo   .venv kreiran uspjesno.
)
echo.

REM ── 3. Instaliraj zavisnosti ─────────────────────────────────
echo [3/5] Instalacija Python paketa (moze trajati 5-10 minuta)...
echo   Molim sacekaj...
echo.
.venv\Scripts\pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo GRESKA: Instalacija paketa nije uspjela!
    echo Provjeri internet konekciju i pokusaj ponovo.
    pause
    exit /b 1
)
echo   Svi paketi instalirani uspjesno.
echo.

REM ── 4. Provjeri .env fajl ────────────────────────────────────
echo [4/5] Provjera konfiguracije (.env)...
if not exist .env (
    echo   .env fajl nije pronadjen - kreiram iz predloska...
    copy .env.example .env >nul 2>&1
    if not exist .env (
        echo   Kreiram .env rucno...
        (
            echo DB_HOST=192.168.0.41
            echo DB_PORT=5432
            echo DB_NAME=deklarant_pro
            echo DB_USER=radovan
            echo DB_PASSWORD=postgres
            echo DEBUG=False
            echo CLIENT_NAME=dmwindows
            echo SEND_SENSITIVE_DATA=false
            echo SESSION_TOKEN_BUDGET=50000
        ) > .env
    )
    echo   VAZNO: Otvori .env i provjeri DB_HOST, DB_USER, DB_PASSWORD!
    notepad .env
) else (
    echo   .env postoji.
)
echo.

REM ── 5. Kratki test konekcije ─────────────────────────────────
echo [5/5] Test konekcije na bazu...
.venv\Scripts\python.exe -c "
import sys, os
sys.path.insert(0, '.')
try:
    from dotenv import load_dotenv
    load_dotenv()
    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST','192.168.0.41'),
        port=os.getenv('DB_PORT','5432'),
        dbname=os.getenv('DB_NAME','deklarant_pro'),
        user=os.getenv('DB_USER','radovan'),
        password=os.getenv('DB_PASSWORD','postgres'),
        connect_timeout=5
    )
    conn.close()
    print('  Konekcija na bazu: OK')
except Exception as e:
    print(f'  UPOZORENJE: Konekcija na bazu nije uspjela: {e}')
    print('  Provjeri DB_HOST i mrežnu konekciju na server 192.168.0.41')
" 2>&1
echo.

REM ── Gotovo ───────────────────────────────────────────────────
echo ============================================================
echo   Postavljanje zavrseno!
echo.
echo   Za pokretanje aplikacije:
echo     - Korisnik:  dvostruki klik na "Deklarant Pro.vbs"
echo     - Developer: pokreni start_debug.bat
echo ============================================================
echo.
pause
