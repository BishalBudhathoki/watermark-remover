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
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')

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
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')
    captions = text_generator.generate_captions(
        video_path="example_video.mp4",  # This is just a placeholder
        clip_metadata=clip_metadata,
        num_variations=3
    )
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')

    # Generate hashtags
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')
    hashtags = text_generator.generate_hashtags(
        video_path="example_video.mp4",  # This is just a placeholder
        clip_metadata=clip_metadata,
        num_hashtags=10
    )
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')

    # Generate platform-specific variations
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')
    platforms = ["TikTok", "Instagram", "YouTube"]
    variations = text_generator.generate_platform_variations(
        video_path="example_video.mp4",  # This is just a placeholder
        clip_metadata=clip_metadata,
        platforms=platforms
    )
ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')


if __name__ == "__main__":
