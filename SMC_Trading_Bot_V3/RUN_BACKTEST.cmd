@echo off
title SMC Phantom V3.0 - Backtest Engine
color 0B
echo.
echo  ===================================================
echo   SMC PHANTOM V3.0 - BACKTEST ENGINE
echo   Running: 30-day + 90-day (Gold + Silver)
echo  ===================================================
echo.
cd /d C:\SMC_Trading_Bot
c:\python314\python.exe backtest\engine.py
echo.
echo Backtest complete. Results saved to backtest\ folder.
pause
