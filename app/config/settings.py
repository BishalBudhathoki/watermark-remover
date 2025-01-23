import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed")

# Authentication settings
SECRET_KEY = "your-secret-key"  # Change this in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Redis settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# File upload settings
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}

# Flask configuration
DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# API configuration
RAPID_API_KEY = os.getenv('RAPID_API_KEY')
RAPID_API_HOST = os.getenv('RAPID_API_HOST')

# Rate limiting configuration
DAILY_LIMIT = int(os.getenv('DAILY_LIMIT', 10))
MONTHLY_LIMIT = int(os.getenv('MONTHLY_LIMIT', 100))

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
