"""
Example script for using the splitter module.

This script demonstrates how to use the splitter module to split videos
based on duration thresholds or silent sections.
"""

import os
import json
import logging
from dotenv import load_dotenv
from splitter import split_video, get_video_info

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

    # Get video info
    try:
        video_info = get_video_info(video_path)
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return

    # Ask for splitting parameters
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
    option = input("Choose an option (1/2): ")

    max_duration = float(input("Enter maximum clip duration in seconds (default: 60): ") or 60)
    min_duration = float(input("Enter minimum clip duration in seconds (default: 5): ") or 5)

    split_on_silence = option == "2"

    if split_on_silence:
        silence_threshold = float(input("Enter silence threshold (0.0-1.0, default: 0.03): ") or 0.03)
        silence_duration = float(input("Enter minimum silence duration in seconds (default: 0.5): ") or 0.5)
    else:
        silence_threshold = 0.03
        silence_duration = 0.5

    # Create output directory
    output_dir = os.path.join(os.path.dirname(video_path), "clips")

    # Split the video
    logger.info("Splitting video...")
    result = split_video(
        video_path=video_path,
        output_dir=output_dir,
        max_clip_duration=max_duration,
        min_clip_duration=min_duration,
        split_on_silence=split_on_silence,
        silence_threshold=silence_threshold,
        silence_duration=silence_duration
    )

    if result["success"]:
        logger.info("Video splitting successful!")
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')

ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
        for i, clip in enumerate(result["clips"]):
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blue# # # # # # print('ai_video', __name__, url_prefix='/ai-video')
    else:
        logger.error(f"Video splitting failed: {result['error']}")


if __name__ == "__main__":
