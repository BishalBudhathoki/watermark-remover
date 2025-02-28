from celery import shared_task
from celery.utils.log import get_task_logger
import os
from pathlib import Path
import time
import json
import psutil
import shutil
from typing import Dict, List, Optional
import redis
from datetime import datetime, timedelta

logger = get_task_logger(__name__)

# Initialize Redis client
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

@shared_task(name='tasks.maintenance.cleanup_old_files')
def cleanup_old_files(max_age_hours: int = 24) -> Dict:
    """
    Clean up old files from various directories and invalid cache entries.
    
    Args:
        max_age_hours: Maximum age of files in hours before deletion
    
    Returns:
        Dict containing cleanup statistics
    """
    try:
        logger.info("Starting old files cleanup")
        stats = {
            'deleted_files': 0,
            'failed_deletes': 0,
            'saved_space': 0,
            'cleaned_cache_entries': 0
        }
        
        directories = ['uploads', 'processed', 'downloads']
        current_time = time.time()
        
        for directory in directories:
            if not os.path.exists(directory):
                continue
                
            for file_path in Path(directory).rglob('*'):
                if not file_path.is_file():
                    continue
                    
                try:
                    file_age_hours = (current_time - os.path.getmtime(file_path)) / 3600
                    
                    if file_age_hours > max_age_hours:
                        # Check if file is referenced in cache
                        rel_path = os.path.relpath(file_path, os.path.dirname(os.path.dirname(__file__)))
                        cache_pattern = f"*:{rel_path}"
                        
                        # Search for cache entries referencing this file
                        for key in redis_client.scan_iter(match=cache_pattern):
                            try:
                                redis_client.delete(key)
                                stats['cleaned_cache_entries'] += 1
                            except Exception as e:
                                logger.error(f"Error cleaning cache for key {key}: {str(e)}")
                        
                        # Delete the file
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        stats['deleted_files'] += 1
                        stats['saved_space'] += file_size
                        logger.info(f"Deleted old file: {file_path}")
                        
                except Exception as e:
                    stats['failed_deletes'] += 1
                    logger.error(f"Error processing file {file_path}: {str(e)}")
        
        # Clean up empty directories
        for directory in directories:
            if os.path.exists(directory):
                for dir_path, _, _ in os.walk(directory, topdown=False):
                    try:
                        if dir_path != directory and not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            logger.info(f"Removed empty directory: {dir_path}")
                    except Exception as e:
                        logger.error(f"Error removing directory {dir_path}: {str(e)}")
        
        # Clean up orphaned cache entries
        platforms = ['tiktok', 'instagram', 'youtube']
        for platform in platforms:
            pattern = f"{platform}:*"
            for key in redis_client.scan_iter(match=pattern):
                try:
                    cached_data = redis_client.get(key)
                    if cached_data:
                        data = json.loads(cached_data)
                        if isinstance(data, dict) and 'file_path' in data:
                            full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), data['file_path'])
                            if not os.path.exists(full_path):
                                redis_client.delete(key)
                                stats['cleaned_cache_entries'] += 1
                                logger.info(f"Removed orphaned cache entry: {key}")
                except Exception as e:
                    logger.error(f"Error cleaning cache entry {key}: {str(e)}")
        
        # Convert saved space to MB
        stats['saved_space'] = round(stats['saved_space'] / (1024 * 1024), 2)
        
        logger.info(f"Cleanup completed: {json.dumps(stats)}")
        return stats
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise

@shared_task(name='tasks.maintenance.update_usage_statistics')
def update_usage_statistics() -> Dict:
    """
    Update system usage statistics in Redis.
    
    Returns:
        Dict containing current usage statistics
    """
    try:
        logger.info("Updating usage statistics")
        
        # System statistics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        stats = {
            'timestamp': datetime.now().isoformat(),
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': round(memory.used / (1024 * 1024), 2),
                'disk_percent': disk.percent,
                'disk_free_gb': round(disk.free / (1024 * 1024 * 1024), 2),
            }
        }
        
        # Directory sizes
        for directory in ['uploads', 'processed', 'downloads']:
            if os.path.exists(directory):
                total_size = sum(
                    os.path.getsize(f) for f in Path(directory).glob('**/*') if f.is_file()
                )
                stats[f'{directory}_size_mb'] = round(total_size / (1024 * 1024), 2)
        
        # Store in Redis with expiration
        redis_client.setex(
            'system_stats',
            timedelta(hours=24),
            json.dumps(stats)
        )
        
        logger.info("Usage statistics updated")
        return stats
        
    except Exception as e:
        logger.error(f"Error updating usage statistics: {str(e)}")
        raise

