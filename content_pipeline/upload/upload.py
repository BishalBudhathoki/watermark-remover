"""
Upload Module for Content Repurposing Pipeline.

This module provides functions to handle video file uploads and validation.
"""

import os
import shutil
import logging
import tempfile
import mimetypes
from typing import Dict, Any, Optional, Tuple, Union
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define constants
MAX_FILE_SIZE_MB = 500  # 500 MB
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'}
ALLOWED_VIDEO_MIMETYPES = {'video/mp4', 'video/quicktime', 'video/x-msvideo',
                          'video/x-matroska', 'video/webm', 'video/x-flv', 'video/x-ms-wmv'}


def validate_video(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a video file based on extension, mimetype, and size.

    Args:
        file_path: Path to the video file

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if file exists
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"

    # Check file extension
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension not in ALLOWED_VIDEO_EXTENSIONS:
        return False, f"Unsupported file extension: {file_extension}. Allowed extensions: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}"

    # Check mimetype
    mimetype, _ = mimetypes.guess_type(file_path)
    if mimetype not in ALLOWED_VIDEO_MIMETYPES:
        return False, f"Unsupported file type: {mimetype}. Allowed types: {', '.join(ALLOWED_VIDEO_MIMETYPES)}"

    # Check file size
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)  # Convert to MB
    if file_size_mb > MAX_FILE_SIZE_MB:
        return False, f"File too large: {file_size_mb:.2f} MB. Maximum allowed size: {MAX_FILE_SIZE_MB} MB"

    return True, None


def upload_video(source_path: str, destination_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Upload a video file from a local path to a destination directory.
    If no destination is provided, a temporary directory will be created.

    Args:
        source_path: Path to the source video file
        destination_dir: Path to the destination directory (optional)

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the upload was successful
            - file_path: Path to the uploaded file
            - error: Error message (if any)
            - metadata: Dictionary containing file metadata
    """
    logger.info(f"Uploading video: {source_path}")

    # Validate the video
    is_valid, error_message = validate_video(source_path)
    if not is_valid:
        logger.error(f"Video validation failed: {error_message}")
        return {
            "success": False,
            "file_path": None,
            "error": error_message,
            "metadata": {}
        }

    try:
        # Create destination directory if not provided
        if destination_dir is None:
            destination_dir = tempfile.mkdtemp(prefix="video_upload_")
            logger.info(f"Created temporary directory: {destination_dir}")
        else:
            os.makedirs(destination_dir, exist_ok=True)
            logger.info(f"Using destination directory: {destination_dir}")

        # Get the filename from the source path
        filename = os.path.basename(source_path)

        # Create the destination path
        destination_path = os.path.join(destination_dir, filename)

        # Copy the file to the destination
        shutil.copy2(source_path, destination_path)
        logger.info(f"Copied video to: {destination_path}")

        # Get file metadata
        file_size_mb = os.path.getsize(destination_path) / (1024 * 1024)
        file_extension = os.path.splitext(filename)[1].lower()

        # Return success
        return {
            "success": True,
            "file_path": destination_path,
            "error": None,
            "metadata": {
                "filename": filename,
                "file_size_mb": file_size_mb,
                "file_extension": file_extension,
                "destination_dir": destination_dir
            }
        }

    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        return {
            "success": False,
            "file_path": None,
            "error": str(e),
            "metadata": {}
        }


def upload_from_url(url: str, destination_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Upload a video file from a URL to a destination directory.
    If no destination is provided, a temporary directory will be created.

    Args:
        url: URL of the video file
        destination_dir: Path to the destination directory (optional)

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the upload was successful
            - file_path: Path to the downloaded file
            - error: Error message (if any)
            - metadata: Dictionary containing file metadata
    """
    logger.info(f"Downloading video from URL: {url}")

    try:
        import requests
        from urllib.parse import urlparse

        # Create destination directory if not provided
        if destination_dir is None:
            destination_dir = tempfile.mkdtemp(prefix="video_download_")
            logger.info(f"Created temporary directory: {destination_dir}")
        else:
            os.makedirs(destination_dir, exist_ok=True)
            logger.info(f"Using destination directory: {destination_dir}")

        # Get the filename from the URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)

        # If filename is empty or doesn't have an extension, use a default name
        if not filename or '.' not in filename:
            filename = "downloaded_video.mp4"

        # Create the destination path
        destination_path = os.path.join(destination_dir, filename)

        # Download the file
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('video/'):
            logger.warning(f"Content type is not video: {content_type}")

        # Save the file
        with open(destination_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded video to: {destination_path}")

        # Validate the downloaded file
        is_valid, error_message = validate_video(destination_path)
        if not is_valid:
            logger.error(f"Downloaded video validation failed: {error_message}")
            os.remove(destination_path)
            return {
                "success": False,
                "file_path": None,
                "error": error_message,
                "metadata": {}
            }

        # Get file metadata
        file_size_mb = os.path.getsize(destination_path) / (1024 * 1024)
        file_extension = os.path.splitext(filename)[1].lower()

        # Return success
        return {
            "success": True,
            "file_path": destination_path,
            "error": None,
            "metadata": {
                "filename": filename,
                "file_size_mb": file_size_mb,
                "file_extension": file_extension,
                "destination_dir": destination_dir,
                "source_url": url
            }
        }

    except Exception as e:
        logger.error(f"Error downloading video from URL: {str(e)}")
        return {
            "success": False,
            "file_path": None,
            "error": str(e),
            "metadata": {}
        }