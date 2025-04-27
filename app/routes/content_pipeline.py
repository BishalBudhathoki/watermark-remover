"""
Content Repurposing Pipeline Routes

This module provides routes for the content repurposing pipeline, allowing users to:
1. Upload videos
2. Split videos into clips
3. Generate text for clips
4. Post clips to social media platforms
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, send_from_directory
import os
import json
import logging
from pathlib import Path
from werkzeug.utils import secure_filename
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the content_pipeline directory to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'content_pipeline'))

# Import content pipeline components
from content_pipeline.upload import upload_video, validate_video
from content_pipeline.splitter import split_video

# Try to import text generator components
try:
    from content_pipeline.text_generator import process_clip
    from content_pipeline.text_generator.ai_models import get_available_models
    TEXT_GENERATOR_AVAILABLE = True
except ImportError:
    logger.warning("Text generator module not available. Text generation features will be disabled.")
    TEXT_GENERATOR_AVAILABLE = False
    # Define a placeholder function for get_available_models
    def get_available_models():
        return []

# Try to import poster components
try:
    from content_pipeline.poster import post_to_platform, post_to_all_platforms, get_available_platforms
    POSTER_AVAILABLE = True
except ImportError:
    logger.warning("Poster module not available. Posting features will be disabled.")
    POSTER_AVAILABLE = False
    # Define a placeholder function for get_available_platforms
    def get_available_platforms():
        return []

# Import from app
from app.auth import login_required

# Create blueprint
content_pipeline_bp = Blueprint('content_pipeline', __name__, url_prefix='/content-pipeline')

# Define routes
@content_pipeline_bp.route('/', methods=['GET'])
@login_required
def index():
    """Render the content pipeline dashboard."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    platforms = get_available_platforms()
    return render_template('content_pipeline/dashboard.html', platforms=platforms)

@content_pipeline_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle video upload for content repurposing."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'video' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['video']

        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if file:
            filename = secure_filename(file.filename)
            upload_dir = Path(current_app.config['DOWNLOAD_FOLDER']) / 'uploads' / user_id
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_path = str(upload_dir / filename)
            file.save(file_path)

            # Validate the video
            if not validate_video(file_path):
                flash('Invalid video file', 'error')
                os.remove(file_path)
                return redirect(request.url)

            # Store the file path in the session
            session['uploaded_video_path'] = file_path

            flash('Video uploaded successfully', 'success')
            return redirect(url_for('content_pipeline.split'))

    return render_template('content_pipeline/upload.html')

