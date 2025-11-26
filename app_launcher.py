import subprocess
import threading
import time
import webview
import os
import sys

def start_django():
    subprocess.Popen([sys.executable, "manage.py", "runserver", "127.0.0.1:8000"])

t = threading.Thread(target=start_django)
t.daemon = True
t.start()

time.sleep(3)

webview.create_window("POS with Sales Forecast", "http://127.0.0.1:8000", width=1200, height=700)
webview.start()
