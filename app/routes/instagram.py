from flask import Blueprint, request, jsonify, render_template, session, current_app, abort, redirect, url_for
from pathlib import Path
import logging
import yt_dlp
import json
import requests
from datetime import datetime
from urllib.parse import urlparse
import os
import secrets

from ..services.cache import MediaCache
from ..utils.path import get_download_path, get_relative_path
from ..routes.media import save_media_metadata
from content_pipeline.poster.auth import get_auth_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
instagram_bp = Blue# # # # # print('instagram', __name__)

# Initialize MediaCache for Instagram
instagram_cache = MediaCache('instagram')

# Instagram OAuth configuration
# Using Instagram Business API scopes (new format)
INSTAGRAM_SCOPES = [
    'instagram_business_basic',
    'instagram_business_content_publish',
    'instagram_business_manage_messages',
    'instagram_business_manage_comments'
]
INSTAGRAM_CALLBACK_ROUTE = '/instagram-callback'

# Instagram OAuth configuration
# Using Basic Display API scopes
INSTAGRAM_SCOPES = ['basic', 'user_profile', 'user_media']
INSTAGRAM_CALLBACK_ROUTE = '/instagram-callback'

# Instagram OAuth configuration
# Using Facebook Graph API v18.0 scopes
INSTAGRAM_SCOPES = [
    'instagram_basic',
    'instagram_content_publish',
    'instagram_manage_comments',
    'instagram_manage_insights',
    'pages_show_list',
    'pages_read_engagement'
]
INSTAGRAM_CALLBACK_ROUTE = '/instagram-callback'

def validate_instagram_url(url: str) -> tuple[bool, str]:
    """Validate if the URL is a valid Instagram URL."""
    try:
        parsed_url = urlparse(url)
        if not parsed_url.netloc in ['www.instagram.com', 'instagram.com']:
            return False, "Invalid Instagram URL domain"

        path_parts = parsed_url.path.strip('/').split('/')
        if not path_parts:
            return False, "Invalid URL format"

        valid_types = ['p', 'reel', 'stories']
        if any(t in url for t in valid_types):
            if len(path_parts) < 2:
                return False, "Invalid content URL format"
        else:
            if not path_parts[0]:
                return False, "Invalid profile URL format"

        return True, None
    except Exception as e:
        return False, f"URL validation error: {str(e)}"

@instagram_bp.route('/instagram-downloader')
def instagram_downloader():
    """Render Instagram downloader page."""
    return render_template('instagram_downloader.html')

