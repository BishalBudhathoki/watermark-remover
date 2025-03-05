import logging
from flask import Blueprint, render_template, jsonify, request, send_file, abort, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
import sqlite3
from PIL import Image
import io
from functools import wraps
import cv2
from pathlib import Path

from ..utils.path import get_download_path, get_relative_path
from ..services.storage import save_media_metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ai_video_bp = Blueprint('ai_video', __name__, url_prefix='/ai-video')

# Get application root directory
APP_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = APP_ROOT / 'media_vault.db'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user'):
            flash('Please login to access the media dashboard.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Create media items table with user_id
    c.execute('''
        CREATE TABLE IF NOT EXISTS media_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            platform TEXT NOT NULL,
            media_type TEXT NOT NULL,
            local_path TEXT NOT NULL,
            thumbnail_path TEXT,
            original_url TEXT,
            duration INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_to TEXT,
            metadata TEXT,
            file_size INTEGER,
            width INTEGER,
            height INTEGER,
            status TEXT DEFAULT 'active'
        )
    ''')

    # Create tags table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER,
            name TEXT NOT NULL,
            FOREIGN KEY (media_id) REFERENCES media_items (id)
        )
    ''')

    # Add indexes for better performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_media_user ON media_items(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_media_platform ON media_items(platform)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_media_type ON media_items(media_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_media_created ON media_items(created_at)')

    conn.commit()
    conn.close()

    # Log schema creation
    logger.info("Database schema initialized")

# Initialize database tables
init_db()

@media_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        # Get user_id from session
        user_id = session['user']['id']

        # Get media items for the current user
        media_items = get_user_media_items(user_id)

        # Debug logging
        logger.info(f"Retrieved {len(media_items)} media items for user {user_id}")
        if media_items:
            logger.info(f"Sample media item: {media_items[0]}")

        # Calculate statistics
        stats = calculate_media_stats(media_items)
        logger.info(f"Media stats: {stats}")

        return render_template('media_dashboard.html',
                             media_items=media_items,
                             stats=stats)
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}", exc_info=True)
        return render_template('error.html', error=str(e))

@media_bp.route('/api/media/search')
@login_required
def search_media():
    query = request.args.get('q', '')
    platform = request.args.get('platform', '')
    media_type = request.args.get('type', '')
    sort_by = request.args.get('sort', 'date')

    conn = get_db_connection()
    c = conn.cursor()

    sql = 'SELECT * FROM media_items WHERE 1=1'
    params = []

    if query:
        sql += ' AND (title LIKE ? OR metadata LIKE ?)'
        params.extend([f'%{query}%', f'%{query}%'])

    if platform:
        sql += ' AND platform = ?'
        params.append(platform)

    if media_type:
        sql += ' AND media_type = ?'
        params.append(media_type)

    if sort_by == 'date':
        sql += ' ORDER BY created_at DESC'
    elif sort_by == 'title':
        sql += ' ORDER BY title'

    media_items = c.execute(sql, params).fetchall()
    conn.close()

    return jsonify([dict(item) for item in media_items])

@media_bp.route('/api/media/delete/<int:media_id>', methods=['POST'])
@login_required
def delete_media_item(media_id):
    try:
        user_id = session['user']['id']
        conn = get_db_connection()
        c = conn.cursor()

        # Get media item and verify ownership
        media_item = c.execute('''
            SELECT * FROM media_items
            WHERE id = ? AND user_id = ?
        ''', (media_id, user_id)).fetchone()

        if not media_item:
            conn.close()
            return jsonify({'error': 'Media not found or unauthorized'}), 404

        # Delete files
        if os.path.exists(media_item['local_path']):
            os.remove(media_item['local_path'])
        if media_item['thumbnail_path'] and os.path.exists(media_item['thumbnail_path']):
            os.remove(media_item['thumbnail_path'])

        # Delete from database
        c.execute('DELETE FROM tags WHERE media_id = ?', (media_id,))
        c.execute('DELETE FROM media_items WHERE id = ?', (media_id,))
        conn.commit()

        return jsonify({'message': 'Media deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting media: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@media_bp.route('/api/media/share/<int:media_id>', methods=['POST'])
@login_required
def share_media(media_id):
    try:
        user_id = session['user']['id']
        platform = request.json.get('platform')

        if not platform:
            return jsonify({'error': 'Platform is required'}), 400

        conn = get_db_connection()
        c = conn.cursor()

        # Get media item and verify ownership
        media_item = c.execute('''
            SELECT * FROM media_items
            WHERE id = ? AND user_id = ?
        ''', (media_id, user_id)).fetchone()

        if not media_item:
            return jsonify({'error': 'Media not found or unauthorized'}), 404

        # Generate share link (implement platform-specific sharing logic here)
        share_url = generate_share_url(media_item, platform)

        return jsonify({
            'message': 'Share link generated',
            'share_url': share_url
        })
    except Exception as e:
        logger.error(f"Error sharing media: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

def generate_share_url(media_item, platform):
    """Generate a sharing URL based on the platform."""
    base_url = request.host_url.rstrip('/')
    media_url = f"{base_url}/media/share/{media_item['id']}"

    if platform == 'twitter':
        return f"https://twitter.com/intent/tweet?url={media_url}"
    elif platform == 'facebook':
        return f"https://www.facebook.com/sharer/sharer.php?u={media_url}"
    else:
        return media_url

@media_bp.route('/api/media/edit/<int:media_id>', methods=['POST'])
@login_required
def edit_media(media_id):
    try:
        user_id = session['user']['id']
        title = request.json.get('title')
        tags = request.json.get('tags', [])

        conn = get_db_connection()
        c = conn.cursor()

        # Update media item
        if title:
            c.execute('''
                UPDATE media_items
                SET title = ?
                WHERE id = ? AND user_id = ?
            ''', (title, media_id, user_id))

        # Update tags
        c.execute('DELETE FROM tags WHERE media_id = ?', (media_id,))
        for tag in tags:
            c.execute('INSERT INTO tags (media_id, name) VALUES (?, ?)',
                     (media_id, tag))

        conn.commit()
        return jsonify({'message': 'Media updated successfully'})
    except Exception as e:
        logger.error(f"Error updating media: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@media_bp.route('/api/media/<int:media_id>/tags', methods=['POST'])
@login_required
def add_tag(media_id):
    tag_name = request.json.get('tag')
    if not tag_name:
        return jsonify({'error': 'Tag name is required'}), 400

    conn = get_db_connection()
    c = conn.cursor()

    # Check if media exists
    if not c.execute('SELECT 1 FROM media_items WHERE id = ?', (media_id,)).fetchone():
        conn.close()
        return jsonify({'error': 'Media not found'}), 404

    # Add tag
    c.execute('INSERT INTO tags (media_id, name) VALUES (?, ?)', (media_id, tag_name))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Tag added successfully'})

@media_bp.route('/api/media/<int:media_id>/upload', methods=['POST'])
@login_required
def upload_to_platform(media_id):
    platform = request.json.get('platform')
    if not platform:
        return jsonify({'error': 'Platform is required'}), 400

    conn = get_db_connection()
    c = conn.cursor()

    # Get media item
    media_item = c.execute('SELECT * FROM media_items WHERE id = ?', (media_id,)).fetchone()
    if not media_item:
        conn.close()
        return jsonify({'error': 'Media not found'}), 404

    # TODO: Implement platform-specific upload logic
    # For now, just mark as uploaded
    c.execute('UPDATE media_items SET uploaded_to = ? WHERE id = ?', (platform, media_id))
    conn.commit()
    conn.close()

    return jsonify({'message': f'Media uploaded to {platform}'})

@media_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        abort(404)

@media_bp.route('/downloads/<path:filename>')
def serve_download(filename):
    """Serve downloaded files with support for subdirectories."""
    try:
        # Get the full path from the app's download folder
        file_path = Path(current_app.config['DOWNLOAD_FOLDER']) / filename

        # Try platform-specific directories if file not found
        if not file_path.exists():
            for platform in ['youtube', 'tiktok', 'instagram']:
                platform_path = Path(current_app.config['DOWNLOAD_FOLDER']) / platform / Path(filename).name
                if platform_path.exists():
                    file_path = platform_path
                    break

        # Verify the file path is within the allowed directory
        if not str(file_path.resolve()).startswith(str(Path(current_app.config['DOWNLOAD_FOLDER']).resolve())):
            logger.error(f"Attempted to access file outside download directory: {file_path}")
            abort(404)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            abort(404)

        # Get file extension
        ext = file_path.suffix.lower()

        # Determine content type
        content_types = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webm': 'video/webm',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4'
        }
        content_type = content_types.get(ext, 'application/octet-stream')

        logger.info(f"Serving file: {file_path} with content type: {content_type}")

        return send_file(
            file_path,
            mimetype=content_type,
            as_attachment=False,
            download_name=file_path.name
        )
    except Exception as e:
        logger.error(f"Error serving file: {str(e)}")
        abort(404)

def save_media_metadata(user_id, platform, media_type, file_path, title, original_url=None, duration=None, metadata=None, thumbnail_path=None):
    """Save media metadata to database."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get file size and dimensions if available
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
        width = height = None
        if media_type == 'video':
            # TODO: Add video dimension extraction
            pass
        elif media_type == 'image':
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
            except Exception as e:
                logger.error(f"Error getting image dimensions: {str(e)}")

        # Insert media item
        c.execute('''
            INSERT INTO media_items (
                user_id, platform, media_type, local_path, title,
                original_url, duration, metadata, file_size,
                width, height, thumbnail_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, platform, media_type, file_path, title,
            original_url, duration, json.dumps(metadata) if metadata else None,
            file_size, width, height, thumbnail_path
        ))

        media_id = c.lastrowid

        # Add tags if present in metadata
        if metadata and 'tags' in metadata:
            for tag in metadata['tags']:
                c.execute('INSERT INTO tags (media_id, name) VALUES (?, ?)',
                         (media_id, tag))

        conn.commit()
        return media_id
    finally:
        conn.close()

