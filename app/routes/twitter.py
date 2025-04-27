from flask import Blueprint, request, jsonify, render_template, url_for, send_file, current_app
import os
from pathlib import Path
import logging
import uuid
import time
import re
import json
from urllib.parse import urlparse
from datetime import datetime
import sqlite3
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from ..routes.media import save_media_metadata
from ..utils.path import APP_ROOT, DOWNLOAD_DIR, get_download_path, get_relative_path
from ..services.cache import MediaCache
from twitter_scraper import get_tweets
import yt_dlp
from bs4 import BeautifulSoup

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Blueprint
twitter_bp =  Blueprint('twitter', __name__)

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

def get_ydl_opts(download_path):
    """Get yt-dlp options optimized for Twitter image/video extraction."""
    return {
        'quiet': True,
        'extract_flat': True,
        'skip_download': False,
        'writeinfojson': True,
        'write_all_thumbnails': True,
        'outtmpl': str(download_path / '%(title)s.%(ext)s'),
        'restrictfilenames': True,  # Restrict filenames to ASCII characters
        'ignoreerrors': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://twitter.com',
            'Referer': 'https://twitter.com/'
        }
    }

def get_tweet_media_urls_tscraper(tweet_url: str) -> list[str]:
    """Extract media URLs from a tweet using twitter_scraper."""
    import re
    match = re.search(r'twitter.com/([^/]+)/status/(\d+)', tweet_url)
    if not match:
        logger.warning(f"Could not extract username and tweet ID from URL: {tweet_url}")
        return []
    
    username, tweet_id = match.group(1), match.group(2)
    try:
        for tweet in get_tweets(username, pages=5):
            if str(tweet.get('tweetId')) == tweet_id:
                media_urls = []
                if 'images' in tweet and tweet['images']:
                    media_urls.extend(tweet['images'])
                if 'video' in tweet and tweet['video']:
                    media_urls.append(tweet['video'])
                logger.info(f"twitter_scraper found media URLs: {media_urls}")
                return media_urls
        logger.info(f"No tweet found for ID {tweet_id} using twitter_scraper.")
        return []
    except Exception as e:
        logger.error(f"twitter_scraper failed for tweet {tweet_id}: {str(e)}")
        return []

def get_media_url_with_yt_dlp(url, download_path):
    """Try to extract image or video URL using yt-dlp."""
    try:
        logger.info(f"Trying to extract media with yt-dlp from: {url}")
        ydl_opts = get_ydl_opts(download_path)
        
        # Skip downloading for info extraction
        ydl_opts['skip_download'] = True
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                logger.warning("yt-dlp could not extract info")
                return None, None
            
            # Check for video content first (prioritize actual video over thumbnails)
            if info.get('formats'):
                # Find best video format
                best_format = None
                for f in info.get('formats', []):
                    # Look for video format with both video and audio
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url'):
                        if best_format is None or f.get('height', 0) > best_format.get('height', 0):
                            best_format = f
                
                # If no format with both video and audio, find best video format
                if not best_format:
                    for f in info.get('formats', []):
                        if f.get('vcodec') != 'none' and f.get('url'):
                            if best_format is None or f.get('height', 0) > best_format.get('height', 0):
                                best_format = f
                
                if best_format:
                    media_url = best_format['url']
                    logger.info(f"Found video URL with yt-dlp: {media_url} (resolution: {best_format.get('height', 'unknown')}p)")
                    return media_url, 'video'
            
            # If direct video URL available, use it
            if info.get('url') and info.get('ext') in ['mp4', 'mov', 'webm']:
                video_url = info.get('url')
                logger.info(f"Found direct video URL with yt-dlp: {video_url}")
                return video_url, 'video'
                
            # If no video found, fall back to thumbnail for image content
            if info.get('thumbnails'):
                thumb_url = next((t['url'] for t in info['thumbnails'] if 'url' in t), None)
                if thumb_url:
                    logger.info(f"Found thumbnail URL with yt-dlp: {thumb_url}")
                    return thumb_url, 'image'
                    
        return None, None
    except Exception as e:
        logger.error(f"yt-dlp extraction error: {str(e)}")
        return None, None

