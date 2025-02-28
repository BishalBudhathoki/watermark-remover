from celery import shared_task
from celery.utils.log import get_task_logger
import yt_dlp
import os
from typing import Dict, List, Optional
import requests
from pathlib import Path
import json
import re
from urllib.parse import urlparse
import time

logger = get_task_logger(__name__)

class VideoDownloader:
    """Base class for video downloading functionality."""
    
    def __init__(self, output_path: str):
        self.output_path = output_path
        os.makedirs(output_path, exist_ok=True)
    
    def get_safe_filename(self, title: str) -> str:
        """Convert title to safe filename."""
        return re.sub(r'[^\w\-_.]', '_', title)

class YTDLDownloader(VideoDownloader):
    """Downloader using yt-dlp for supported platforms."""
    
    def __init__(self, output_path: str):
        super().__init__(output_path)
        self.ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'concurrent_fragment_downloads': 4,
        }
    
    def download(self, url: str) -> Dict:
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return {
                    'status': 'success',
                    'title': info.get('title'),
                    'filename': filename,
                    'duration': info.get('duration'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'description': info.get('description'),
                }
            except Exception as e:
                logger.error(f"Error downloading video: {str(e)}")
                raise

@shared_task(bind=True, name='tasks.social_media.download_tiktok')
def download_tiktok(self, url: str, output_path: str) -> Dict:
    """
    Download video from TikTok.
    
    Args:
        url: TikTok video URL
        output_path: Directory to save the video
    
    Returns:
        Dict containing download status and video information
    """
    try:
        logger.info(f"Starting TikTok download: {url}")
        downloader = YTDLDownloader(output_path)
        result = downloader.download(url)
        logger.info(f"TikTok download completed: {result['filename']}")
        return result
    except Exception as e:
        logger.error(f"Error downloading TikTok video: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

@shared_task(bind=True, name='tasks.social_media.download_instagram')
def download_instagram(self, url: str, output_path: str) -> Dict:
    """
    Download video from Instagram.
    
    Args:
        url: Instagram video URL
        output_path: Directory to save the video
    
    Returns:
        Dict containing download status and video information
    """
    try:
        logger.info(f"Starting Instagram download: {url}")
        downloader = YTDLDownloader(output_path)
        result = downloader.download(url)
        logger.info(f"Instagram download completed: {result['filename']}")
        return result
    except Exception as e:
        logger.error(f"Error downloading Instagram video: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

@shared_task(bind=True, name='tasks.social_media.download_youtube')
def download_youtube(self, url: str, output_path: str, options: Optional[Dict] = None) -> Dict:
    """
    Download video from YouTube with options.
    
    Args:
        url: YouTube video URL
        output_path: Directory to save the video
        options: Dictionary containing download options
            - quality: Video quality (e.g., "1080p")
            - format: Video format
            - extract_audio: Boolean to extract audio only
    
    Returns:
        Dict containing download status and video information
    """
    try:
        logger.info(f"Starting YouTube download: {url}")
        
        if options is None:
            options = {}
        
        ydl_opts = {
            'format': 'bestvideo[height<=?1080]+bestaudio/best',
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'concurrent_fragment_downloads': 4,
        }
        
        # Modify options based on user preferences
        if options.get('quality'):
            height = int(options['quality'].replace('p', ''))
            ydl_opts['format'] = f'bestvideo[height<=?{height}]+bestaudio/best'
        
        if options.get('format'):
            ydl_opts['merge_output_format'] = options['format']
        
        if options.get('extract_audio'):
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            result = {
                'status': 'success',
                'title': info.get('title'),
                'filename': filename,
                'duration': info.get('duration'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'description': info.get('description'),
                'uploader': info.get('uploader'),
                'upload_date': info.get('upload_date'),
            }
            
            logger.info(f"YouTube download completed: {filename}")
            return result
            
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

@shared_task(bind=True, name='tasks.social_media.batch_download')
def batch_download(self, urls: List[str], output_path: str) -> List[Dict]:
    """
    Download multiple videos in batch.
    
    Args:
        urls: List of video URLs
        output_path: Directory to save the videos
    
    Returns:
        List of dictionaries containing download status and video information
    """
    results = []
    
    for url in urls:
        try:
            domain = urlparse(url).netloc
            
            if 'tiktok.com' in domain:
                result = download_tiktok.delay(url, output_path)
            elif 'instagram.com' in domain:
                result = download_instagram.delay(url, output_path)
            elif 'youtube.com' in domain or 'youtu.be' in domain:
                result = download_youtube.delay(url, output_path)
            else:
                logger.warning(f"Unsupported platform: {domain}")
                continue
            
            results.append(result.get())
            
        except Exception as e:
            logger.error(f"Error in batch download for {url}: {str(e)}")
            results.append({
                'status': 'error',
                'url': url,
                'error': str(e)
            })
    
    return results

@shared_task(name='tasks.social_media.cleanup_failed_downloads')
def cleanup_failed_downloads(max_age_hours: int = 24) -> None:
    """
    Clean up incomplete or failed downloads.
    
    Args:
        max_age_hours: Maximum age of files in hours before deletion
    """
    try:
        logger.info("Starting cleanup of failed downloads")
        
        download_path = 'downloads'
        if not os.path.exists(download_path):
            return
            
        current_time = time.time()
        
        for file_path in Path(download_path).glob('**/*'):
            if not file_path.is_file():
                continue
                
            # Check if file is incomplete (e.g., .part files)
            if file_path.suffix in ['.part', '.temp']:
                file_age_hours = (current_time - os.path.getmtime(file_path)) / 3600
                
                if file_age_hours > max_age_hours:
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted incomplete download: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        logger.info("Cleanup of failed downloads completed")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise 