@echo off
title Babata V6.0 Ultimate Supervisor
C:
cd C:\TradingBot_v3\smc_v3_core

:loop
echo [%date% %time%] Starting Babata V6.0 (Ultimate Command)...
python main.py
echo [%date% %time%] Bot crashed. Restarting in 5 seconds...
timeout /t 5
goto loop
