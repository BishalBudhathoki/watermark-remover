import random
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
import yt_dlp
from urllib.parse import urlparse
from datetime import datetime, timedelta
import sqlite3
from fastapi.websockets import WebSocket
import re
from io import BytesIO
import zipfile
from fastapi.responses import StreamingResponse
import glob
from typing import List, Dict, Optional, Tuple
import redis
import json
import logging
import uuid
import asyncio
from pydantic import BaseModel
import io

# Add the request model
class DownloadRequest(BaseModel):
    url: str
    type: str
    quality: str
    format: str

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Define base directory and download paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Go up to project root
DOWNLOADS_DIR = BASE_DIR / 'downloads' / 'youtube'
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR = BASE_DIR / 'processed'

# Create necessary directories
DOWNLOADS_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

# Global progress tracking
DOWNLOAD_PROGRESS = 0

# Redis client
redis_client = redis.Redis(host='localhost', port=6379, db=0)
CACHE_EXPIRY = 24 * 60 * 60  # 24 hours

# Logger setup
logger = logging.getLogger(__name__)

# yt-dlp options
YDL_OPTS = {
    'format': 'best[ext=mp4]/best',  # Try best MP4, fallback to best available
    'outtmpl': os.path.join(DOWNLOADS_DIR, 'tiktok_%(id)s.%(ext)s'),
    'quiet': False,
    'no_warnings': False,
    'verbose': True,
    'force_generic_extractor': False,
    'extract_flat_best': True,
    'cookiesfrombrowser': ['chrome'],  # Extract cookies from Chrome
    'nocheckcertificate': True,
    'extractor_retries': 5,
    'file_access_retries': 5,
    'fragment_retries': 5,
    'skip_download_archive': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'player_skip': ['webpage', 'config']
        }
    },
    'http_headers': {
        'User-Agent': random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',]),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
        'Referer': 'https://www.youtube.com/'
    }
}


# Updated BASE_YDL_OPTS
BASE_YDL_OPTS = {
    'quiet': False,
    'no_warnings': False,
    'verbose': True,
    'format_sort': ['res:2160', 'res:1440', 'res:1080', 'res:720', 'res:480', 'res:360'],
    'ignoreerrors': True,
    'no_color': True,
    'extractor_retries': 3,
    'fragment_retries': 3,
    'retry_sleep_functions': {'http': lambda n: 5 * (2 ** (n - 1))},
    'socket_timeout': 30,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.youtube.com/',
        'DNT': '1',
        'Sec-Fetch-Mode': 'navigate'
    },
    'concurrent_fragment_downloads': 4,
    'hls_prefer_native': True,
    'cookiesfrombrowser': ['chrome'],
    'nocheckcertificate': True,
    'skip_download_archive': True,
    'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'merge_output_format': 'mp4',
    'postprocessors': [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4'
    }],
    'prefer_native_hls': True,
    'geo_bypass': True,
    'geo_bypass_country': 'US'
}

