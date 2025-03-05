"""
Example script for using the text generator.

This script demonstrates how to use the text generator to generate captions,
hashtags, and platform-specific text variations for a video clip.
"""

import os
import json
from dotenv import load_dotenv
from factory import TextGeneratorFactory

# Load environment variables
load_dotenv()


def main():
    """Run the example script."""
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        # # # # print("Warning: OPENAI_API_KEY environment variable not set.")
        # # # # print("Please set it in your .env file or export it in your shell.")
        # # # # print("For testing purposes, you can continue with fallback responses.")

    # Create a text generator using the factory
    text_generator = TextGeneratorFactory.create()

    # Example video metadata
    clip_metadata = {
        "duration": 30,
        "description": "A person showing a quick cooking tutorial for a healthy breakfast",
        "target_audience": "Health-conscious young adults",
        "tone": "Informative and energetic"
    }

    # Generate captions
    # # # # print("\n=== Generating Captions ===")
    captions = text_generator.generate_captions(
        video_path="example_video.mp4",  # This is just a placeholder
        clip_metadata=clip_metadata,
        num_variations=3
    )
    # # # # print(json.dumps(captions, indent=2))

    # Generate hashtags
    # # # # print("\n=== Generating Hashtags ===")
    hashtags = text_generator.generate_hashtags(
        video_path="example_video.mp4",  # This is just a placeholder
        clip_metadata=clip_metadata,
        num_hashtags=10
    )
    # # # # print(json.dumps(hashtags, indent=2))

    # Generate platform-specific variations
    # # # # print("\n=== Generating Platform Variations ===")
    platforms = ["TikTok", "Instagram", "YouTube"]
    variations = text_generator.generate_platform_variations(
        video_path="example_video.mp4",  # This is just a placeholder
        clip_metadata=clip_metadata,
        platforms=platforms
    )
    # # # # print(json.dumps(variations, indent=2))


if __name__ == "__main__":
    main()