"""
Instagram Poster Module for Content Repurposing Pipeline.

This module provides functions to post videos to Instagram Reels.
"""

import os
import logging
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv
from .poster import register_platform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def post_to_instagram(
    video_path: str,
    caption: str,
    hashtags: List[str],
    credentials: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Post a video to Instagram Reels.

    Args:
        video_path: Path to the video file
        caption: Caption for the video
        hashtags: List of hashtags for the video
        credentials: Dictionary containing Instagram credentials (optional)
            - username: Instagram username
            - password: Instagram password
            - session_id: Instagram session ID (alternative to username/password)
        options: Dictionary containing Instagram-specific options (optional)
            - location: Location ID or name
            - tagged_users: List of usernames to tag
            - share_to_feed: Boolean indicating if the Reel should be shared to the feed
            - share_to_story: Boolean indicating if the Reel should be shared to the story

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the posting was successful
            - platform: "instagram"
            - post_url: URL of the Instagram post (if available)
            - post_id: ID of the Instagram post (if available)
            - error: Error message (if any)
    """
    logger.info(f"Posting to Instagram Reels: {video_path}")

    # Get credentials from parameters or environment variables
    if credentials is None:
        credentials = {}

    username = credentials.get("username") or os.getenv("INSTAGRAM_USERNAME")
    password = credentials.get("password") or os.getenv("INSTAGRAM_PASSWORD")
    session_id = credentials.get("session_id") or os.getenv("INSTAGRAM_SESSION_ID")

    if not ((username and password) or session_id):
        logger.error("Instagram credentials not provided")
        return {
            "success": False,
            "platform": "instagram",
            "post_url": None,
            "post_id": None,
            "error": "Instagram credentials not provided. Please authenticate with Instagram first."
        }

    # Get options
    if options is None:
        options = {}

    # Format hashtags
    formatted_hashtags = " ".join([f"#{tag}" for tag in hashtags])
    full_caption = f"{caption}\n\n{formatted_hashtags}"

    try:
        # This would use the Instagram API or a third-party library
        # For now, we'll return an authentication required response
        logger.error("Instagram authentication required")
        return {
            "success": False,
            "platform": "instagram",
            "post_url": None,
            "post_id": None,
            "error": "Instagram authentication required. Please log in to Instagram first."
        }

    except Exception as e:
        logger.error(f"Error posting to Instagram Reels: {str(e)}")
        return {
            "success": False,
            "platform": "instagram",
            "post_url": None,
            "post_id": None,
            "error": str(e)
        }


# Register the platform
register_platform("instagram", post_to_instagram)