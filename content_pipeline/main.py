"""
Main script for the Content Repurposing Pipeline.

This script ties together all the components of the pipeline:
1. Video Upload
2. Video Splitting
3. Text Generation
4. Cross-Posting
"""

import os
import json
import logging
import argparse
from typing import Dict, List, Any, Optional
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

# Import components
from upload import upload_video, upload_from_url
from splitter import split_video
from text_generator import process_clip
from poster import post_to_platform, post_to_all_platforms

# Import platform-specific modules to register them
from poster import tiktok, instagram, youtube

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def process_video(
    video_path: str,
    output_dir: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    max_clip_duration: float = 60,
    min_clip_duration: float = 5,
    split_on_silence: bool = False,
    silence_threshold: float = 0.03,
    silence_duration: float = 0.5,
    num_caption_variations: int = 3,
    num_hashtags: int = 10,
    post_to_platforms: bool = False,
    credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    options: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Process a video through the entire pipeline.

    Args:
        video_path: Path to the video file
        output_dir: Directory to save the clips and results (optional)
        platforms: List of platforms to generate variations for (default: ["TikTok", "Instagram", "YouTube"])
        max_clip_duration: Maximum duration of each clip in seconds
        min_clip_duration: Minimum duration of each clip in seconds
        split_on_silence: Whether to split on silent sections
        silence_threshold: Threshold for silence detection (0.0 to 1.0)
        silence_duration: Minimum duration of silence to consider (in seconds)
        num_caption_variations: Number of caption variations to generate
        num_hashtags: Number of hashtags to generate
        post_to_platforms: Whether to post the clips to the platforms
        credentials: Dictionary mapping platform names to credential dictionaries (optional)
        options: Dictionary mapping platform names to option dictionaries (optional)

    Returns:
        Dictionary containing the results of each step
    """
    # Set default platforms if not provided
    if platforms is None:
        platforms = ["tiktok", "instagram", "youtube"]

    # Create output directory if not provided
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(video_path), "processed")

    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Using output directory: {output_dir}")

    # Step 1: Upload the video
    logger.info("Step 1: Uploading video...")
    upload_result = upload_video(video_path, output_dir)

    if not upload_result["success"]:
        logger.error(f"Video upload failed: {upload_result['error']}")
        return {
            "success": False,
            "error": f"Video upload failed: {upload_result['error']}",
            "upload_result": upload_result,
            "split_result": None,
            "text_results": [],
            "post_results": []
        }

    processed_video_path = upload_result["file_path"]
    logger.info(f"Video uploaded to: {processed_video_path}")

    # Step 2: Split the video
    logger.info("Step 2: Splitting video...")
    split_result = split_video(
        video_path=processed_video_path,
        output_dir=os.path.join(output_dir, "clips"),
        max_clip_duration=max_clip_duration,
        min_clip_duration=min_clip_duration,
        split_on_silence=split_on_silence,
        silence_threshold=silence_threshold,
        silence_duration=silence_duration
    )

    if not split_result["success"]:
        logger.error(f"Video splitting failed: {split_result['error']}")
        return {
            "success": False,
            "error": f"Video splitting failed: {split_result['error']}",
            "upload_result": upload_result,
            "split_result": split_result,
            "text_results": [],
            "post_results": []
        }

    clips = split_result["clips"]
    logger.info(f"Created {len(clips)} clips")

    # Step 3: Generate text for each clip
    logger.info("Step 3: Generating text for clips...")
    text_results = []

    for clip in tqdm(clips, desc="Generating text"):
        # Create clip metadata
        clip_metadata = {
            "duration": clip["duration"],
            "description": f"Clip {clip['index']} from video",
            "target_audience": "General audience",
            "tone": "Casual and engaging"
        }

        # Generate text
        text_result = process_clip(
            clip_path=clip["path"],
            clip_metadata=clip_metadata,
            platforms=platforms,
            num_caption_variations=num_caption_variations,
            num_hashtags=num_hashtags
        )

        # Add clip info to the result
        text_result["clip"] = clip
        text_results.append(text_result)

    logger.info(f"Generated text for {len(text_results)} clips")

    # Step 4: Post clips to platforms (if enabled)
    post_results = []

    if post_to_platforms:
        logger.info("Step 4: Posting clips to platforms...")

        for i, (clip, text_result) in enumerate(zip(clips, text_results)):
            logger.info(f"Posting clip {i+1}/{len(clips)}...")

            # Create platform-specific data
            platforms_data = {}
            for platform in platforms:
                if platform.lower() in text_result["platforms"]:
                    platforms_data[platform.lower()] = text_result["platforms"][platform.lower()]

            # Post to all platforms
            post_result = post_to_all_platforms(
                video_path=clip["path"],
                platforms_data=platforms_data,
                credentials=credentials,
                options=options
            )

            # Add clip info to the result
            post_result["clip"] = clip
            post_results.append(post_result)

        logger.info(f"Posted {len(post_results)} clips to platforms")
    else:
        logger.info("Step 4: Skipping posting to platforms")

    # Save results to JSON file
    results = {
        "success": True,
        "error": None,
        "upload_result": upload_result,
        "split_result": split_result,
        "text_results": text_results,
        "post_results": post_results
    }

    results_file = os.path.join(output_dir, "results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to: {results_file}")

    return results


def main():
    """Run the main script."""
    parser = argparse.ArgumentParser(description="Content Repurposing Pipeline")

    # Input options
    parser.add_argument("--video", "-v", type=str, help="Path to the video file")
    parser.add_argument("--url", "-u", type=str, help="URL to download the video from")
    parser.add_argument("--output", "-o", type=str, help="Output directory")

    # Splitting options
    parser.add_argument("--max-duration", type=float, default=60, help="Maximum clip duration in seconds")
    parser.add_argument("--min-duration", type=float, default=5, help="Minimum clip duration in seconds")
    parser.add_argument("--split-on-silence", action="store_true", help="Split on silent sections")
    parser.add_argument("--silence-threshold", type=float, default=0.03, help="Threshold for silence detection")
    parser.add_argument("--silence-duration", type=float, default=0.5, help="Minimum silence duration in seconds")

    # Text generation options
    parser.add_argument("--caption-variations", type=int, default=3, help="Number of caption variations to generate")
    parser.add_argument("--hashtags", type=int, default=10, help="Number of hashtags to generate")

    # Platform options
    parser.add_argument("--platforms", type=str, default="tiktok,instagram,youtube", help="Comma-separated list of platforms")
    parser.add_argument("--post", action="store_true", help="Post clips to platforms")

    args = parser.parse_args()

    # Check if video path or URL is provided
    if not args.video and not args.url:
        parser.error("Either --video or --url must be provided")

    # Get video path
    if args.video:
        video_path = args.video
    else:
        # Download from URL
        logger.info(f"Downloading video from URL: {args.url}")
        download_result = upload_from_url(args.url)

        if not download_result["success"]:
            logger.error(f"Video download failed: {download_result['error']}")
            return

        video_path = download_result["file_path"]
        logger.info(f"Video downloaded to: {video_path}")

    # Parse platforms
    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]

    # Process the video
    process_video(
        video_path=video_path,
        output_dir=args.output,
        platforms=platforms,
        max_clip_duration=args.max_duration,
        min_clip_duration=args.min_duration,
        split_on_silence=args.split_on_silence,
        silence_threshold=args.silence_threshold,
        silence_duration=args.silence_duration,
        num_caption_variations=args.caption_variations,
        num_hashtags=args.hashtags,
        post_to_platforms=args.post
    )


if __name__ == "__main__":
    main()