def sanitize_filename(filename):
    """Sanitize filename to make it safe for file systems."""
    # Replace problematic characters with underscores
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '：', '⧸']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200] + ext
    return filename

def download_video_with_yt_dlp(url, download_path):
    """Download video directly using yt-dlp."""
    try:
        logger.info(f"Downloading video with yt-dlp from: {url}")
        ydl_opts = get_ydl_opts(download_path)
        ydl_opts['skip_download'] = False  # Ensure download happens
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'  # Ensure we get the best quality
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if not info:
                logger.warning("yt-dlp could not download video")
                return None, None
            
            # Get the downloaded file path
            if 'requested_downloads' in info:
                downloaded_file = info['requested_downloads'][0]['filepath'] 
                filename = os.path.basename(downloaded_file)
                
                # If the filename contains problematic characters, rename it
                sanitized_filename = sanitize_filename(filename)
                if sanitized_filename != filename:
                    new_path = os.path.join(os.path.dirname(downloaded_file), sanitized_filename)
                    os.rename(downloaded_file, new_path)
                    downloaded_file = new_path
                    filename = sanitized_filename
                    logger.info(f"Renamed file to {sanitized_filename}")
                    
                return downloaded_file, filename
                
        return None, None
    except Exception as e:
        logger.error(f"yt-dlp download error: {str(e)}")
        return None, None

def get_tweet_image_url(url):
    """Extract image URL directly from tweet HTML for image-only tweets."""
    try:
        logger.info(f"Attempting to extract image directly from tweet HTML: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        # Try to get the tweet HTML
        response = requests.get(url, headers=headers)
        if not response.ok:
            logger.warning(f"Failed to fetch tweet HTML: {response.status_code}")
            return None
            
        # Look for og:image meta tag in HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # First check for og:image meta tags (most reliable)
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image.get('content')
            logger.info(f"Found image URL from og:image tag: {image_url}")
            return image_url
            
        # Also check for twitter:image meta tags
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            image_url = twitter_image.get('content')
            logger.info(f"Found image URL from twitter:image tag: {image_url}")
            return image_url
            
        # Look for img tags with src containing 'tweet_video_thumb' or specific Twitter image patterns
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '')
            if ('pbs.twimg.com/media' in src or 'tweet_video_thumb' in src) and not src.endswith('.svg'):
                logger.info(f"Found image URL from img tag: {src}")
                return src
                
        # If nothing found, try some fallback methods
        # Check for any reference to pbs.twimg.com/media in the page source
        media_urls = re.findall(r'https?://pbs\.twimg\.com/media/[^\s\'"]+', response.text)
        if media_urls:
            logger.info(f"Found image URL from regex: {media_urls[0]}")
            # Remove query parameters
            clean_url = media_urls[0].split('?')[0]
            return clean_url
            
        logger.warning("No image URL found in tweet HTML")
        return None
    except Exception as e:
        logger.error(f"Error extracting image URL from HTML: {str(e)}")
        return None

