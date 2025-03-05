from flask import Flask, render_template, session, redirect, url_for, flash, request, send_file
from flask_cors import CORS
from flask_session import Session
from datetime import timedelta, datetime
import os
import logging
from dotenv import load_dotenv
from .utils.path import APP_ROOT, DOWNLOAD_DIR, ensure_directories
from .auth import login_required, register_user, login_user, logout_user
from .routes.ai_video import ai_video_bp
from .routes.content_pipeline import content_pipeline_bp
from .routes.auth_routes import social_auth_bp
from pathlib import Path
from app.routes.views import views_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    # Load environment variables first
    load_dotenv()

    # Log loaded environment variables (masked)
    instagram_client_id = os.getenv('INSTAGRAM_CLIENT_ID')
    instagram_client_secret = os.getenv('INSTAGRAM_CLIENT_SECRET')

    if instagram_client_id:
        masked_id = instagram_client_id[:4] + '*' * (len(instagram_client_id) - 8) + instagram_client_id[-4:] if len(instagram_client_id) > 8 else '****'
        logger.info(f"Loaded Instagram client ID from environment: {masked_id}")
    else:
        logger.warning("Instagram client ID not found in environment variables")

    if instagram_client_secret:
        masked_secret = instagram_client_secret[:4] + '*' * (len(instagram_client_secret) - 8) + instagram_client_secret[-4:] if len(instagram_client_secret) > 8 else '****'
        logger.info(f"Loaded Instagram client secret from environment: {masked_secret}")
    else:
        logger.warning("Instagram client secret not found in environment variables")

    app = Flask(__name__,
                template_folder='../templates',  # Point to templates directory
                static_folder='../static')       # Point to static directory

    # Initialize Flask app with session settings
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'your-secret-key-for-sessions'),  # Use environment variable or fixed key
        SESSION_TYPE='filesystem',
        SESSION_COOKIE_SECURE=False,  # Set to False for development
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        SESSION_REFRESH_EACH_REQUEST=True,  # Refresh session on each request
        DOWNLOAD_FOLDER=str(DOWNLOAD_DIR),
        HOST=os.getenv('HOST', '0.0.0.0'),
        PORT=int(os.getenv('PORT', 5001)),
        MAX_CONTENT_LENGTH=1000 * 1024 * 1024  # Allow uploads up to 1000MB
    )

    # Initialize Flask-Session
    Session(app)

    # Configure CORS
    CORS(app, resources={
        r"/*": {
            "origins": [
                "http://localhost:5000",
                "http://127.0.0.1:5000",
                "http://localhost:5001",
                "http://127.0.0.1:5001",
                "https://accounts.google.com",
                "https://www.tiktok.com",
                "https://open-api.tiktok.com",
                "https://*.ngrok-free.app"  # Allow all ngrok subdomains
            ],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })

    # Create necessary directories
    ensure_directories()

    # Add TikTok verification file route
    @app.route('/tiktok<filename>.txt')
    def tiktok_verification(filename):
        """Serve TikTok domain verification file."""
        try:
            # Look for the verification file in the root directory
            file_path = Path(APP_ROOT) / f'tiktok{filename}.txt'
            if file_path.exists():
                return send_file(file_path, mimetype='text/plain')
            else:
                logger.error(f"TikTok verification file not found: {file_path}")
                return 'File not found', 404
        except Exception as e:
            logger.error(f"Error serving TikTok verification file: {str(e)}")
            return 'Error serving file', 500

    # Add security headers middleware
    @app.after_request
    def add_security_headers(response):
        if request.headers.get('Origin'):
            response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin')
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'

        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://accounts.google.com"

        return response

    # Register blueprints
    app.register_blue# print(ai_video_bp)
    app.register_blue# print(content_pipeline_bp)
    app.register_blue# print(social_auth_bp)
    app.register_blue# print(views_bp)

    # Import and register other routes
    from app.routes.twitter import twitter_bp, init_twitter_resources
    from app.routes.instagram import instagram_bp
    from app.routes.tiktok import tiktok_bp
    from app.routes.youtube import youtube_bp
    from app.routes.media import media_bp

    app.register_blue# print(twitter_bp, url_prefix='/api/v1/twitter') # Initialize Twitter resources
    app.register_blue# print(instagram_bp)
    app.register_blue# print(tiktok_bp)
    app.register_blue# print(youtube_bp)
    app.register_blue# print(media_bp)

    # Add context processor for datetime
    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}

    # Add index route
    @app.route('/')
    def index():
        return render_template('index.html')

    # Add auth routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # Clear any existing flash messages at the start
        session.pop('_flashes', None)

        # If user is already logged in, redirect to index
        if session.get('user'):
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')

            if not email or not password:
                flash('Email and password are required', 'error')
                return render_template('login.html')

            try:
                auth_response = login_user(email, password)
                if auth_response.user:
                    flash('Login successful!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Login failed. Please check your credentials.', 'error')
                    return render_template('login.html')

            except Exception as e:
                error_message = str(e)
                if 'Invalid login credentials' in error_message:
                    flash('Invalid email or password', 'error')
                else:
                    flash(f'Login failed: {error_message}', 'error')
                return render_template('login.html')

        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        # Clear any existing flash messages at the start
        session.pop('_flashes', None)

        # If user is already logged in, redirect to index
        if session.get('user'):
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = request.form.get('email')
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not email or not password or not confirm_password:
                flash('All fields are required', 'error')
                return render_template('register.html')

            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('register.html')

            try:
                auth_response = register_user(email, password, username)
                if auth_response.user:
                    flash('Registration successful! Please check your email to confirm your account.', 'success')
                    return redirect(url_for('login'))
                else:
                    flash('Registration failed. Please try again.', 'error')
                    return render_template('register.html')

            except Exception as e:
                error_message = str(e)
                if 'already exists' in error_message.lower():
                    flash('Email already registered. Please login or use a different email.', 'error')
                else:
                    flash(f'Registration failed: {error_message}', 'error')
                return render_template('register.html')

        return render_template('register.html')

    @app.route('/logout')
    @login_required
    def logout():
        try:
            session.pop('_flashes', None)
            session.clear()
            logout_user()
            flash('Successfully logged out!', 'success')
        except Exception as e:
            flash(f'Error during logout: {str(e)}', 'error')
        return redirect(url_for('login'))

    return app
