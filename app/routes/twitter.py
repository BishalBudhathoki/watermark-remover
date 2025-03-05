from flask import Blueprint, request, jsonify, render_template, url_for, send_file, current_app
import os
from pathlib import Path
import logging
import yt_dlp
import uuid
import time
import re
import json
from urllib.parse import urlparse
from copy import deepcopy
from datetime import datetime
import sqlite3
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from ..routes.media import save_media_metadata
from ..utils.path import APP_ROOT, DOWNLOAD_DIR, get_download_path, get_relative_path
from ..services.cache import MediaCache

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Blueprint
twitter_bp = Blue# # print('twitter', __name__)

# Define download and processed folders
BASE_DIR = APP_ROOT
DOWNLOAD_FOLDER = DOWNLOAD_DIR
TWITTER_DOWNLOAD_PATH = DOWNLOAD_FOLDER / 'twitter'
DB_PATH = BASE_DIR / 'media_vault.db'

# Create necessary directories
DOWNLOAD_FOLDER.mkdir(exist_ok=True)
TWITTER_DOWNLOAD_PATH.mkdir(exist_ok=True)

# Initialize MediaCache for Twitter
twitter_cache = MediaCache('twitter')

# Ensure static folder exists for placeholder images
def ensure_static_folder(app=None):
    """Ensure static folder exists for placeholder images."""
    try:
        # Use the provided app or current_app if in application context
        if app is None:
            from flask import current_app
            app = current_app

        static_folder = Path(app.static_folder)
        if not static_folder.exists():
            static_folder.mkdir(exist_ok=True)

        images_folder = static_folder / 'images'
        if not images_folder.exists():
            images_folder.mkdir(exist_ok=True)

        # Create a default placeholder image if it doesn't exist
        placeholder_path = images_folder / 'twitter_placeholder.jpg'
        if not placeholder_path.exists():
            # Create a blue placeholder image
            img = Image.new('RGB', (800, 600), color=(73, 109, 137))
            draw = ImageDraw.Draw(img)

            # Add text if possible
            try:
                # Try to use a system font
                font_path = '/System/Library/Fonts/Helvetica.ttc'  # macOS
                if not os.path.exists(font_path):
                    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'  # Linux
                if not os.path.exists(font_path):
                    font_path = 'C:\\Windows\\Fonts\\arial.ttf'  # Windows

                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 40)
                    draw.text((400, 300), "Twitter Image Placeholder", fill=(255, 255, 255), font=font, anchor="mm")
                else:
                    # If no font available, use default
                    draw.text((400, 300), "Twitter Image Placeholder", fill=(255, 255, 255))
            except Exception as font_error:
                logger.warning(f"Could not add text to placeholder: {str(font_error)}")

            img.save(placeholder_path)
            logger.info(f"Created placeholder image at {placeholder_path}")
    except Exception as e:
        logger.error(f"Error ensuring static folder: {str(e)}")

