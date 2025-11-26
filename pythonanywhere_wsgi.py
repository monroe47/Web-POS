"""
WSGI config specifically for PythonAnywhere deployment.

This file will be used by PythonAnywhere's web application.
Path: /home/username/POSwithSalesandInventoryManagementwithSalesForecast/pythonanywhere_wsgi.py

In PythonAnywhere Web tab:
- Source code: /home/username/POSwithSalesandInventoryManagementwithSalesForecast
- WSGI configuration file: /home/username/POSwithSalesandInventoryManagementwithSalesForecast/pythonanywhere_wsgi.py
"""

import os
import sys
from pathlib import Path

# Add your project directory to the sys.path
project_folder = os.path.dirname(__file__)
sys.path.insert(0, project_folder)

# Set production settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'POSwithSalesForecast.settings_production'

# Configure Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
