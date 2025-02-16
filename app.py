# app.py
import os
import tempfile
import sys
import yt_dlp
from urllib.parse import urlparse, unquote
from flask import Flask, request, render_template, redirect, url_for, send_file, send_from_directory, jsonify, session
from werkzeug.utils import secure_filename
import cv2
import numpy as np
from moviepy.editor import VideoFileClip
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
import json
from dotenv import load_dotenv
import requests
import logging  # Import logging module
import threading
import redis
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from io import BytesIO
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
from flask_cors import CORS
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from flask_session import Session
from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables first
load_dotenv()

# Configure Flask app with session settings
app.config.update(
    SECRET_KEY=os.urandom(24),
    SESSION_TYPE='filesystem',
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30)
)

# Initialize Flask-Session
Session(app)

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:5001",
            "http://127.0.0.1:5001",
            "https://accounts.google.com"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Create session directory if it doesn't exist
if not os.path.exists('flask_session'):
    os.makedirs('flask_session')

# Add security headers middleware
@app.after_request
def add_security_headers(response):
    # Remove COOP header that's causing the postMessage issue
    # response.headers['Cross-Origin-Opener-Policy'] = 'unsafe-none'
    response.headers['Cross-Origin-Embedder-Policy'] = 'unsafe-none'
    
    # Set CORS headers
    if request.headers.get('Origin'):
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin')
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
    
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    # Add CSP header to allow Google Sign-In
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://accounts.google.com"
    
    return response

