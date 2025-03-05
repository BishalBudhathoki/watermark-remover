"""
Social Media Authentication Routes

This module provides routes for authenticating with various social media platforms.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
import os
import logging
import json
import requests
from urllib.parse import urlencode
import secrets
import time
from pathlib import Path
import hashlib
import base64

# Import from content_pipeline
from content_pipeline.poster.auth import get_auth_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import from app
from app.auth import login_required

# Create blueprint
social_auth_bp = Blue# # print('social_auth', __name__, url_prefix='/social-auth')

# Platform configurations
PLATFORM_CONFIGS = {
    'tiktok': {
        'name': 'TikTok',
        'auth_url': 'https://www.tiktok.com/v2/auth/authorize/',
        'token_url': 'https://open-api.tiktok.com/v2/oauth/token/',
        'scope': 'user.info.basic,video.upload,video.list',
        'icon': 'fab fa-tiktok',
        'sandbox': True,  # Enable sandbox mode
        'api_version': 'v2'  # Specify API version
    },
    'instagram': {
        'name': 'Instagram',
        'auth_url': 'https://www.facebook.com/v18.0/dialog/oauth',  # Facebook OAuth dialog
        'token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',  # Graph API token endpoint
        'scope': 'instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,instagram_manage_insights',  # Required scopes
        'icon': 'fab fa-instagram',
        'api_version': 'v18.0',  # Latest stable version of Graph API
        'requires_facebook': True,  # Flag to indicate Facebook Page requirement
        'business_account_required': True,  # Flag to indicate business account requirement
        'graph_api_base': 'https://graph.facebook.com/v18.0',  # Base URL for Graph API calls
        'debug_mode': True  # Enable debug mode for detailed error messages
    },
    'youtube': {
        'name': 'YouTube',
        'auth_url': 'https://accounts.google.com/o/oauth2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'scope': 'https://www.googleapis.com/auth/youtube.upload',
        'icon': 'fab fa-youtube'
    }
}


@social_auth_bp.route('/', methods=['GET'])
@login_required
def index():
    """Render the social media authentication dashboard."""
    user_id = session.get('user_id', 'anonymous')
    auth_manager = get_auth_manager(user_id)

    # Check authentication status for each platform
    platform_status = {}
    for platform in PLATFORM_CONFIGS:
        platform_status[platform] = {
            'authenticated': auth_manager.is_authenticated(platform),
            'name': PLATFORM_CONFIGS[platform]['name'],
            'icon': PLATFORM_CONFIGS[platform]['icon']
        }

    return render_template('social_auth/index.html', platforms=platform_status)


def generate_code_verifier():
    """Generate a code verifier for PKCE."""
    token = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(token).rstrip(b'=').decode('utf-8')

def generate_code_challenge(verifier):
    """Generate a code challenge for PKCE."""
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(sha256_hash).rstrip(b'=').decode('utf-8')

@social_auth_bp.route('/login/<platform>', methods=['GET'])
@login_required
def login(platform):
    """Initiate OAuth flow for the specified platform."""
    logger.info(f"Starting OAuth flow for platform: {platform}")

    if platform not in PLATFORM_CONFIGS:
        flash(f'Unsupported platform: {platform}', 'error')
        return redirect(url_for('social_auth.index'))

    config = PLATFORM_CONFIGS[platform]

    # Generate CSRF state token for all platforms
    csrf_state = secrets.token_hex(16)
    session[f'{platform}_oauth_state'] = csrf_state
    logger.info(f"Generated CSRF state for {platform}: {csrf_state[:4]}...")

    if platform == 'tiktok':
        # Validate TikTok client key
        client_key = os.getenv('TIKTOK_CLIENT_KEY')
        logger.info(f"TikTok client key from env: {'*' * 4 + client_key[-4:] if client_key else 'None'}")

        if not client_key:
            flash('Missing TikTok client key. Please configure the application.', 'error')
            logger.error("TikTok client key not found in environment variables")
            return redirect(url_for('social_auth.index'))

        # Generate PKCE code verifier and challenge
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)

        # Store code verifier in session for later use
        session[f'{platform}_code_verifier'] = code_verifier

        # Get the redirect URI - must be HTTPS in production
        redirect_uri = os.getenv('TIKTOK_REDIRECT_URI')
        if not redirect_uri:
            redirect_uri = url_for('social_auth.callback', platform=platform, _external=True)

        logger.info(f"Using redirect URI: {redirect_uri}")

        if not redirect_uri.startswith('https://') and not 'localhost' in redirect_uri:
            flash('TikTok requires HTTPS redirect URI in production', 'error')
            return redirect(url_for('social_auth.index'))

        # Build TikTok authorization URL with required parameters
        params = {
            'client_key': client_key,
            'response_type': 'code',
            'scope': config['scope'],
            'redirect_uri': redirect_uri,
            'state': csrf_state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }

        # Add sandbox-specific parameters if in sandbox mode
        if config.get('sandbox'):
            params.update({
                'aid': 'dev',  # Developer mode identifier
                'sdk_version': '2',  # SDK version for sandbox
                'platform': 'web'  # Platform identifier
            })

        logger.info(f"TikTok auth redirect URI: {redirect_uri}")
        logger.info(f"TikTok auth params (client_key masked): {dict(params, client_key='*' * 8)}")

        # Ensure session is saved before redirect
        session.modified = True

        auth_url = f"{config['auth_url']}?{urlencode(params)}"
        logger.info(f"Redirecting to TikTok auth URL: {auth_url}")
        return redirect(auth_url)

    elif platform == 'instagram':
        try:
            # Get Facebook App ID and Secret
            client_id = os.getenv('FACEBOOK_APP_ID')  # Using Facebook App credentials
            logger.info(f"Facebook App ID from env: {'*' * 4 + client_id[-4:] if client_id else 'None'}")

            if not client_id:
                error_msg = 'Missing Facebook App ID. Please configure the application.'
                logger.error(error_msg)
                flash(error_msg, 'error')
                return redirect(url_for('social_auth.index'))

            # Build redirect URI with _external=True and scheme=https
            redirect_uri = url_for('social_auth.callback', platform=platform, _external=True, _scheme='https')
            logger.info(f"Instagram auth redirect URI: {redirect_uri}")

            # Build authorization URL with Graph API parameters
            params = {
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'response_type': 'code',
                'scope': config['scope'],
                'state': csrf_state,
                'display': 'page'  # Force full-page display
            }

            auth_url = f"{config['auth_url']}?{urlencode(params)}"
            logger.info(f"Full Instagram auth URL (masked client_id): {auth_url.replace(client_id, '*' * 8)}")

            # Ensure session is saved before redirect
            session.modified = True

            return redirect(auth_url)

        except Exception as e:
            error_msg = f"Error initiating Instagram auth: {str(e)}"
            logger.error(error_msg)
            flash(error_msg, 'error')
            return redirect(url_for('social_auth.index'))

    else:
        # Get client ID from environment variables
        client_id = os.getenv(f'{platform.upper()}_CLIENT_ID')
        if not client_id:
            flash(f'Missing client ID for {PLATFORM_CONFIGS[platform]["name"]}. Please configure the application.', 'error')
            return redirect(url_for('social_auth.index'))

        # Build redirect URI
        redirect_uri = url_for('social_auth.callback', platform=platform, _external=True)

        # Build authorization URL
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': config['scope'],
            'state': csrf_state
        }

        # Add platform-specific parameters
        if platform == 'youtube':
            params['access_type'] = 'offline'
            params['prompt'] = 'consent'

        auth_url = f"{config['auth_url']}?{urlencode(params)}"
        logger.info(f"Redirecting to {platform} auth URL: {auth_url}")
        return redirect(auth_url)


@social_auth_bp.route('/callback/<platform>', methods=['GET'])
@login_required
def callback(platform):
    """Handle OAuth callback for the specified platform."""
    if platform not in PLATFORM_CONFIGS:
        flash(f'Unsupported platform: {platform}', 'error')
        return redirect(url_for('social_auth.index'))

    # Get authorization code
    code = request.args.get('code')
    if not code:
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        if error:
            error_msg = f"Auth error: {error}"
            if error_description:
                error_msg += f" - {error_description}"
            flash(error_msg, 'error')
            logger.error(f"Auth error: {error_msg}")
        else:
            flash('No authorization code received', 'error')
        return redirect(url_for('social_auth.index'))

    # Verify state parameter to prevent CSRF
    state = request.args.get('state')
    stored_state = session.pop(f'{platform}_oauth_state', None)
    if not state or state != stored_state:
        flash('Invalid state parameter - possible CSRF attack', 'error')
        return redirect(url_for('social_auth.index'))

    try:
        if platform == 'tiktok':
            # Validate TikTok credentials
            client_key = os.getenv('TIKTOK_CLIENT_KEY')
            client_secret = os.getenv('TIKTOK_CLIENT_SECRET')
            if not client_key or not client_secret:
                raise Exception('Missing TikTok credentials. Please check your environment variables.')

            # Get the redirect URI
            redirect_uri = url_for('social_auth.callback', platform=platform, _external=True)

            # Get stored code verifier
            code_verifier = session.pop(f'{platform}_code_verifier', None)
            if not code_verifier:
                raise Exception('Code verifier not found in session')

            # Exchange code for access token
            token_params = {
                'client_key': client_key,  # Use validated client key
                'client_secret': client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
                'code_verifier': code_verifier
            }

            logger.info(f"TikTok token exchange params (credentials masked): {dict(token_params, client_key='*' * 8, client_secret='*' * 8)}")

            # Make token request
            response = requests.post(
                PLATFORM_CONFIGS[platform]['token_url'],
                data=token_params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            logger.info(f"TikTok token response status: {response.status_code}")
            response.raise_for_status()

            token_data = response.json()
            if 'error' in token_data:
                error_msg = token_data.get('error', 'Unknown error')
                error_description = token_data.get('error_description', '')
                if error_description:
                    error_msg += f" - {error_description}"
                raise Exception(error_msg)

            # Store credentials
            credentials = {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'open_id': token_data.get('open_id'),
                'expires_in': token_data.get('expires_in'),
                'refresh_expires_in': token_data.get('refresh_expires_in'),
                'scope': request.args.get('scopes', PLATFORM_CONFIGS[platform]['scope'])  # Get granted scopes from callback
            }

            # Store credentials using auth manager
            auth_manager = get_auth_manager(session['user']['id'])
            auth_manager.store_credentials(platform, credentials)

            flash(f'Successfully connected to {platform.capitalize()}!', 'success')
            return redirect(url_for('social_auth.index'))

        elif platform == 'instagram':
            # Get Facebook credentials
            client_id = os.getenv('FACEBOOK_APP_ID')
            client_secret = os.getenv('FACEBOOK_APP_SECRET')
            if not client_id or not client_secret:
                raise Exception('Missing Facebook credentials. Please check your environment variables.')

            # Get the redirect URI
            redirect_uri = url_for('social_auth.callback', platform=platform, _external=True)

            # Exchange code for access token
            token_params = {
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }

            # Make token request to Graph API
            response = requests.get(
                PLATFORM_CONFIGS[platform]['token_url'],
                params=token_params
            )

            logger.info(f"Instagram token response status: {response.status_code}")
            response.raise_for_status()

            token_data = response.json()
            if 'error' in token_data:
                error_msg = token_data.get('error', {}).get('message', 'Unknown error')
                raise Exception(error_msg)

            # Get long-lived token
            long_lived_token_params = {
                'grant_type': 'fb_exchange_token',
                'client_id': client_id,
                'client_secret': client_secret,
                'fb_exchange_token': token_data['access_token']
            }

            response = requests.get(
                f"https://graph.facebook.com/{PLATFORM_CONFIGS[platform]['api_version']}/oauth/access_token",
                params=long_lived_token_params
            )

            response.raise_for_status()
            long_lived_token_data = response.json()

            # Get connected Instagram Business Account ID
            accounts_response = requests.get(
                f"https://graph.facebook.com/{PLATFORM_CONFIGS[platform]['api_version']}/me/accounts",
                params={'access_token': long_lived_token_data['access_token']}
            )

            accounts_data = accounts_response.json()
            if not accounts_data.get('data'):
                flash('Warning: No Facebook Page found. To post content via API, you need to create a Facebook Page and connect it to your Instagram Business Account.', 'warning')
                logger.warning('No Facebook Pages found. Some API features may be limited.')
                facebook_page_id = None
            else:
                facebook_page_id = accounts_data['data'][0]['id']

            # Store credentials
            credentials = {
                'access_token': long_lived_token_data['access_token'],
                'token_type': long_lived_token_data.get('token_type', 'bearer'),
                'expires_in': long_lived_token_data.get('expires_in'),
                'facebook_page_id': facebook_page_id,
                'scope': token_data.get('scope', PLATFORM_CONFIGS[platform]['scope'])
            }

            # Store credentials using auth manager
            auth_manager = get_auth_manager(session['user']['id'])
            auth_manager.store_credentials(platform, credentials)

            flash(f'Successfully connected to {platform.capitalize()}!', 'success')
            return redirect(url_for('social_auth.index'))

        else:
            # Get client ID from environment variables
            client_id = os.getenv(f'{platform.upper()}_CLIENT_ID')
            if not client_id:
                flash(f'Missing client ID for {PLATFORM_CONFIGS[platform]["name"]}. Please configure the application.', 'error')
                return redirect(url_for('social_auth.index'))

            # Build redirect URI
            redirect_uri = url_for('social_auth.callback', platform=platform, _external=True)

            # Build authorization URL
            params = {
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'response_type': 'code',
                'scope': PLATFORM_CONFIGS[platform]['scope'],
                'state': csrf_state
            }

            # Add platform-specific parameters
            if platform == 'youtube':
                params['access_type'] = 'offline'
                params['prompt'] = 'consent'

            auth_url = f"{PLATFORM_CONFIGS[platform]['auth_url']}?{urlencode(params)}"
            logger.info(f"Redirecting to {platform} auth URL: {auth_url}")
            return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error in {platform} callback: {str(e)}")
        flash(f'Authentication error: {str(e)}', 'error')

    return redirect(url_for('social_auth.index'))


@social_auth_bp.route('/logout/<platform>', methods=['POST'])
@login_required
def logout(platform):
    """Remove authentication for a social media platform."""
    if platform not in PLATFORM_CONFIGS:
        flash(f'Unsupported platform: {platform}', 'error')
        return redirect(url_for('social_auth.index'))

    # Get platform config
    config = PLATFORM_CONFIGS[platform]

    # Remove credentials
    user_id = session.get('user_id', 'anonymous')
    auth_manager = get_auth_manager(user_id)

    if auth_manager.remove_credentials(platform):
        flash(f'Successfully logged out from {config["name"]}', 'success')
    else:
        flash(f'Failed to log out from {config["name"]}', 'error')

    return redirect(url_for('social_auth.index'))


@social_auth_bp.route('/status/<platform>', methods=['GET'])
@login_required
def status(platform):
    """Check authentication status for a social media platform."""
    if platform not in PLATFORM_CONFIGS:
        return jsonify({'error': f'Unsupported platform: {platform}'}), 400

    # Check authentication status
    user_id = session.get('user_id', 'anonymous')
    auth_manager = get_auth_manager(user_id)

    authenticated = auth_manager.is_authenticated(platform)

    return jsonify({
        'platform': platform,
        'authenticated': authenticated,
        'name': PLATFORM_CONFIGS[platform]['name']
    })


def process_token_response(platform, token_info):
    """
    Process platform-specific token response format.

    Args:
        platform: Name of the platform
        token_info: Token response from the platform

    Returns:
        Dictionary containing standardized credentials
    """
    if platform == 'tiktok':
        # TikTok returns data in a nested structure
        data = token_info.get('data', {})
        return {
            'access_token': data.get('access_token'),
            'refresh_token': data.get('refresh_token'),
            'open_id': data.get('open_id'),
            'expires_in': data.get('expires_in'),
            'scope': data.get('scope')
        }

    elif platform == 'instagram':
        # Instagram returns a flat structure
        return {
            'access_token': token_info.get('access_token'),
            'user_id': token_info.get('user_id')
        }

    elif platform == 'youtube':
        # YouTube (Google) returns a flat structure
        return {
            'access_token': token_info.get('access_token'),
            'refresh_token': token_info.get('refresh_token'),
            'expires_in': token_info.get('expires_in'),
            'token_type': token_info.get('token_type'),
            'scope': token_info.get('scope')
        }

    # Default case
    return token_info