def try_api_services(url):
    """Try multiple API services to extract media URL."""
    tweet_id = None
    username = None
    
    # Extract tweet ID and username
    match = re.search(r'twitter\.com/([^/]+)/status/(\d+)', url)
    if match:
        username = match.group(1)
        tweet_id = match.group(2)
    else:
        logger.warning(f"Could not extract tweet ID and username from {url}")
        return None, None
        
    logger.info(f"Trying alternative API services for tweet {tweet_id} by {username}")
    
    # List of API services to try
    services = [
        # vxtwitter API - one of the most reliable
        {
            'url': f'https://api.vxtwitter.com/{username}/status/{tweet_id}',
            'parser': lambda resp: extract_from_vxtwitter_api(resp)
        },
        # vxtwitter web - similar to fxtwitter but more reliable recently
        {
            'url': url.replace('twitter.com', 'vxtwitter.com'),
            'parser': lambda resp: extract_from_vx_fx_html(resp)
        },
        # nitter.net - an alternative Twitter frontend
        {
            'url': f'https://nitter.net/{username}/status/{tweet_id}',
            'parser': lambda resp: extract_from_nitter_html(resp)
        }
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for service in services:
        try:
            logger.info(f"Trying {service['url']}")
            response = requests.get(service['url'], headers=headers, timeout=5)
            if response.ok:
                media_url, media_type = service['parser'](response)
                if media_url:
                    return media_url, media_type
            else:
                logger.warning(f"Service {service['url']} returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Error with service {service['url']}: {str(e)}")
            
    return None, None

def extract_from_vxtwitter_api(response):
    """Extract media URL from vxtwitter API response."""
    try:
        data = response.json()
        
        # Check for media in the response
        if data.get('media_extended'):
            media = data['media_extended']
            for item in media:
                if item.get('type') == 'image' and item.get('url'):
                    return item['url'], 'image'
                elif item.get('type') == 'video' and item.get('url'):
                    return item['url'], 'video'
        
        # Check for single media object
        if data.get('media') and data['media'].get('photos') and len(data['media']['photos']) > 0:
            photo = data['media']['photos'][0]
            if photo.get('url'):
                return photo['url'], 'image'
                
        # Check for video
        if data.get('media') and data['media'].get('videos') and len(data['media']['videos']) > 0:
            video = data['media']['videos'][0]
            if video.get('url'):
                return video['url'], 'video'
                
        logger.warning("No media found in vxtwitter API response")
        return None, None
    except Exception as e:
        logger.error(f"Error parsing vxtwitter API response: {str(e)}")
        return None, None

def extract_from_vx_fx_html(response):
    """Extract media URL from vxtwitter or fxtwitter HTML response."""
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for og:image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image.get('content'), 'image'
            
        # Check for twitter:image
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return twitter_image.get('content'), 'image'
            
        # Look for specific image elements in the HTML
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'pbs.twimg.com/media' in src and not src.endswith('.svg'):
                return src, 'image'
                
        # Look for video elements
        for video in soup.find_all('video'):
            src = video.get('src', '')
            if src and ('pbs.twimg.com' in src or 'video.twimg.com' in src):
                return src, 'video'
                
        # Check for source tags in video elements
        for source in soup.find_all('source'):
            src = source.get('src', '')
            if src and ('pbs.twimg.com' in src or 'video.twimg.com' in src):
                return src, 'video'
                
        logger.warning("No media found in vxtwitter/fxtwitter HTML")
        return None, None
    except Exception as e:
        logger.error(f"Error parsing vxtwitter/fxtwitter HTML: {str(e)}")
        return None, None

def extract_from_nitter_html(response):
    """Extract media URL from nitter.net HTML."""
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for images in the tweet
        for img in soup.select('.tweet-media img'):
            src = img.get('src', '')
            if src:
                # Convert relative URLs to absolute
                if src.startswith('/'):
                    src = f"https://nitter.net{src}"
                return src, 'image'
                
        # Check for videos
        for video in soup.select('.tweet-media video'):
            poster = video.get('poster', '')
            if poster:
                # Often the poster attribute contains the preview image
                if poster.startswith('/'):
                    poster = f"https://nitter.net{poster}"
                return poster, 'image'
                
            # Try to get the video source
            for source in video.find_all('source'):
                src = source.get('src', '')
                if src:
                    if src.startswith('/'):
                        src = f"https://nitter.net{src}"
                    return src, 'video'
                    
        logger.warning("No media found in nitter HTML")
        return None, None
    except Exception as e:
        logger.error(f"Error parsing nitter HTML: {str(e)}")
        return None, None

class MediaDownloader:
    def __init__(self, url, download_path, media_type='auto'):
        self.url = url
        self.download_path = download_path
        self.media_type = media_type
        self.media_info = {
            'id': str(uuid.uuid4()),
            'platform': 'twitter',
            'media_type': media_type if media_type != 'auto' else 'unknown',
            'original_url': url,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Convert to string for JSON serialization
        }

    def download_media(self):
        """General method to download media (image or video) with multiple fallbacks."""
        try:
            logger.info(f"Starting media download for tweet: {self.url}")
            
            # Try yt-dlp first for video content
            logger.info("Attempting to download media with yt-dlp first (prioritizing videos)")
            video_path, video_name = download_video_with_yt_dlp(self.url, self.download_path)
            
            if video_path and os.path.exists(video_path):
                logger.info(f"Successfully downloaded video using yt-dlp to {video_path}")
                self.media_info['media_type'] = 'video'
                
                # Process the downloaded video
                with open(video_path, 'rb') as f:
                    content = f.read()
                
                return self._process_video(video_path, content, filename=video_name)
            
            # If video download failed, try twitter_scraper for any media content
            try:
                media_urls = get_tweet_media_urls_tscraper(self.url)
                
                if media_urls:
                    logger.info(f"Found media URLs with twitter_scraper: {media_urls}")
                    media_url = media_urls[0]
                    
                    # Check if it's a video based on URL
                    is_video = any(ext in media_url.lower() for ext in ['.mp4', '.mov', '.avi', '.webm']) or 'video' in media_url.lower()
                    
                    if is_video:
                        self.media_info['media_type'] = 'video'
                    else:
                        self.media_info['media_type'] = 'image'
                        
                    # Download and process the media
                    response = requests.get(media_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://twitter.com/'
                    })
                    response.raise_for_status()
                    
                    if self.media_info['media_type'] == 'video':
                        return self._process_video(media_url, response.content)
                    else:
                        return self._process_image(response.content)
                else:
                    logger.warning("twitter_scraper did not find any media URLs, trying yt-dlp URL extraction as fallback.")
            except Exception as scraper_error:
                logger.warning(f"twitter_scraper failed: {str(scraper_error)}, continuing with fallbacks")
                
            # If direct video download and twitter_scraper both failed, try URL extraction with yt-dlp
            media_url, detected_type = get_media_url_with_yt_dlp(self.url, self.download_path)
            
            # If yt-dlp extraction fails, try direct HTML extraction for images
            if not media_url:
                logger.warning("yt-dlp extraction failed, trying direct HTML extraction for images")
                image_url = get_tweet_image_url(self.url)
                
                if image_url:
                    logger.info(f"Found image URL through direct HTML extraction: {image_url}")
                    media_url = image_url
                    detected_type = 'image'
                else:
                    # Last resort: try alternative API services
                    logger.warning("Direct HTML extraction failed, trying alternative API services")
                    media_url, detected_type = try_api_services(self.url)
                    
                    # Old fxtwitter code as additional fallback
                    if not media_url:
                        fx_url = self.url.replace("twitter.com", "fxtwitter.com")
                        logger.info(f"Trying fxtwitter.com API: {fx_url}")
                        try:
                            fx_response = requests.get(fx_url, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            })
                            fx_response.raise_for_status()
                            
                            # Try to extract image from JSON response
                            if 'application/json' in fx_response.headers.get('Content-Type', ''):
                                data = fx_response.json()
                                if data.get('media') and data['media'].get('photos'):
                                    image_url = data['media']['photos'][0].get('url')
                                    if image_url:
                                        logger.info(f"Found image URL through fxtwitter.com: {image_url}")
                                        media_url = image_url
                                        detected_type = 'image'
                            
                            # If JSON extraction fails, try HTML extraction from fxtwitter response
                            if not media_url and fx_response.text:
                                fx_soup = BeautifulSoup(fx_response.text, 'html.parser')
                                og_image = fx_soup.find('meta', property='og:image')
                                if og_image and og_image.get('content'):
                                    image_url = og_image.get('content')
                                    logger.info(f"Found image URL from fxtwitter og:image: {image_url}")
                                    media_url = image_url
                                    detected_type = 'image'
                        except Exception as fx_error:
                            logger.warning(f"fxtwitter.com extraction failed: {str(fx_error)}")
            
            if not media_url:
                # Super last resort: Try TwitterAPI v2 using a guest token
                try:
                    logger.info("Attempting to use Twitter API v2 as last resort")
                    match = re.search(r'twitter\.com/[^/]+/status/(\d+)', self.url)
                    if match:
                        tweet_id = match.group(1)
                        
                        # Get a guest token first
                        guest_token_response = requests.post(
                            "https://api.twitter.com/1.1/guest/activate.json",
                            headers={
                                "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                            }
                        )
                        
                        if guest_token_response.ok:
                            guest_token = guest_token_response.json().get("guest_token")
                            
                            # Use the guest token to fetch tweet details
                            tweet_response = requests.get(
                                f"https://api.twitter.com/2/timeline/conversation/{tweet_id}.json?tweet_mode=extended",
                                headers={
                                    "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                                    "x-guest-token": guest_token,
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                }
                            )
                            
                            if tweet_response.ok:
                                tweet_data = tweet_response.json()
                                # Extract media from the response
                                if "globalObjects" in tweet_data and "tweets" in tweet_data["globalObjects"]:
                                    tweets = tweet_data["globalObjects"]["tweets"]
                                    if tweet_id in tweets and "extended_entities" in tweets[tweet_id]:
                                        entities = tweets[tweet_id]["extended_entities"]
                                        if "media" in entities and len(entities["media"]) > 0:
                                            media_item = entities["media"][0]
                                            
                                            # Check for image
                                            if "media_url_https" in media_item:
                                                media_url = media_item["media_url_https"]
                                                detected_type = "image"
                                                logger.info(f"Found image URL via Twitter API v2: {media_url}")
                                            
                                            # Check for video
                                            elif "video_info" in media_item and "variants" in media_item["video_info"]:
                                                variants = media_item["video_info"]["variants"]
                                                best_variant = max(variants, key=lambda x: x.get("bitrate", 0) if "bitrate" in x else 0)
                                                if "url" in best_variant:
                                                    media_url = best_variant["url"]
                                                    detected_type = "video"
                                                    logger.info(f"Found video URL via Twitter API v2: {media_url}")
                except Exception as api_error:
                    logger.warning(f"Twitter API v2 extraction failed: {str(api_error)}")
            
            if not media_url:
                raise ValueError("No media could be found for this tweet after trying all available methods")
            
            logger.info(f"Found media URL: {media_url}, type: {detected_type}")
            self.media_info['media_type'] = detected_type
            
            # Download using the extracted URL
            response = requests.get(media_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://twitter.com/'
            })
            response.raise_for_status()
            
            if detected_type == 'video':
                return self._process_video(media_url, response.content)
            else:
                return self._process_image(response.content)
                
        except Exception as e:
            logger.error(f"Media download error: {str(e)}")
            raise

    def _process_image(self, content):
        """Process downloaded image content."""
        try:
            img = Image.open(BytesIO(content))
            filename = sanitize_filename(f"image_{uuid.uuid4()}.{img.format.lower() if img.format else 'jpg'}")
            filepath = self.download_path / filename
            img.save(filepath)
            logger.info(f"Saved image to {filepath}")

            thumbnail = img.copy()
            thumbnail.thumbnail((300, 300))
            thumb_path = self.download_path / f"thumb_{filename}"
            thumbnail.save(thumb_path)
            logger.info(f"Created thumbnail at {thumb_path}")

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
            logger.error(f"Error processing image: {str(e)}")
            raise

    def _process_video(self, video_url, content, filename=None):
        """Process downloaded video content."""
        try:
            # Save the video file
            if filename is None:
                filename = sanitize_filename(f"video_{uuid.uuid4()}.mp4")
            else:
                filename = sanitize_filename(filename)
                
            filepath = self.download_path / filename
            
            # Only write if content provided or file doesn't exist
            if not os.path.exists(filepath) or content:
                with open(filepath, 'wb') as f:
                    f.write(content)
            
            logger.info(f"Saved video to {filepath}")

            # Create a thumbnail (could use ffmpeg for a better thumbnail if available)
            thumb_path = self.download_path / f"thumb_{filename}.jpg"
            
            # First try to use yt-dlp to extract a thumbnail - most reliable method
            try:
                ydl_opts = get_ydl_opts(self.download_path)
                ydl_opts['skip_download'] = True
                ydl_opts['writethumbnail'] = True
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(self.url, download=False)
                    # Look for any generated thumbnails
                    thumb_files = [f for f in self.download_path.iterdir() 
                                if f.is_file() and any(f.name.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp'])]
                    
                    if thumb_files:
                        # Use the first thumbnail file found
                        source_thumb = thumb_files[0]
                        with open(source_thumb, 'rb') as src, open(thumb_path, 'wb') as dest:
                            dest.write(src.read())
                        logger.info(f"Created thumbnail from yt-dlp at {thumb_path}")
                    else:
                        # Thumbnail extraction failed, try twitter_scraper
                        raise ValueError("No thumbnail found via yt-dlp")
            except Exception:
                # If yt-dlp fails, try twitter_scraper
                try:
                    # Attempt to use an image from the same tweet as thumbnail
                    media_urls = get_tweet_media_urls_tscraper(self.url)
                    for url in media_urls:
                        if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            thumb_response = requests.get(url)
                            if thumb_response.ok:
                                with open(thumb_path, 'wb') as f:
                                    f.write(thumb_response.content)
                                logger.info(f"Created thumbnail from tweet image at {thumb_path}")
                                break
                    else:
                        # Create a default thumbnail
                        img = Image.new('RGB', (640, 360), color=(33, 33, 33))
                        draw = ImageDraw.Draw(img)
                        draw.text((320, 180), "Video Thumbnail", fill=(255, 255, 255))
                        img.save(thumb_path)
                        logger.info(f"Created default thumbnail at {thumb_path}")
                except Exception as thumb_error:
                    logger.error(f"Error creating thumbnail: {str(thumb_error)}")
                    thumb_path = None

            self.media_info.update({
                'local_path': str(filepath),
                'thumbnail_path': str(thumb_path) if thumb_path else None,
                'file_size': os.path.getsize(filepath),
                'title': f"Twitter Video {datetime.now().strftime('%Y-%m-%d')}",
                'status': 'completed',
                'metadata': {
                    'uploader': 'Twitter User',
                    'upload_date': datetime.now().strftime('%Y%m%d'),
                }
            })

            return self.media_info
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise
    
    # Legacy methods for backward compatibility
    def simple_image_download(self):
        """Legacy method for backward compatibility."""
        return self.download_media()
        
    def download_image(self):
        """Legacy method for backward compatibility."""
        return self.download_media()
        
    def download_video(self):
        """Legacy method for backward compatibility."""
        return self.download_media()

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

        # Check Redis cache first
        cache_key = f"twitter:{user_id}:{url}"
        try:
            # Check if media is already cached in Redis
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
        except Exception as cache_error:
            logger.warning(f"Cache check error (continuing without cache): {str(cache_error)}")

        # Create download directory with deterministic name based on tweet ID
        tweet_id = get_tweet_id_from_url(url)
        download_id = f"tweet_{tweet_id}"
        download_path = TWITTER_DOWNLOAD_PATH / download_id
        download_path.mkdir(exist_ok=True)

        # Determine media type - always use auto since we'll detect it during download
        downloader = MediaDownloader(url, download_path, 'auto')

        try:
            # Use the unified media download method
            media_info = downloader.download_media()

            # Convert paths ensuring we use absolute paths for access and relative paths for storage
            if 'local_path' in media_info and media_info['local_path']:
                # Store the absolute path for immediate file operations
                if isinstance(media_info['local_path'], str):
                    abs_file_path = Path(media_info['local_path'])
                else:
                    abs_file_path = media_info['local_path']
                
                # Include the tweet_id subdirectory in the relative path
                rel_path = f"twitter/{download_id}/{abs_file_path.name}"
                media_info['file_path'] = rel_path
                
                # Store both paths
                media_info['absolute_path'] = str(abs_file_path)
                media_info['local_path'] = rel_path

            if 'thumbnail_path' in media_info and media_info['thumbnail_path']:
                if isinstance(media_info['thumbnail_path'], str):
                    abs_thumb_path = Path(media_info['thumbnail_path'])
                else:
                    abs_thumb_path = media_info['thumbnail_path']

                # Ensure thumbnail path includes the tweet_id subdirectory
                rel_path = f"twitter/{download_id}/{abs_thumb_path.name}"
                media_info['thumbnail_path'] = rel_path
                media_info['absolute_thumb_path'] = str(abs_thumb_path)

            # Convert any datetime objects to strings for JSON serialization
            def sanitize_for_json(data):
                if isinstance(data, dict):
                    return {k: sanitize_for_json(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [sanitize_for_json(item) for item in data]
                elif isinstance(data, datetime):
                    return data.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    return data
            
            media_info = sanitize_for_json(media_info)

            # Save metadata to database using the prepared absolute path
            try:
                absolute_path = media_info.get('absolute_path')
                
                # Remove extra parameters that aren't supported
                save_media_metadata(
                    user_id=user_id,
                    platform='twitter',
                    media_type=media_info['media_type'],
                    file_path=media_info['local_path'],  # Relative path for storage
                    title=media_info.get('title', 'Twitter Media'),
                    original_url=url,
                    duration=media_info.get('duration', 0),
                    metadata=media_info.get('metadata', {}),
                    thumbnail_path=media_info.get('thumbnail_path')
                    # Removed width and height parameters that were causing errors
                )
                logger.info(f"Media metadata saved successfully for URL: {url}")

                # Remove absolute paths before sending to client or cache
                clean_media_info = media_info.copy()
                if 'absolute_path' in clean_media_info:
                    del clean_media_info['absolute_path']
                if 'absolute_thumb_path' in clean_media_info:
                    del clean_media_info['absolute_thumb_path']
                
                # Cache the media info
                try:
                    twitter_cache.cache_media(url, user_id, clean_media_info)
                    logger.info(f"Successfully cached media for URL: {url}")
                except Exception as cache_error:
                    logger.error(f"Cache error: {str(cache_error)}")
                    # Continue even if cache fails

            except Exception as db_error:
                logger.error(f"Error saving media metadata: {str(db_error)}")
                # Continue even if database save fails

            # Remove absolute paths before sending to client
            client_media_info = media_info.copy()
            if 'absolute_path' in client_media_info:
                del client_media_info['absolute_path']
            if 'absolute_thumb_path' in client_media_info:
                del client_media_info['absolute_thumb_path']

            return jsonify({
                'status': 'success',
                'media_info': client_media_info,
                'download_url': url_for('twitter.download_file',
                                       download_id=download_id,
                                       filename=os.path.basename(media_info['local_path']))
            })

        except Exception as e:
            error_message = str(e)
            logger.error(f"Download error: {error_message}")

            if "Unsupported URL" in error_message:
                return jsonify({'error': 'This Twitter URL is not supported or the content is private'}), 400
            elif "unavailable" in error_message.lower():
                return jsonify({'error': 'The content is no longer available or is private'}), 400
            else:
                return jsonify({'error': f'Failed to download: {error_message}'}), 500

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

# Add a global error handler for the blueprint
@twitter_bp.errorhandler(Exception)
def handle_twitter_exception(e):
    logger.error(f"Unhandled exception in Twitter blueprint: {str(e)}", exc_info=True)
    return jsonify({'error': 'An unexpected error occurred in Twitter media extraction.'}), 500