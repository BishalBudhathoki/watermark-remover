from flask import Blueprint, jsonify
from redis import Redis
from celery.task.control import inspect
from app import celery

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health_check():
    health_status = {
        'status': 'healthy',
        'components': {
            'flask': True,
            'redis': check_redis(),
            'celery': check_celery()
        }
    }
    
    if not all(health_status['components'].values()):
        health_status['status'] = 'unhealthy'
        return jsonify(health_status), 503
    
    return jsonify(health_status)

def check_redis():
    try:
        redis_client = Redis.from_url(celery.conf.broker_url)
        redis_client.ping()
        return True
    except Exception:
        return False

def check_celery():
    try:
        insp = inspect()
        if not insp.active():
            return False
        return True
    except Exception:
        return False 