def get_user_media_items(user_id):
    """Get media items for a specific user."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # First, get all media items for the user with complete information
        media_items = c.execute('''
            SELECT
                id,
                user_id,
                platform,
                media_type,
                title,
                local_path,
                thumbnail_path,
                original_url,
                duration,
                created_at,
                uploaded_to,
                metadata,
                file_size,
                width,
                height
            FROM media_items
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,)).fetchall()

        # Convert to list of dictionaries with proper metadata
        items = []
        for item in media_items:
            item_dict = dict(item)

            # Parse metadata if it exists
            if item_dict.get('metadata'):
                try:
                    item_dict['metadata'] = json.loads(item_dict['metadata'])
                except:
                    item_dict['metadata'] = {}
            else:
                item_dict['metadata'] = {}

            # Get tags for this media item
            tags = c.execute('''
                SELECT name FROM tags
                WHERE media_id = ?
            ''', (item_dict['id'],)).fetchall()

            item_dict['tags'] = [tag[0] for tag in tags] if tags else []

            # Add formatted date
            if item_dict.get('created_at'):
                try:
                    if isinstance(item_dict['created_at'], str):
                        item_dict['created_at'] = datetime.strptime(item_dict['created_at'], '%Y-%m-%d %H:%M:%S')
                except:
                    item_dict['created_at'] = datetime.now()

            # Ensure all required fields exist
            item_dict.setdefault('title', 'Untitled')
            item_dict.setdefault('platform', 'unknown')
            item_dict.setdefault('media_type', 'video')
            item_dict.setdefault('created_at', datetime.now())

            # Log each item for debugging
            logger.info(f"Processing media item: {item_dict}")

            items.append(item_dict)

        return items
    finally:
        conn.close()

def calculate_media_stats(media_items):
    """Calculate media statistics from items."""
    return {
        'total_media': len(media_items),
        'videos': sum(1 for item in media_items if item.get('media_type') == 'video'),
        'images': sum(1 for item in media_items if item.get('media_type') == 'image'),
        'uploaded': sum(1 for item in media_items if item.get('uploaded_to') is not None)
