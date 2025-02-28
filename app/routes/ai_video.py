import logging
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, session, current_app, send_file
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import cv2
import numpy as np
import uuid
import time
from functools import wraps
import mediapipe as mp
import redis
import pickle

from ..utils.path import get_download_path, get_relative_path
from ..services.storage import save_media_metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class AIVideoCache:
    """Handle caching for AI video processing"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.prefix = 'ai_video:'
    
    def _get_face_detection_key(self, video_id):
        return f"{self.prefix}face_detection:{video_id}"
    
    def _get_status_key(self, video_id):
        return f"{self.prefix}status:{video_id}"
    
    def _get_highlight_key(self, video_id, face_id):
        return f"{self.prefix}highlight:{video_id}:{face_id}"
    
    def cache_face_detection(self, video_id, detection_data):
        """Cache face detection results"""
        try:
            key = self._get_face_detection_key(video_id)
            self.redis.setex(
                key,
                self.cache_ttl,
                json.dumps(detection_data)
            )
            logger.info(f"Cached face detection data for video {video_id}")
        except Exception as e:
            logger.warning(f"Failed to cache face detection data: {str(e)}")
    
    def get_face_detection(self, video_id):
        """Get cached face detection results"""
        try:
            key = self._get_face_detection_key(video_id)
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to get cached face detection data: {str(e)}")
        return None
    
    def cache_status(self, video_id, status_data):
        """Cache video processing status"""
        try:
            key = self._get_status_key(video_id)
            self.redis.setex(
                key,
                300,  # 5 minutes TTL for status
                json.dumps(status_data)
            )
            logger.info(f"Cached status for video {video_id}")
        except Exception as e:
            logger.warning(f"Failed to cache status: {str(e)}")
    
    def get_status(self, video_id):
        """Get cached video processing status"""
        try:
            key = self._get_status_key(video_id)
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except redis.RedisError as e:
            logger.warning(f"Redis error: {str(e)}")
            # Continue with database query
        return None
    
    def cache_highlight(self, video_id, face_id, highlight_data):
        """Cache highlight video data"""
        try:
            key = self._get_highlight_key(video_id, face_id)
            self.redis.setex(
                key,
                self.cache_ttl,
                json.dumps(highlight_data)
            )
            logger.info(f"Cached highlight data for video {video_id}, face {face_id}")
        except Exception as e:
            logger.warning(f"Failed to cache highlight data: {str(e)}")
    
    def get_highlight(self, video_id, face_id):
        """Get cached highlight video data"""
        try:
            key = self._get_highlight_key(video_id, face_id)
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to get cached highlight data: {str(e)}")
        return None
    
    def invalidate_video_cache(self, video_id):
        """Invalidate all cache entries for a video"""
        try:
            # Get all keys related to this video
            pattern = f"{self.prefix}*:{video_id}*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                logger.info(f"Invalidated cache for video {video_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate video cache: {str(e)}")

# Initialize cache handler
ai_video_cache = AIVideoCache(redis_client)

ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')

# Get application root directory
APP_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = APP_ROOT / 'media_vault.db'
PROCESSED_DIR = APP_ROOT / 'static' / 'processed'
FACE_DETECTION_MODEL_DIR = APP_ROOT / 'models'

# Ensure directories exist
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
FACE_DETECTION_MODEL_DIR.mkdir(parents=True, exist_ok=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user'):
            flash('Please login to access the AI video features.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

@ai_video_bp.route('/')
@login_required
def ai_video_index():
    """Main page for AI video features"""
    return render_template('ai_video/index.html')

def cleanup_face_thumbnails(face_thumbnails, force=False):
    """Clean up face thumbnail images
    Args:
        face_thumbnails: List of thumbnail URLs to clean up
        force: If True, force cleanup regardless of retention period
    """
    try:
        # Get the current time
        current_time = time.time()
        
        for thumbnail in face_thumbnails:
            try:
                # Get the file path from the thumbnail URL
                thumbnail_path = thumbnail.replace('/static/processed/', '')
                full_path = os.path.join(PROCESSED_DIR, thumbnail_path)
                
                if os.path.exists(full_path):
                    # Check if file is older than retention period (24 hours) or force cleanup
                    file_age = current_time - os.path.getctime(full_path)
                    if force or file_age > (24 * 3600):  # 24 hours retention
                        os.remove(full_path)
                        logger.info(f"Cleaned up thumbnail: {full_path}")
                    else:
                        logger.info(f"Retaining thumbnail within retention period: {full_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up thumbnail {thumbnail}: {str(e)}")
    except Exception as e:
        logger.error(f"Error during thumbnail cleanup: {str(e)}")

def cleanup_old_files(max_age_hours=24):
    """Clean up old face thumbnails and temporary files"""
    try:
        current_time = time.time()
        for filename in os.listdir(PROCESSED_DIR):
            file_path = os.path.join(PROCESSED_DIR, filename)
            # Skip if not a file
            if not os.path.isfile(file_path):
                continue
                
            # Check if file is older than max_age_hours
            file_age = current_time - os.path.getctime(file_path)
            if file_age > (max_age_hours * 3600):  # Convert hours to seconds
                # Only remove face thumbnails and temp files
                if filename.startswith('face_') or filename.startswith('temp_'):
                    try:
                        os.remove(file_path)
                        logger.info(f"Cleaned up old file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up old file {file_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error during old files cleanup: {str(e)}")

def manage_thumbnails(video_id, new_thumbnails=None):
    """Manage thumbnails for a video
    Args:
        video_id: ID of the video
        new_thumbnails: List of new thumbnail URLs to track
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get existing thumbnails for other videos
        cursor.execute(
            "SELECT id, metadata FROM media_items WHERE id != ? AND platform = 'ai_video'",
            (video_id,)
        )
        results = cursor.fetchall()
        
        # Clean up thumbnails from old videos (older than 24 hours)
        for result in results:
            try:
                metadata = json.loads(result['metadata'])
                if 'thumbnails' in metadata:
                    cleanup_face_thumbnails(metadata['thumbnails'], force=False)
            except Exception as e:
                logger.warning(f"Failed to clean up thumbnails for video {result['id']}: {str(e)}")
        
        # If new thumbnails are provided, update the database
        if new_thumbnails:
            cursor.execute(
                "UPDATE media_items SET metadata = ? WHERE id = ?",
                (json.dumps({'thumbnails': new_thumbnails}), video_id)
            )
            conn.commit()
        
        conn.close()
    except Exception as e:
        logger.error(f"Error managing thumbnails: {str(e)}")

