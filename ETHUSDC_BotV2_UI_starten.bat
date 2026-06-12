@echo off
setlocal

cd /d "%~dp0"

python -m src.ui.app
if errorlevel 1 (
    echo.
    echo Fehler: Die ETHUSDC Bot V2 UI konnte nicht gestartet werden.
    echo Bitte pruefen, ob Python installiert ist und im PATH verfuegbar ist.
    echo Befehl: python -m src.ui.app
    echo.
    pause
)