@echo off
title Vanguard Gym OS - Local Server
echo ============================================================
echo Starting Vanguard Gym OS (Local Mode)...
echo ============================================================

if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo Checking requirements...
pip install -r requirements.txt

echo Launching Gym Management Portal...
echo Open your browser at: http://127.0.0.1:5000
echo Press Ctrl+C to stop the server.
echo ============================================================

python app.py
pause
