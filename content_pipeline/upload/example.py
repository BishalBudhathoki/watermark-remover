"""
Example script for using the upload module.

This script demonstrates how to use the upload module to upload videos
from local files or URLs.
"""

import os
import json
import logging
from dotenv import load_dotenv
from upload import upload_video, upload_from_url

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
    # Example local file upload
    local_file_path = input("Enter the path to a local video file (or press Enter to skip): ")
    if local_file_path and os.path.exists(local_file_path):
        logger.info("Uploading local file...")
        result = upload_video(local_file_path)

        if result["success"]:
            logger.info("Local file upload successful!")
            # # # print("\n=== Local File Upload Result ===")
            print(json.dumps({
                "file_path": result["file_path"],
                "metadata": result["metadata"]
            }, indent=2))
        else:
            logger.error(f"Local file upload failed: {result['error']}")
    elif local_file_path:
        logger.error(f"Local file not found: {local_file_path}")

    # Example URL upload
    video_url = input("\nEnter a URL to a video file (or press Enter to skip): ")
    if video_url:
        logger.info("Downloading from URL...")
        result = upload_from_url(video_url)

        if result["success"]:
            logger.info("URL download successful!")
            # # # print("\n=== URL Download Result ===")
            print(json.dumps({
                "file_path": result["file_path"],
                "metadata": result["metadata"]
            }, indent=2))
        else:
            logger.error(f"URL download failed: {result['error']}")


if __name__ == "__main__":
    main()