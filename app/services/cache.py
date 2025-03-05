import redis
import json
from datetime import timedelta
import logging
import os
from pathlib import Path
import time
from flask import current_app

from ..utils.path import get_download_path, get_relative_path, is_safe_path, APP_ROOT, DOWNLOAD_DIR

logger = logging.getLogger(__name__)

def get_redis_client(max_retries=3, retry_delay=1):
    """Initialize Redis client with retry logic."""
    for attempt in range(max_retries):
        try:
            client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            client.ping()
            return client
        except redis.ConnectionError as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect to Redis after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying...")
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Unexpected Redis error: {str(e)}")
            raise

# Initialize Redis client with retry logic
try:
    redis_client = get_redis_client()
    logger.info("Successfully connected to Redis")
except Exception as e:
    logger.error(f"Failed to initialize Redis: {str(e)}")
    redis_client = None

class MediaCache:
    def __init__(self, platform):
        self.platform = platform
        self.cache_duration = timedelta(days=7)

    def get_cache_key(self, url, user_id):
        """Generate a unique cache key."""
        return f"{self.platform}:{user_id}:{url}"

    def get_cached_media(self, url, user_id):
        """Get cached media info if it exists and file is valid."""
        try:
            cache_key = self.get_cache_key(url, user_id)
            cached_data = redis_client.get(cache_key)

            if not cached_data:
                logger.debug(f"No cached data found for key: {cache_key}")
                return None

            media_info = json.loads(cached_data)
            if not isinstance(media_info, dict):
                logger.warning(f"Cached data is not a dictionary: {type(media_info)}")
                return None

            # Check for file_path or local_path
            file_path_key = None
            if 'file_path' in media_info:
                file_path_key = 'file_path'
            elif 'local_path' in media_info:
                file_path_key = 'local_path'
                # For consistency, add file_path if it doesn't exist
                media_info['file_path'] = media_info['local_path']

            if not file_path_key:
                logger.warning("Cached media info missing both file_path and local_path")
                return None

            # Check if file exists
            file_path = Path(media_info[file_path_key])
            if not file_path.is_absolute():
                file_path = DOWNLOAD_DIR / file_path

            if not file_path.exists():
                logger.warning(f"Cached file not found: {file_path}")
                redis_client.delete(cache_key)
                return None

            if file_path.stat().st_size == 0:
                logger.warning(f"Cached file is empty: {file_path}")
                redis_client.delete(cache_key)
                return None

            logger.info(f"Successfully retrieved cached media for URL: {url}")
            return media_info

        except Exception as e:
            logger.error(f"Error getting cached media: {str(e)}")
            return None

    def cache_media(self, url, user_id, media_info):
        """Cache media information if file exists."""
        try:
            if not isinstance(media_info, dict):
                logger.error("Invalid media info format - not a dictionary")
                return False

            # Check for file_path or local_path
            file_path_key = None
            if 'file_path' in media_info:
                file_path_key = 'file_path'
                logger.debug(f"Using file_path: {media_info['file_path']}")
            elif 'local_path' in media_info:
                file_path_key = 'local_path'
                # For consistency, add file_path if only local_path exists
                media_info['file_path'] = media_info['local_path']
                logger.debug(f"Using local_path and setting file_path: {media_info['local_path']}")

            if not file_path_key:
                logger.error("Invalid media info format - missing file_path or local_path")
                return False

            # Get the file path and verify it exists
            file_path = Path(media_info[file_path_key])

            # Check if we have an absolute_path provided (added for Twitter)
            if 'absolute_path' in media_info and media_info['absolute_path']:
                logger.debug(f"Using provided absolute_path: {media_info['absolute_path']}")
                absolute_path = Path(media_info['absolute_path'])

                # Verify this path exists
                if absolute_path.exists():
                    logger.debug(f"Verified absolute_path exists: {absolute_path}")
                else:
                    logger.warning(f"Provided absolute_path does not exist: {absolute_path}")
                    # Fall back to standard path resolution
                    absolute_path = None
            else:
                absolute_path = None

            # If we don't have a valid absolute_path, resolve it using standard logic
            if absolute_path is None:
                if not file_path.is_absolute():
                    # Try with DOWNLOAD_DIR first
                    absolute_path = DOWNLOAD_DIR / file_path
                    logger.debug(f"Converted relative path to absolute using DOWNLOAD_DIR: {absolute_path}")

                    # If that doesn't exist, try with download_dir from media_info if available
                    if not absolute_path.exists() and 'download_dir' in media_info:
                        download_dir = Path(media_info['download_dir'])
                        absolute_path = download_dir / file_path
                        logger.debug(f"Trying with provided download_dir: {absolute_path}")
                else:
                    absolute_path = file_path
                    logger.debug(f"Using absolute path: {absolute_path}")

            # Verify the file exists
            if not absolute_path.exists():
                logger.error(f"File verification failed - file does not exist: {absolute_path}")
                # Try alternate path without DOWNLOAD_DIR
                alt_path = Path(APP_ROOT) / 'downloads' / file_path
                logger.debug(f"Trying alternate path: {alt_path}")
                if alt_path.exists():
                    logger.info(f"File found at alternate path: {alt_path}")
                    absolute_path = alt_path
                else:
                    # For Twitter, try one more path pattern
                    if self.platform == 'twitter':
                        # Try with just the filename in the twitter directory
                        twitter_path = DOWNLOAD_DIR / 'twitter' / file_path.name
                        logger.debug(f"Trying Twitter-specific path: {twitter_path}")
                        if twitter_path.exists():
                            logger.info(f"File found at Twitter-specific path: {twitter_path}")
                            absolute_path = twitter_path
                        else:
                            return False
                    else:
                        return False

            if absolute_path.stat().st_size == 0:
                logger.error(f"File verification failed - file is empty: {absolute_path}")
                return False

            logger.debug(f"File verified: {absolute_path}, size: {absolute_path.stat().st_size} bytes")

            # Cache the media info
            cache_key = self.get_cache_key(url, user_id)
            logger.debug(f"Setting cache key: {cache_key}")

            # Ensure the media_info is JSON serializable
            media_info_copy = dict(media_info)

            # Add the verified absolute path to help with future retrievals
            media_info_copy['verified_path'] = str(absolute_path)

            try:
                json_data = json.dumps(media_info_copy)
                logger.debug(f"JSON serialization successful, data length: {len(json_data)}")
            except Exception as json_err:
                logger.error(f"JSON serialization error: {str(json_err)}")
                return False

            try:
                redis_client.setex(
                    cache_key,
                    int(self.cache_duration.total_seconds()),
                    json_data
                )
                logger.debug(f"Cache set successful for key: {cache_key}")
            except Exception as redis_err:
                logger.error(f"Redis error setting cache: {str(redis_err)}")
                return False

            logger.info(f"Successfully cached media for URL: {url}")
            return True

        except Exception as e:
            logger.error(f"Error caching media: {str(e)}")
            return False

    def is_media_cached(self, url, user_id):
        """Check if valid media exists in cache."""
        return self.get_cached_media(url, user_id) is not None

    def remove_cache(self, url, user_id):
        """Remove cached media entry."""
        try:
            cache_key = self.get_cache_key(url, user_id)
            redis_client.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Error removing cache: {str(e)}")
            return False

    def verify_file_exists(self, file_path):
        """Verify if file exists and is within allowed directory."""
        try:
            if not file_path:
                return False

            # Convert to Path object if it's a string
            path = Path(file_path)

            # If path is relative, make it absolute using APP_ROOT
            if not path.is_absolute():
                path = APP_ROOT / path

            # Verify path is within APP_ROOT
            if not is_safe_path(path):
                logger.error(f"File path {path} is outside allowed directory")
                return False

            # Check file existence and size
            if not path.exists():
                logger.error(f"File not found: {path}")
                return False

            if path.stat().st_size == 0:
                logger.error(f"File is empty: {path}")
                return False

            # Verify file is readable
            with open(path, 'rb') as f:
                f.read(1)

            return True

        except Exception as e:
            logger.error(f"Error verifying file: {str(e)}")
            return False

    def cleanup_expired_cache(self):
        """Clean up expired cache entries and missing files."""
        try:
            pattern = f"{self.platform}:*"
            for key in redis_client.scan_iter(pattern):
                try:
                    cached_data = redis_client.get(key)
                    if cached_data:
                        media_info = json.loads(cached_data)
                        if isinstance(media_info, dict):
                            if not self.verify_file_exists(media_info.get('file_path')):
                                redis_client.delete(key)
                                logger.info(f"Removed cache for missing file: {media_info.get('file_path')}")
                        elif isinstance(media_info, list):
                            if not any(isinstance(item, dict) and
                                     self.verify_file_exists(item.get('file_path'))
                                     for item in media_info):
                                redis_client.delete(key)
                                logger.info(f"Removed cache for missing files in list: {key}")
                except Exception as e:
                    logger.error(f"Error cleaning up key {key}: {str(e)}")
                    redis_client.delete(key)
                    continue
        except Exception as e:
            logger.error(f"Cache cleanup error: {str(e)}")

    def get_file_cache_key(self, filename, user_id):
        """Generate a unique cache key for file path."""
        return f"{self.platform}:file:{user_id}:{filename}"

    def get_cached_file(self, filename, user_id):
        """Get cached media info by filename."""
        try:
            cache_key = self.get_file_cache_key(filename, user_id)
            cached_data = redis_client.get(cache_key)
            if cached_data:
                media_info = json.loads(cached_data)
                if os.path.exists(media_info['file_path']):
                    return media_info
                else:
                    redis_client.delete(cache_key)
            return None
        except Exception as e:
            logger.error(f"Redis get file error: {str(e)}")
            return None

    def cache_bulk_media(self, url, user_id, media_list):
        """Cache multiple media items."""
        try:
            if not isinstance(media_list, list):
                logger.error("Invalid media list format - not a list")
                return False

            # Verify all items have file_path and files exist
            valid_items = []
            for item in media_list:
                if not isinstance(item, dict):
                    logger.warning(f"Skipping invalid item: not a dictionary")
                    continue

                if 'file_path' not in item:
                    logger.warning(f"Skipping invalid item: no file_path")
                    continue

                # Get the file path and verify it exists
                file_path = Path(item['file_path'])
                if not file_path.is_absolute():
                    file_path = DOWNLOAD_DIR / file_path

                if not file_path.exists() or file_path.stat().st_size == 0:
                    logger.warning(f"Skipping invalid item: file not found or empty - {file_path}")
                    continue

                valid_items.append(item)

            if not valid_items:
                logger.error("No valid items to cache")
                return False

            # Cache URL to media list mapping
            url_cache_key = self.get_cache_key(url, user_id)
            redis_client.setex(
                url_cache_key,
                int(self.cache_duration.total_seconds()),
                json.dumps(valid_items)
            )

            # Cache individual files
            for item in valid_items:
                filename = Path(item['file_path']).name
                file_cache_key = self.get_file_cache_key(filename, user_id)
                redis_client.setex(
                    file_cache_key,
                    int(self.cache_duration.total_seconds()),
                    json.dumps(item)
                )

            logger.info(f"Successfully cached {len(valid_items)} items for URL: {url}")
            return True
        except Exception as e:
            logger.error(f"Redis bulk set error: {str(e)}")
            return False