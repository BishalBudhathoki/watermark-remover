from flask import Blueprint, request, jsonify, render_template, url_for, session, current_app, abort, redirect
from pathlib import Path
from urllib.parse import urlparse
import logging
import yt_dlp
import uuid
from datetime import datetime
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os

from ..services.cache import MediaCache
from ..utils.path import get_download_path, get_relative_path
from ..routes.media import save_media_metadata

logger = logging.getLogger(__name__)

def get_yt_dlp_opts():
    """Get default options for yt-dlp."""
    return {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'format': 'best',
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'no_color': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate'
        }
    }

# Create Blueprint
youtube_bp = Blueprint('youtube', __name__)

# Initialize MediaCache for YouTube
youtube_cache = MediaCache('youtube')

# YouTube OAuth configuration
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

@youtube_bp.route('/get-youtube-auth-url')
def get_youtube_auth_url():
    """Generate YouTube OAuth URL."""
    try:
        # Use a fixed redirect URI that matches what's registered in Google Cloud Console
        # This should be the exact same URI that you registered in the Google Cloud Console
        redirect_uri = url_for('youtube.oauth_callback', _external=True)

        # Log the redirect URI for debugging
        logger.info(f"Using redirect URI: {redirect_uri}")

        # Store the return URL in session for later use
        session['youtube_callback_return_url'] = session.get('youtube_auth_return_url')

        # Get client ID and secret from environment variables
        client_id = os.getenv('YOUTUBE_CLIENT_ID')
        client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')

        if not client_id or not client_secret:
            logger.error("Missing YouTube client credentials in environment variables")
            return jsonify({'error': 'Missing YouTube client credentials'}), 500

        # Create client config dictionary
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [redirect_uri]
            }
        }

        # Create flow from client config
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )

        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )

        return jsonify({
            'auth_url': auth_url
        })

    except Exception as e:
        logger.error(f"Error generating auth URL: {str(e)}")
        return jsonify({'error': str(e)}), 500

def validate_youtube_url(url: str) -> tuple[bool, str]:
    """Validate if the URL is a valid YouTube URL."""
    try:
        parsed_url = urlparse(url)
        valid_domains = ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com']

        if not any(domain in parsed_url.netloc for domain in valid_domains):
            return False, "Invalid YouTube URL domain"

        # For youtu.be short URLs
        if 'youtu.be' in parsed_url.netloc:
            if not parsed_url.path[1:]:
                return False, "Invalid YouTube short URL format"
            return True, "video"

        # For youtube.com URLs
        if '/watch' in parsed_url.path:
            if not 'v=' in parsed_url.query:
                return False, "Invalid YouTube video URL format"
            return True, "video"

        # For YouTube Shorts
        if '/shorts/' in parsed_url.path:
            video_id = parsed_url.path.split('/shorts/')[1].split('/')[0]
            if video_id and len(video_id) > 0:
                return True, "video"
            return False, "Invalid YouTube shorts URL format"

        # For YouTube Live streams
        if '/live/' in parsed_url.path:
            live_id = parsed_url.path.split('/live/')[1].split('/')[0]
            if live_id and len(live_id) > 0:
                return True, "video"
            return False, "Invalid YouTube live URL format"

        if '/playlist' in parsed_url.path:
            if not 'list=' in parsed_url.query:
                return False, "Invalid YouTube playlist URL format"
            return True, "playlist"

        if '/channel/' in parsed_url.path or '/c/' in parsed_url.path or '/user/' in parsed_url.path:
            return True, "channel"

        return False, "Invalid YouTube URL format"

    except Exception as e:
        return False, f"URL validation error: {str(e)}"

