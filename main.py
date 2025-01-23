from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.routes.download import router as download_router
from app.routes.auth import router as auth_router
from app.routes.pages import router as pages_router
from app.utils.database import init_db
from app.config.settings import UPLOAD_FOLDER, PROCESSED_FOLDER
from app.middleware.auth import AuthMiddleware
from app.database import engine, Base
import os
from pathlib import Path
from fastapi.responses import FileResponse

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="Watermark Remover",
    description="A FastAPI application for removing watermarks from videos and downloading TikTok content",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.add_middleware(
    AuthMiddleware,
    protected_paths=[
        "/api/download/profile",  # Protect profile download endpoints
        "/api/download/files",    # Protect file listing
        "/api/download/upload",   # Protect file upload
        "/api/download/batch-download",  # Protect batch downloads
        "/api/download/clear-cache",     # Protect cache clearing
    ]
)

# Ensure folders exist
for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER, "downloads"]:
    os.makedirs(folder, exist_ok=True)

# Mount static files and downloads
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# Include routers
app.include_router(pages_router)  # Include pages router first for proper route matching
app.include_router(auth_router)
app.include_router(download_router, prefix="/api/download")

# Create templates instance
templates = Jinja2Templates(directory="app/templates")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Root route
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/downloads/{filename}")
async def serve_download(filename: str):
    # Construct the full path to the downloads directory
    downloads_dir = Path("processed")
    file_path = downloads_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type based on file extension
    if filename.endswith('.mp3'):
        media_type = "audio/mpeg"
    else:
        media_type = "video/mp4"
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    ) 