# Add this above the router definition
def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS format."""
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02d}"

def get_cached_videos() -> List[str]:
    """Get a list of all cached video filenames."""
    return [os.path.basename(f) for f in glob.glob(os.path.join(DOWNLOADS_DIR, "*.mp4"))]

def get_video_filename(video_id: str) -> str:
    """Generate a consistent filename for a video ID."""
    return f"tiktok_{video_id}.mp4"

def is_video_cached(video_id: str) -> bool:
    """Check if a video is already cached."""
    filename = get_video_filename(video_id)
    return os.path.exists(os.path.join(DOWNLOADS_DIR, filename))

def get_video_info_from_cache(video_id: str) -> List[Dict]:
    """Get video info from Redis cache."""
    try:
        # Check both video and audio metadata and file existence
        video_cache_key = f"tiktok:video:{video_id}_video"
        audio_cache_key = f"tiktok:video:{video_id}_audio"
        video_file_key = f"tiktok:file:{video_id}_video"
        audio_file_key = f"tiktok:file:{video_id}_audio"
        
        results = []
        
        # Check for video
        video_data = redis_client.get(video_cache_key)
        video_exists = redis_client.get(video_file_key)
        if video_data and video_exists:
            video_info = json.loads(video_data)
            # Verify the file still exists on disk
            if os.path.exists(os.path.join(DOWNLOADS_DIR, f"tiktok_{video_id}.mp4")):
                results.append(video_info)
        
        # Check for audio
        audio_data = redis_client.get(audio_cache_key)
        audio_exists = redis_client.get(audio_file_key)
        if audio_data and audio_exists:
            audio_info = json.loads(audio_data)
            # Verify the file still exists on disk
            if os.path.exists(os.path.join(DOWNLOADS_DIR, f"tiktok_{video_id}.mp3")):
                results.append(audio_info)
        
        return results
    except Exception as e:
        print(f"Cache error: {str(e)}")
        return []

def cache_video_info(video_id: str, video_info: Dict):
    """Cache video info and file status in Redis."""
    try:
        cache_key = f"tiktok:video:{video_id}"
        file_key = f"tiktok:file:{video_id}"
        
        # Store video metadata
        redis_client.setex(cache_key, CACHE_EXPIRY, json.dumps(video_info))
        
        # Mark file as downloaded
        redis_client.setex(file_key, CACHE_EXPIRY, "1")
        
        print(f"Cached {video_info.get('file_type', 'video')} {video_id} successfully")
    except Exception as e:
        print(f"Cache error: {str(e)}")

@router.get("/cache-status")
async def get_cache_status():
    """Get the number of cached videos."""
    cached_videos = get_cached_videos()
    return {"cached_videos": len(cached_videos)}

@router.get("/tiktok")
async def tiktok_downloader_page(request: Request):
    """Show the TikTok downloader page."""
    return templates.TemplateResponse(
        "tiktok_downloader.html",
        {"request": request}
    )

@router.get("/audio-video")
async def video_downloader_page(request: Request):
    """Show the video downloader page."""
    return templates.TemplateResponse(
        "download_audio_video.html",
        {"request": request}
    )

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a video file for watermark removal."""
    try:
        # Ensure uploads directory exists
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Save uploaded file
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        return {"filename": file.filename, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
async def list_files():
    """List all uploaded files."""
    try:
        files = []
        for dir_name in ["uploads", "processed"]:
            dir_path = Path(dir_name)
            if dir_path.exists():
                files.extend([
                    {
                        "name": f.name,
                        "type": dir_name,
                        "size": f.stat().st_size
                    } for f in dir_path.glob("*") if f.is_file()
                ])
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/remove/{filename}")
async def remove_watermark_page(request: Request, filename: str):
    """Show the watermark removal page."""
    return templates.TemplateResponse(
        "remove.html",
        {"request": request, "filename": filename}
    )

@router.post("/remove/{filename}")
async def process_watermark_removal(filename: str, regions: str):
    """Process watermark removal from video."""
    try:
        input_path = Path("uploads") / filename
        output_path = Path("processed") / filename
        
        # TODO: Implement watermark removal logic
        # For now, just copy the file to processed directory
        import shutil
        shutil.copy(input_path, output_path)
        
        return {"status": "success", "processed_file": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def is_valid_tiktok_url(url):
    try:
        parsed_url = urlparse(url)
        return (
            parsed_url.netloc.endswith('tiktok.com') and 
            '@' in parsed_url.path
        )
    except:
        return False

def get_username_from_url(url):
    try:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        username = next((part for part in path_parts if part.startswith('@')), None)
        if not username:
            raise ValueError('Username not found in URL')
        return username[1:]
    except Exception as e:
        raise ValueError(f'Failed to extract username from URL: {str(e)}')

def get_db():
    db = sqlite3.connect('downloads.db')
    db.row_factory = sqlite3.Row
    return db

def get_highest_quality_video(video_info: dict) -> str:
    """Get the highest quality video URL from available formats."""
    if not video_info.get('formats'):
        return video_info.get('url')  # Fallback to default URL
    
    # Sort formats by quality (highest first)
    sorted_formats = sorted(
        video_info['formats'],
        key=lambda x: x.get('height', 0),
        reverse=True
    )
    
    # Return URL of the highest quality format
    return sorted_formats[0]['url']

def get_format_string(download_type: str, quality: str) -> str:
    """Generate the format string based on download type and quality."""
    if download_type == 'audio':
        return 'bestaudio'
    
    # For video downloads, keep it simple
    if quality == 'best':
        return 'best'
    
    # Convert quality string to number (e.g., '1080p' -> '1080')
    height = quality.lower().replace('p', '')
    if not height.isdigit():
        height = '1080'  # Default to 1080p if invalid
    
    return f'best[height<={height}]'

async def download_video(url: str, download_type: str, quality: str, format: str) -> dict:
    """Download video from URL with specified options."""
    global DOWNLOAD_PROGRESS
    DOWNLOAD_PROGRESS = 0
    
    try:
        # Ensure download directory exists
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using download directory: {DOWNLOADS_DIR}")
        
        # Generate unique filename using timestamp and sanitize it
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_timestamp = re.sub(r'[^\w\-_.]', '_', timestamp)
        
        def progress_hook(d):
            global DOWNLOAD_PROGRESS
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        DOWNLOAD_PROGRESS = int((downloaded / total) * 100)
                    logger.info(f"Download progress: {DOWNLOAD_PROGRESS}%")
                except Exception as e:
                    logger.error(f"Progress hook error: {str(e)}")
            elif d['status'] == 'finished':
                DOWNLOAD_PROGRESS = 100
                logger.info("Download finished")
            elif d['status'] == 'error':
                logger.error(f"Download error: {d.get('error')}")

        # Create a temporary filename template
        temp_filename = f'video_{safe_timestamp}.%(ext)s'
        output_template = str(DOWNLOADS_DIR / temp_filename)
        
        # Simplified yt-dlp options
        ydl_opts = {
            'outtmpl': output_template,
            'progress_hooks': [progress_hook],
            'format': get_format_string(download_type, quality),
            'merge_output_format': format,
            'quiet': False,
            'verbose': True,
            'no_warnings': False,
            'retries': 3,
            'fragment_retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.youtube.com/'
            },
            'cookiesfrombrowser': ['chrome'],
            'nocheckcertificate': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': format
            }] if download_type == 'video' else [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': format,
                'preferredquality': '192',
            }]
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Starting download for {url}")
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                
                if not info:
                    raise ValueError("Could not extract video information")
                
                # List all files in the download directory
                downloaded_files = list(DOWNLOADS_DIR.glob(f'video_{safe_timestamp}.*'))
                logger.info(f"Found files: {downloaded_files}")
                
                if not downloaded_files:
                    raise FileNotFoundError("No files found matching the download pattern")
                
                # Get the most recently modified file
                file_path = max(downloaded_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Selected file: {file_path}")
                
                if not file_path.exists():
                    raise FileNotFoundError(f"File not found at {file_path}")
                
                file_size = file_path.stat().st_size
                if file_size == 0:
                    raise ValueError("Downloaded file is empty")
                
                # Get just the filename without the full path
                final_filename = file_path.name
                
                return {
                    'success': True,
                    'message': 'Download completed successfully',
                    'filename': final_filename,
                    'file_path': str(file_path),
                    'file_size': file_size,
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', None),
                    'download_url': f'/api/download/file/{final_filename}'
                }
                
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            # Clean up any partial downloads
            for f in DOWNLOADS_DIR.glob(f'video_{safe_timestamp}.*'):
                try:
                    f.unlink()
                    logger.info(f"Cleaned up partial download: {f}")
                except Exception as cleanup_error:
                    logger.error(f"Cleanup error: {str(cleanup_error)}")
            raise
            
    except Exception as e:
        error_msg = f"Download failed: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'message': error_msg,
            'error': str(e)
        }