@ai_video_bp.route('/detect-faces', methods=['POST'])
@login_required
def detect_faces():
    """Detect faces in the uploaded video"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({'error': 'No video selected'}), 400
    
    # Save the uploaded video
    user_id = session['user']['id']
    filename = secure_filename(f"{user_id}_{int(time.time())}_{video_file.filename}")
    video_path = os.path.join(PROCESSED_DIR, filename)
    video_file.save(video_path)
    
    # Process video to detect faces
    try:
        # Initialize MediaPipe Face Detection
        mp_face_detection = mp.solutions.face_detection
        mp_drawing = mp.solutions.drawing_utils
        
        # Configure face detection with higher min_detection_confidence for better accuracy
        face_detection = mp_face_detection.FaceDetection(
            model_selection=1,  # 0 for short-range, 1 for full-range detection
            min_detection_confidence=0.6  # Confidence threshold to filter weak detections
        )
        
        # Open the video
        cap = cv2.VideoCapture(video_path)
        
        # Sample frames for face detection (every 15 frames for better tracking)
        faces_data = []
        frame_count = 0
        sample_rate = 15  # Increased sampling rate for better face tracking
        
        # Dictionary to track faces across frames for consistency
        face_tracking = {}
        next_face_id = 0
        
        # Keep track of generated thumbnails for cleanup
        generated_thumbnails = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % sample_rate == 0:
                # Convert to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Process the frame for face detection
                results = face_detection.process(rgb_frame)
                
                # If faces found in this frame
                if results.detections:
                    frame_faces = []
                    
                    for detection in results.detections:
                        # Get detection confidence
                        confidence = detection.score[0]
                        
                        # Skip low confidence detections
                        if confidence < 0.6:
                            continue
                            
                        # Get bounding box coordinates
                        bbox = detection.location_data.relative_bounding_box
                        ih, iw, _ = frame.shape
                        x = max(0, int(bbox.xmin * iw))
                        y = max(0, int(bbox.ymin * ih))
                        w = min(int(bbox.width * iw), iw - x)
                        h = min(int(bbox.height * ih), ih - y)
                        
                        # Skip if bounding box is invalid
                        if w <= 0 or h <= 0:
                            continue
                        
                        # Generate a unique ID for this face or use existing ID if similar face was tracked
                        face_id = str(uuid.uuid4())[:8]
                        
                        # Save face thumbnail
                        face_img = frame[y:y+h, x:x+w]
                        face_filename = f"face_{face_id}_{frame_count}.jpg"
                        face_path = os.path.join(PROCESSED_DIR, face_filename)
                        cv2.imwrite(face_path, face_img)
                        
                        # Track thumbnail for cleanup
                        thumbnail_url = f"/static/processed/{face_filename}"
                        generated_thumbnails.append(thumbnail_url)
                        
                        # Add face data with confidence score
                        frame_faces.append({
                            'id': face_id,
                            'x': int(x),
                            'y': int(y),
                            'width': int(w),
                            'height': int(h),
                            'confidence': float(confidence),
                            'thumbnail': thumbnail_url
                        })
                    
                    # Add frame data with faces if any valid faces were detected
                    if frame_faces:
                        faces_data.append({
                            'frame': frame_count,
                            'timestamp': frame_count / cap.get(cv2.CAP_PROP_FPS),
                            'faces': frame_faces
                        })
            
            frame_count += 1
        
        cap.release()
        
        # Group similar faces (basic implementation - can be enhanced with face recognition)
        unique_faces = {}
        for frame_data in faces_data:
            for face in frame_data['faces']:
                face_id = face['id']
                if face_id not in unique_faces:
                    unique_faces[face_id] = {
                        'id': face_id,
                        'thumbnail': face['thumbnail'],
                        'occurrences': 1
                    }
                else:
                    unique_faces[face_id]['occurrences'] += 1
        
        # Save detection results to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Store video metadata
        cursor.execute(
            "INSERT INTO media_items (user_id, title, platform, media_type, local_path, original_url, metadata, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, filename, 'ai_video', 'video', f"/static/processed/{filename}", '', json.dumps({
                'faces_detected': len(unique_faces),
                'frame_count': frame_count,
                'duration': frame_count / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0,
                'thumbnails': generated_thumbnails  # Store thumbnail paths for future cleanup
            }), 'processing')
        )
        video_id = cursor.lastrowid
        
        # Store face detection data
        detection_data = {
            'video_id': video_id,
            'video_path': f"/static/processed/{filename}",
            'unique_faces': list(unique_faces.values()),
            'faces_data': faces_data
        }
        
        cursor.execute(
            "INSERT INTO ai_video_data (video_id, detection_data) VALUES (?, ?)",
            (video_id, json.dumps(detection_data))
        )
        
        conn.commit()
        conn.close()
        
        # Clean up old files in the background
        cleanup_old_files()
        
        # Cache the detection results
        cache_data = {
            'video_id': video_id,
            'unique_faces': list(unique_faces.values()),
            'video_path': f"/static/processed/{filename}",
            'metadata': {
                'faces_detected': len(unique_faces),
                'frame_count': frame_count,
                'duration': frame_count / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0,
                'thumbnails': generated_thumbnails
            }
        }
        ai_video_cache.cache_face_detection(video_id, cache_data)
        
        # Cache initial status
        status_data = {
            'status': 'processing',
            'progress': 0,
            'metadata': cache_data['metadata']
        }
        ai_video_cache.cache_status(video_id, status_data)
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'unique_faces': list(unique_faces.values()),
            'video_path': f"/static/processed/{filename}"
        })
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        # Clean up any generated thumbnails on error
        if 'generated_thumbnails' in locals():
            cleanup_face_thumbnails(generated_thumbnails)
        return jsonify({'error': f"Error processing video: {str(e)}"}), 500

@ai_video_bp.route('/generate-highlight', methods=['POST'])
@login_required
def generate_highlight():
    """Generate a highlight video focusing on the selected face"""
    data = request.json
    if not data or 'video_id' not in data or 'face_id' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    video_id = data['video_id']
    face_id = data['face_id']
    
    # Check cache for existing highlight
    cached_highlight = ai_video_cache.get_highlight(video_id, face_id)
    if cached_highlight:
        return jsonify(cached_highlight)
    
    try:
        # Get video and face data from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the original video metadata to access thumbnails
        cursor.execute(
            "SELECT m.local_path, m.metadata, a.detection_data FROM media_items m JOIN ai_video_data a ON m.id = a.video_id WHERE m.id = ?",
            (video_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Video not found'}), 404
        
        video_path = result['local_path']
        video_metadata = json.loads(result['metadata'])
        detection_data = json.loads(result['detection_data'])
        
        # Don't clean up thumbnails immediately, manage them instead
        if 'thumbnails' in video_metadata:
            manage_thumbnails(video_id)
        
        # Find all frames containing the selected face
        selected_frames = []
        for frame_data in detection_data['faces_data']:
            for face in frame_data['faces']:
                if face['id'] == face_id:
                    selected_frames.append(frame_data['frame'])
        
        if not selected_frames:
            return jsonify({'error': 'No frames found with the selected face'}), 404
        
        # Generate highlight video
        full_video_path = str(APP_ROOT / video_path.lstrip('/'))
        output_filename = f"highlight_{video_id}_{face_id}_{int(time.time())}.mp4"
        output_path = os.path.join(PROCESSED_DIR, output_filename)
        
        # Open the original video
        cap = cv2.VideoCapture(full_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Create temporary video file for frames
        temp_output = os.path.join(PROCESSED_DIR, f"temp_{output_filename}")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        
        # Extract segments with the selected face - optimized approach
        frame_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        segment_length = int(fps * 3)  # 3 seconds before and after face appearance
        
        # Pre-compute all frames to include in the highlight
        frames_to_include = set()
        for frame_num in selected_frames:
            # Add the frame with the face
            frames_to_include.add(frame_num)
            
            # Add buffer frames before the face (if they exist)
            start_buffer = max(0, frame_num - segment_length)
            for i in range(start_buffer, frame_num):
                frames_to_include.add(i)
            
            # Add buffer frames after the face
            end_buffer = min(total_frames, frame_num + segment_length)
            for i in range(frame_num + 1, end_buffer):
                frames_to_include.add(i)
        
        # Process frames efficiently
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only process frames that need to be included
            if frame_count in frames_to_include:
                out.write(frame)
            
            # Skip to next frame that needs processing if possible
            # This optimization helps with short videos
            if frame_count % 30 == 0 and frame_count + 1 < total_frames:
                next_needed = next((f for f in sorted(frames_to_include) if f > frame_count), total_frames)
                if next_needed > frame_count + 1:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, next_needed)
                    frame_count = next_needed - 1  # Will be incremented below
            
            frame_count += 1
        
        cap.release()
        out.release()

        # Use FFmpeg to copy the video stream from temp file and audio from original video
        import subprocess
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', temp_output,  # First input (video)
            '-i', full_video_path,  # Second input (original video with audio)
            '-c:v', 'libx264',  # Use H.264 codec for better compatibility
            '-preset', 'medium',  # Balance between speed and quality
            '-c:a', 'aac',  # Use AAC audio codec
            '-b:a', '192k',  # Audio bitrate
            '-shortest',  # Cut to shortest stream
            '-map', '0:v:0',  # Take video from first input
            '-map', '1:a:0?',  # Take audio from second input (if exists)
            '-movflags', '+faststart',  # Enable fast start for web playback
            output_path
        ]
        
        try:
            # Run FFmpeg command
            result = subprocess.run(ffmpeg_cmd, 
                                 check=True,
                                 capture_output=True,
                                 text=True)
            logger.info("FFmpeg command completed successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise Exception(f"Error during video processing: {e.stderr}")
            
        # Clean up temporary file
        try:
            os.remove(temp_output)
            logger.info(f"Temporary file removed: {temp_output}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary file: {e}")
        
        # Update database with highlight video
        highlight_path = f"/static/processed/{output_filename}"
        cursor.execute(
            "INSERT INTO media_items (user_id, title, platform, media_type, local_path, original_url, metadata, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session['user']['id'], f"Highlight of {face_id}", 'ai_video', 'highlight', highlight_path, '', json.dumps({
                'original_video_id': video_id,
                'face_id': face_id,
                'frame_count': len(selected_frames)
            }), 'completed')
        )
        highlight_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        # Cache the highlight data
        highlight_data = {
            'success': True,
            'highlight_id': highlight_id,
            'highlight_path': highlight_path
        }
        ai_video_cache.cache_highlight(video_id, face_id, highlight_data)
        
        return jsonify(highlight_data)
        
    except Exception as e:
        logger.error(f"Error generating highlight: {str(e)}")
        return jsonify({'error': f"Error generating highlight: {str(e)}"}), 500

@ai_video_bp.route('/check-status/<int:video_id>', methods=['GET'])
@login_required
def check_status(video_id):
    """Check the status of video processing"""
    try:
        # Check cache first
        cached_data = ai_video_cache.get_status(video_id)
        if cached_data:
            return jsonify(cached_data)
        
        # If not in cache, get from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT status, metadata FROM media_items WHERE id = ? AND user_id = ?",
            (video_id, session['user']['id'])
        )
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Video not found'}), 404
            
        status = result['status']
        metadata = json.loads(result['metadata'])
        
        # Calculate progress
        progress = 0
        if status == 'completed':
            progress = 100
        elif status == 'processing':
            progress = 85
        
        # Cache the status
        status_data = {
            'status': status,
            'progress': progress,
            'metadata': metadata
        }
        ai_video_cache.cache_status(video_id, status_data)
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error checking video status: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# Initialize database tables
# Using Blueprint's before_app_request instead of before_app_first_request
# This will run once when the application starts
_init_db_done = False

@ai_video_bp.before_app_request
def init_ai_video_db():
    global _init_db_done
    
    # Only run once
    if _init_db_done:
        return
    
    _init_db_done = True
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create AI video data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_video_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            detection_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES media_items (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("AI video database tables initialized")

def monitor_cache_health():
    try:
        info = redis_client.info()
        used_memory = info['used_memory_human']
        hit_rate = info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses'])
        return {'status': 'healthy', 'memory_usage': used_memory, 'hit_rate': hit_rate}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def cleanup_expired_cache():
    try:
        pattern = "ai_video:*"
        keys = redis_client.keys(pattern)
        for key in keys:
            if not redis_client.ttl(key):
                redis_client.delete(key)
    except Exception as e:
        logger.error(f"Cache cleanup error: {str(e)}")

@ai_video_bp.route('/media/<path:filename>')
@login_required
def serve_ai_video(filename):
    """Serve AI video files"""
    try:
        file_path = os.path.join(PROCESSED_DIR, filename)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found'}), 404
            
        # For video files, use conditional response to support seeking
        response = send_file(
            file_path,
            mimetype='video/mp4' if filename.endswith('.mp4') else 'image/jpeg',
            as_attachment=False,
            conditional=True
        )
        response.headers['Accept-Ranges'] = 'bytes'
        return response
        
    except Exception as e:
        logger.error(f"Error serving file: {str(e)}")
        return jsonify({'error': str(e)}), 500 