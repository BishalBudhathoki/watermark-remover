# app.py
import os
import tempfile
import sys
import yt_dlp
from urllib.parse import urlparse, unquote
from flask import Flask, request, render_template, redirect, url_for, send_file, send_from_directory, jsonify
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
import redis
import glob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
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

    def update_progress(self, d):
        if d['status'] == 'downloading':
            self.progress = (d.get('downloaded_bytes', 0) / d.get('total_bytes', 1)) * 100
            self.status = f'Downloading: {self.progress:.1f}%'
        elif d['status'] == 'finished':
            self.progress = 100
            self.status = 'Download complete'
        elif d['status'] == 'error':
            self.status = f'Error: {d.get("error")}'

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

# Load environment variables
load_dotenv()

# API Configuration
RAPID_API_KEY = os.getenv('RAPID_API_KEY')
RAPID_API_HOST = os.getenv('RAPID_API_HOST')

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
    return render_template('index.html')

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
            
        return render_template('tiktok_results.html', content={
            'username': username,
            'videos': processed_videos
        }, playlist_info=playlist_info)
            
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', '5001'), debug=True)