@router.post("/profile")
async def download_profile(
    request: Request,
    profile_url: str = Form(...),
    force_download: bool = Form(False)
):
    """Download content from a TikTok profile."""
    if not profile_url:
        raise HTTPException(status_code=400, detail="Profile URL is required")

    # Initialize counters
    total_videos = 0
    processed_videos = 0
    failed_videos = 0
    skipped_videos = 0
    videos_info = []

    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(profile_url, download=False)
            if not info or 'entries' not in info:
                raise HTTPException(status_code=400, detail="No videos found for this profile")

            total_videos = len(info['entries'])
            for entry in info['entries']:
                video_id = entry.get('id')
                if not video_id:
                    failed_videos += 1
                    continue

                # Check cache first
                cached_info = get_video_info_from_cache(video_id)
                if cached_info and not force_download:
                    # Add all cached files (both video and audio)
                    videos_info.extend(cached_info)
                    skipped_videos += 1
                    processed_videos += len(cached_info)
                    continue

                # Download video
                video_url = f"https://www.tiktok.com/@{entry.get('uploader', '')}/video/{video_id}"
                if await download_video(video_url, 'video', 'best', 'mp4'):
                    cached_info = get_video_info_from_cache(video_id)
                    if cached_info:
                        videos_info.extend(cached_info)
                        processed_videos += len(cached_info)
                else:
                    failed_videos += 1

            if processed_videos == 0:
                raise HTTPException(status_code=400, detail="No videos could be processed")

            return templates.TemplateResponse(
                "tiktok_results.html",
                {
                    "request": request,
                    "videos": videos_info,
                    "total_videos": total_videos,
                    "processed_videos": processed_videos,
                    "failed_videos": failed_videos,
                    "skipped_videos": skipped_videos,
                    "profile_url": profile_url
                }
            )

    except Exception as e:
        print(f"Error processing profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting video information: {str(e)}")


