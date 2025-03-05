"""
Test script for the text generator module.

This script tests the text generator module by generating captions, hashtags,
and platform-specific text variations for a sample video clip.
"""

import os
import json
import logging
from dotenv import load_dotenv

from text_generator import process_clip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def main():
    """Run the test script."""
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY environment variable not set.")
        logger.warning("Please set it in your .env file or export it in your shell.")
        logger.warning("For testing purposes, you can continue with fallback responses.")

    # Sample video clip metadata
    clip_metadata = {
        "duration": 45,
        "description": "A tutorial on how to make a delicious homemade pizza from scratch",
        "target_audience": "Home cooks and food enthusiasts",
        "tone": "Instructional and friendly"
    }

    # Process the clip
    logger.info("Processing sample clip...")
    result = process_clip(
        clip_path="sample_clip.mp4",  # This is just a placeholder
        clip_metadata=clip_metadata,
        platforms=["TikTok", "Instagram", "YouTube", "Facebook"],
        num_caption_variations=4,
        num_hashtags=12
    )

    # Print the results
    logger.info("Processing complete!")
    # # # # # print("\n=== Generated Captions ===")
    # # # # # print(json.dumps(result["captions"], indent=2))

    # # # # # print("\n=== Generated Hashtags ===")
    # # # # # print(json.dumps(result["hashtags"], indent=2))

    # # # # # print("\n=== Platform-Specific Variations ===")
    # # # # # print(json.dumps(result["platforms"], indent=2))


if __name__ == "__main__":
    main()