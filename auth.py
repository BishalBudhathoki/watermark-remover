from functools import wraps
from flask import request, jsonify, session, redirect, url_for
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    supabase_url=os.getenv('SUPABASE_URL'),
    supabase_key=os.getenv('SUPABASE_KEY')
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            # Check for session-based authentication
            if not session.get('user'):
                return jsonify({"error": "Authentication required"}), 401
            return f(*args, **kwargs)
            
        try:
            # Extract token from Bearer header
            token = auth_header.split(' ')[1]
            
            # Verify token with Supabase
            user = supabase.auth.get_user(token)
            
            # Store user in request context
            request.user = user
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return jsonify({"error": "Invalid authentication token"}), 401
            
    return decorated_function

def register_user(email: str, password: str, username: str = None):
    """Register a new user with Supabase Auth."""
    try:
        # Register user with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "username": username,
                    "display_name": username,
                    "email": email,
                    "email_confirmed": False
                }
            }
        })
        
        if not auth_response.user:
            raise Exception("Failed to create user account")

        # Store initial session data
        if auth_response.session:
            session['user'] = {
                'id': auth_response.user.id,
                'email': email,
                'username': username,
                'access_token': auth_response.session.access_token,
                'email_confirmed': False
            }
        
        return auth_response
            
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise Exception(str(e))

def confirm_email(user_id: str, email: str):
    """Confirm a user's email address."""
    try:
        # Update user metadata in Supabase
        response = supabase.auth.admin.update_user_by_id(
            user_id,
            {
                "user_metadata": {
                    "email_confirmed": True
                }
            }
        )
        
        if response.user:
            # Update session if user is logged in
            if 'user' in session:
                session['user']['email_confirmed'] = True
            
            return True
            
    except Exception as e:
        logger.error(f"Email confirmation error: {str(e)}")
        return False

def login_user(email: str, password: str):
    """Login a user with Supabase Auth."""
    try:
        # Authenticate user with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Get username from user metadata
            username = (auth_response.user.user_metadata.get('username') 
                      or auth_response.user.email.split('@')[0])
            
            # Store user session
            session['user'] = {
                'id': auth_response.user.id,
                'email': auth_response.user.email,
                'access_token': auth_response.session.access_token,
                'username': username
            }
            
            return auth_response
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise Exception(str(e))

def logout_user():
    """Logout the current user."""
    try:
        # Clear Supabase session
        supabase.auth.sign_out()
        
        # Clear Flask session
        session.pop('user', None)
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise Exception(f"Logout failed: {str(e)}")

def get_current_user():
    """Get the current authenticated user."""
    try:
        if session.get('user'):
            return session['user']
            
        auth_header = request.headers.get('Authorization')
        if auth_header:
            token = auth_header.split(' ')[1]
            return supabase.auth.get_user(token)
            
        return None
        
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None 