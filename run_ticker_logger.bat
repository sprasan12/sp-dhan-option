@echo off
echo Starting Simple Ticker Logger...
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the ticker logger
python simple_ticker_logger.py

REM Keep window open to see any errors
pause
