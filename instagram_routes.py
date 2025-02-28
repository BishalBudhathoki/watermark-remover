from flask import Blueprint, render_template, request, jsonify, session
import os
from pathlib import Path
import logging
import yt_dlp
import json
import requests
from datetime import datetime
from urllib.parse import urlparse
from media_routes import save_media_metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Blueprint
instagram_bp = Blueprint('instagram', __name__)

# Define download and processed folders
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_FOLDER = BASE_DIR / 'downloads'
INSTAGRAM_DOWNLOAD_PATH = DOWNLOAD_FOLDER / 'instagram'

# Create necessary directories
DOWNLOAD_FOLDER.mkdir(exist_ok=True)
INSTAGRAM_DOWNLOAD_PATH.mkdir(exist_ok=True)

def validate_instagram_url(url):
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
    return render_template('instagram_downloader.html')

@instagram_bp.route('/instagram-download', methods=['POST'])
def instagram_download():
    if not session.get('user'):
        return jsonify({'error': 'Please login to download content'}), 401

    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # Validate URL
    is_valid, error_message = validate_instagram_url(url)
    if not is_valid:
        return jsonify({'error': error_message}), 400

    try:
        # Get user_id from session
        user_id = session['user']['id']
        
        # Clean up the URL to remove query parameters and get the shortcode
        cleaned_url = url.split('?')[0]
        shortcode = cleaned_url.split('/')[-2] if cleaned_url.endswith('/') else cleaned_url.split('/')[-1]
        
        # Configure headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

        # First try with yt-dlp
        try:
            ydl_opts = {
                'outtmpl': str(INSTAGRAM_DOWNLOAD_PATH / f'%(title)s_{shortcode}.%(ext)s'),
                'format': 'best',
                'quiet': True,
                'no_warnings': True,
                'http_headers': headers,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                filename = str(Path(filename))

                # Save metadata for media dashboard
                media_id = save_media_metadata(
                    user_id=user_id,
                    platform='instagram',
                    media_type='video',
                    file_path=filename,
                    title=info.get('title', f'Instagram Reel {shortcode}'),
                    original_url=url,
                    duration=info.get('duration'),
                    metadata={
                        'uploader': info.get('uploader', 'unknown'),
                        'like_count': info.get('like_count', 0),
                        'comment_count': info.get('comment_count', 0),
                        'description': info.get('description', ''),
                        'timestamp': info.get('timestamp', int(datetime.now().timestamp()))
                    }
                )

        except Exception as e:
            logger.warning(f"yt-dlp download failed, trying alternative method: {str(e)}")
            
            # Alternative method using Instagram's public API
            try:
                # Get the post metadata
                api_url = f"https://www.instagram.com/graphql/query/"
                params = {
                    'query_hash': '2b0673e0dc4580674a88d426fe00ea90',
                    'variables': json.dumps({
                        'shortcode': shortcode
                    })
                }
                
                response = requests.get(api_url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Extract media URL
                media_url = data['data']['shortcode_media']['video_url']
                
                # Download the video
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = str(INSTAGRAM_DOWNLOAD_PATH / f'instagram_reel_{shortcode}_{timestamp}.mp4')
                
                with requests.get(media_url, stream=True, headers=headers) as r:
                    r.raise_for_status()
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                
                # Save metadata for media dashboard
                media_id = save_media_metadata(
                    user_id=user_id,
                    platform='instagram',
                    media_type='video',
                    file_path=filename,
                    title=f'Instagram Reel {shortcode}',
                    original_url=url,
                    metadata={
                        'uploader': data['data']['shortcode_media']['owner']['username'],
                        'like_count': data['data']['shortcode_media'].get('edge_media_preview_like', {}).get('count', 0),
                        'comment_count': data['data']['shortcode_media'].get('edge_media_preview_comment', {}).get('count', 0),
                        'description': data['data']['shortcode_media'].get('caption', ''),
                        'timestamp': data['data']['shortcode_media']['taken_at_timestamp']
                    }
                )

            except Exception as api_error:
                logger.error(f"Alternative download method failed: {str(api_error)}")
                raise Exception("Failed to download reel. Please try again later.")

        return render_template('instagram_results.html',
            content={
                'username': info.get('uploader', 'unknown'),
                'posts': [{
                    'type': 'video',
                    'caption': info.get('description', ''),
                    'likes': info.get('like_count', 0),
                    'comments': info.get('comment_count', 0),
                    'date': datetime.fromtimestamp(info.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                    'filename': os.path.basename(filename),
                    'shortcode': shortcode,
                    'extension': 'mp4'
                }]
            }
        )

    except Exception as e:
        logger.error(f"Instagram download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to download Instagram content. Please check the URL and try again.'
        }), 500 