@content_pipeline_bp.route('/split', methods=['GET', 'POST'])
@login_required
def split():
    """Split the uploaded video into clips."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    if 'uploaded_video_path' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': 'Please upload a video first'
            }), 400
        flash('Please upload a video first', 'error')
        return redirect(url_for('content_pipeline.upload'))

    video_path = session['uploaded_video_path']
    logger.info(f"Processing video: {video_path}")

    if not os.path.exists(video_path):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': 'Video file not found'
            }), 404
        flash('Video file not found', 'error')
        return redirect(url_for('content_pipeline.upload'))

    if request.method == 'POST':
        try:
            # Get splitting parameters
            max_clip_duration = float(request.form.get('max_clip_duration', 60))
            min_clip_duration = float(request.form.get('min_clip_duration', 5))
            split_on_silence = 'split_on_silence' in request.form
            silence_threshold = float(request.form.get('silence_threshold', 0.03))
            silence_duration = float(request.form.get('silence_duration', 0.5))

            logger.info(f"Split parameters: max_duration={max_clip_duration}, min_duration={min_clip_duration}, "
                       f"split_on_silence={split_on_silence}, threshold={silence_threshold}, "
                       f"silence_duration={silence_duration}")

            # Create output directory
            output_dir = Path(current_app.config['DOWNLOAD_FOLDER']) / 'clips' / user_id
            output_dir.mkdir(parents=True, exist_ok=True)

            # Split the video
            result = split_video(
                video_path=video_path,
                output_dir=str(output_dir),
                max_clip_duration=max_clip_duration,
                min_clip_duration=min_clip_duration,
                split_on_silence=split_on_silence,
                silence_threshold=silence_threshold,
                silence_duration=silence_duration
            )

            # Store the clips in the session
            if result["success"]:
                session['clips'] = result["clips"]
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'redirect': url_for('content_pipeline.generate_text'),
                        'message': f'Video split into {len(result["clips"])} clips successfully'
                    })
                flash(f'Video split into {len(result["clips"])} clips successfully', 'success')
                return redirect(url_for('content_pipeline.generate_text'))
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False,
                        'error': result["error"]
                    }), 500
                flash(f'Error splitting video: {result["error"]}', 'error')
                return redirect(request.url)

        except Exception as e:
            logger.error(f"Error splitting video: {e}", exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
            flash(f'Error splitting video: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('content_pipeline/split.html', video_path=video_path)

@content_pipeline_bp.route('/generate-text', methods=['GET', 'POST'])
@login_required
def generate_text():
    """Generate text for the video clips."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    if not TEXT_GENERATOR_AVAILABLE:
        flash('Text generation is not available. Please install the required dependencies.', 'error')
        return redirect(url_for('content_pipeline.index'))

    if 'clips' not in session:
        flash('Please split a video first', 'error')
        return redirect(url_for('content_pipeline.split'))

    clips = session['clips']
    available_models = get_available_models()

    if request.method == 'POST':
        # Get text generation parameters with more robust handling
        try:
            # Log all form data for debugging
            logger.info(f"Form data received: {request.form}")

            # Get parameters with explicit validation
            num_caption_variations = int(request.form.get('num_caption_variations', 3))
            num_hashtags = int(request.form.get('num_hashtags', 10))

            # Get AI provider with validation
            ai_provider = request.form.get('ai_provider')
            if not ai_provider or ai_provider == 'None':
                # If no AI provider is specified, use the first available one
                if available_models:
                    ai_provider = available_models[0]
                    logger.warning(f"No AI provider specified, defaulting to: {ai_provider}")
                else:
                    flash('No AI provider available. Please configure API keys.', 'error')
                    return redirect(request.url)

            # Get caption style with validation
            caption_style = request.form.get('caption_style')
            if not caption_style or caption_style == 'None':
                caption_style = 'casual'  # Default to casual if not specified
                logger.warning(f"No caption style specified, defaulting to: {caption_style}")

            # Get user-selected tone/style
            tone_style = request.form.get('tone_style', 'neutral')
            logger.info(f"User selected tone/style: {tone_style}")

            # Get user-provided video description
            video_description = request.form.get('video_description', '').strip()

            # Log the selected parameters
            logger.info(f"Generating text with: AI provider={ai_provider}, Style={caption_style}, Tone={tone_style}, Captions={num_caption_variations}, Hashtags={num_hashtags}")

            # Process each clip to generate text
            processed_clips = []
            from app.routes.media import save_media_metadata
            for clip in clips:
                clip_metadata = {
                    "description": video_description if video_description else os.path.basename(clip['path']),
                    "duration": clip['duration'],
                    "start_time": clip['start_time'],
                    "end_time": clip['end_time'],
                    "caption_style": caption_style
                }
                processed_clip = process_clip(
                    clip_path=clip['path'],
                    clip_metadata=clip_metadata,
                    num_caption_variations=num_caption_variations,
                    num_hashtags=num_hashtags,
                    ai_provider=ai_provider,
                    tone_style=tone_style
                )
                processed_clips.append(processed_clip)

                # Index the processed clip in the media database
                # Avoid duplicates by checking if already indexed (by path and user)
                try:
                    from app.routes.media import get_user_media_items
                    already_indexed = False
                    user_media = get_user_media_items(user_id)
                    for item in user_media:
                        if item.get('local_path') == clip['path']:
                            already_indexed = True
                            break
                    if not already_indexed:
                        save_media_metadata(
                            user_id=user_id,
                            platform='ai_video',
                            media_type='video',
                            file_path=clip['path'],
                            title=os.path.basename(clip['path']),
                            original_url=None,
                            duration=clip['duration'],
                            metadata={
                                'captions': processed_clip.get('captions', []),
                                'hashtags': processed_clip.get('hashtags', []),
                                'description': clip_metadata['description'],
                                'caption_style': caption_style,
                                'tone_style': tone_style
                            }
                        )
                except Exception as e:
                    logger.error(f"Failed to index generated clip in media database: {e}")

            # Store the processed clips in the session
            session['processed_clips'] = processed_clips

            flash('Text generated successfully for all clips', 'success')
            return redirect(url_for('content_pipeline.post'))
        except Exception as e:
            logger.error(f"Error generating text: {e}", exc_info=True)
            flash(f'Error generating text: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('content_pipeline/generate_text.html', clips=clips, available_models=available_models)

@content_pipeline_bp.route('/post', methods=['GET', 'POST'])
@login_required
def post():
    """Post clips to social media platforms."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    if not POSTER_AVAILABLE:
        flash('Posting is not available. Please install the required dependencies.', 'error')
        return redirect(url_for('content_pipeline.index'))

    if 'processed_clips' not in session:
        flash('Please generate text for clips first', 'error')
        return redirect(url_for('content_pipeline.generate_text'))

    processed_clips = session['processed_clips']
    platforms = get_available_platforms()

    # Check if there are any available platforms
    if not platforms:
        flash('No posting platforms are available. Please check your configuration.', 'error')
        return redirect(url_for('content_pipeline.index'))

    # Import auth manager
    from content_pipeline.poster.auth import get_auth_manager
    auth_manager = get_auth_manager(user_id)

    # Check if auth_manager was created successfully
    if auth_manager is None:
        flash('Error initializing authentication manager. Please try again.', 'error')
        return redirect(url_for('content_pipeline.index'))

    # Check authentication status for each platform
    platform_auth_status = {}
    for platform in platforms:
        platform_auth_status[platform] = auth_manager.is_authenticated(platform)

    if request.method == 'POST':
        # Get selected platforms
        selected_platforms = request.form.getlist('platforms')

        if not selected_platforms:
            flash('Please select at least one platform', 'error')
            return redirect(request.url)

        # Check if all selected platforms are authenticated
        unauthenticated_platforms = []
        for platform in selected_platforms:
            if platform != 'all' and not platform_auth_status.get(platform, False):
                unauthenticated_platforms.append(platform)

        if unauthenticated_platforms:
            platform_names = ', '.join([p.capitalize() for p in unauthenticated_platforms])
            flash(f'Please authenticate with the following platforms first: {platform_names}', 'error')
            return redirect(url_for('social_auth.index'))

        # Get selected clips
        selected_clip_indices = [int(i) for i in request.form.getlist('clips')]

        if not selected_clip_indices:
            flash('Please select at least one clip', 'error')
            return redirect(request.url)

        # Get selected captions and hashtags
        selected_captions = {}
        selected_hashtags = {}

        for i in selected_clip_indices:
            caption_key = f'caption_{i}'
            hashtags_key = f'hashtags_{i}'

            if caption_key in request.form and hashtags_key in request.form:
                selected_captions[i] = request.form[caption_key]
                selected_hashtags[i] = request.form[hashtags_key]

        # Post to platforms
        results = []

        for i in selected_clip_indices:
            clip = processed_clips[i]
            caption = selected_captions.get(i, clip['captions'][0])
            hashtags = selected_hashtags.get(i, ' '.join(clip['hashtags']))

            # Combine caption and hashtags
            full_caption = f"{caption}\n\n{hashtags}"

            # Add credentials to options
            credentials = {'user_id': user_id}

            # Post to selected platforms
            if 'all' in selected_platforms:
                result = post_to_all_platforms(
                    video_path=clip['path'],
                    caption=full_caption,
                    credentials=credentials
                )
            else:
                platform_results = {}
                for platform in selected_platforms:
                    platform_result = post_to_platform(
                        platform=platform,
                        video_path=clip['path'],
                        caption=full_caption,
                        hashtags=[],
                        credentials=credentials
                    )
                    platform_results[platform] = platform_result

                    # Check if authentication is required
                    if not platform_result.get('success') and platform_result.get('auth_required'):
                        flash(f'Authentication required for {platform.capitalize()}. Please connect your account.', 'error')
                        return redirect(url_for('social_auth.index'))

                result = platform_results

            results.append({
                'clip': clip,
                'result': result
            })

        # Store the results in the session
        session['posting_results'] = results

        flash('Content posted successfully', 'success')
        return redirect(url_for('content_pipeline.results'))

    # Debug log to see what's in the processed_clips
    for i, clip in enumerate(processed_clips):
        logger.info(f"Clip {i+1} data: captions_count={len(clip.get('captions', []))}, hashtags_count={len(clip.get('hashtags', []))}")
        if clip.get('captions'):
            logger.info(f"Sample caption: {clip['captions'][0]}")
        if clip.get('hashtags'):
            logger.info(f"Sample hashtags: {', '.join(clip['hashtags'][:3])}")

    return render_template('content_pipeline/post.html', clips=processed_clips, platforms=platforms, platform_auth_status=platform_auth_status)

@content_pipeline_bp.route('/results', methods=['GET'])
@login_required
def results():
    """Display the results of the content repurposing pipeline."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    if 'posting_results' not in session:
        flash('No posting results available', 'error')
        return redirect(url_for('content_pipeline.index'))

    results = session['posting_results']

    return render_template('content_pipeline/results.html', results=results)

@content_pipeline_bp.route('/clip/<path:filename>')
def serve_clip(filename):
    """Serve a clip file from the downloads directory."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    clips_dir = os.path.join(current_app.config['DOWNLOAD_FOLDER'], 'clips', user_id)
    return send_from_directory(clips_dir, filename)

@content_pipeline_bp.route('/uploaded-video/<path:filename>')
def serve_uploaded_video(filename):
    """Serve an uploaded video file from the uploads directory."""
    if 'user' not in session or 'id' not in session['user']:
        flash('User not authenticated. Please log in.', 'error')
        return redirect(url_for('auth.login'))
    user_id = session['user']['id']
    uploads_dir = os.path.join(current_app.config['DOWNLOAD_FOLDER'], 'uploads', user_id)
    return send_from_directory(uploads_dir, filename)