# Initialize database
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS media_items (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            platform TEXT,
            media_type TEXT,
            title TEXT,
            description TEXT,
            original_url TEXT,
            local_path TEXT,
            thumbnail_path TEXT,
            metadata JSON,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            status TEXT,
            file_size INTEGER,
            duration INTEGER,
            width INTEGER,
            height INTEGER
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS media_tags (
            media_id TEXT,
            tag TEXT,
            FOREIGN KEY(media_id) REFERENCES media_items(id),
            PRIMARY KEY(media_id, tag)
        )
        """)

init_db()

def clean_twitter_url(url):
    """Clean and validate Twitter/X URL"""
    try:
        parsed = urlparse(url)
        if not parsed.netloc in ['twitter.com', 'x.com']:
            raise ValueError('Invalid domain')

        # Convert x.com to twitter.com
        if parsed.netloc == 'x.com':
            url = url.replace('x.com', 'twitter.com')

        # Convert /i/web/ URLs to standard format
        url = url.replace('/i/web/', '/')

        return url
    except Exception as e:
        logger.error(f'Error cleaning URL {url}: {str(e)}')
        raise ValueError('Invalid Twitter URL')

def get_tweet_id_from_url(url):
    """Extract tweet ID from Twitter URL for consistent folder naming."""
    try:
        match = re.search(r'status/(\d+)', url)
        if match:
            return match.group(1)
        else:
            # If no tweet ID found, hash the URL for consistent naming
            import hashlib
            return hashlib.md5(url.encode()).hexdigest()[:16]
    except Exception as e:
        logger.error(f"Error extracting tweet ID: {str(e)}")
        # Fall back to hashing the URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:16]

def get_safe_ydl_opts(download_path):
    """Get yt-dlp options without non-serializable objects."""
    return {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': str(download_path / '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'verbose': True,
        'extractor_retries': 5,
        'socket_timeout': 30,
        'nocheckcertificate': True,
        'extract_flat': True,
        'write_thumbnail': True,
        'writethumbnail': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://twitter.com',
            'Referer': 'https://twitter.com/'
        },
        'external_downloader_args': ['--max-filesize', '2G'],
        'merge_output_format': 'mp4'
    }

class MediaDownloader:
    def __init__(self, url, download_path, media_type='video'):
        self.url = url
        self.download_path = download_path
        self.media_type = media_type
        self.progress_hook = DownloadProgressHook()
        self.media_info = {
            'id': str(uuid.uuid4()),
            'platform': 'twitter',
            'media_type': media_type,
            'original_url': url,
            'created_at': datetime.now()
        }

    def simple_image_download(self):
        """A simplified approach to download Twitter images."""
        try:
            logger.info(f"Using simplified image download for tweet: {self.url}")
            logger.info(f"Download path: {self.download_path}")

            # Extract tweet ID from URL
            match = re.search(r'status/(\d+)', self.url)
            if not match:
                raise ValueError("Could not extract tweet ID from URL")

            tweet_id = match.group(1)
            logger.info(f"Extracted tweet ID: {tweet_id}")

            image_url = None

            # Method 1: Try the Twitter API directly
            try:
                logger.info(f"Trying Twitter API for tweet {tweet_id}")
                api_url = f"https://api.twitter.com/2/tweets/{tweet_id}?expansions=attachments.media_keys&media.fields=url,preview_image_url,type"
                response = requests.get(api_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                })

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Twitter API response: {data}")

                    if 'includes' in data and 'media' in data['includes']:
                        for media in data['includes']['media']:
                            if media['type'] == 'photo':
                                image_url = media.get('url')
                                if image_url:
                                    logger.info(f"Found image URL using Twitter API: {image_url}")
                                    break
                else:
                    logger.warning(f"Twitter API returned status code {response.status_code}")
            except Exception as api_error:
                logger.error(f"Error with Twitter API: {str(api_error)}")

            # Method 2: Use yt-dlp to extract thumbnail URLs
            if not image_url:
                logger.info(f"Using yt-dlp to extract thumbnail URLs for tweet {tweet_id}")
                ydl_opts = {
                    'quiet': True,
                    'extract_flat': False,  # We want full extraction
                    'skip_download': True,
                    'writeinfojson': True,
                    'write_all_thumbnails': True,
                    'ignoreerrors': True,
                    'no_warnings': True
                }

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(self.url, download=False)

                        # Check if we have thumbnails
                        if info and info.get('thumbnails'):
                            # Get the highest quality thumbnail
                            thumbnails = sorted(info['thumbnails'],
                                            key=lambda x: x.get('width', 0) * x.get('height', 0) if x.get('width') and x.get('height') else 0,
                                            reverse=True)
                            image_url = thumbnails[0]['url']
                            logger.info(f"Found image URL using yt-dlp: {image_url}")
                except Exception as ydl_error:
                    logger.error(f"Error with yt-dlp: {str(ydl_error)}")

            # Method 3: Try the syndication API
            if not image_url:
                try:
                    logger.info(f"Trying syndication API for tweet {tweet_id}")
                    api_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
                    response = requests.get(api_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    })
                    response.raise_for_status()
                    tweet_data = response.json()
                    logger.info(f"Successfully retrieved syndication data: {tweet_data}")

                    # Check for photos
                    if 'photos' in tweet_data and tweet_data['photos']:
                        # Get the first photo
                        photo = tweet_data['photos'][0]
                        image_url = photo.get('url')
                        if image_url:
                            # Ensure we get the highest quality
                            if '?format=' in image_url:
                                image_url = re.sub(r'\?format=.*', '?format=jpg&name=large', image_url)
                            else:
                                image_url = image_url + '?format=jpg&name=large'
                            logger.info(f"Found image URL in syndication API: {image_url}")

                    # Check for media in the tweet
                    elif 'mediaDetails' in tweet_data:
                        for media in tweet_data['mediaDetails']:
                            if media.get('type') == 'photo':
                                image_url = media.get('media_url_https')
                                if image_url:
                                    # Ensure we get the highest quality
                                    if '?format=' in image_url:
                                        image_url = re.sub(r'\?format=.*', '?format=jpg&name=large', image_url)
                                    else:
                                        image_url = image_url + '?format=jpg&name=large'
                                    logger.info(f"Found image URL in mediaDetails: {image_url}")
                                    break
                except Exception as api_error:
                    logger.error(f"Error with syndication API: {str(api_error)}")

            # Method 4: Try direct HTML scraping
            if not image_url:
                try:
                    logger.info(f"Trying direct HTML scraping for tweet {tweet_id}")
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }

                    # Try to get the tweet page
                    response = requests.get(self.url, headers=headers)
                    response.raise_for_status()
                    html_content = response.text
                    logger.info(f"Successfully retrieved HTML content")

                    # Look for image URLs in the HTML using multiple patterns
                    # Pattern 1: Twitter card image (most reliable)
                    card_pattern = r'<meta property="og:image" content="([^"]+)"'
                    match = re.search(card_pattern, html_content)
                    if match:
                        image_url = match.group(1)
                        # Ensure we get the highest quality
                        if '?format=' in image_url:
                            image_url = re.sub(r'\?format=.*', '?format=jpg&name=large', image_url)
                        else:
                            image_url = image_url + '?format=jpg&name=large'
                        logger.info(f"Found image URL using Twitter card: {image_url}")

                    # Pattern 2: Direct image URL in HTML
                    if not image_url:
                        image_patterns = [
                            r'https://pbs\.twimg\.com/media/[A-Za-z0-9_-]+\.(jpg|png|webp)',
                            r'https://pbs\.twimg\.com/media/[A-Za-z0-9_-]+\?format=',
                            r'https://pbs\.twimg\.com/ext_tw_video_thumb/[A-Za-z0-9_-]+/[A-Za-z0-9_/]+\.(jpg|png|webp)',
                            r'https://pbs\.twimg\.com/tweet_video_thumb/[A-Za-z0-9_-]+\.(jpg|png|webp)',
                            r'https://pbs\.twimg\.com/profile_images/[A-Za-z0-9_/-]+\.(jpg|png|webp)',
                            r'https://pbs\.twimg\.com/amplify_video_thumb/[A-Za-z0-9_-]+/[A-Za-z0-9_/]+\.(jpg|png|webp)'
                        ]

                        for pattern in image_patterns:
                            match = re.search(pattern, html_content)
                            if match:
                                img_path = match.group(1)
                                # If it's a relative URL, make it absolute
                                if img_path.startswith('/'):
                                    image_url = f"https://nitter.net{img_path}"
                                else:
                                    image_url = img_path
                                logger.info(f"Found image URL using pattern: {image_url}")
                                break
                except Exception as html_error:
                    logger.error(f"Error with HTML scraping: {str(html_error)}")

            # Method 5: Try using nitter.net as a proxy
            if not image_url:
                try:
                    logger.info(f"Trying nitter.net proxy for tweet {tweet_id}")
                    nitter_url = f"https://nitter.net/i/status/{tweet_id}"
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }

                    response = requests.get(nitter_url, headers=headers)
                    response.raise_for_status()
                    html_content = response.text
                    logger.info(f"Successfully retrieved nitter.net content")

                    # Look for image URLs in the HTML
                    image_patterns = [
                        r'<img src="([^"]+)" class="media-image"',
                        r'<a href="([^"]+)" class="still-image"',
                        r'<a href="([^"]+)" target="_blank" class="media-link"',
                        r'<a href="([^"]+)" class="image-attachment"'
                    ]

                    for pattern in image_patterns:
                        match = re.search(pattern, html_content)
                        if match:
                            img_path = match.group(1)
                            # If it's a relative URL, make it absolute
                            if img_path.startswith('/'):
                                image_url = f"https://nitter.net{img_path}"
                            else:
                                image_url = img_path
                            logger.info(f"Found image URL using nitter.net: {image_url}")
                            break
                except Exception as nitter_error:
                    logger.error(f"Error with nitter.net: {str(nitter_error)}")

            # Method 6: Try using fxtwitter.com as a proxy
            if not image_url:
                try:
                    logger.info(f"Trying fxtwitter.com proxy for tweet {tweet_id}")
                    fx_url = f"https://api.fxtwitter.com/status/{tweet_id}"
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    }

                    response = requests.get(fx_url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    logger.info(f"Successfully retrieved fxtwitter.com data")

                    if 'tweet' in data and 'media' in data['tweet']:
                        media = data['tweet']['media']
                        if 'photos' in media and media['photos']:
                            # Get the first photo
                            photo = media['photos'][0]
                            image_url = photo.get('url')
                            if image_url:
                                logger.info(f"Found image URL using fxtwitter.com: {image_url}")
                except Exception as fx_error:
                    logger.error(f"Error with fxtwitter.com: {str(fx_error)}")

            # If we still don't have an image URL, use a default placeholder
            if not image_url:
                logger.warning("Could not find any image URL, using a default image")
                # Ensure static folder and placeholder image exist
                ensure_static_folder(current_app)

                # Use a default image from the static folder
                default_image_path = Path(current_app.static_folder) / 'images' / 'twitter_placeholder.jpg'

                # If the default image doesn't exist, create a simple one
                if not default_image_path.exists():
                    logger.info("Creating a default placeholder image")
                    img = Image.new('RGB', (800, 600), color=(73, 109, 137))
                    default_image_path.parent.mkdir(exist_ok=True)
                    img.save(default_image_path)

                # Copy the default image to our download path
                filename = f"image_{uuid.uuid4()}.jpg"
                filepath = self.download_path / filename

                import shutil
                shutil.copy(default_image_path, filepath)
                logger.info(f"Copied placeholder image to {filepath}")

                # Create a small thumbnail
                thumbnail = Image.open(default_image_path)
                thumbnail.thumbnail((300, 300))
                thumb_path = self.download_path / f"thumb_{filename}"
                thumbnail.save(thumb_path)
                logger.info(f"Created thumbnail at {thumb_path}")

                # Update media info
                self.media_info.update({
                    'local_path': str(filepath),
                    'thumbnail_path': str(thumb_path),
                    'file_size': os.path.getsize(filepath),
                    'width': 800,
                    'height': 600,
                    'title': f"Twitter Image {datetime.now().strftime('%Y-%m-%d')}",
                    'status': 'completed',
                    'metadata': {
                        'uploader': 'Twitter User',
                        'upload_date': datetime.now().strftime('%Y%m%d'),
                        'note': 'Default placeholder image used as original could not be retrieved'
                    }
                })

                return self.media_info

            # Download the image
            logger.info(f"Downloading image from URL: {image_url}")
            response = requests.get(image_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://twitter.com/'
            })
            response.raise_for_status()

            # Check if the response is actually an image
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"Response is not an image. Content-Type: {content_type}")

                # Try to extract image from HTML if the response is HTML
                if content_type.startswith('text/html'):
                    logger.info("Response is HTML, trying to extract image URL from it")
                    html_content = response.text
                    image_patterns = [
                        r'<img src="([^"]+)" class="media-image"',
                        r'<a href="([^"]+)" class="still-image"',
                        r'<img src="([^"]+)"',
                        r'<meta property="og:image" content="([^"]+)"'
                    ]

                    for pattern in image_patterns:
                        match = re.search(pattern, html_content)
                        if match:
                            new_image_url = match.group(1)
                            logger.info(f"Found new image URL in HTML response: {new_image_url}")

                            # Try to download the new image URL
                            try:
                                new_response = requests.get(new_image_url, headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                                    'Accept-Language': 'en-US,en;q=0.9',
                                    'Referer': 'https://twitter.com/'
                                })
                                new_response.raise_for_status()

                                # Check if the new response is an image
                                new_content_type = new_response.headers.get('Content-Type', '')
                                if new_content_type.startswith('image/'):
                                    response = new_response
                                    content_type = new_content_type
                                    break
                            except Exception as e:
                                logger.error(f"Error downloading new image URL: {str(e)}")

                # If still not an image, raise an error
                if not content_type.startswith('image/'):
                    raise ValueError(f"Response is not an image. Content-Type: {content_type}")

            # Save image
            img = Image.open(BytesIO(response.content))
            filename = f"image_{uuid.uuid4()}.{img.format.lower() if img.format else 'jpg'}"
            filepath = self.download_path / filename
            img.save(filepath)
            logger.info(f"Saved image to {filepath}")

            # Create thumbnail
            thumbnail = img.copy()
            thumbnail.thumbnail((300, 300))
            thumb_path = self.download_path / f"thumb_{filename}"
            thumbnail.save(thumb_path)
            logger.info(f"Created thumbnail at {thumb_path}")

            # Update media info
            self.media_info.update({
                'local_path': str(filepath),
                'thumbnail_path': str(thumb_path),
                'file_size': os.path.getsize(filepath),
                'width': img.width,
                'height': img.height,
                'title': f"Twitter Image {datetime.now().strftime('%Y-%m-%d')}",
                'status': 'completed',
                'metadata': {
                    'uploader': 'Twitter User',
                    'upload_date': datetime.now().strftime('%Y%m%d'),
                }
            })

            return self.media_info

        except Exception as e:
            logger.error(f"Simple image download error: {str(e)}")
            raise

    def download_image(self):
        """Legacy method for backward compatibility."""
        return self.simple_image_download()

    def download_video(self):
        """Download Twitter video."""
        try:
            ydl_opts = get_safe_ydl_opts(self.download_path)
            ydl_opts['progress_hooks'] = [self.progress_hook]

            logger.info(f"Downloading video from {self.url} to {self.download_path}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)

                if not info:
                    raise ValueError("Could not extract video information")

                # Get the downloaded file path
                if 'requested_downloads' in info:
                    downloaded_file = info['requested_downloads'][0]['filepath']
                else:
                    downloaded_file = str(self.download_path / f"{info.get('title', 'video')}.{info.get('ext', 'mp4')}")

                logger.info(f"Video downloaded to: {downloaded_file}")

                # Verify the file exists
                if not os.path.exists(downloaded_file):
                    logger.error(f"Downloaded file not found at {downloaded_file}")
                    raise FileNotFoundError(f"Downloaded file not found at {downloaded_file}")

                # Get thumbnail
                thumbnail_path = None
                if info.get('thumbnail'):
                    try:
                        thumb_response = requests.get(info['thumbnail'])
                        if thumb_response.ok:
                            thumbnail_path = str(self.download_path / f"thumb_{os.path.basename(downloaded_file)}.jpg")
                            with open(thumbnail_path, 'wb') as f:
                                f.write(thumb_response.content)
                            logger.info(f"Thumbnail saved to: {thumbnail_path}")
                    except Exception as thumb_error:
                        logger.error(f"Error downloading thumbnail: {str(thumb_error)}")

                # Update media info
                self.media_info.update({
                    'local_path': downloaded_file,
                    'thumbnail_path': thumbnail_path,
                    'title': info.get('title'),
                    'description': info.get('description'),
                    'file_size': os.path.getsize(downloaded_file) if os.path.exists(downloaded_file) else 0,
                    'duration': info.get('duration'),
                    'metadata': {
                        'uploader': info.get('uploader'),
                        'upload_date': info.get('upload_date'),
                        'view_count': info.get('view_count'),
                        'like_count': info.get('like_count'),
                        'repost_count': info.get('repost_count')
                    },
                    'status': 'completed'
                })

                return self.media_info

        except Exception as e:
            logger.error(f"Video download error: {str(e)}")
            raise

class DownloadProgressHook:
    def __call__(self, d):
        if d['status'] == 'downloading':
            logger.info(f"Downloading: {d.get('_percent_str', '0%')} of {d.get('_total_bytes_str', 'unknown size')}")
        elif d['status'] == 'finished':
            logger.info(f"Download completed: {d.get('filename')}")
        elif d['status'] == 'error':
            logger.error(f"Download error: {d.get('error')}")

@twitter_bp.route('/twitter-downloader')
def twitter_downloader():
    """Render Twitter video downloader page."""
    return render_template('twitter_downloader.html')

# Replace the incorrect decorator with a function that will be called when the blueprint is registered
def init_twitter_resources(app):
    """Initialize resources for the Twitter blueprint."""
    ensure_static_folder(app)

@twitter_bp.route('/download', methods=['POST'])
def twitter_download_route():
    """Handle Twitter media download request with enhanced error handling."""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400

        url = data['url']
        try:
            url = clean_twitter_url(url)
            logger.info(f"Processing URL: {url}")
        except ValueError as e:
            logger.error(f"URL validation error: {str(e)}")
            return jsonify({'error': str(e)}), 400

        # Get user ID from session or use anonymous
        from flask import session
        user_id = 'anonymous'
        if session.get('user') and isinstance(session['user'], dict) and 'id' in session['user']:
            user_id = session['user']['id']

        logger.info(f"User ID for media request: {user_id}")

        # Check if media is already cached
        if twitter_cache.is_media_cached(url, user_id):
            logger.info(f"Found cached media for URL: {url}")
            cached_media = twitter_cache.get_cached_media(url, user_id)

            # Ensure we have the download_id for the URL
            if cached_media and 'local_path' in cached_media:
                local_path = Path(cached_media['local_path'])
                parts = local_path.parts
                if len(parts) >= 2 and parts[0] == 'twitter':
                    download_id = parts[1]
                    filename = local_path.name

                    return jsonify({
                        'status': 'success',
                        'media_info': cached_media,
                        'download_url': url_for('twitter.download_file',
                                              download_id=download_id,
                                              filename=filename),
                        'cached': True
                    })

        # Create download directory with deterministic name based on tweet ID
        tweet_id = get_tweet_id_from_url(url)
        download_id = f"tweet_{tweet_id}"
        download_path = TWITTER_DOWNLOAD_PATH / download_id
        download_path.mkdir(exist_ok=True)

        # Determine media type - check if URL contains image indicators or use the type from the request
        requested_type = data.get('type', 'auto')
        if requested_type == 'image':
            media_type = 'image'
        elif requested_type == 'video':
            media_type = 'video'
        else:
            # Auto detect based on URL
            media_type = 'image' if 'photo' in url.lower() or url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')) else 'video'

        logger.info(f"Processing media type: {media_type} for URL: {url}")
        downloader = MediaDownloader(url, download_path, media_type)

        try:
            if media_type == 'image':
                # Use the simplified image download method
                media_info = downloader.simple_image_download()
            else:
                try:
                    media_info = downloader.download_video()
                except yt_dlp.utils.DownloadError as e:
                    error_message = str(e)
                    logger.error(f"Download error: {error_message}")

                    # If no video found, try to get an image instead
                    if "No video could be found in this tweet" in error_message:
                        logger.info("No video found in tweet, trying to download as image instead")
                        downloader.media_type = 'image'
                        media_info = downloader.simple_image_download()
                        # Ensure media_type is set to 'image'
                        media_info['media_type'] = 'image'
                    else:
                        raise

            # Convert absolute paths to relative paths for storage in the database
            if 'local_path' in media_info and media_info['local_path']:
                # If it's already a string, convert to Path object
                if isinstance(media_info['local_path'], str):
                    file_path = Path(media_info['local_path'])
                else:
                    file_path = media_info['local_path']

                # Include the tweet_id subdirectory in the relative path
                rel_path = f"twitter/{download_id}/{file_path.name}"
                media_info['file_path'] = rel_path
                media_info['local_path'] = rel_path

            if 'thumbnail_path' in media_info and media_info['thumbnail_path']:
                if isinstance(media_info['thumbnail_path'], str):
                    thumb_path = Path(media_info['thumbnail_path'])
                else:
                    thumb_path = media_info['thumbnail_path']

                # Ensure thumbnail path includes the tweet_id subdirectory
                rel_path = f"twitter/{download_id}/{thumb_path.name}"
                media_info['thumbnail_path'] = rel_path

            # Save metadata to database
            try:
                save_media_metadata(
                    user_id=user_id,
                    platform='twitter',
                    media_type=media_info['media_type'],
                    file_path=media_info['local_path'],  # Now includes tweet_id subdirectory
                    title=media_info.get('title', 'Twitter Media'),
                    original_url=url,
                    duration=media_info.get('duration', 0),
                    metadata=media_info.get('metadata', {}),
                    thumbnail_path=media_info.get('thumbnail_path')
                )
                logger.info(f"Media metadata saved successfully for URL: {url}")

                # Cache the media info
                if not twitter_cache.cache_media(url, user_id, media_info):
                    logger.warning(f"Failed to cache media for URL: {url}")
                    # Debug info for cache failure
                    logger.warning(f"Media info structure: {media_info.keys()}")

                    if 'file_path' in media_info:
                        logger.warning(f"File path: {media_info['file_path']}")

                    if 'local_path' in media_info:
                        logger.warning(f"Local path: {media_info['local_path']}")
                        file_path = DOWNLOAD_DIR / media_info['local_path']
                        logger.warning(f"Absolute path: {file_path}")
                        logger.warning(f"File exists: {file_path.exists()}")

                        # Create media_info with correct absolute paths
                        media_info_for_cache = media_info.copy()
                        media_info_for_cache['absolute_path'] = str(file_path)
                        media_info_for_cache['download_dir'] = str(DOWNLOAD_DIR)

                        # Second attempt with correct paths
                        if not twitter_cache.cache_media(url, user_id, media_info_for_cache):
                            logger.warning("Second cache attempt also failed")

                            # Try with a direct file check
                            if os.path.exists(str(file_path)):
                                logger.info(f"File exists at {file_path}, trying with simplified media info")
                                # Create a minimal media info with just the essential fields
                                simple_media_info = {
                                    'file_path': media_info['local_path'],
                                    'local_path': media_info['local_path'],
                                    'absolute_path': str(file_path),
                                    'title': media_info.get('title', 'Twitter Media'),
                                    'media_type': media_info['media_type'],
                                    'platform': 'twitter'
                                }

                                # Third attempt with simplified info
                                if not twitter_cache.cache_media(url, user_id, simple_media_info):
                                    logger.error("All cache attempts failed")
                                else:
                                    logger.info("Third cache attempt with simplified info succeeded")
                        else:
                            logger.info("Second cache attempt with enhanced path information succeeded")
                else:
                    logger.info(f"Successfully cached media for URL: {url}")
                    # Verify cache entry was created
                    if twitter_cache.is_media_cached(url, user_id):
                        logger.info("Verified cache entry exists")
                    else:
                        logger.warning("Cache entry verification failed")

            except Exception as db_error:
                logger.error(f"Error saving media metadata: {str(db_error)}")
                # Continue even if database save fails

            return jsonify({
                'status': 'success',
                'media_info': media_info,
                'download_url': url_for('twitter.download_file',
                                      download_id=download_id,
                                      filename=os.path.basename(media_info['local_path']))
            })

        except yt_dlp.utils.DownloadError as e:
            error_message = str(e)
            logger.error(f"Download error: {error_message}")

            if "Unsupported URL" in error_message:
                return jsonify({'error': 'This Twitter URL is not supported or the content is private'}), 400
            elif "unavailable" in error_message.lower():
                return jsonify({'error': 'The content is no longer available or is private'}), 400
            else:
                return jsonify({'error': 'Failed to download. Please check the URL and try again.'}), 500

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500

@twitter_bp.route('/downloads/<download_id>/<filename>')
def download_file(download_id, filename):
    """Serve downloaded Twitter files with enhanced security."""
    try:
        file_path = TWITTER_DOWNLOAD_PATH / download_id / filename
        logger.info(f"Attempting to serve file: {file_path}")

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError("File not found")

        # Verify file is within allowed directory
        if not str(file_path.resolve()).startswith(str(TWITTER_DOWNLOAD_PATH.resolve())):
            logger.error(f"Invalid file path: {file_path}")
            raise ValueError("Invalid file path")

        # Determine content type
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webm': 'video/webm',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4'
        }
        content_type = content_types.get(ext, 'application/octet-stream')

        logger.info(f"Serving file {file_path} with content type {content_type}")

        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=filename,
            mimetype=content_type
        )
    except Exception as e:
        logger.error(f"Error serving file: {str(e)}", exc_info=True)
        return jsonify({'error': 'File not found'}), 404

# Enhanced cleanup function
def cleanup_old_downloads():
    """Cleanup old downloads with enhanced error handling."""
    try:
        max_age = 3600  # 1 hour
        current_time = time.time()

        for download_dir in TWITTER_DOWNLOAD_PATH.iterdir():
            try:
                if download_dir.is_dir():
                    dir_age = current_time - download_dir.stat().st_mtime
                    if dir_age > max_age:
                        for file in download_dir.iterdir():
                            try:
                                file.unlink()
                            except Exception as e:
                                logger.error(f"Error deleting file {file}: {str(e)}")
                        try:
                            download_dir.rmdir()
                        except Exception as e:
                            logger.error(f"Error removing directory {download_dir}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing directory {download_dir}: {str(e)}")
    except Exception as e:
        logger.error(f"Error in cleanup: {str(e)}", exc_info=True)

# Add a route for cache cleanup
@twitter_bp.route('/cleanup-cache', methods=['POST'])
def cleanup_cache():
    """Clean up expired cache entries."""
    try:
        twitter_cache.cleanup_expired_cache()
        # Also clean up old files that might not be in the cache
        cleanup_old_downloads()
        return jsonify({'status': 'success', 'message': 'Cache cleanup completed'})
    except Exception as e:
        logger.error(f"Cache cleanup error: {str(e)}")
        return jsonify({'error': 'Failed to clean up cache'}), 500

# Schedule periodic cache cleanup
def schedule_cleanup(app):
    """Schedule periodic cache cleanup when app starts."""
    try:
        from flask_apscheduler import APScheduler

        # Create scheduler
        scheduler = APScheduler()
        scheduler.init_app(app)

        # Add cache cleanup job - run once per day
        scheduler.add_job(
            id='twitter_cache_cleanup',
            func=twitter_cache.cleanup_expired_cache,
            trigger='interval',
            hours=24
        )

        # Add file cleanup job - run every 6 hours
        scheduler.add_job(
            id='twitter_file_cleanup',
            func=cleanup_old_downloads,
            trigger='interval',
            hours=6
        )

        scheduler.start()
        logger.info("Scheduled Twitter cache and file cleanup jobs")
    except ImportError:
        logger.warning("Flask-APScheduler not installed, skipping scheduled cleanup")
    except Exception as e:
        logger.error(f"Error scheduling cleanup: {str(e)}")