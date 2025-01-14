# Gunicorn configuration file
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"  # Default to 8000 if PORT is not set
workers = 2  # Adjust based on your app's load
threads = 2  # Optional: Use threads if necessary
timeout = 30  # Optional: Set timeout to handle long requests