def download_youtube_content(url: str, user_id: str, download_path: Path) -> tuple[dict, Path]:
    """Download YouTube content and save metadata."""
    try:
        # Check if content is already cached
        cached_media = youtube_cache.get_cached_media(url, user_id)
        if cached_media:
            logger.info(f"Using cached media for URL: {url}")
            file_path = get_download_path('youtube', Path(cached_media['file_path']).name)
            if file_path.exists():
                return cached_media, file_path
            else:
                logger.info(f"Cached file not found, re-downloading: {url}")
                youtube_cache.remove_cached_media(url, user_id)

        # Validate URL before proceeding
        is_valid, url_type = validate_youtube_url(url)
        if not is_valid:
            raise ValueError(f"Invalid YouTube URL: {url_type}")

        # Prepare download path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]

        # Create output template with proper path handling
        output_template = str(download_path.joinpath(
            f'youtube_%(title)s_{timestamp}_{unique_id}.%(ext)s'
        ))

        # Get base options and update with download-specific settings
        ydl_opts = get_yt_dlp_opts()
        ydl_opts.update({
            'outtmpl': str(output_template),
            'extract_flat': False,
            'writeinfojson': False,
            'writethumbnail': False,
            'format': 'best',
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],  # Remove android client to avoid GVS PO Token requirement
                    'player_skip': ['webpage', 'configs'],
                    'max_comments': [0],
                    'formats': ['missing_pot']  # Allow formats without PO Token
                }
            },
            'quiet': False,  # Enable output for better error tracking
            'verbose': True  # Enable verbose output
        })

        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # First try to extract info without downloading
                logger.info(f"Extracting video information for URL: {url}")
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise ValueError("Failed to extract video information")

                # Now proceed with download
                logger.info(f"Downloading video from URL: {url}")
                info = ydl.extract_info(url, download=True)
                filename = Path(ydl.prepare_filename(info))

                # Ensure file was downloaded successfully
                if not filename.exists() or filename.stat().st_size == 0:
                    raise Exception(f"Download failed: File not found or empty - {filename}")

                # Ensure the download directory exists
                download_path.mkdir(parents=True, exist_ok=True)

                # Get relative path for storage
                relative_path = get_relative_path(filename)

                # Prepare media info
                media_info = {
                    'id': info['id'],
                    'title': info.get('title', ''),
                    'file_path': str(relative_path),
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

                # Cache the successful download
                youtube_cache.cache_media(url, user_id, media_info)

                return media_info, filename

            except Exception as e:
                logger.error(f"Error during YouTube download: {str(e)}")
                raise Exception(f"Failed to download video: {str(e)}")

    except Exception as e:
        logger.error(f"YouTube download error: {str(e)}")
        raise

@youtube_bp.route('/youtube-downloader')
def youtube_downloader():
    """Render YouTube video downloader page."""
    return render_template('download_audio_video.html')

@youtube_bp.route('/youtube-single-download', methods=['POST'])
def youtube_single_download():
    """Handle single YouTube video download."""
    if not session.get('user'):
        return jsonify({'error': 'Please login to download content'}), 401

    url = request.form.get('video_url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # Validate URL
    is_valid, url_type = validate_youtube_url(url)
    if not is_valid or url_type != "video":
        return jsonify({'error': 'Invalid YouTube video URL'}), 400

    try:
        user_id = session['user']['id']
        # Specify the download path
        download_path = Path(current_app.config['DOWNLOAD_FOLDER']) / 'youtube'
        download_path.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist

        media_info, filename = download_youtube_content(url, user_id, download_path)

        return render_template('youtube_results.html',
            content={
                'username': media_info['metadata']['uploader'],
                'download_url': url_for('media.serve_download', filename=filename),
                # Add other necessary fields
            }
        )
    except Exception as e:
        logger.error(f"Error processing download request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@youtube_bp.route('/fetch-video-info', methods=['POST'])
def fetch_video_info():
    """Fetch video information from YouTube URL."""
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        is_valid, content_type = validate_youtube_url(url)
        if not is_valid:
            return jsonify({'error': content_type}), 400

        ydl_opts = get_yt_dlp_opts()
        ydl_opts.update({
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'format': 'best',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs'],
                    'max_comments': [0]
                }
            }
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                logger.info(f'Fetching video info for URL: {url}')
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise ValueError('Failed to extract video information')

                # Prepare video info in the expected structure
                video_info = {
                    'title': info.get('title', 'Untitled Video'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'uploader': info.get('uploader', 'Unknown Uploader'),
                    'available_qualities': []
                }

                # Extract available qualities from formats
                if info.get('formats'):
                    qualities = set()
                    for f in info['formats']:
                        if f.get('height') and f.get('vcodec') != 'none':
                            qualities.add(f.get('height'))
                    video_info['available_qualities'] = sorted(list(qualities), reverse=True)

                return jsonify({
                    'success': True,
                    'video_info': video_info
                })

            except Exception as e:
                logger.error(f'Error extracting video info: {str(e)}')
                return jsonify({
                    'error': f'Failed to extract video information: {str(e)}'
                }), 500

    except Exception as e:
        logger.error(f'Error in fetch_video_info: {str(e)}')
        return jsonify({'error': str(e)}), 500

@youtube_bp.route('/download-video', methods=['POST'])
def download_video():
    """Handle video download request."""
    try:
        if not session.get('user'):
            return jsonify({'error': 'Please login to download content'}), 401

        data = request.get_json()
        url = data.get('url')
        download_type = data.get('downloadType')
        format_type = data.get('format')
        quality = data.get('quality')

        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Validate URL
        is_valid, url_type = validate_youtube_url(url)
        if not is_valid:
            return jsonify({'error': url_type}), 400

        # Specify the download path
        download_path = Path(current_app.config['DOWNLOAD_FOLDER']) / 'youtube'
        download_path.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist

        # Configure format based on download type and quality
        ydl_opts = {
            'outtmpl': str(download_path / f'youtube_%(title)s_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True,
        }

        # Quality description for logging and response
        quality_description = quality
        if quality != 'best':
            quality_description = f"{quality}p"

        if download_type == 'audio':
            if format_type == 'mp3':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                })
            else:  # m4a
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                        'preferredquality': '192',
                    }]
                })
        else:  # video
            if quality == 'best':
                format_str = f'bestvideo+bestaudio/best'
            else:
                height = int(quality)
                format_str = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'

            ydl_opts.update({
                'format': format_str,
                'merge_output_format': format_type,
            })

        # Log the download options
        logger.info(f"Downloading {download_type} in {format_type} format with quality {quality_description}")

        # Download the content
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                # Handle potential extension changes from post-processing
                if download_type == 'audio':
                    if format_type == 'mp3':
                        filename = str(Path(filename).with_suffix('.mp3'))
                    elif format_type == 'm4a':
                        filename = str(Path(filename).with_suffix('.m4a'))
                else:
                    filename = str(Path(filename).with_suffix(f'.{format_type}'))

                file_path = Path(filename)

                # Ensure file exists
                if not file_path.exists():
                    raise Exception(f"Download failed: File not found - {file_path}")

                # Get relative path for database
                relative_path = get_relative_path(file_path)

                # Get actual file size
                file_size = file_path.stat().st_size
                file_size_mb = round(file_size / (1024 * 1024), 2)

                # Get actual resolution for videos
                actual_resolution = "N/A"
                if download_type == 'video':
                    try:
                        # Try to get actual resolution from downloaded file
                        formats = info.get('formats', [])
                        logger.info(f"Available formats: {[f.get('format_id', 'unknown') for f in formats]}")

                        # First try to get the selected format
                        selected_format = None
                        format_id = info.get('format_id')
                        requested_format = info.get('requested_format')  # New: check requested format
                        logger.info(f"Looking for format_id: {format_id}, requested_format: {requested_format}")

                        # First check the requested format
                        if requested_format:
                            width = requested_format.get('width')
                            height = requested_format.get('height')
                            if width or height:
                                selected_format = requested_format
                                logger.info(f"Using requested format: {requested_format}")

                        # If no resolution in requested format, look for the exact format
                        if not selected_format:
                            for fmt in formats:
                                if fmt.get('format_id') == format_id:
                                    selected_format = fmt
                                    logger.info(f"Found exact format match: {fmt}")
                                    break

                        # If not found, look for the format with matching height
                        if not selected_format and quality != 'best':
                            target_height = int(quality)
                            logger.info(f"Looking for format with height: {target_height}")
                            matching_formats = [f for f in formats
                                             if f.get('height') == target_height and f.get('vcodec') != 'none']
                            if matching_formats:
                                # Choose the one with the best video codec and bitrate
                                selected_format = max(matching_formats,
                                                    key=lambda f: (f.get('vbr', 0) or 0))
                                logger.info(f"Found height match: {selected_format}")

                        # If still not found, use the format with the best video quality
                        if not selected_format:
                            logger.info("Looking for best video quality format")
                            video_formats = [f for f in formats if f.get('vcodec') != 'none']
                            if video_formats:
                                selected_format = max(video_formats,
                                                    key=lambda f: (f.get('height', 0) or 0,
                                                                 f.get('width', 0) or 0,
                                                                 f.get('vbr', 0) or 0))
                                logger.info(f"Selected best quality format: {selected_format}")

                        if selected_format:
                            width = selected_format.get('width')
                            height = selected_format.get('height')
                            logger.info(f"Format dimensions - width: {width}, height: {height}")
                            if width and height:
                                actual_resolution = f"{width}x{height}"
                            elif height:
                                actual_resolution = f"{height}p"
                            else:
                                actual_resolution = "Unknown"
                            logger.info(f"Final resolution: {actual_resolution}")
                    except Exception as e:
                        logger.error(f"Could not determine actual resolution: {str(e)}")
                        logger.error(f"Format info: {info}")
                        actual_resolution = "Unknown"

                # Save to database
                media_info = {
                    'id': info['id'],
                    'title': info.get('title', ''),
                    'file_path': str(relative_path),
                    'metadata': {
                        'duration': info.get('duration', 0),
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'comment_count': info.get('comment_count', 0),
                        'uploader': info.get('uploader', ''),
                        'description': info.get('description', ''),
                        'upload_date': info.get('upload_date', ''),
                        'download_type': download_type,
                        'format': format_type,
                        'requested_quality': quality_description,
                        'actual_resolution': actual_resolution,
                        'file_size_mb': file_size_mb
                    }
                }

                save_media_metadata(
                    user_id=session['user']['id'],
                    platform='youtube',
                    media_type='video' if download_type == 'video' else 'audio',
                    file_path=str(relative_path),
                    title=media_info['title'],
                    original_url=url,
                    duration=media_info['metadata']['duration'],
                    metadata=media_info['metadata']
                )

                # Cache the media info
                youtube_cache.cache_media(url, session['user']['id'], media_info)

                # Return JSON response with download URL and detailed info
                return jsonify({
                    'success': True,
                    'download_url': url_for('media.serve_download', filename=file_path.name),
                    'title': media_info['title'],
                    'uploader': media_info['metadata']['uploader'],
                    'download_type': download_type,
                    'format': format_type,
                    'requested_quality': quality_description,
                    'actual_resolution': actual_resolution,
                    'file_size_mb': file_size_mb,
                    'duration': media_info['metadata']['duration'],
                    'media_dashboard_url': url_for('index')  # Use the index route which likely shows the dashboard
                })

        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return jsonify({'error': str(e)}), 500

    except Exception as e:
        logger.error(f"Error processing download request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@youtube_bp.route('/list-routes')
def list_routes():
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    return jsonify(routes)

@youtube_bp.route('/oauth-callback')
def oauth_callback():
    """Handle OAuth callback from YouTube."""
    try:
        # Get the authorization code from the request
        code = request.args.get('code')
        if not code:
            logger.error("No authorization code received")
            return render_template('youtube_auth_result.html', success=False, message="No authorization code received")

        # Use a fixed redirect URI that matches what's registered in Google Cloud Console
        redirect_uri = url_for('youtube.oauth_callback', _external=True)
        logger.info(f"Using callback redirect URI: {redirect_uri}")

        # Get client ID and secret from environment variables
        client_id = os.getenv('YOUTUBE_CLIENT_ID')
        client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')

        if not client_id or not client_secret:
            logger.error("Missing YouTube client credentials in environment variables")
            return render_template('youtube_auth_result.html', success=False, message="Missing YouTube client credentials")

        # Create client config dictionary
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [redirect_uri]
            }
        }

        try:
            # Exchange the code for credentials
            flow = InstalledAppFlow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            flow.fetch_token(code=code)
            credentials = flow.credentials
        except Exception as e:
            # If there's a scope mismatch, try again with the scopes from the response
            if 'Scope has changed' in str(e):
                logger.warning(f"Scope mismatch detected: {str(e)}")

                # Extract the scopes from the error message
                scope_str = request.args.get('scope', '')
                logger.info(f"Received scopes: {scope_str}")

                # Create a new flow with the expanded scopes
                expanded_scopes = scope_str.split()
                logger.info(f"Using expanded scopes: {expanded_scopes}")

                flow = InstalledAppFlow.from_client_config(
                    client_config,
                    scopes=expanded_scopes,
                    redirect_uri=redirect_uri
                )
                flow.fetch_token(code=code)
                credentials = flow.credentials
            else:
                # If it's not a scope issue, re-raise the exception
                raise

        # Store the credentials in the session
        session['youtube_credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        # Store in auth manager if available
        try:
            from content_pipeline.poster.auth import get_auth_manager
            user_id = session.get('user_id', 'anonymous')
            auth_manager = get_auth_manager(user_id)
            auth_manager.store_credentials('youtube', session['youtube_credentials'])
            logger.info(f"Stored YouTube credentials for user {user_id}")
        except Exception as e:
            logger.error(f"Error storing credentials in auth manager: {str(e)}")

        # Check if we have a return URL in the session
        return_url = session.pop('youtube_callback_return_url', None)
        if return_url:
            return redirect(return_url)

        # Otherwise, show a success message
        return render_template('youtube_auth_result.html', success=True, message="Successfully authenticated with YouTube")

    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}")
        return render_template('youtube_auth_result.html', success=False, message=f"Authentication error: {str(e)}")

@youtube_bp.route('/get-redirect-uri')
def get_redirect_uri():
    """Display the redirect URI for registration in Google Cloud Console."""
    redirect_uri = url_for('youtube.oauth_callback', _external=True)
    return jsonify({
        'redirect_uri': redirect_uri,
        'instructions': 'Add this exact URI to the list of authorized redirect URIs in your Google Cloud Console project.'
