from .video_processing import *
from .social_media import *
from .maintenance import *
from .twitter import *  # We'll create this module next

# Version
__version__ = '1.0.0'

# All available tasks
__all__ = [
    # Video Processing Tasks
    'remove_watermark',
    'enhance_video',
    'compress_video',
    'cleanup_processed_files',
    
    # Social Media Tasks
    'download_tiktok',
    'download_instagram',
    'download_youtube',
    'download_twitter',  # New Twitter task
    'batch_download',
    'cleanup_failed_downloads',
    
    # Maintenance Tasks
    'cleanup_old_files',
    'update_usage_statistics',
    'check_api_limits',
    'backup_database',
    'monitor_system_health'
]