@shared_task(name='tasks.maintenance.check_api_limits')
def check_api_limits() -> Dict:
    """
    Check and update API usage limits.
    
    Returns:
        Dict containing API usage statistics
    """
    try:
        logger.info("Checking API limits")
        
        # Load current usage from Redis
        usage_key = f"api_usage:{datetime.now().strftime('%Y-%m-%d')}"
        current_usage = redis_client.get(usage_key)
        
        if current_usage:
            usage = json.loads(current_usage)
        else:
            usage = {
                'total_requests': 0,
                'downloads': {
                    'tiktok': 0,
                    'instagram': 0,
                    'youtube': 0
                },
                'processing': {
                    'watermark_removal': 0,
                    'enhancement': 0,
                    'compression': 0
                }
            }
        
        # Check against limits
        limits = {
            'daily_requests': 10000,
            'downloads': {
                'tiktok': 1000,
                'instagram': 1000,
                'youtube': 1000
            },
            'processing': {
                'watermark_removal': 500,
                'enhancement': 500,
                'compression': 500
            }
        }
        
        # Calculate usage percentages
        usage_stats = {
            'total_requests_percent': (usage['total_requests'] / limits['daily_requests']) * 100,
            'downloads': {
                platform: (count / limits['downloads'][platform]) * 100
                for platform, count in usage['downloads'].items()
            },
            'processing': {
                op: (count / limits['processing'][op]) * 100
                for op, count in usage['processing'].items()
            }
        }
        
        # Store updated stats in Redis
        redis_client.setex(
            usage_key,
            timedelta(days=7),  # Keep for a week for historical analysis
            json.dumps(usage)
        )
        
        # Log warnings for high usage
        for category, percent in usage_stats['downloads'].items():
            if percent > 80:
                logger.warning(f"High usage warning: {category} downloads at {percent:.1f}%")
        
        for category, percent in usage_stats['processing'].items():
            if percent > 80:
                logger.warning(f"High usage warning: {category} processing at {percent:.1f}%")
        
        logger.info("API limits checked")
        return usage_stats
        
    except Exception as e:
        logger.error(f"Error checking API limits: {str(e)}")
        raise

@shared_task(name='tasks.maintenance.backup_database')
def backup_database() -> Dict:
    """
    Create a backup of the database.
    
    Returns:
        Dict containing backup status and information
    """
    try:
        logger.info("Starting database backup")
        
        backup_dir = 'backups'
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f'db_backup_{timestamp}.json')
        
        # Example: Backup data from Redis
        # In a real application, you would backup your actual database
        all_keys = redis_client.keys('*')
        backup_data = {}
        
        for key in all_keys:
            key_type = redis_client.type(key)
            if key_type == b'string':
                backup_data[key] = redis_client.get(key)
            elif key_type == b'hash':
                backup_data[key] = redis_client.hgetall(key)
            elif key_type == b'list':
                backup_data[key] = redis_client.lrange(key, 0, -1)
            elif key_type == b'set':
                backup_data[key] = list(redis_client.smembers(key))
            elif key_type == b'zset':
                backup_data[key] = redis_client.zrange(key, 0, -1, withscores=True)
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)
        
        # Cleanup old backups (keep last 7 days)
        cleanup_old_backups(backup_dir, max_age_days=7)
        
        backup_size = os.path.getsize(backup_file)
        
        logger.info(f"Database backup completed: {backup_file}")
        return {
            'status': 'success',
            'backup_file': backup_file,
            'timestamp': timestamp,
            'size_mb': round(backup_size / (1024 * 1024), 2)
        }
        
    except Exception as e:
        logger.error(f"Error creating database backup: {str(e)}")
        raise

def cleanup_old_backups(backup_dir: str, max_age_days: int) -> None:
    """Helper function to clean up old database backups."""
    current_time = time.time()
    
    for backup_file in Path(backup_dir).glob('db_backup_*.json'):
        file_age_days = (current_time - os.path.getmtime(backup_file)) / (24 * 3600)
        
        if file_age_days > max_age_days:
            try:
                os.remove(backup_file)
                logger.info(f"Deleted old backup: {backup_file}")
            except Exception as e:
                logger.error(f"Error deleting backup {backup_file}: {str(e)}")

@shared_task(name='tasks.maintenance.monitor_system_health')
def monitor_system_health() -> Dict:
    """
    Monitor system health and resources.
    
    Returns:
        Dict containing system health metrics
    """
    try:
        logger.info("Monitoring system health")
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Process metrics
        process = psutil.Process()
        process_memory = process.memory_info()
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'system': {
                'cpu_percent': cpu_percent,
                'memory_used_percent': memory.percent,
                'memory_available_mb': round(memory.available / (1024 * 1024), 2),
                'disk_used_percent': disk.percent,
                'disk_free_gb': round(disk.free / (1024 * 1024 * 1024), 2),
            },
            'process': {
                'cpu_percent': process.cpu_percent(),
                'memory_rss_mb': round(process_memory.rss / (1024 * 1024), 2),
                'memory_vms_mb': round(process_memory.vms / (1024 * 1024), 2),
                'threads': process.num_threads(),
                'open_files': len(process.open_files()),
            }
        }
        
        # Check thresholds and log warnings
        if cpu_percent > 80:
            logger.warning(f"High CPU usage: {cpu_percent}%")
        
        if memory.percent > 80:
            logger.warning(f"High memory usage: {memory.percent}%")
        
        if disk.percent > 80:
            logger.warning(f"High disk usage: {disk.percent}%")
        
        # Store metrics in Redis for historical analysis
        redis_client.lpush('system_metrics', json.dumps(metrics))
        redis_client.ltrim('system_metrics', 0, 1439)  # Keep last 24 hours (1 metric per minute)
        
        logger.info("System health monitored")
        return metrics
        
    except Exception as e:
        logger.error(f"Error monitoring system health: {str(e)}")
        raise 