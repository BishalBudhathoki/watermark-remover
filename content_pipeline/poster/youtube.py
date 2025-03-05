"""
YouTube Poster Module for Content Repurposing Pipeline.

This module provides functions to post videos to YouTube Shorts.
"""

import os
import logging
from typing import Dict, List, Any, Optional

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


def post_to_youtube(
    video_path: str,
    caption: str,
    hashtags: List[str],
    credentials: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Post a video to YouTube Shorts.

    Args:
        video_path: Path to the video file
        caption: Caption for the video (will be used as the title)
        hashtags: List of hashtags for the video
        credentials: Dictionary containing YouTube credentials (optional)
            - client_id: YouTube API client ID
            - client_secret: YouTube API client secret
            - refresh_token: YouTube API refresh token
            - user_id: User ID for authentication manager
        options: Dictionary containing YouTube-specific options (optional)
            - description: Additional description text
            - category_id: YouTube category ID
            - privacy_status: "public", "unlisted", or "private"
            - made_for_kids: Boolean indicating if the video is made for kids

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the posting was successful
            - platform: "youtube"
            - post_url: URL of the YouTube video (if available)
            - post_id: ID of the YouTube video (if available)
            - error: Error message (if any)
            - auth_required: Boolean indicating if authentication is required
    """
    logger.info(f"Posting to YouTube Shorts: {video_path}")

    # Get credentials from parameters or environment variables
    if credentials is None:
        credentials = {}

    # Check if user is authenticated
    user_id = credentials.get("user_id", "anonymous")
    auth_manager = get_auth_manager(user_id)

    if not auth_manager.is_authenticated("youtube"):
        logger.error("YouTube authentication required")
        return {
            "success": False,
            "platform": "youtube",
            "post_url": None,
            "post_id": None,
            "error": "YouTube authentication required. Please log in to YouTube first.",
            "auth_required": True
        }

    # Get stored credentials
    stored_credentials = auth_manager.get_credentials("youtube")
    if not stored_credentials:
        logger.error("YouTube credentials not found")
        return {
            "success": False,
            "platform": "youtube",
            "post_url": None,
            "post_id": None,
            "error": "YouTube credentials not found. Please log in to YouTube again.",
            "auth_required": True
        }

    # Get options
    if options is None:
        options = {}

    # Get description from options or use caption as fallback
    description = options.get("description", "")

    # Add hashtags to description
    formatted_hashtags = " ".join([f"#{tag}" for tag in hashtags])
    if description:
        full_description = f"{description}\n\n{formatted_hashtags}"
    else:
        full_description = formatted_hashtags

    # Add #Shorts hashtag if not already present
    if "#shorts" not in full_description.lower():
        full_description = f"{full_description} #Shorts"

    try:
        # This would use the YouTube API
        # For now, we'll return an authentication required response
        logger.error("YouTube API integration not implemented")
        return {
            "success": False,
            "platform": "youtube",
            "post_url": None,
            "post_id": None,
            "error": "YouTube API integration not implemented. Please use the YouTube Studio to post manually.",
            "auth_required": False
        }

    except Exception as e:
        logger.error(f"Error posting to YouTube Shorts: {str(e)}")
        return {
            "success": False,
            "platform": "youtube",
            "post_url": None,
            "post_id": None,
            "error": str(e),
            "auth_required": False
        }


# Register the platform
register_platform("youtube", post_to_youtube)