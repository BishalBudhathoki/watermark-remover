from flask import Blueprint, request, jsonify, render_template, session, current_app, abort
from pathlib import Path
import logging
import yt_dlp
import json
import requests
from datetime import datetime
from urllib.parse import urlparse
import os

from ..services.cache import MediaCache
from ..utils.path import get_download_path, get_relative_path
from ..routes.media import save_media_metadata

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
instagram_bp = Blueprint('instagram', __name__)

# Initialize MediaCache for Instagram
instagram_cache = MediaCache('instagram')

def validate_instagram_url(url: str) -> tuple[bool, str]:
    """Validate if the URL is a valid Instagram URL."""
    try:
        parsed_url = urlparse(url)
        if not parsed_url.netloc in ['www.instagram.com', 'instagram.com']:
            return False, "Invalid Instagram URL domain"
        
        path_parts = parsed_url.path.strip('/').split('/')
        if not path_parts:
            return False, "Invalid URL format"
            
        valid_types = ['p', 'reel', 'stories']
        if any(t in url for t in valid_types):
            if len(path_parts) < 2:
                return False, "Invalid content URL format"
        else:
            if not path_parts[0]:
                return False, "Invalid profile URL format"
                
        return True, None
    except Exception as e:
        return False, f"URL validation error: {str(e)}"

@instagram_bp.route('/instagram-downloader')
def instagram_downloader():
    """Render Instagram downloader page."""
    return render_template('instagram_downloader.html')

@instagram_bp.route('/instagram-download', methods=['POST'])
def instagram_download():
    """Handle Instagram content download."""
    try:
        # Check authentication
        if not session.get('user'):
            return jsonify({'error': 'Please login to download content'}), 401

        url = request.form.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Validate URL
        is_valid, error_message = validate_instagram_url(url)
        if not is_valid:
            return jsonify({'error': error_message}), 400

        # Clean up the URL to remove query parameters and get the shortcode
        cleaned_url = url.split('?')[0].rstrip('/')
        shortcode = cleaned_url.split('/')[-1]
        
        # Check if content is already cached
        cached_media = instagram_cache.get_cached_media(url, session['user']['id'])
        if cached_media:
            logger.info(f"Using cached media for URL: {url}")
            # Log the cached file path for debugging
            logger.info(f"Cached file path: {cached_media['file_path']}")
            
            return render_template('instagram_results.html',
                content={
                    'username': cached_media['metadata']['uploader'],
                    'posts': [{
                        'type': cached_media.get('media_type', 'video'),
                        'caption': cached_media.get('description', ''),
                        'likes': cached_media['metadata'].get('like_count', 0),
                        'comments': cached_media['metadata'].get('comment_count', 0),
                        'date': datetime.fromtimestamp(cached_media['metadata'].get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                        'filename': Path(cached_media['file_path']).name,  # Just the filename part
                        'shortcode': shortcode,
                        'extension': 'mp4'  # Always mp4 due to forced conversion
                    }]
                }
            )

        # Configure headers with more browser-like values
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"'
        }

        # First try with yt-dlp
        try:
            # Prepare download path
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_template = get_download_path(
                'instagram',
                f'instagram_{shortcode}_{timestamp}.%(ext)s'
            )

            ydl_opts = {
                'outtmpl': str(output_template),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # Force mp4 format
                'quiet': True,
                'no_warnings': True,
                'http_headers': headers,
                'extract_flat': False,
                'writeinfojson': False,
                'writethumbnail': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',  # Force conversion to mp4
                }],
                'cookiesfrombrowser': ('chrome',),  # Try to use Chrome cookies
                'socket_timeout': 30,  # Increase timeout
                'retries': 10,  # Increase retries
                'ignoreerrors': False,  # Don't ignore errors
                'nocheckcertificate': True,  # Skip certificate validation
                'extractor_args': {
                    'instagram': {
                        'direct': True,  # Try direct download
                        'fatal_direct': False  # Don't fail if direct download fails
                    }
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # First try to extract info without downloading
                    info = ydl.extract_info(url, download=False)
                    logger.info(f"Successfully extracted info for URL: {url}")
                    
                    # Then download
                    info = ydl.extract_info(url, download=True)
                    filename = Path(ydl.prepare_filename(info))
                    
                    # Ensure file has .mp4 extension
                    if not filename.suffix or filename.suffix == '.NA':
                        new_filename = filename.with_suffix('.mp4')
                        if filename.exists():
                            filename.rename(new_filename)
                        filename = new_filename
                    
                    # Get relative path for storage
                    relative_path = f"instagram/{filename.name}"  # Store with platform prefix

                    # Prepare media info
                    media_info = {
                        'id': shortcode,
                        'title': info.get('title', f'Instagram Post {shortcode}'),
                        'file_path': relative_path,  # Use platform-prefixed path
                        'media_type': 'video',
                        'description': info.get('description', ''),
                        'metadata': {
                            'uploader': info.get('uploader', 'unknown'),
                            'like_count': info.get('like_count', 0),
                            'comment_count': info.get('comment_count', 0),
                            'timestamp': info.get('timestamp', int(datetime.now().timestamp())),
                            'duration': info.get('duration', 0)
                        }
                    }

                    # Save to database
                    save_media_metadata(
                        user_id=session['user']['id'],
                        platform='instagram',
                        media_type='video',
                        file_path=relative_path,
                        title=media_info['title'],
                        original_url=url,
                        duration=media_info['metadata'].get('duration', 0),
                        metadata=json.dumps({  # Properly format metadata
                            'uploader': media_info['metadata'].get('uploader', 'unknown'),
                            'like_count': media_info['metadata'].get('like_count', 0),
                            'comment_count': media_info['metadata'].get('comment_count', 0),
                            'timestamp': media_info['metadata'].get('timestamp', int(datetime.now().timestamp())),
                            'description': media_info.get('description', ''),
                            'duration': media_info['metadata'].get('duration', 0)
                        })
                    )

                    # Log successful save
                    logger.info(f"Saved Instagram media to database: {media_info['title']}")

                    # Cache the media info
                    if not instagram_cache.cache_media(url, session['user']['id'], media_info):
                        logger.warning(f"Failed to cache media for URL: {url}")
                    else:
                        logger.info(f"Successfully downloaded and cached: {url}")

                    # Log the file paths for debugging
                    logger.info(f"File path: {filename}")
                    logger.info(f"Relative path: {relative_path}")
                    logger.info(f"Media info: {media_info}")

                    return render_template('instagram_results.html',
                        content={
                            'username': media_info['metadata']['uploader'],
                            'posts': [{
                                'type': 'video',
                                'caption': media_info.get('description', ''),
                                'likes': media_info['metadata'].get('like_count', 0),
                                'comments': media_info['metadata'].get('comment_count', 0),
                                'date': datetime.fromtimestamp(media_info['metadata'].get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                                'filename': filename.name,
                                'shortcode': shortcode,
                                'extension': 'mp4'
                            }]
                        }
                    )
                except Exception as e:
                    logger.error(f"Error during download: {str(e)}")
                    raise

        except Exception as e:
            logger.warning(f"yt-dlp download failed: {str(e)}")
            return jsonify({
                'error': str(e),
                'message': 'Failed to download Instagram content. Please check the URL and try again.'
            }), 500

    except Exception as e:
        logger.error(f"Instagram download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to download Instagram content. Please check the URL and try again.'
        }), 500 