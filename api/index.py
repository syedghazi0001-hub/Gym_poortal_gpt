"""
api/index.py

Vercel Serverless Function entrypoint.
Exposes Flask `app` callable for Vercel Python runtime.
"""
import os
import sys

project_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import create_app

app = application = create_app()