# Add configuration for development
if app.debug:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['PROCESSED_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'm4v', '3gp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Global variable to store download progress
download_progress = {'progress': 0, 'status': 'idle'}

class ProgressTracker:
    def __init__(self):
        self.progress = 0
        self.status = 'starting'
        self._lock = threading.Lock()

    def update_progress(self, d):
        global download_progress
        with self._lock:
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total_bytes > 0:
                    self.progress = (d.get('downloaded_bytes', 0) / total_bytes) * 100
                    speed = d.get('speed', 0)
                    if speed:
                        speed_mb = speed / 1024 / 1024  # Convert to MB/s
                        self.status = f'Downloading: {self.progress:.1f}% ({speed_mb:.1f} MB/s)'
                    else:
                        self.status = f'Downloading: {self.progress:.1f}%'
                    # Update global download_progress
                    download_progress['progress'] = self.progress
                    download_progress['status'] = self.status
            elif d['status'] == 'finished':
                self.progress = 100
                self.status = 'Processing...'
                download_progress['progress'] = self.progress
                download_progress['status'] = self.status
            elif d['status'] == 'error':
                self.status = f'Error: {d.get("error", "Unknown error")}'
                download_progress['status'] = self.status

# Define download and processed folders
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_FOLDER = BASE_DIR / 'downloads'
PROCESSED_FOLDER = BASE_DIR / 'processed'

# Create necessary directories
DOWNLOAD_FOLDER.mkdir(exist_ok=True)
PROCESSED_FOLDER.mkdir(exist_ok=True)

# Configure Flask app
app.config['DOWNLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
app.config['PROCESSED_FOLDER'] = str(PROCESSED_FOLDER)

# API Configuration
RAPID_API_KEY = os.getenv('RAPID_API_KEY')
RAPID_API_HOST = os.getenv('RAPID_API_HOST')

# Google/YouTube API Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
YOUTUBE_CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
YOUTUBE_CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')

# Add OAuth configuration
app.config.update(
    GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID,
    YOUTUBE_CLIENT_ID=YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET=YOUTUBE_CLIENT_SECRET,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Rate limiting configuration
DAILY_LIMIT = 10
MONTHLY_LIMIT = 100

class APIUsageTracker:
    def __init__(self):
        self.usage_file = Path('api_usage.json')
        self.load_usage()

    def load_usage(self):
        if self.usage_file.exists():
            with open(self.usage_file, 'r') as f:
                self.usage = json.load(f)
        else:
            self.usage = {
                'daily': {'count': 0, 'date': str(datetime.now().date())},
                'monthly': {'count': 0, 'month': datetime.now().strftime('%Y-%m')}
            }

    def save_usage(self):
        with open(self.usage_file, 'w') as f:
            json.dump(self.usage, f)

    def check_and_update(self):
        current_date = datetime.now().date()
        current_month = datetime.now().strftime('%Y-%m')

        # Reset daily count if it's a new day
        if str(current_date) != self.usage['daily']['date']:
            self.usage['daily'] = {'count': 0, 'date': str(current_date)}

        # Reset monthly count if it's a new month
        if current_month != self.usage['monthly']['month']:
            self.usage['monthly'] = {'count': 0, 'month': current_month}

        # Check limits
        if self.usage['daily']['count'] >= DAILY_LIMIT:
            raise Exception('Daily API limit reached. Please try again tomorrow.')
        if self.usage['monthly']['count'] >= MONTHLY_LIMIT:
            raise Exception('Monthly API limit reached. Please try again next month.')

        # Increment counters
        self.usage['daily']['count'] += 1
        self.usage['monthly']['count'] += 1
        self.save_usage()

# Create API usage tracker instance
api_tracker = APIUsageTracker()

def check_api_limits(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            api_tracker.check_and_update()
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': str(e)}), 429
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file uploaded.", 400
        
        file = request.files['file']
        if file.filename == '':
            return "No file selected.", 400
            
        if not allowed_file(file.filename):
            return "Invalid file format. Supported formats: MP4, MOV, M4V, 3GP", 400
            
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return redirect(url_for('remove_watermark', filename=filename))
    return render_template('index.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/processed/<filename>')
def processed_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

@app.route('/remove/<filename>', methods=['GET', 'POST'])
def remove_watermark(filename):
    if request.method == 'POST':
        regions_str = request.form.get('regions', '')
        if not regions_str:
            return "No regions selected", 400
        
        try:
            # Parse regions from form data
            regions = []
            for region in regions_str.split(';'):
                if region:
                    try:
                        x, y, w, h = map(float, region.split(','))
                        # Ensure positive width and height
                        w = abs(w)
                        h = abs(h)
                        regions.append([x, y, w, h])
                    except ValueError as e:
                        print(f"Error parsing region {region}: {str(e)}")
                        continue
            
            if not regions:
                return "Invalid region data", 400
            
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            output_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
            
            # Process the video
            if process_video(input_path, regions, output_path):
                return redirect(url_for('preview', filename=filename))
            else:
                return "Error processing video", 500
                
        except Exception as e:
            print(f"Error in remove_watermark: {str(e)}")
            return f"Error processing video: {str(e)}", 500
            
    return render_template('remove.html', filename=filename)

def process_video(input_path, regions, output_path):
    try:
        clip = VideoFileClip(input_path)
        
        def remove_watermark(frame):
            # Convert frame to BGR (OpenCV format)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            for region in regions:
                x, y, w, h = map(int, region)
                
                # Ensure coordinates are within frame bounds
                x = max(0, min(x, frame_bgr.shape[1] - 1))
                y = max(0, min(y, frame_bgr.shape[0] - 1))
                w = max(0, min(w, frame_bgr.shape[1] - x))
                h = max(0, min(h, frame_bgr.shape[0] - y))
                
                if w <= 0 or h <= 0:
                    continue
                
                # Create mask for the selected region
                mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
                mask[y:y+h, x:x+w] = 255
                
                # Expand the region slightly for better blending
                expanded_x = max(0, x - 10)
                expanded_y = max(0, y - 10)
                expanded_w = min(frame_bgr.shape[1] - expanded_x, w + 20)
                expanded_h = min(frame_bgr.shape[0] - expanded_y, h + 20)
                
                # Apply inpainting
                frame_bgr = cv2.inpaint(
                    frame_bgr,
                    mask,
                    inpaintRadius=3,
                    flags=cv2.INPAINT_TELEA
                )
                
                # Additional content-aware fill using surrounding pixels
                roi = frame_bgr[expanded_y:expanded_y+expanded_h, expanded_x:expanded_x+expanded_w]
                if roi.size > 0:
                    # Apply slight blur to blend the edges
                    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
                    mask_roi = mask[expanded_y:expanded_y+expanded_h, expanded_x:expanded_x+expanded_w]
                    roi[mask_roi > 0] = blurred[mask_roi > 0]
            
            # Convert back to RGB
            return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        
        # Process the video
        processed_clip = clip.fl_image(remove_watermark)
        
        # Write the processed video with original audio
        processed_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            audio=clip.audio is not None
        )
        
        # Clean up
        clip.close()
        processed_clip.close()
        
        return True
        
    except Exception as e:
        print(f"Error in process_video: {str(e)}")
        raise e

@app.route('/download/<filename>')
def download(filename):
    return send_file(
        os.path.join(app.config['PROCESSED_FOLDER'], filename),
        as_attachment=True
    )

@app.route('/static/processed/<filename>')
def serve_processed_video(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

@app.route('/preview/<filename>')
def preview(filename):
    return render_template('preview.html', filename=filename)

@app.route('/download-progress')
def get_download_progress():
    return jsonify(download_progress)

@app.route('/download-video', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    format_type = data.get('format', 'mp4')
    quality = data.get('quality', 'best')
    download_type = data.get('downloadType', 'video')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    progress_tracker = ProgressTracker()

    def progress_hook(d):
        progress_tracker.update_progress(d)

    try:
        # Create a unique filename to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        ydl_opts = {
            'outtmpl': str(DOWNLOAD_FOLDER / f'%(title)s_{timestamp}.%(ext)s'),
            'progress_hooks': [progress_hook],
            'merge_output_format': format_type,
            'format': None,
            'postprocessors': [{
                'key': 'FFmpegMetadata',
            }]
        }

        if download_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': format_type,
                    'preferredquality': '192',
                }]
            })
        else:
            # Video download
            if quality == 'best':
                format_str = f'bestvideo[ext={format_type}]+bestaudio/best'
            else:
                height = int(quality)
                # More specific format selection
                format_str = (
                    f'bestvideo[height={height}][ext={format_type}]+'
                    f'bestaudio[ext=m4a]/bestvideo[height<={height}][ext={format_type}]+'
                    f'bestaudio[ext=m4a]/best[height<={height}]'
                )
            
            ydl_opts.update({
                'format': format_str,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': format_type,
                }]
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = str(Path(filename).with_suffix(f'.{format_type}'))
            
            # Get just the filename without the full path
            download_filename = Path(filename).name
            
            return jsonify({
                'success': True,
                'filename': download_filename,
                'download_url': url_for('serve_download', filename=download_filename),
                'progress': progress_tracker.progress,
                'status': progress_tracker.status
            })

    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'progress': 0,
            'status': f'Error: {str(e)}'
        }), 500

