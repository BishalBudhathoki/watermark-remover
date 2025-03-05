"""
Authentication Module for Social Media Platforms.

This module handles user authentication for various social media platforms,
securely storing and managing credentials and sessions.
"""

import os
import json
import logging
import secrets
import time
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
AUTH_DIR = Path(os.path.expanduser("~/.content_pipeline/auth"))
SALT_FILE = AUTH_DIR / "salt"
KEY_FILE = AUTH_DIR / "key"
SESSION_EXPIRY = 30  # Days


class AuthManager:
    """Manages authentication for social media platforms."""

    def __init__(self, user_id: str):
        """
        Initialize the AuthManager.

        Args:
            user_id: Unique identifier for the user
        """
        self.user_id = user_id
        self.auth_dir = AUTH_DIR / user_id
        self.auth_dir.mkdir(parents=True, exist_ok=True)

        # Initialize encryption
        self._init_encryption()

    def _init_encryption(self):
        """Initialize encryption for secure storage of credentials."""
        # Create salt if it doesn't exist
        if not SALT_FILE.exists():
            salt = os.urandom(16)
            with open(SALT_FILE, 'wb') as f:
                f.write(salt)
        else:
            with open(SALT_FILE, 'rb') as f:
                salt = f.read()

        # Create key if it doesn't exist
        if not KEY_FILE.exists():
            # Generate a random password for the key
            password = secrets.token_bytes(32)

            # Derive a key from the password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))

            # Save the key
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
        else:
            with open(KEY_FILE, 'rb') as f:
                key = f.read()

        self.cipher = Fernet(key)

    def _get_platform_file(self, platform: str) -> Path:
        """Get the path to the platform credentials file."""
        return self.auth_dir / f"{platform}.json"

    def is_authenticated(self, platform: str) -> bool:
        """
        Check if the user is authenticated for a platform.

        Args:
            platform: Name of the platform

        Returns:
            True if authenticated and session is valid, False otherwise
        """
        platform_file = self._get_platform_file(platform)

        if not platform_file.exists():
            return False

        try:
            creds = self.get_credentials(platform)
            if not creds:
                return False

            # Check if session is expired
            if "expiry" in creds:
                expiry = datetime.fromisoformat(creds["expiry"])
                if expiry < datetime.now():
                    logger.info(f"Session for {platform} has expired")
                    return False

            return True
        except Exception as e:
            logger.error(f"Error checking authentication for {platform}: {str(e)}")
            return False

    def store_credentials(self, platform: str, credentials: Dict[str, Any]) -> bool:
        """
        Store credentials for a platform.

        Args:
            platform: Name of the platform
            credentials: Dictionary containing platform-specific credentials

        Returns:
            True if successful, False otherwise
        """
        platform_file = self._get_platform_file(platform)

        try:
            # Add expiry date
            credentials["expiry"] = (datetime.now() + timedelta(days=SESSION_EXPIRY)).isoformat()

            # Encrypt credentials
            encrypted_data = self.cipher.encrypt(json.dumps(credentials).encode())

            # Save to file
            with open(platform_file, 'wb') as f:
                f.write(encrypted_data)

            logger.info(f"Stored credentials for {platform}")
            return True
        except Exception as e:
            logger.error(f"Error storing credentials for {platform}: {str(e)}")
            return False

    def get_credentials(self, platform: str) -> Optional[Dict[str, Any]]:
        """
        Get credentials for a platform.

        Args:
            platform: Name of the platform

        Returns:
            Dictionary containing platform-specific credentials, or None if not found
        """
        platform_file = self._get_platform_file(platform)

        if not platform_file.exists():
            return None

        try:
            # Read encrypted data
            with open(platform_file, 'rb') as f:
                encrypted_data = f.read()

            # Decrypt data
            decrypted_data = self.cipher.decrypt(encrypted_data)

            # Parse JSON
            credentials = json.loads(decrypted_data.decode())

            return credentials
        except Exception as e:
            logger.error(f"Error getting credentials for {platform}: {str(e)}")
            return None

    def remove_credentials(self, platform: str) -> bool:
        """
        Remove credentials for a platform.

        Args:
            platform: Name of the platform

        Returns:
            True if successful, False otherwise
        """
        platform_file = self._get_platform_file(platform)

        if not platform_file.exists():
            return True

        try:
            platform_file.unlink()
            logger.info(f"Removed credentials for {platform}")
            return True
        except Exception as e:
            logger.error(f"Error removing credentials for {platform}: {str(e)}")
            return False

    def update_session(self, platform: str, session_data: Dict[str, Any]) -> bool:
        """
        Update session data for a platform.

        Args:
            platform: Name of the platform
            session_data: Dictionary containing updated session data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing credentials
            credentials = self.get_credentials(platform)
            if not credentials:
                return False

            # Update session data
            credentials.update(session_data)

            # Update expiry
            credentials["expiry"] = (datetime.now() + timedelta(days=SESSION_EXPIRY)).isoformat()

            # Store updated credentials
            return self.store_credentials(platform, credentials)
        except Exception as e:
            logger.error(f"Error updating session for {platform}: {str(e)}")
            return False


# Factory function to get an AuthManager instance
def get_auth_manager(user_id: str) -> AuthManager:
    """
    Get an AuthManager instance for a user.

    Args:
        user_id: Unique identifier for the user

    Returns:
        AuthManager instance
    """
    return AuthManager(user_id)