@router.get("/batch-download/{username}")
async def batch_download(username: str):
    """Download all videos for a user as a zip file."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM downloaded_videos WHERE username = ?', (username,))
        videos = cursor.fetchall()
        
        if not videos:
            raise HTTPException(status_code=404, detail="No videos found")
            
        # Create a zip file in memory
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for video in videos:
                video_path = os.path.join('downloads', video['filename'])
                if os.path.exists(video_path):
                    safe_title = re.sub(r'[^\w\s-]', '', video['title'] or '')
                    safe_title = safe_title.strip().replace(' ', '_')
                    filename = f"{safe_title}_{video['video_id']}.mp4" if safe_title else f"{video['video_id']}.mp4"
                    zf.write(video_path, filename)
        
        # Seek to the beginning of the file
        memory_file.seek(0)
        
        # Generate a timestamp for the zip filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'tiktok_{username}_{timestamp}_videos.zip'
        
        return StreamingResponse(
            memory_file,
            media_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename={zip_filename}'
            }
        )
        
    except Exception as e:
        print(f"Batch download error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'db' in locals():
            db.close()

@router.get("/clear-cache/{username}")
async def clear_cache(username: str):
    """Clear downloaded videos for a user from the database."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM downloaded_videos WHERE username = ?', (username,))
        db.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/downloads/{filename}")
async def serve_download(filename: str):
    """Serve downloaded files."""
    try:
        file_path = os.path.join(DOWNLOADS_DIR, filename)
        if not os.path.exists(file_path):
            # Try to find the file with a different extension
            base_name = os.path.splitext(filename)[0]
            possible_files = glob.glob(os.path.join(DOWNLOADS_DIR, f"{base_name}.*"))
            if possible_files:
                file_path = possible_files[0]
            else:
                raise HTTPException(status_code=404, detail="File not found")
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Determine content type based on file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.mp3':
            media_type = "audio/mpeg"
        elif ext == '.m4a':
            media_type = "audio/mp4"
        elif ext == '.webm':
            media_type = "video/webm"
        elif ext == '.mkv':
            media_type = "video/x-matroska"
        else:  # Default to MP4
            media_type = "video/mp4"
        
        # Return file response with content type and size
        return FileResponse(
            file_path,
            media_type=media_type,
            filename=os.path.basename(file_path),
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes"
            }
        )
    except Exception as e:
        print(f"Error serving file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error serving file")

def process_video_info(video_data: dict, video_id: str) -> dict:
    """Process video information and determine if it's audio or video."""
    # Get the file path base
    file_path = os.path.join(DOWNLOADS_DIR, f"tiktok_{video_id}")
    
    # Check for both MP4 and MP3 files
    is_video = os.path.exists(f"{file_path}.mp4")
    is_audio = os.path.exists(f"{file_path}.mp3")
    
    # Determine file extension and type
    if is_video:
        file_extension = "mp4"
        file_type = "video"
    elif is_audio:
        file_extension = "mp3"
        file_type = "audio"
    else:
        # Default to mp4 if neither exists (shouldn't happen)
        file_extension = "mp4"
        file_type = "video"
    
    # Construct the download URL
    download_url = f"/downloads/tiktok_{video_id}.{file_extension}"
    
    return {
        'title': video_data.get('title', 'Untitled'),
        'description': video_data.get('description', ''),
        'duration': format_duration(int(video_data.get('duration', 0))),
        'download_url': download_url,
        'file_type': file_type,
        'thumbnail': video_data.get('thumbnail', ''),
        'uploader': video_data.get('uploader', 'Unknown')
    }