@app.route('/download-audio-video')
def download_audio_video():
    return render_template('download_audio_video.html')

@app.route('/fetch-video-info', methods=['POST'])
def fetch_video_info():
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Configure yt-dlp options for info extraction
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best'  # Request best format to get all format info
        }

        # Extract video info
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract relevant information
            video_info = {
                'title': info.get('title', 'Unknown Title'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'description': info.get('description', ''),
                'view_count': info.get('view_count', 0),
                'formats': []
            }

            # Extract available formats and qualities
            formats = info.get('formats', [])
            available_qualities = set()
            
            for f in formats:
                if f.get('height'):
                    available_qualities.add(f.get('height'))
                
                format_info = {
                    'format_id': f.get('format_id', ''),
                    'ext': f.get('ext', ''),
                    'quality': f.get('quality', 0),
                    'height': f.get('height', 0),
                    'filesize': f.get('filesize', 0),
                    'vcodec': f.get('vcodec', ''),
                    'acodec': f.get('acodec', '')
                }
                video_info['formats'].append(format_info)
            
            # Add available qualities to response
            video_info['available_qualities'] = sorted(list(available_qualities), reverse=True)

            return jsonify({
                'success': True,
                'video_info': video_info
            })

    except Exception as e:
        error_msg = str(e)
        print(f"Info fetch error: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/downloads/<filename>')
def serve_download(filename):
    return send_from_directory(
        app.config['DOWNLOAD_FOLDER'],
        filename,
        as_attachment=False
    )

@app.route('/tiktok-downloader')
def tiktok_downloader():
    return render_template('tiktok_downloader.html')

@app.route('/tiktok-download', methods=['POST'])
def tiktok_download():
    profile_url = request.form.get('profile_url')
    
    if not profile_url:
        return jsonify({'error': 'No URL provided'}), 400
    
    if not is_valid_tiktok_url(profile_url):
        return jsonify({'error': 'Invalid TikTok profile URL'}), 400
    
    download_type = request.form.get('downloadType', 'video')  # Determine download type (video or audio)
    file_extension = 'mp4' if download_type == 'video' else 'mp3'  # Set file extension based on download type
    
    try:
        username = get_username_from_url(profile_url)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        progress_tracker = ProgressTracker()
        
        # Configure yt-dlp options
        ydl_opts = {
            'outtmpl': os.path.join(
                app.config['DOWNLOAD_FOLDER'],
                f'tiktok_{timestamp}_%(id)s.{file_extension}'  # Use the determined file extension
            ),
            'format': 'best',
            'playlistend': 10,  # Limit to 10 videos
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'progress_hooks': [progress_tracker.update_progress],
        }
        
        processed_videos = []
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract playlist info first
            playlist_info = ydl.extract_info(profile_url, download=False)
            
            # Process only the first 10 videos
            for entry in playlist_info['entries'][:10]:
                video_id = entry['id']
                video_url = f"https://www.tiktok.com/@{username}/video/{video_id}"
                
                # Check Redis for existing downloads
                if redis_client.exists(video_id):
                    logger.info(f"Video {video_id} already downloaded. Skipping.")
                    # Retrieve video info from Redis
                    video_data = redis_client.hgetall(video_id)
                    processed_videos.append({
                        'id': video_id,
                        'title': entry.get('title', 'Unknown Title'),
                        'description': entry.get('description', ''),
                        'duration_string': entry.get('duration_string', 'N/A'),
                        'view_count': entry.get('view_count', 0),
                        'like_count': entry.get('like_count', 0),
                        'comment_count': entry.get('comment_count', 0),
                        'uploader': entry.get('uploader', 'Unknown Uploader'),
                        'uploader_url': entry.get('uploader_url', '#'),
                        'url': video_data.get('url', '')
                    })
                    continue
                
                # Download individual video
                video_info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(video_info)
                
                # Clean filename and ensure it exists
                clean_filename = os.path.basename(filename)
                
                # Store metadata in Redis
                redis_client.hset(video_id, mapping={
                    'id': video_id,
                    'title': entry.get('title', 'Unknown Title'),
                    'description': entry.get('description', ''),
                    'duration_string': entry.get('duration_string', 'N/A'),
                    'view_count': entry.get('view_count', 0),
                    'like_count': entry.get('like_count', 0),
                    'comment_count': entry.get('comment_count', 0),
                    'uploader': entry.get('uploader', 'Unknown Uploader'),
                    'uploader_url': entry.get('uploader_url', '#'),
                    'url': url_for('serve_download', filename=clean_filename)
                })
                
                processed_videos.append({
                    'id': video_info['id'],
                    'title': video_info.get('title', '').split('#')[0][:50],  # Truncate title and remove hashtags
                    'description': video_info.get('description', '')[:100],  # Truncate description
                    'description': entry.get('description', ''),
                    'duration_string': entry.get('duration_string', 'N/A'),
                    'view_count': entry.get('view_count', 0),
                    'like_count': entry.get('like_count', 0),
                    'comment_count': entry.get('comment_count', 0),
                    'uploader': entry.get('uploader', 'Unknown Uploader'),
                    'uploader_url': entry.get('uploader_url', '#'),
                    'url': url_for('serve_download', filename=clean_filename)
                })
        
        if not processed_videos:
            raise Exception('No videos were downloaded successfully')
            
        return render_template('tiktok_results.html', 
            content={
                'username': username,
                'videos': processed_videos
            }, 
            google_client_id=GOOGLE_CLIENT_ID,
            youtube_client_id=YOUTUBE_CLIENT_ID,
            playlist_info=playlist_info
        )
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to download TikTok videos. Please check the URL and try again.'
        }), 500

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
        # Handle both URL formats:
        # https://www.tiktok.com/@username
        # https://www.tiktok.com/@username/video/1234567890
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        
        # Find the username part (starts with @)
        username = next((part for part in path_parts if part.startswith('@')), None)
        
        if not username:
            raise ValueError('Username not found in URL')
            
        # Remove @ symbol from username
        return username[1:]
    except Exception as e:
        raise ValueError(f'Failed to extract username from URL: {str(e)}')

