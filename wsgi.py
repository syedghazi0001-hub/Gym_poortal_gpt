"""
wsgi.py

PythonAnywhere WSGI configuration entrypoint.
Notice: Does NOT call application.run() - purely exposes `application` callable for WSGI servers (Gunicorn, uWSGI, PythonAnywhere WSGI).
"""

import os
import sys

# Ensure current project directory is in python search path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import create_app

# Create WSGI application object
application = create_app()
