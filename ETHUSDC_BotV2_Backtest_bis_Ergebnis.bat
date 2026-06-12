@echo off
cd /d "%~dp0"
echo ETHUSDC Bot V2 - echter Daten-/Backtest-Smoke-Run
echo.
echo Regeln: Binance Spot Marktdaten, keine API-Keys, kein Trading, keine Orders.
echo Der Runner laedt/resumed ETHUSDC 1m Daten und startet den Backtest erst bei genug Candles.
echo.
python scripts\run_backtest_smoke.py
echo.
echo Prozess beendet. Fenster bleibt offen, damit Fortschritt oder Fehler lesbar bleiben.
pause