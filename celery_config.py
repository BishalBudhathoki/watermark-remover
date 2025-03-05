from celery import Celery
from celery.schedules import crontab
import os

def create_celery_app(app=None):
    """Create and configure Celery app with Flask integration."""
    celery = Celery(
        'videovault',
        broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        include=['tasks.video_processing', 'tasks.social_media', 'tasks.maintenance']
    )

    # Celery configuration
    celery.conf.update(
        # Task settings
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,

        # Task execution settings
        task_time_limit=3600,  # 1 hour
        task_soft_time_limit=3300,  # 55 minutes
        worker_max_tasks_per_child=200,
        worker_prefetch_multiplier=1,

        # Result backend settings
        result_expires=86400,  # 24 hours

        # Rate limiting
        task_annotations={
            'tasks.video_processing.*': {'rate_limit': '10/m'},
            'tasks.social_media.*': {'rate_limit': '30/m'},
        },

        # Routing
        task_routes={
            'tasks.video_processing.*': {'queue': 'video_processing'},
            'tasks.social_media.*': {'queue': 'social_media'},
            'tasks.maintenance.*': {'queue': 'maintenance'},
        },

        # Scheduled tasks
        beat_schedule={
            'cleanup-old-files': {
                'task': 'tasks.maintenance.cleanup_old_files',
                'schedule': crontab(hour=3, minute=0),  # Run at 3 AM daily
            },
            'update-usage-statistics': {
                'task': 'tasks.maintenance.update_usage_statistics',
                'schedule': crontab(minute='*/15'),  # Run every 15 minutes
            },
            'check-api-limits': {
                'task': 'tasks.maintenance.check_api_limits',
                'schedule': crontab(minute='*/5'),  # Run every 5 minutes
            },
        },

        # Error handling
        task_acks_late=True,
        task_reject_on_worker_lost=True,

        # Logging
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s',
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            if app:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# Create default celery app
app = create_celery_app()

# Task retry settings
default_retry_policy = {
    'max_retries': 3,
    'interval_start': 0,
    'interval_step': 0.2,
    'interval_max': 0.2,
}