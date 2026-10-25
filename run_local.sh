#!/usr/bin/env bash
set -e

echo "============================================================"
echo "Starting Vanguard Gym OS..."
echo "============================================================"

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

echo "Launching Gym Management Portal..."
echo "Open your browser at: http://127.0.0.1:5000"
echo "Press Ctrl+C to stop the server."
echo "============================================================"

python3 app.py
