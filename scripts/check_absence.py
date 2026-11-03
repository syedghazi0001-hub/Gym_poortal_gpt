#!/usr/bin/env python3
"""
scripts/check_absence.py

Scheduled Task / CLI Script for Gym Management System.
Evaluates all active gym members for 10+ consecutive days of absence.
Creates owner notifications and member portal warnings.

Usage on PythonAnywhere:
    Add scheduled daily task at 00:00 UTC:
    python /home/<username>/gym-management/scripts/check_absence.py
"""

import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.absence_service import run_ten_day_absence_check

def main():
    print("=" * 60)
    print("Vanguard Gym OS — Automated 10-Day Absence Check Engine")
    print("=" * 60)
    
    try:
        result = run_ten_day_absence_check(force=True)
        print(f"Status: {result.get('status')}")
        print(f"Active members evaluated: {result.get('checked_members')}")
        print(f"New 10-day alerts generated: {result.get('new_alerts_count')}")
        print(f"Completed at: {result.get('run_at')}")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"ERROR running absence check: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
