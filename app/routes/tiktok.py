from flask import Blueprint, request, jsonify, render_template, url_for, session, current_app, abort
import os
from pathlib import Path
import logging
import yt_dlp
import uuid
import time
from urllib.parse import urlparse
from datetime import datetime

from ..routes.media import save_media_metadata
from ..utils.path import get_download_path, get_relative_path, ensure_directories, TIKTOK_DIR
from ..services.cache import MediaCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Blueprint
tiktok_bp = Blueprint('tiktok', __name__)

# Initialize MediaCache for TikTok
tiktok_cache = MediaCache('tiktok')

# Ensure directories exist
ensure_directories()

def validate_tiktok_url(url):
    """Validate if the URL is a valid TikTok URL and extract username."""
    try:
        parsed_url = urlparse(url)
        valid_domains = ['tiktok.com', 'www.tiktok.com', 'vt.tiktok.com', 'm.tiktok.com']
        
        if not any(domain in parsed_url.netloc for domain in valid_domains):
            return False, "Invalid TikTok URL domain", None
            
        # For profile URLs
        if '@' in parsed_url.path:
            username = parsed_url.path.split('@')[1].split('?')[0].split('/')[0]
            if username:
                return True, "profile", username
            
        # For single video URLs
        if '/video/' in url or 'vt.tiktok.com' in url:
            return True, "video", None
            
        return False, "Invalid TikTok URL format", None
    except Exception as e:
        return False, f"URL validation error: {str(e)}", None

def download_tiktok_content(url, user_id, profile_username=None):
    """Download TikTok content and save metadata."""
    try:
        # Check if content is already cached
        cached_media = tiktok_cache.get_cached_media(url, user_id)
        if cached_media:
            logger.info(f"Using cached media for URL: {url}")
            return cached_media, cached_media['file_path']

        # Prepare download path with timestamp and unique ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        
        # Create filename template
        filename_template = f'tiktok_%(title)s_{timestamp}_{unique_id}.%(ext)s'
        
        # Create output template using get_download_path
        output_template = str(get_download_path('tiktok', filename_template))
        
        # Download options
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'restrictfilenames': True,
            'writeinfojson': False,
            'writethumbnail': False
        }

        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Download the video
                info = ydl.extract_info(url, download=True)
                filename = Path(ydl.prepare_filename(info))
                
                # Ensure file was downloaded successfully
                if not filename.exists() or filename.stat().st_size == 0:
                    raise Exception(f"Download failed: File not found or empty - {filename}")
                
                # Get relative path for storage
                relative_path = get_relative_path(filename)
                
                # Prepare media info
                media_info = {
                    'id': info['id'],
                    'title': info.get('title', ''),
                    'file_path': f"tiktok/{filename.name}",  # Store with platform prefix
                    'metadata': {
                        'duration': info.get('duration', 0),
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'comment_count': info.get('comment_count', 0),
                        'uploader': info.get('uploader', ''),
                        'description': info.get('description', ''),
                        'upload_date': info.get('upload_date', '')
                    }
                }
                
                # Save to database
                save_media_metadata(
                    user_id=user_id,
                    platform='tiktok',
                    media_type='video',
                    file_path=media_info['file_path'],
                    title=media_info['title'],
                    original_url=url,
                    duration=media_info['metadata']['duration'],
                    metadata=media_info['metadata']
                )
                
                # Cache the media info
                if not tiktok_cache.cache_media(url, user_id, media_info):
                    logger.warning(f"Failed to cache media for URL: {url}")
                else:
                    logger.info(f"Successfully downloaded and cached: {url}")
                
                return media_info, media_info['file_path']
                
            except Exception as e:
                # Clean up any partially downloaded files
                try:
                    if 'filename' in locals() and filename.exists():
                        filename.unlink()
                        logger.info(f"Cleaned up failed download: {filename}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up failed download: {cleanup_error}")
                raise
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise

@tiktok_bp.route('/tiktok-downloader')
def tiktok_downloader():
    """Render TikTok downloader page."""
    return render_template('tiktok_downloader.html')

