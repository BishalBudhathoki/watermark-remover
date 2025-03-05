from typing import Dict, Any
import logging
from datetime import datetime
from pathlib import Path
import json
from ..utils.path import get_download_path, get_relative_path

logger = logging.getLogger(__name__)

def save_media_metadata(
    user_id: str,
    platform: str,
    media_type: str,
    file_path: str,
    title: str,
    original_url: str = None,
    duration: float = None,
    metadata: Dict[str, Any] = None
) -> bool:
    """
    Save media metadata to a JSON file in the user's directory.

    Args:
        user_id: The ID of the user who downloaded the media
        platform: The platform the media was downloaded from (e.g., 'tiktok')
        media_type: The type of media (e.g., 'video', 'image')
        file_path: The relative path to the media file
        title: The title of the media
        original_url: The original URL the media was downloaded from (optional)
        duration: The duration of the media in seconds (0 for images) (optional)
        metadata: Additional metadata about the media (optional)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create metadata directory if it doesn't exist
        metadata_dir = get_download_path(platform, 'metadata')
        metadata_dir.mkdir(parents=True, exist_ok=True)

        # Create metadata file path
        metadata_file = metadata_dir / f"{Path(file_path).stem}_metadata.json"

        # Prepare metadata
        metadata_obj = {
            'user_id': user_id,
            'platform': platform,
            'media_type': media_type,
            'file_path': file_path,
            'title': title,
            'original_url': original_url,
            'duration': duration,
            'download_date': datetime.now().isoformat(),
            'metadata': metadata
        }

        # Save metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata_obj, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved metadata for {file_path} to {metadata_file}")
        return True

    except Exception as e:
        logger.error(f"Failed to save metadata for {file_path}: {str(e)}")
        return False

def get_media_metadata(file_path: str) -> Dict[str, Any]:
    """
    Get metadata for a media file.

    Args:
        file_path: The relative path to the media file

    Returns:
        dict: The metadata for the media file, or None if not found
    """
    try:
        # Get metadata file path
        metadata_file = get_download_path(
            Path(file_path).parts[0],  # platform directory
            'metadata',
            f"{Path(file_path).stem}_metadata.json"
        )

        # Read metadata
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        return None

    except Exception as e:
        logger.error(f"Failed to get metadata for {file_path}: {str(e)}")
        return None

def delete_media_metadata(file_path: str) -> bool:
    """
    Delete metadata for a media file.

    Args:
        file_path: The relative path to the media file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get metadata file path
        metadata_file = get_download_path(
            Path(file_path).parts[0],  # platform directory
            'metadata',
            f"{Path(file_path).stem}_metadata.json"
        )

        # Delete metadata file if it exists
        if metadata_file.exists():
            metadata_file.unlink()
            logger.info(f"Deleted metadata file: {metadata_file}")
            return True

        return False

    except Exception as e:
        logger.error(f"Failed to delete metadata for {file_path}: {str(e)}")
        return False