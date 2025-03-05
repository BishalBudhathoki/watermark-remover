from celery import shared_task
from celery.utils.log import get_task_logger
import tweepy
import requests
import os
from pathlib import Path
import json
from typing import Dict, List, Optional
from datetime import datetime
import re
from urllib.parse import urlparse
import time

logger = get_task_logger(__name__)

class TwitterAPI:
    """Twitter API wrapper for video downloading."""

    def __init__(self):
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        if not self.bearer_token:
            raise ValueError("TWITTER_BEARER_TOKEN environment variable is required")

        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            wait_on_rate_limit=True
        )

    def get_tweet_by_id(self, tweet_id: str) -> Dict:
        """Get tweet information by ID."""
        try:
            tweet = self.client.get_tweet(
                tweet_id,
                expansions=['attachments.media_keys'],
                media_fields=['duration_ms', 'height', 'width', 'variants', 'url', 'type']
            )

            if not tweet.data:
                raise ValueError("Tweet not found")

            return tweet

        except Exception as e:
            logger.error(f"Error getting tweet {tweet_id}: {str(e)}")
            raise

    def get_tweet_id_from_url(self, url: str) -> str:
        """Extract tweet ID from URL."""
        try:
            # Handle various Twitter URL formats
            path = urlparse(url).path
            tweet_id = path.split('/')[-1]

            # Validate tweet ID format
            if not re.match(r'^\d+$', tweet_id):
                raise ValueError("Invalid tweet ID format")

            return tweet_id

        except Exception as e:
            logger.error(f"Error extracting tweet ID from {url}: {str(e)}")
            raise ValueError("Invalid Twitter URL format")

    def get_video_url(self, tweet: Dict) -> Optional[str]:
        """Extract highest quality video URL from tweet."""
        try:
            if not tweet.includes or 'media' not in tweet.includes:
                return None

            for media in tweet.includes['media']:
                if media.type == 'video':
                    # Get video variants
                    variants = media.variants

                    # Filter video variants and sort by bitrate
                    video_variants = [
                        v for v in variants
                        if v.get('content_type') == 'video/mp4' and v.get('bit_rate')
                    ]

                    if not video_variants:
                        return None

                    # Get highest quality video URL
                    best_variant = max(video_variants, key=lambda x: x['bit_rate'])
                    return best_variant['url']

            return None

        except Exception as e:
            logger.error(f"Error extracting video URL: {str(e)}")
            return None

@shared_task(bind=True, name='tasks.twitter.download_twitter')
def download_twitter(self, url: str, output_path: str, options: Optional[Dict] = None) -> Dict:
    """
    Download video from Twitter.

    Args:
        url: Twitter video URL
        output_path: Directory to save the video
        options: Dictionary containing download options
            - quality: Video quality preference
            - include_metadata: Include tweet metadata

    Returns:
        Dict containing download status and video information
    """
    try:
        logger.info(f"Starting Twitter video download: {url}")

        # Create output directory
        os.makedirs(output_path, exist_ok=True)

        # Initialize Twitter API
        api = TwitterAPI()

        # Get tweet ID from URL
        tweet_id = api.get_tweet_id_from_url(url)

        # Get tweet information
        tweet = api.get_tweet_by_id(tweet_id)

        # Get video URL
        video_url = api.get_video_url(tweet)
        if not video_url:
            raise ValueError("No video found in tweet")

        # Generate output filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"twitter_{tweet_id}_{timestamp}.mp4"
        output_file = os.path.join(output_path, filename)

        # Download video
        logger.info(f"Downloading video from {video_url}")
        response = requests.get(video_url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0

        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        self.update_state(
                            state='PROGRESS',
                            meta={'progress': progress}
                        )

        # Prepare response
        result = {
            'status': 'success',
            'tweet_id': tweet_id,
            'filename': filename,
            'file_path': output_file,
            'size_mb': round(os.path.getsize(output_file) / (1024 * 1024), 2)
        }

        # Include tweet metadata if requested
        if options and options.get('include_metadata'):
            result['metadata'] = {
                'text': tweet.data.text,
                'created_at': tweet.data.created_at.isoformat(),
                'author_id': tweet.data.author_id,
                'public_metrics': tweet.data.public_metrics
            }

        logger.info(f"Twitter video download completed: {filename}")
        return result

    except Exception as e:
        logger.error(f"Error downloading Twitter video: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

@shared_task(bind=True, name='tasks.twitter.batch_download_twitter')
def batch_download_twitter(self, urls: List[str], output_path: str, options: Optional[Dict] = None) -> List[Dict]:
    """
    Download multiple Twitter videos in batch.

    Args:
        urls: List of Twitter video URLs
        output_path: Directory to save the videos
        options: Dictionary containing download options

    Returns:
        List of dictionaries containing download status and video information
    """
    results = []

    for url in urls:
        try:
            result = download_twitter.delay(url, output_path, options)
            results.append(result.get())

        except Exception as e:
            logger.error(f"Error in batch download for {url}: {str(e)}")
            results.append({
                'status': 'error',
                'url': url,
                'error': str(e)
            })

    return results