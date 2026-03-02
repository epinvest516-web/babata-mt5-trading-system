@echo off
title Babata V5.0 Ultimate Supervisor
C:
cd C:\TradingBot_v3\smc_v3_core

:loop
echo [%date% %time%] Starting Babata V5.0 (Ultimate Edition)...
python main.py
echo [%date% %time%] Bot crashed. Restarting in 5 seconds...
timeout /t 5
goto loop