# Initialize Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Define OAuth scopes
OAUTH_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

# Add test users configuration
TEST_USERS = [
    'deverbishal331@gmail.com'  # Add your test user email
]

@app.route('/get-youtube-auth-url', methods=['GET'])
def get_youtube_auth_url():
    try:
        # Load client configuration
        client_config = {
            "web": {
                "client_id": YOUTUBE_CLIENT_ID,
                "project_id": "tiktok-to-youtube-shorts",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "redirect_uris": ["http://localhost:5001/oauth2callback"],
                "javascript_origins": ["http://localhost:5001"]
            }
        }

        # Create the OAuth2 flow with all required scopes
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=OAUTH_SCOPES,
            redirect_uri="http://localhost:5001/oauth2callback"
        )
        
        # Generate the authorization URL with test users
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=os.urandom(16).hex(),
            login_hint=TEST_USERS[0]
        )
        
        # Store state in session
        session['oauth_state'] = state
        logger.info(f"Generated auth URL: {auth_url}")
        logger.info(f"State stored in session: {state}")
        
        return jsonify({'auth_url': auth_url})
    except Exception as e:
        logger.error(f"Error generating auth URL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/oauth2callback')
def oauth2callback():
    try:
        # Verify state parameter
        state = request.args.get('state')
        stored_state = session.get('oauth_state')
        
        logger.info(f"Received state: {state}")
        logger.info(f"Stored state: {stored_state}")
        
        if not state or state != stored_state:
            logger.error("State mismatch or missing")
            return jsonify({'error': 'Invalid state parameter'}), 400

        # Get the authorization code
        code = request.args.get('code')
        if not code:
            logger.error("No authorization code received")
            return jsonify({'error': 'No authorization code received'}), 400

        # Create the OAuth2 flow with the same configuration
        client_config = {
            "web": {
                "client_id": YOUTUBE_CLIENT_ID,
                "project_id": "tiktok-to-youtube-shorts",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "redirect_uris": ["http://localhost:5001/oauth2callback"],
                "javascript_origins": ["http://localhost:5001"]
            }
        }

        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=OAUTH_SCOPES,
            redirect_uri="http://localhost:5001/oauth2callback"
        )

        # Exchange the authorization code for credentials
        flow.fetch_token(code=code)
        credentials = flow.credentials

        if not credentials or not credentials.refresh_token:
            logger.error("No refresh token received")
            return jsonify({'error': 'Failed to obtain refresh token. Please try again.'}), 400

        # Store credentials in session
        session['youtube_credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        logger.info("Successfully obtained and stored credentials with refresh token")
        return render_template('oauth2_success.html')
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload-video', methods=['POST'])
def upload_video():
    try:
        logger.info("Received upload request")
        if 'youtube_credentials' not in session:
            return jsonify({'error': 'Not authenticated with YouTube. Please sign in first.'}), 401

        creds_data = session.get('youtube_credentials')
        if not creds_data or 'refresh_token' not in creds_data:
            logger.error("No refresh token found in credentials")
            return jsonify({'error': 'Invalid credentials. Please authorize again.'}), 401

        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        video_url = data.get('video_url')
        title = data.get('title')
        description = data.get('description')

        if not all([video_url, title, description]):
            missing = []
            if not video_url: missing.append('video_url')
            if not title: missing.append('title')
            if not description: missing.append('description')
            return jsonify({'error': f"Missing required fields: {', '.join(missing)}"}), 400

        # Create credentials from stored session data
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )

        # Check if credentials are expired and refresh if needed
        if credentials.expired:
            logger.info("Refreshing expired credentials")
            refresh_request = google_requests.Request()
            credentials.refresh(refresh_request)
            session['youtube_credentials']['token'] = credentials.token

        # Download the video to a temporary file
        logger.info("Downloading video to temporary file...")
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            download_response = requests.get(video_url, stream=True)
            download_response.raise_for_status()
            for chunk in download_response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        logger.info("Video downloaded successfully")

        try:
            # Verify video properties and convert if necessary
            clip = VideoFileClip(temp_file_path)
            duration = clip.duration
            width = clip.w
            height = clip.h
            
            if duration > 180:  # 3 minutes max
                raise ValueError("Video is too long for Shorts (max 3 minutes)")

            # Calculate current aspect ratio
            current_ratio = height / width if width > 0 else 0
            target_ratio = 16/9  # Target ratio for Shorts (9:16 vertical)
            
            # If aspect ratio isn't 9:16, convert it
            if abs(current_ratio - target_ratio) > 0.1:  # Allow small deviation
                logger.info("Converting video to 9:16 aspect ratio")
                
                # Create a new temporary file for the converted video
                converted_temp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                converted_path = converted_temp.name
                
                # Calculate new dimensions (maintaining 9:16 ratio)
                new_height = 1920  # Standard Shorts height
                new_width = 1080   # Standard Shorts width
                
                # Create black background with matching duration
                final_clip = ColorClip(size=(new_width, new_height), 
                                     color=(0,0,0),
                                     duration=clip.duration)
                
                # Resize video maintaining aspect ratio
                # Calculate resize dimensions while preserving aspect ratio
                original_ratio = clip.w / clip.h
                target_ratio = new_width / new_height

                if original_ratio > target_ratio:
                    # Width is the limiting factor
                    resized_clip = clip.resize(width=new_width)
                else:
                    # Height is the limiting factor
                    resized_clip = clip.resize(height=new_height)
                
                # Position video in center
                x_center = (new_width - resized_clip.w) // 2
                y_center = (new_height - resized_clip.h) // 2
                
                # Composite video onto black background
                final_clip = CompositeVideoClip(
                    [final_clip, resized_clip.set_position((x_center, y_center))],
                    size=(new_width, new_height)
                ).set_duration(clip.duration)
                
                # Write converted video with high quality settings
                final_clip.write_videofile(
                    converted_path,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate='16000k',  # Doubled bitrate for better quality
                    preset='veryslow',  # Use veryslow preset for maximum quality
                    ffmpeg_params=[
                        '-profile:v', 'high',
                        '-level', '4.2',
                        '-crf', '15',        # Lower CRF value for even higher quality
                        '-movflags', '+faststart',
                        '-pix_fmt', 'yuv420p',
                        '-bufsize', '32000k',  # Increased buffer size
                        '-maxrate', '16000k',  # Maximum bitrate
                        '-g', '30',            # Keyframe interval
                        '-keyint_min', '25',   # Minimum keyframe interval
                        '-sc_threshold', '0',  # Disable scene change detection
                        '-bf', '2',            # Maximum 2 B-frames
                        '-refs', '6',          # Use 6 reference frames
                        '-threads', '0'        # Use all available threads
                    ],
                    audio_bitrate='384k',
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True,
                    fps=30,  # Ensure consistent frame rate
                    logger=None,  # Disable progress bar to reduce overhead
                    verbose=False,
                    threads=0,  # Use all available CPU threads
                    write_logfile=True  # Enable logging for debugging
                )

                # Verify the converted video
                logger.info("Verifying converted video...")
                try:
                    verification_clip = VideoFileClip(converted_path)
                    if verification_clip.duration == 0 or verification_clip.w == 0 or verification_clip.h == 0:
                        raise ValueError("Converted video verification failed: Invalid dimensions or duration")
                    verification_clip.close()
                except Exception as ve:
                    logger.error(f"Video conversion verification failed: {str(ve)}")
                    raise ValueError("Failed to create a valid converted video")

                # Close clips in reverse order of creation
                if 'final_clip' in locals() and final_clip is not None:
                    final_clip.close()
                if 'resized_clip' in locals() and resized_clip is not None:
                    resized_clip.close()
                if 'clip' in locals() and clip is not None:
                    clip.close()

                # Update the path to use the verified converted video
                clip = VideoFileClip(converted_path)
                temp_file_path = converted_path

            logger.info("Creating YouTube API client...")
            youtube = build('youtube', 'v3', credentials=credentials)

            # Enhanced Shorts-specific metadata
            request_body = {
                'snippet': {
                    'title': f"#Shorts | {title[:90]}",
                    'description': f"{description}\n\n#Shorts #Short #YouTubeShorts #Vertical",
                    'tags': ['Shorts', 'YouTube Shorts', 'Short', 'Vertical Video'],
                    'categoryId': '24'
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False,
                    'embeddable': True
                }
            }

            logger.info("Starting video upload...")
            media = MediaFileUpload(
                temp_file_path,
                mimetype='video/mp4',
                resumable=True,
                chunksize=1024*1024
            )

            insert_request = youtube.videos().insert(
                part='snippet,status',
                body=request_body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    logger.info(f"Uploaded {int(status.progress() * 100)}%")

            video_id = response['id']
            logger.info(f"Video uploaded successfully. Video ID: {video_id}")

            return jsonify({
                'success': True,
                'video_id': video_id,
                'message': 'Video uploaded successfully to YouTube Shorts'
            })

        except ValueError as ve:
            logger.error(f"Video validation error: {str(ve)}")
            return jsonify({'error': str(ve)}), 400
        except Exception as e:
            logger.error(f"Error during video upload: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            # Clean up resources
            temp_files_to_delete = []
            
            # Add the initial temp file to the cleanup list
            if 'temp_file_path' in locals():
                temp_files_to_delete.append(temp_file_path)
            
            # Add the converted file if it exists
            if 'converted_path' in locals():
                temp_files_to_delete.append(converted_path)
            
            # Close video clips if they exist
            try:
                if 'clip' in locals() and clip is not None:
                    clip.close()
                if 'resized_clip' in locals() and resized_clip is not None:
                    resized_clip.close()
                if 'final_clip' in locals() and final_clip is not None:
                    final_clip.close()
            except Exception as e:
                logger.error(f"Error closing video clips: {str(e)}")
            
            # Delete all temporary files
            for temp_file in temp_files_to_delete:
                try:
                    if temp_file and os.path.exists(temp_file):
                        os.unlink(temp_file)
                        logger.info(f"Successfully deleted temporary file: {temp_file}")
                except Exception as e:
                    logger.error(f"Error deleting temporary file {temp_file}: {str(e)}")
                    continue

    except Exception as e:
        logger.error(f"Error in upload_video: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/tiktok-results')
def tiktok_results():
    logger.info(f"Using Google Client ID: {GOOGLE_CLIENT_ID}")  # Add logging
    return render_template('tiktok_results.html',
        content=session.get('content', {}),
        google_client_id=GOOGLE_CLIENT_ID,
        youtube_client_id=YOUTUBE_CLIENT_ID
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', '5001'), debug=True)