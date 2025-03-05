"""
Poster Module for Content Repurposing Pipeline.

This module provides functions to handle cross-posting of video clips to various
social media platforms, applying the generated captions and hashtags.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from pathlib import Path

from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import platform-specific posting functions
# These will be imported from their respective modules
# and registered in the PLATFORM_POSTERS dictionary


# Dictionary mapping platform names to posting functions
PLATFORM_POSTERS = {}


def register_platform(platform_name: str, poster_func: Callable) -> None:
    """
    Register a platform posting function.

    Args:
        platform_name: Name of the platform
        poster_func: Function to post to the platform
    """
    PLATFORM_POSTERS[platform_name.lower()] = poster_func
    logger.info(f"Registered poster function for platform: {platform_name}")


def post_to_platform(
    platform: str,
    video_path: str,
    caption: str,
    hashtags: List[str],
    credentials: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Post a video to a specific platform.

    Args:
        platform: Name of the platform (e.g., "tiktok", "instagram", "youtube")
        video_path: Path to the video file
        caption: Caption for the video
        hashtags: List of hashtags for the video
        credentials: Dictionary containing platform-specific credentials (optional)
        options: Dictionary containing platform-specific options (optional)

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the posting was successful
            - platform: Name of the platform
            - post_url: URL of the post (if available)
            - post_id: ID of the post (if available)
            - error: Error message (if any)
    """
    platform = platform.lower()
    logger.info(f"Posting to {platform}: {video_path}")

    # Check if the platform is supported
    if platform not in PLATFORM_POSTERS:
        logger.error(f"Unsupported platform: {platform}")
        return {
            "success": False,
            "platform": platform,
            "post_url": None,
            "post_id": None,
            "error": f"Unsupported platform: {platform}"
        }

    # Get the poster function for the platform
    poster_func = PLATFORM_POSTERS[platform]

    try:
        # Call the platform-specific posting function
        result = poster_func(
            video_path=video_path,
            caption=caption,
            hashtags=hashtags,
            credentials=credentials,
            options=options
        )

        return result
    except Exception as e:
        logger.error(f"Error posting to {platform}: {str(e)}")
        return {
            "success": False,
            "platform": platform,
            "post_url": None,
            "post_id": None,
            "error": str(e)
        }


async def post_to_platform_async(
    platform: str,
    video_path: str,
    caption: str,
    hashtags: List[str],
    credentials: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Post a video to a specific platform asynchronously.

    Args:
        platform: Name of the platform (e.g., "tiktok", "instagram", "youtube")
        video_path: Path to the video file
        caption: Caption for the video
        hashtags: List of hashtags for the video
        credentials: Dictionary containing platform-specific credentials (optional)
        options: Dictionary containing platform-specific options (optional)

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the posting was successful
            - platform: Name of the platform
            - post_url: URL of the post (if available)
            - post_id: ID of the post (if available)
            - error: Error message (if any)
    """
    # Run the synchronous function in a thread pool
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: post_to_platform(
            platform=platform,
            video_path=video_path,
            caption=caption,
            hashtags=hashtags,
            credentials=credentials,
            options=options
        )
    )


async def post_to_all_platforms_async(
    video_path: str,
    platforms_data: Dict[str, Dict[str, Union[str, List[str]]]],
    credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    options: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Post a video to multiple platforms asynchronously.

    Args:
        video_path: Path to the video file
        platforms_data: Dictionary mapping platform names to dictionaries containing:
            - caption: Platform-specific caption
            - hashtags: Platform-specific hashtags
        credentials: Dictionary mapping platform names to credential dictionaries (optional)
        options: Dictionary mapping platform names to option dictionaries (optional)

    Returns:
        Dictionary mapping platform names to result dictionaries
    """
    # Create tasks for each platform
    tasks = []
    for platform, data in platforms_data.items():
        platform_credentials = credentials.get(platform) if credentials else None
        platform_options = options.get(platform) if options else None

        task = post_to_platform_async(
            platform=platform,
            video_path=video_path,
            caption=data.get("caption", ""),
            hashtags=data.get("hashtags", []),
            credentials=platform_credentials,
            options=platform_options
        )
        tasks.append((platform, task))

    # Wait for all tasks to complete
    results = {}
    for platform, task in tasks:
        try:
            result = await task
            results[platform] = result
        except Exception as e:
            logger.error(f"Error posting to {platform}: {str(e)}")
            results[platform] = {
                "success": False,
                "platform": platform,
                "post_url": None,
                "post_id": None,
                "error": str(e)
            }

    return results


def post_to_all_platforms(
    video_path: str,
    caption: str = "",
    hashtags: List[str] = None,
    platforms_data: Optional[Dict[str, Dict[str, Union[str, List[str]]]]] = None,
    credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    options: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Post a video to multiple platforms.

    Args:
        video_path: Path to the video file
        caption: Default caption to use for all platforms if not specified in platforms_data
        hashtags: Default hashtags to use for all platforms if not specified in platforms_data
        platforms_data: Dictionary mapping platform names to dictionaries containing:
            - caption: Platform-specific caption
            - hashtags: Platform-specific hashtags
        credentials: Dictionary mapping platform names to credential dictionaries (optional)
        options: Dictionary mapping platform names to option dictionaries (optional)

    Returns:
        Dictionary mapping platform names to result dictionaries
    """
    # Initialize hashtags if None
    if hashtags is None:
        hashtags = []

    # If no platforms_data is provided, use all available platforms with the same caption and hashtags
    if platforms_data is None:
        available_platforms = get_available_platforms()
        if not available_platforms:
            logger.warning("No platforms available for posting")
            return {}

        platforms_data = {
            platform: {
                "caption": caption,
                "hashtags": hashtags
            }
            for platform in available_platforms
        }

    logger.info(f"Posting to multiple platforms: {', '.join(platforms_data.keys())}")

    # Create a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Run the async function in the event loop
        return loop.run_until_complete(
            post_to_all_platforms_async(
                video_path=video_path,
                platforms_data=platforms_data,
                credentials=credentials,
                options=options
            )
        )
    finally:
        # Close the event loop
        loop.close()


def get_available_platforms() -> List[str]:
    """
    Get a list of all available platforms for posting.

    Returns:
        List of platform names that are registered for posting
    """
    return list(PLATFORM_POSTERS.keys())