import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
    PORT = 5001  # Set default port to 5001
    HOST = os.environ.get('HOST', '0.0.0.0')
    # Add other configuration variables here 