@instagram_bp.route('/instagram-download', methods=['POST'])
def instagram_download():
    """Handle Instagram content download."""
    try:
        # Check authentication
        if not session.get('user'):
            return jsonify({'error': 'Please login to download content'}), 401

        url = request.form.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Validate URL
        is_valid, error_message = validate_instagram_url(url)
        if not is_valid:
            return jsonify({'error': error_message}), 400

        # Clean up the URL to remove query parameters and get the shortcode
        cleaned_url = url.split('?')[0].rstrip('/')
        shortcode = cleaned_url.split('/')[-1]

        # Check if content is already cached
        cached_media = instagram_cache.get_cached_media(url, session['user']['id'])
        if cached_media:
            logger.info(f"Using cached media for URL: {url}")
            # Log the cached file path for debugging
            logger.info(f"Cached file path: {cached_media['file_path']}")

            return render_template('instagram_results.html',
                content={
                    'username': cached_media['metadata']['uploader'],
                    'posts': [{
                        'type': cached_media.get('media_type', 'video'),
                        'caption': cached_media.get('description', ''),
                        'likes': cached_media['metadata'].get('like_count', 0),
                        'comments': cached_media['metadata'].get('comment_count', 0),
                        'date': datetime.fromtimestamp(cached_media['metadata'].get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                        'filename': Path(cached_media['file_path']).name,  # Just the filename part
                        'shortcode': shortcode,
                        'extension': 'mp4'  # Always mp4 due to forced conversion
                    }]
                }
            )

        # Configure headers with more browser-like values
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"'
        }

        # First try with yt-dlp
        try:
            # Prepare download path
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_template = get_download_path(
                'instagram',
                f'instagram_{shortcode}_{timestamp}.%(ext)s'
            )

            ydl_opts = {
                'outtmpl': str(output_template),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # Force mp4 format
                'quiet': True,
                'no_warnings': True,
                'http_headers': headers,
                'extract_flat': False,
                'writeinfojson': False,
                'writethumbnail': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',  # Force conversion to mp4
                }],
                'cookiesfrombrowser': ('chrome',),  # Try to use Chrome cookies
                'socket_timeout': 30,  # Increase timeout
                'retries': 10,  # Increase retries
                'ignoreerrors': False,  # Don't ignore errors
                'nocheckcertificate': True,  # Skip certificate validation
                'extractor_args': {
                    'instagram': {
                        'direct': True,  # Try direct download
                        'fatal_direct': False  # Don't fail if direct download fails
                    }
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # First try to extract info without downloading
                    info = ydl.extract_info(url, download=False)
                    logger.info(f"Successfully extracted info for URL: {url}")

                    # Then download
                    info = ydl.extract_info(url, download=True)
                    filename = Path(ydl.prepare_filename(info))

                    # Ensure file has .mp4 extension
                    if not filename.suffix or filename.suffix == '.NA':
                        new_filename = filename.with_suffix('.mp4')
                        if filename.exists():
                            filename.rename(new_filename)
                        filename = new_filename

                    # Get relative path for storage
                    relative_path = f"instagram/{filename.name}"  # Store with platform prefix

                    # Prepare media info
                    media_info = {
                        'id': shortcode,
                        'title': info.get('title', f'Instagram Post {shortcode}'),
                        'file_path': relative_path,  # Use platform-prefixed path
                        'media_type': 'video',
                        'description': info.get('description', ''),
                        'metadata': {
                            'uploader': info.get('uploader', 'unknown'),
                            'like_count': info.get('like_count', 0),
                            'comment_count': info.get('comment_count', 0),
                            'timestamp': info.get('timestamp', int(datetime.now().timestamp())),
                            'duration': info.get('duration', 0)
                        }
                    }

                    # Save to database
                    save_media_metadata(
                        user_id=session['user']['id'],
                        platform='instagram',
                        media_type='video',
                        file_path=relative_path,
                        title=media_info['title'],
                        original_url=url,
                        duration=media_info['metadata'].get('duration', 0),
                        metadata=json.dumps({  # Properly format metadata
                            'uploader': media_info['metadata'].get('uploader', 'unknown'),
                            'like_count': media_info['metadata'].get('like_count', 0),
                            'comment_count': media_info['metadata'].get('comment_count', 0),
                            'timestamp': media_info['metadata'].get('timestamp', int(datetime.now().timestamp())),
                            'description': media_info.get('description', ''),
                            'duration': media_info['metadata'].get('duration', 0)
                        })
                    )

                    # Log successful save
                    logger.info(f"Saved Instagram media to database: {media_info['title']}")

                    # Cache the media info
                    if not instagram_cache.cache_media(url, session['user']['id'], media_info):
                        logger.warning(f"Failed to cache media for URL: {url}")
                    else:
                        logger.info(f"Successfully downloaded and cached: {url}")

                    # Log the file paths for debugging
                    logger.info(f"File path: {filename}")
                    logger.info(f"Relative path: {relative_path}")
                    logger.info(f"Media info: {media_info}")

                    return render_template('instagram_results.html',
                        content={
                            'username': media_info['metadata']['uploader'],
                            'posts': [{
                                'type': 'video',
                                'caption': media_info.get('description', ''),
                                'likes': media_info['metadata'].get('like_count', 0),
                                'comments': media_info['metadata'].get('comment_count', 0),
                                'date': datetime.fromtimestamp(media_info['metadata'].get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                                'filename': filename.name,
                                'shortcode': shortcode,
                                'extension': 'mp4'
                            }]
                        }
                    )
                except Exception as e:
                    logger.error(f"Error during download: {str(e)}")
                    raise

        except Exception as e:
            logger.warning(f"yt-dlp download failed: {str(e)}")
            return jsonify({
                'error': str(e),
                'message': 'Failed to download Instagram content. Please check the URL and try again.'
            }), 500

    except Exception as e:
        logger.error(f"Instagram download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to download Instagram content. Please check the URL and try again.'
        }), 500

@instagram_bp.route('/get-instagram-auth-url')
def get_instagram_auth_url():
    """Generate Instagram OAuth URL using Facebook Login."""
    try:
        # Use a fixed redirect URI that matches what's registered in Facebook Developer Console
        redirect_uri = url_for('instagram.instagram_callback', _external=True)

        # Log the redirect URI for debugging
        logger.info(f"Using Instagram redirect URI: {redirect_uri}")

        # Store the return URL in session for later use
        session['instagram_callback_return_url'] = session.get('instagram_auth_return_url')

        # Get client ID from environment variables
        client_id = os.getenv('INSTAGRAM_CLIENT_ID')

        if not client_id:
            logger.error("Missing Instagram client ID in environment variables")
            return jsonify({'error': 'Missing Instagram client ID'}), 500

        # Generate state parameter to prevent CSRF
        state = secrets.token_hex(16)
        session['instagram_oauth_state'] = state

        # Build authorization URL - Using Facebook's OAuth endpoint for Instagram API
        auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={client_id}&redirect_uri={redirect_uri}&scope={','.join(INSTAGRAM_SCOPES)}&response_type=code&state={state}"

        return jsonify({
            'auth_url': auth_url
        })

    except Exception as e:
        logger.error(f"Error generating Instagram auth URL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@instagram_bp.route('/debug-env')
def debug_env():
    """Debug route to check environment variables and Instagram API configuration."""
    client_id = os.getenv('INSTAGRAM_CLIENT_ID')
    client_secret = os.getenv('INSTAGRAM_CLIENT_SECRET')

    # Check for whitespace in credentials
    client_id_has_whitespace = client_id and (client_id.strip() != client_id)
    client_secret_has_whitespace = client_secret and (client_secret.strip() != client_secret)

    # Get lengths
    client_id_length = len(client_id) if client_id else 0
    client_secret_length = len(client_secret) if client_secret else 0

    # Create masked versions
    masked_id = client_id[:4] + '*' * (len(client_id) - 8) + client_id[-4:] if client_id and len(client_id) > 8 else 'Not set'
    masked_secret = client_secret[:4] + '*' * (len(client_secret) - 8) + client_secret[-4:] if client_secret and len(client_secret) > 8 else 'Not set'

    # Check if .env file exists and read its contents
    env_file_exists = os.path.exists('.env')
    env_file_contents = None
    if env_file_exists:
        try:
            with open('.env', 'r') as f:
                env_lines = f.readlines()
                # Mask sensitive information
                masked_lines = []
                for line in env_lines:
                    if line.startswith('INSTAGRAM_CLIENT_ID='):
                        parts = line.split('=', 1)
                        if len(parts) > 1 and len(parts[1].strip()) > 8:
                            value = parts[1].strip()
                            masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:]
                            masked_lines.append(f"{parts[0]}={masked_value}\n")
                        else:
                            masked_lines.append(line)
                    elif line.startswith('INSTAGRAM_CLIENT_SECRET='):
                        parts = line.split('=', 1)
                        if len(parts) > 1 and len(parts[1].strip()) > 8:
                            value = parts[1].strip()
                            masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:]
                            masked_lines.append(f"{parts[0]}={masked_value}\n")
                        else:
                            masked_lines.append(line)
                    else:
                        masked_lines.append(line)
                env_file_contents = ''.join(masked_lines)
        except Exception as e:
            env_file_contents = f"Error reading .env file: {str(e)}"

    # Get all environment variables that start with INSTAGRAM_
    instagram_vars = {k: v[:4] + '****' + v[-4:] if len(v) > 8 else '****'
                     for k, v in os.environ.items()
                     if k.startswith('INSTAGRAM_')}

    # Get the redirect URI
    redirect_uri = url_for('instagram.instagram_callback', _external=True)

    # Get the auth URL for testing
    auth_url = None
    try:
        if client_id:
            state = secrets.token_hex(16)
            auth_url = f"https://www.facebook.com/v19.0/dialog/oauth?client_id={client_id}&redirect_uri={redirect_uri}&scope={','.join(INSTAGRAM_SCOPES)}&response_type=code&state={state}"
    except Exception as e:
        auth_url = f"Error generating auth URL: {str(e)}"

    return jsonify({
        'instagram_client_id': masked_id,
        'instagram_client_secret': masked_secret,
        'client_id_length': client_id_length,
        'client_secret_length': client_secret_length,
        'client_id_has_whitespace': client_id_has_whitespace,
        'client_secret_has_whitespace': client_secret_has_whitespace,
        'env_file_exists': env_file_exists,
        'env_file_contents': env_file_contents,
        'all_instagram_vars': instagram_vars,
        'redirect_uri': redirect_uri,
        'instagram_scopes': INSTAGRAM_SCOPES,
        'auth_url': auth_url,
        'api_version': 'Instagram API with Facebook Login (for professional accounts)',
        'requirements': [
            'Instagram account must be a Business or Creator account',
            'Instagram account must be connected to a Facebook Page',
            'App must be approved for instagram_basic permission',
            'Redirect URI must be registered in Facebook Developer Console'
        ],
        'troubleshooting_steps': [
            'Verify your Instagram account is a Business or Creator account',
            'Ensure your Instagram account is connected to a Facebook Page',
            'Check that your app is approved for the required permissions',
            'Verify the redirect URI matches exactly what is registered in Facebook Developer Console',
            'Make sure your app is in Live mode, not Development mode',
            'Check for whitespace in your client ID and secret',
            'Ensure your client secret is correct and matches what is in the Facebook Developer Console'
        ],
        'note': 'Sensitive information is masked for security'
    })

