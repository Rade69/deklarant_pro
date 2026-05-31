@echo off
chcp 65001 >nul
REM ================================================================
REM  Deklarant Pro — Pokretanje sa konzolom (za developere)
REM  Greske su vidljive direktno u ovom prozoru
REM ================================================================

cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo GRESKA: .venv nije pronadjen!
    echo Pokreni prvo: setup_windows_venv.bat
    pause
    exit /b 1
)

echo Pokretanje Deklarant Pro (debug rezim)...
echo Greske ce biti prikazane ovdje.
echo.
.venv\Scripts\python.exe run.py
echo.
echo Aplikacija zatvorena. Pritisni bilo koji taster za izlaz.
pause
