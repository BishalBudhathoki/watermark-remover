"""
Example script for using the poster module.

This script demonstrates how to use the poster module to post videos
to various social media platforms.
"""

import os
import json
import logging
from dotenv import load_dotenv

# Import platform-specific modules to register them
from poster import post_to_platform, post_to_all_platforms
import tiktok
import instagram
import youtube

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def main():
    """Run the example script."""
    # Get video path from user
    video_path = input("Enter the path to a video file: ")

    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return

    # Get caption and hashtags
    caption = input("Enter a caption for the video: ")
    hashtags_input = input("Enter hashtags (comma-separated): ")
    hashtags = [tag.strip() for tag in hashtags_input.split(",") if tag.strip()]

    # Choose platforms
    # # # # # # print("\n=== Available Platforms ===")
    # # # # # # print("1. TikTok")
    # # # # # # print("2. Instagram Reels")
    # # # # # # print("3. YouTube Shorts")
    # # # # # # print("4. All Platforms")

    choice = input("Choose a platform (1-4): ")

    if choice == "1":
        # Post to TikTok
        logger.info("Posting to TikTok...")
        result = post_to_platform(
            platform="tiktok",
            video_path=video_path,
            caption=caption,
            hashtags=hashtags
        )

        # # # # # # print("\n=== TikTok Posting Result ===")
        # # # # # # print(f"Success: {result['success']}")
        if result['success']:
            # # # # # # print(f"Post URL: {result['post_url']}")
            # # # # # # print(f"Post ID: {result['post_id']}")
        else:
            # # # # # # print(f"Error: {result['error']}")

    elif choice == "2":
        # Post to Instagram
        logger.info("Posting to Instagram Reels...")
        result = post_to_platform(
            platform="instagram",
            video_path=video_path,
            caption=caption,
            hashtags=hashtags
        )

        # # # # # # print("\n=== Instagram Posting Result ===")
        # # # # # # print(f"Success: {result['success']}")
        if result['success']:
            # # # # # # print(f"Post URL: {result['post_url']}")
            # # # # # # print(f"Post ID: {result['post_id']}")
        else:
            # # # # # # print(f"Error: {result['error']}")

    elif choice == "3":
        # Post to YouTube
        logger.info("Posting to YouTube Shorts...")
        result = post_to_platform(
            platform="youtube",
            video_path=video_path,
            caption=caption,
            hashtags=hashtags
        )

        # # # # # # print("\n=== YouTube Posting Result ===")
        # # # # # # print(f"Success: {result['success']}")
        if result['success']:
            # # # # # # print(f"Post URL: {result['post_url']}")
            # # # # # # print(f"Post ID: {result['post_id']}")
        else:
            # # # # # # print(f"Error: {result['error']}")

    elif choice == "4":
        # Post to all platforms
        logger.info("Posting to all platforms...")

        # Create platform-specific data
        platforms_data = {
            "tiktok": {
                "caption": caption,
                "hashtags": hashtags + ["tiktok"]
            },
            "instagram": {
                "caption": caption,
                "hashtags": hashtags + ["reels"]
            },
            "youtube": {
                "caption": caption,
                "hashtags": hashtags + ["shorts"]
            }
        }

        results = post_to_all_platforms(
            video_path=video_path,
            platforms_data=platforms_data
        )

        # # # # # # print("\n=== All Platforms Posting Results ===")
        for platform, result in results.items():
            # # # # # # print(f"\n{platform.capitalize()}:")
            # # # # # # print(f"  Success: {result['success']}")
            if result['success']:
                # # # # # # print(f"  Post URL: {result['post_url']}")
                # # # # # # print(f"  Post ID: {result['post_id']}")
            else:
                # # # # # # print(f"  Error: {result['error']}")

    else:
        logger.error("Invalid choice")


if __name__ == "__main__":
    main()