@instagram_bp.route(INSTAGRAM_CALLBACK_ROUTE)
def instagram_callback():
    """Handle OAuth callback from Instagram API with Facebook Login."""
    try:
        # Get the authorization code from the request
        code = request.args.get('code')
        if not code:
            logger.error("No authorization code received")
            return render_template('instagram_auth_result.html', success=False, message="No authorization code received")

        # Verify state parameter to prevent CSRF
        state = request.args.get('state')
        stored_state = session.get('instagram_oauth_state')

        if not state or not stored_state or state != stored_state:
            logger.error(f"State parameter mismatch")
            return render_template('instagram_auth_result.html', success=False, message="Invalid state parameter. Please try the authentication again.")

        # Clear the stored state after verification
        session.pop('instagram_oauth_state', None)

        # Use a fixed redirect URI that matches what's registered in Facebook Developer Console
        redirect_uri = url_for('instagram.instagram_callback', _external=True)

        # Get client ID and secret from environment variables
        client_id = os.getenv('INSTAGRAM_CLIENT_ID')
        client_secret = os.getenv('INSTAGRAM_CLIENT_SECRET')

        if not client_id or not client_secret:
            logger.error("Missing Instagram client credentials in environment variables")
            return render_template('instagram_auth_result.html', success=False, message="Missing Instagram client credentials")

        # Exchange code for token using Facebook's Graph API v18.0
        token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        token_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'code': code,
            'grant_type': 'authorization_code'
        }

        logger.info("Exchanging code for token")
        response = requests.post(token_url, data=token_data)

        if response.status_code != 200:
            error_message = response.text
            logger.error(f"Error exchanging code for token: {error_message}")
            return render_template('instagram_auth_result.html', success=False,
                                message=f"Error exchanging code for token: {error_message}")

        token_info = response.json()
        logger.info("Successfully received access token")

        # Get user's Instagram business accounts
        user_accounts_url = "https://graph.facebook.com/v18.0/me/accounts"
        user_accounts_params = {
            'access_token': token_info['access_token']
        }

        accounts_response = requests.get(user_accounts_url, params=user_accounts_params)
        if accounts_response.status_code != 200:
            logger.error(f"Error getting user accounts: {accounts_response.text}")
            return render_template('instagram_auth_result.html', success=False,
                                message=f"Error getting Facebook pages: {accounts_response.text}")

        accounts_info = accounts_response.json()

        # Check if we have any pages
        if not accounts_info.get('data') or len(accounts_info.get('data', [])) == 0:
            logger.error("No Facebook pages found for this user")
            return render_template('instagram_auth_result.html', success=False,
                                message="No Facebook pages found. Your Instagram business account must be connected to a Facebook page.")

        # Find Instagram business account
        instagram_business_account = None
        page_access_token = None
        page_id = None
        page_name = None

        for page in accounts_info.get('data', []):
            page_id = page.get('id')
            page_name = page.get('name')
            page_access_token = page.get('access_token')

            # Get Instagram business account ID for this page
            instagram_account_url = f"https://graph.facebook.com/v18.0/{page_id}"
            instagram_account_params = {
                'fields': 'instagram_business_account',
                'access_token': page_access_token
            }

            ig_response = requests.get(instagram_account_url, params=instagram_account_params)
            if ig_response.status_code == 200:
                ig_data = ig_response.json()
                if 'instagram_business_account' in ig_data:
                    instagram_business_account = ig_data['instagram_business_account']['id']
                    break

        if not instagram_business_account:
            logger.error("No Instagram business account found")
            return render_template('instagram_auth_result.html', success=False,
                                message="No Instagram business account found. Please make sure your Instagram account is a Business or Creator account and is connected to a Facebook Page.")

        # Get Instagram account details for confirmation
        instagram_details_url = f"https://graph.facebook.com/v18.0/{instagram_business_account}"
        instagram_details_params = {
            'fields': 'username,profile_picture_url',
            'access_token': page_access_token
        }

        ig_details_response = requests.get(instagram_details_url, params=instagram_details_params)
        instagram_username = "Unknown"

        if ig_details_response.status_code == 200:
            ig_details = ig_details_response.json()
            instagram_username = ig_details.get('username', 'Unknown')
            logger.info(f"Connected to Instagram business account: {instagram_username}")

        # Store the credentials
        credentials = {
            'access_token': page_access_token,
            'user_id': instagram_business_account,
            'page_id': page_id,
            'page_name': page_name,
            'instagram_username': instagram_username,
            'fb_access_token': token_info['access_token'],
            'expires_in': token_info.get('expires_in', 0)
        }

        # Store in auth manager
        try:
            user_id = session.get('user', {}).get('id', 'anonymous')
            auth_manager = get_auth_manager(user_id)
            auth_manager.store_credentials('instagram', credentials)
            logger.info(f"Stored Instagram credentials for user {user_id}")
        except Exception as e:
            logger.error(f"Error storing Instagram credentials in auth manager: {str(e)}")
            return render_template('instagram_auth_result.html', success=False, message=f"Error storing credentials: {str(e)}")

        # Check if we have a return URL in the session
        return_url = session.pop('instagram_callback_return_url', None)
        if return_url:
            return redirect(return_url)

        # Otherwise, show a success message
        return render_template('instagram_auth_result.html', success=True,
                            message=f"Successfully connected Instagram business account: {instagram_username}")

    except Exception as e:
        logger.error(f"Error in Instagram OAuth callback: {str(e)}")
        return render_template('instagram_auth_result.html', success=False, message=f"Authentication error: {str(e)}")

