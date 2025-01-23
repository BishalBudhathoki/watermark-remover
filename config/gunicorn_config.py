# Gunicorn configuration file
import os
import sys

# Add the virtual environment site-packages to Python path
venv_path = os.path.join(os.path.dirname(__file__), '.venv/lib/python3.11/site-packages')
sys.path.append(venv_path)

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"  # Default to 8000 if PORT is not set
workers = 2  # Adjust based on your app's load
threads = 2  # Optional: Use threads if necessary
timeout = 120  # Increased timeout for video processing
preload_app = True
