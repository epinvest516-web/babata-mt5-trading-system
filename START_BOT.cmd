@echo off
setlocal enabledelayedexpansion
cd /d C:\TradingBot
echo [%date% %time%] Babata bot supervisor starting...>> C:\TradingBot\bot.log
:loop
echo [%date% %time%] launching python...>> C:\TradingBot\bot.log
"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" C:\TradingBot\main.py 1>> C:\TradingBot\bot.log 2>> C:\TradingBot\bot.err.log
echo [%date% %time%] python exited with code !errorlevel!>> C:\TradingBot\bot.err.log
timeout /t 5 /nobreak >nul
goto loop