@instagram_bp.route('/get-instagram-redirect-uri')
def get_instagram_redirect_uri():
    """Display the redirect URI for registration in Meta Developer Console."""
    redirect_uri = url_for('instagram.instagram_callback', _external=True)
    return jsonify({
        'redirect_uri': redirect_uri,
        'oauth_callback_route': INSTAGRAM_CALLBACK_ROUTE,
        'instructions': 'You must add this exact URI in TWO places in your Meta Developer Console',
        'meta_developer_console_link': 'https://developers.facebook.com/apps/',
        'api_type': 'Instagram API with Facebook Login',
        'required_permissions': INSTAGRAM_SCOPES,
        'redirect_uri_locations': [
            {
                'name': 'Basic Settings',
                'path': 'Settings > Basic > OAuth Settings > Valid OAuth Redirect URIs',
                'uri': redirect_uri,
                'notes': [
                    'Must match exactly (including http/https)',
                    'No trailing slashes',
                    'Domain must match your app settings'
                ]
            },
            {
                'name': 'Instagram Basic Display',
                'path': 'Products > Instagram Basic Display > Basic Display > Client OAuth Settings',
                'uri': redirect_uri,
                'notes': [
                    'Must match Basic Settings URI',
                    'Required for Instagram API access'
                ]
            }
        ],
        'setup_steps': [
            {
                'title': '1. Configure Basic Settings',
                'steps': [
                    'Go to Meta Developer Console',
                    'Select your app',
                    'Go to Settings > Basic',
                    'Under "OAuth Settings", add the redirect URI',
                    'Save Changes'
                ]
            },
            {
                'title': '2. Configure Instagram Basic Display',
                'steps': [
                    'Go to Products > Instagram Basic Display',
                    'Click "Basic Display" in the left menu',
                    'Under "Client OAuth Settings", add the same redirect URI',
                    'Enable required permissions',
                    'Save Changes'
                ]
            },
            {
                'title': '3. Verify App Settings',
                'steps': [
                    'Ensure app is in Live mode',
                    'Verify App Domain matches redirect URI domain',
                    'Check that Privacy Policy URL is set',
                    'Verify User Data Deletion callback URL is set'
                ]
            }
        ],
        'required_app_settings': {
            'app_domains': ['localhost'],
            'privacy_policy_url': 'Required for app review',
            'app_mode': 'Live mode required',
            'business_verification': 'Required for some permissions'
        },
        'troubleshooting': [
            'URIs must match exactly in both locations',
            'Check for any whitespace in the URIs',
            'Verify app is in Live mode',
            'Ensure all required app settings are configured',
            'Verify client ID and secret are correct',
            'Check that your Instagram account is a Business/Creator account',
            'Verify Instagram account is connected to a Facebook Page'
        ]
    })