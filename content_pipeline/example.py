"""
Example script demonstrating the entire Content Repurposing Pipeline.

This script shows how to use the pipeline to:
1. Upload a video
2. Split it into clips
3. Generate text for each clip
4. Post the clips to social media platforms
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the path to import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import components
from content_pipeline.upload import upload_video
from content_pipeline.splitter import split_video
from content_pipeline.text_generator import process_clip
from content_pipeline.poster import post_to_all_platforms

# Import platform-specific modules to register them
from content_pipeline.poster import tiktok, instagram, youtube

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_example():
    """Run the example pipeline."""
    # Get the example video path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    example_video = input("Enter the path to a video file: ")

    if not os.path.exists(example_video):
        logger.error(f"Video file not found: {example_video}")
        return

    # Create output directory
    output_dir = os.path.join(script_dir, "example_output")
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Upload the video
    logger.info("Step 1: Uploading video...")
    upload_result = upload_video(example_video, output_dir)

    if not upload_result["success"]:
        logger.error(f"Video upload failed: {upload_result['error']}")
        return

    processed_video_path = upload_result["file_path"]
    logger.info(f"Video uploaded to: {processed_video_path}")

    # Step 2: Split the video
    logger.info("Step 2: Splitting video...")
    split_result = split_video(
        video_path=processed_video_path,
        output_dir=os.path.join(output_dir, "clips"),
        max_clip_duration=30,  # Shorter for the example
        min_clip_duration=5,
        split_on_silence=True,
        silence_threshold=0.03,
        silence_duration=0.5
    )

    if not split_result["success"]:
        logger.error(f"Video splitting failed: {split_result['error']}")
        return

    clips = split_result["clips"]
    logger.info(f"Created {len(clips)} clips")

    # Step 3: Generate text for each clip
    logger.info("Step 3: Generating text for clips...")
    text_results = []

    for clip in clips:
        # Create clip metadata
        clip_metadata = {
            "duration": clip["duration"],
            "description": f"Clip {clip['index']} from example video",
            "target_audience": "General audience",
            "tone": "Casual and engaging"
        }

        # Generate text
        text_result = process_clip(
            clip_path=clip["path"],
            clip_metadata=clip_metadata,
            platforms=["tiktok", "instagram", "youtube"],
            num_caption_variations=2,  # Fewer for the example
            num_hashtags=5  # Fewer for the example
        )

        # Add clip info to the result
        text_result["clip"] = clip
        text_results.append(text_result)

        # Only process the first clip for the example
        if len(text_results) >= 1:
            logger.info("Processing only the first clip for this example")
            break

    logger.info(f"Generated text for {len(text_results)} clips")

    # Step 4: Ask if user wants to post to platforms
    post_to_platforms = input("Do you want to post to social media platforms? (y/n): ").lower() == 'y'

    if post_to_platforms:
        logger.info("Step 4: Posting clips to platforms...")

        # Create dummy credentials for the example
        # In a real scenario, these would be loaded from environment variables
        credentials = {
            "tiktok": {
                "username": os.getenv("TIKTOK_USERNAME", "example_user"),
                "password": os.getenv("TIKTOK_PASSWORD", "example_pass"),
                "api_key": os.getenv("TIKTOK_API_KEY", "example_key")
            },
            "instagram": {
                "username": os.getenv("INSTAGRAM_USERNAME", "example_user"),
                "password": os.getenv("INSTAGRAM_PASSWORD", "example_pass"),
                "api_key": os.getenv("INSTAGRAM_API_KEY", "example_key")
            },
            "youtube": {
                "client_id": os.getenv("YOUTUBE_CLIENT_ID", "example_id"),
                "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET", "example_secret"),
                "refresh_token": os.getenv("YOUTUBE_REFRESH_TOKEN", "example_token")
            }
        }

        # Create platform-specific data
        for text_result in text_results:
            clip = text_result["clip"]

            # Create platform-specific data
            platforms_data = {}
            for platform in ["tiktok", "instagram", "youtube"]:
                if platform.lower() in text_result["platforms"]:
                    platforms_data[platform.lower()] = text_result["platforms"][platform.lower()]

            # Post to all platforms
            post_result = post_to_all_platforms(
                video_path=clip["path"],
                platforms_data=platforms_data,
                credentials=credentials
            )

            logger.info(f"Post result: {post_result}")
    else:
        logger.info("Step 4: Skipping posting to platforms")

    logger.info("Example pipeline completed successfully!")
    logger.info(f"Output directory: {output_dir}")


if __name__ == "__main__":
    run_example()