async def download_tiktok_video(video_url: str, video_id: str) -> Tuple[bool, dict]:
    """Download TikTok video and return success status and video info."""
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',  # Prefer MP4, fallback to best
            'outtmpl': {
                'default': f'downloads/tiktok_{video_id}.%(ext)s'
            },
            'extract_flat': True,
            'quiet': False,
            'verbose': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            video_info = ydl.extract_info(video_url, download=True)
            
            if not video_info:
                raise Exception("Failed to extract video info")
                
            processed_info = process_video_info(video_info, video_id)
            return True, processed_info
            
    except Exception as e:
        logger.error(f"Unexpected error downloading video {video_id}: {str(e)}")
        return False, {}

def get_download_opts(output_path: str, download_type: str, quality: str, format: str) -> dict:
    """Get download options based on user preferences."""
    opts = BASE_YDL_OPTS.copy()
    opts.update({
        'outtmpl': output_path,
        'progress_hooks': [lambda d: logger.info(f"Download progress: {d.get('_percent_str', '0%')}")],
        'quiet': False,
        'no_warnings': False,
        'cookiesfrombrowser': ['chrome'],
        'format': get_format_string(download_type, quality),
        'merge_output_format': format,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': format,
        }] if download_type == 'video' else [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format,
            'preferredquality': '192',
        }]
    })
    return opts

@router.post("/download")
async def handle_download(request: DownloadRequest):
    """Handle video download request."""
    try:
        # Validate quality parameter
        valid_qualities = ['best', '1080', '720', '480', '360']
        quality = request.quality.lower().replace('p', '')
        
        if quality not in valid_qualities:
            return JSONResponse(
                status_code=400,
                content={'success': False, 'message': f'Invalid quality. Valid options: {", ".join(valid_qualities)}'}
            )

        # Normalize quality format
        formatted_quality = f"{quality}p" if quality != 'best' else 'best'
        
        # Attempt download
        result = await download_video(
            request.url, 
            request.type, 
            formatted_quality, 
            request.format
        )
        
        if not result['success']:
            return JSONResponse(
                status_code=500,
                content=result
            )
        
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.error(f"Unexpected error in download handler: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': f'Server error: {str(e)}'}
        )

@router.get("/progress")
async def get_progress():
    """Get current download progress."""
    global DOWNLOAD_PROGRESS
    return JSONResponse(content={"progress": DOWNLOAD_PROGRESS})

@router.post("/fetch-video-info")
async def fetch_video_info(url: str = Form(...)):
    """Fetch video information without downloading."""
    try:
        ydl_opts = BASE_YDL_OPTS.copy()
        ydl_opts.update({
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'format': 'best',
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {"success": False, "error": "Could not fetch video information"}
            
            # Extract available qualities
            qualities = set()
            for fmt in info.get('formats', []):
                if fmt.get('vcodec') != 'none' and fmt.get('height'):
                    qualities.add(fmt['height'])
            
            sorted_qualities = sorted(
                [f"{q}p" for q in qualities if q is not None], 
                key=lambda x: int(x.replace('p', '')), 
                reverse=True
            )
            
            # Add best option and ensure 1080p comes first if present
            available_qualities = ['best'] + sorted_qualities
            
            return {
                "success": True,
                "video_info": {
                    "title": info.get('title', 'Unknown Title'),
                    "duration": format_duration(info.get('duration', 0)),
                    "thumbnail": info.get('thumbnail', ''),
                    "available_qualities": available_qualities
                }
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/file/{filename}")
async def download_file(filename: str):
    """Stream file directly to browser for download."""
    file_path = DOWNLOADS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type based on extension
    ext = file_path.suffix.lower()
    content_type = {
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.webm': 'video/webm',
    }.get(ext, 'application/octet-stream')
    
    # Stream the file
    def iterfile():
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                yield chunk
        # Optionally delete the file after streaming
        # os.unlink(file_path)
    
    # Encode filename for Content-Disposition header using RFC 5987
    encoded_filename = filename.encode('utf-8').decode('latin-1')
    content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
    
    return StreamingResponse(
        iterfile(),
        media_type=content_type,
        headers={
            'Content-Disposition': content_disposition,
            'Accept-Ranges': 'bytes'
        }
    )