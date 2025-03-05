"""
TikTok Poster Module for Content Repurposing Pipeline.

This module provides functions to post videos to TikTok using the official TikTok API.
"""

import os
import logging
import json
import time
from typing import Dict, List, Any, Optional
import requests
from pathlib import Path

from dotenv import load_dotenv
from .poster import register_platform
from .auth import get_auth_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class TikTokAPI:
    """TikTok API client for video uploads."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = 'https://open-api.tiktok.com/v2'  # Updated to v2 endpoint
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

    def init_upload(self, video_path: str) -> Dict:
        """Initialize video upload and get upload URL."""
        try:
            file_size = Path(video_path).stat().st_size

            response = requests.post(
                f'{self.base_url}/video/upload/',
                headers=self.headers,
                json={
                    'source_info': {
                        'source': 'FILE',
                        'video_size': file_size,
                        'chunk_size': file_size  # For non-chunked upload
                    }
                }
            )

            # Log the response for debugging
            logger.info(f"TikTok upload init response: {response.text}")

            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                raise Exception(f"TikTok API error: {data['error']}")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during upload initialization: {str(e)}")
            raise Exception(f"Failed to initialize upload: {str(e)}")
        except Exception as e:
            logger.error(f"Error during upload initialization: {str(e)}")
            raise

    def upload_video(self, upload_url: str, video_path: str) -> bool:
        """Upload video to TikTok servers."""
        try:
            with open(video_path, 'rb') as f:
                # Add required headers for video upload
                headers = {
                    'Content-Type': 'video/mp4',
                    'Authorization': f'Bearer {self.access_token}'
                }

                response = requests.put(upload_url, data=f, headers=headers)

                # Log the response for debugging
                logger.info(f"TikTok video upload response: {response.text}")

                response.raise_for_status()
                return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during video upload: {str(e)}")
            raise Exception(f"Failed to upload video: {str(e)}")
        except Exception as e:
            logger.error(f"Error during video upload: {str(e)}")
            raise

    def create_post(self, video_id: str, caption: str, privacy_level: str = 'PUBLIC') -> Dict:
        """Create a TikTok post with the uploaded video."""
        try:
            response = requests.post(
                f'{self.base_url}/video/publish/',
                headers=self.headers,
                json={
                    'video_id': video_id,
                    'post_info': {
                        'title': caption,
                        'privacy_level': privacy_level,
                        'disable_duet': False,
                        'disable_stitch': False,
                        'disable_comment': False,
                        'video_cover_timestamp_ms': 0
                    }
                }
            )

            # Log the response for debugging
            logger.info(f"TikTok post creation response: {response.text}")

            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                raise Exception(f"TikTok API error: {data['error']}")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during post creation: {str(e)}")
            raise Exception(f"Failed to create post: {str(e)}")
        except Exception as e:
            logger.error(f"Error during post creation: {str(e)}")
            raise

def post_to_tiktok(
    video_path: str,
    caption: str,
    hashtags: List[str],
    credentials: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Post a video to TikTok using the official TikTok API.

    Args:
        video_path: Path to the video file
        caption: Caption for the video
        hashtags: List of hashtags for the video
        credentials: Dictionary containing TikTok credentials (optional)
            - access_token: TikTok OAuth access token
            - user_id: User ID for authentication manager
        options: Dictionary containing TikTok-specific options (optional)
            - privacy_level: "PUBLIC", "FRIEND", or "PRIVATE"
            - disable_duet: Boolean indicating if duets are disabled
            - disable_stitch: Boolean indicating if stitching is disabled
            - disable_comment: Boolean indicating if comments are disabled

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the posting was successful
            - platform: "tiktok"
            - post_url: URL of the TikTok post (if available)
            - post_id: ID of the TikTok post (if available)
            - error: Error message (if any)
            - auth_required: Boolean indicating if authentication is required
    """
    logger.info(f"Posting to TikTok: {video_path}")

    # Get credentials from parameters or environment variables
    if credentials is None:
        credentials = {}

    # Check if user is authenticated
    user_id = credentials.get("user_id", "anonymous")
    auth_manager = get_auth_manager(user_id)

    if not auth_manager.is_authenticated("tiktok"):
        logger.error("TikTok authentication required")
        return {
            "success": False,
            "platform": "tiktok",
            "post_url": None,
            "post_id": None,
            "error": "TikTok authentication required. Please log in to TikTok first.",
            "auth_required": True
        }

    # Get stored credentials
    stored_credentials = auth_manager.get_credentials("tiktok")
    if not stored_credentials:
        logger.error("TikTok credentials not found")
        return {
            "success": False,
            "platform": "tiktok",
            "post_url": None,
            "post_id": None,
            "error": "TikTok credentials not found. Please log in to TikTok again.",
            "auth_required": True
        }

    # Get options
    if options is None:
        options = {}

    # Format hashtags
    formatted_hashtags = " ".join([f"#{tag}" for tag in hashtags])
    full_caption = f"{caption}\n\n{formatted_hashtags}"

    try:
        # Initialize TikTok API client
        api = TikTokAPI(stored_credentials['access_token'])

        # Initialize upload
        upload_info = api.init_upload(video_path)
        video_id = upload_info['video_id']
        upload_url = upload_info['upload_url']

        # Upload video
        if not api.upload_video(upload_url, video_path):
            raise Exception("Failed to upload video to TikTok servers")

        # Create post
        post_info = api.create_post(
            video_id=video_id,
            caption=full_caption,
            privacy_level=options.get('privacy_level', 'PUBLIC')
        )

        return {
            "success": True,
            "platform": "tiktok",
            "post_url": post_info.get('share_url'),
            "post_id": post_info.get('video_id'),
            "error": None,
            "auth_required": False
        }

    except Exception as e:
        logger.error(f"Error posting to TikTok: {str(e)}")
        return {
            "success": False,
            "platform": "tiktok",
            "post_url": None,
            "post_id": None,
            "error": str(e),
            "auth_required": False
        }

# Register the platform
register_platform('tiktok', post_to_tiktok)