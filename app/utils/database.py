import sqlite3
from sqlite3 import Row
from typing import Any
from fastapi import FastAPI
from app.config.settings import DATABASE_URL

def get_db() -> sqlite3.Connection:
    """Get a database connection."""
    db = sqlite3.connect(DATABASE_URL.replace('sqlite:///', ''))
    db.row_factory = Row
    return db

def init_db() -> None:
    """Initialize the database with required tables."""
    db = get_db()
    cursor = db.cursor()
    
    # Create downloaded_videos table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloaded_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            video_id TEXT NOT NULL,
            title TEXT,
            description TEXT,
            filename TEXT NOT NULL,
            download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, video_id)
        )
    ''')
    
    # Add more table creation statements here as needed
    
    db.commit()
    db.close()

def init_app(app: FastAPI) -> None:
    """Initialize database with the FastAPI app."""
    init_db()
    
    @app.on_event("startup")
    async def startup():
        init_db()
    
    @app.on_event("shutdown")
    async def shutdown():
        # Close any open connections
        pass