@tiktok_bp.route('/tiktok-single-download', methods=['POST'])
def tiktok_single_download():
    """Handle single TikTok video download."""
    if not session.get('user'):
        return jsonify({'error': 'Please login to download content'}), 401

    url = request.form.get('video_url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # Validate URL
    is_valid, url_type = validate_tiktok_url(url)
    if not is_valid or url_type != "video":
        return jsonify({'error': 'Invalid TikTok video URL'}), 400

    try:
        user_id = session['user']['id']

        # Check if video is already cached
        if tiktok_cache.is_media_cached(url, user_id):
            cached_media = tiktok_cache.get_cached_media(url, user_id)
            if cached_media:
                return render_template('tiktok_results.html',
                    content={
                        'username': cached_media['metadata']['uploader'],
                        'videos': [{
                            'id': cached_media['id'],
                            'title': cached_media['title'],
                            'description': cached_media['metadata']['description'],
                            'duration_string': str(cached_media['metadata']['duration']),
                            'view_count': cached_media['metadata']['view_count'],
                            'like_count': cached_media['metadata']['like_count'],
                            'comment_count': cached_media['metadata']['comment_count'],
                            'uploader': cached_media['metadata']['uploader'],
                            'url': url_for('media.serve_download', filename=cached_media['file_path'])
                        }]
                    }
                )

        media_info, filename = download_tiktok_content(url, user_id)
        
        return render_template('tiktok_results.html',
            content={
                'username': media_info['metadata']['uploader'],
                'videos': [{
                    'id': media_info['id'],
                    'title': media_info['title'],
                    'description': media_info['metadata']['description'],
                    'duration_string': str(media_info['metadata']['duration']),
                    'view_count': media_info['metadata']['view_count'],
                    'like_count': media_info['metadata']['like_count'],
                    'comment_count': media_info['metadata']['comment_count'],
                    'uploader': media_info['metadata']['uploader'],
                    'url': url_for('media.serve_download', filename=media_info['file_path'])
                }]
            }
        )

    except Exception as e:
        logger.error(f"TikTok download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to download TikTok video. Please check the URL and try again.'
        }), 500

@tiktok_bp.route('/tiktok-profile-download', methods=['POST'])
def tiktok_profile_download():
    """Handle TikTok profile download request."""
    if not session.get('user'):
        return jsonify({'error': 'Please login to download content'}), 401

    url = request.form.get('profile_url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # Validate URL and get username
    is_valid, url_type, username = validate_tiktok_url(url)
    if not is_valid or url_type != "profile":
        return jsonify({'error': 'Invalid TikTok profile URL'}), 400

    if not username:
        return jsonify({'error': 'Could not extract username from URL'}), 400

    try:
        user_id = session['user']['id']
        logger.info(f"Processing TikTok profile for username: {username}")

        processed_videos = []
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'playlistend': 10  # Limit to 10 videos
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract playlist info first
            playlist_info = ydl.extract_info(url, download=False)
            
            # Process only the first 10 videos
            for entry in playlist_info['entries'][:10]:
                video_url = f"https://www.tiktok.com/@{username}/video/{entry['id']}"
                
                # Check if video is already cached
                cached_media = tiktok_cache.get_cached_media(video_url, user_id)
                if cached_media:
                    logger.info(f"Using cached media for URL: {video_url}")
                    processed_videos.append({
                        'id': cached_media['id'],
                        'title': cached_media['title'],
                        'description': cached_media['metadata']['description'],
                        'duration_string': str(cached_media['metadata']['duration']),
                        'view_count': cached_media['metadata']['view_count'],
                        'like_count': cached_media['metadata']['like_count'],
                        'comment_count': cached_media['metadata']['comment_count'],
                        'uploader': username,
                        'file_path': cached_media['file_path'],  # Keep original file_path for caching
                        'url': url_for('media.serve_download', filename=cached_media['file_path'])  # Use full file_path
                    })
                else:
                    # Download new video
                    media_info, _ = download_tiktok_content(video_url, user_id, username)
                    processed_videos.append({
                        'id': media_info['id'],
                        'title': media_info['title'],
                        'description': media_info['metadata']['description'],
                        'duration_string': str(media_info['metadata']['duration']),
                        'view_count': media_info['metadata']['view_count'],
                        'like_count': media_info['metadata']['like_count'],
                        'comment_count': media_info['metadata']['comment_count'],
                        'uploader': username,
                        'file_path': media_info['file_path'],  # Keep original file_path for caching
                        'url': url_for('media.serve_download', filename=media_info['file_path'])  # Use full file_path
                    })

        if not processed_videos:
            raise Exception('No videos were downloaded successfully')

        # Cache the profile videos
        try:
            tiktok_cache.cache_bulk_media(url, user_id, processed_videos)
        except Exception as cache_error:
            logger.error(f"Failed to cache profile videos: {str(cache_error)}")
            # Continue even if caching fails

        # Return only the display data (without file_path)
        display_videos = [{k: v for k, v in video.items() if k != 'file_path'} 
                         for video in processed_videos]

        return render_template('tiktok_results.html',
            content={
                'username': username,
                'videos': display_videos
            }
        )

    except Exception as e:
        logger.error(f"TikTok profile download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to download TikTok videos. Please check the URL and try again.'
        }), 500

# Enhanced cleanup function
def cleanup_old_downloads():
    """Cleanup old downloads and cache."""
    try:
        max_age = 3600  # 1 hour
        current_time = time.time()
        
        # Clean up files in the main TikTok directory
        for file in TIKTOK_DIR.iterdir():
            try:
                if file.is_file():
                    file_age = current_time - file.stat().st_mtime
                    if file_age > max_age:
                        file.unlink()
                        logger.info(f"Deleted old file: {file}")
            except Exception as e:
                logger.error(f"Error deleting file {file}: {str(e)}")

        # Clean up expired cache entries
        tiktok_cache.cleanup_expired_cache()
    except Exception as e:
        logger.error(f"Error in cleanup: {str(e)}", exc_info=True)