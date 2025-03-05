import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
from app import create_app
from flask.sessions import SecureCookieSessionInterface
from app.services.cache import MediaCache
from app.utils.path import DOWNLOAD_DIR

DOWNLOAD_DIR = Path('/tmp/test_downloads')

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SESSION_TYPE'] = None  # Use Flask's default session
    app.session_interface = SecureCookieSessionInterface()  # Use Flask's default session interface
    app.config['DOWNLOAD_FOLDER'] = str(DOWNLOAD_DIR)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client):
    with client.session_transaction() as session:
        session['user'] = {'id': 'test_user'}
    return client

def test_tiktok_downloader_page(client):
    """Test that the TikTok downloader page loads correctly"""
    response = client.get('/tiktok-downloader')
    assert response.status_code == 200
    assert b'TikTok Downloader' in response.data

def test_tiktok_download_unauthorized(client):
    """Test that unauthorized users cannot download TikTok content"""
    response = client.post('/tiktok-single-download', data={'video_url': 'https://www.tiktok.com/@user/video/1234567890'})
    assert response.status_code == 401

def test_tiktok_download_no_url(auth_client):
    """Test that an error is returned when no URL is provided"""
    response = auth_client.post('/tiktok-single-download', data={})
    assert response.status_code == 400

def test_tiktok_download_invalid_url(auth_client):
    """Test that an error is returned when an invalid URL is provided"""
    response = auth_client.post('/tiktok-single-download', data={'video_url': 'https://invalid.com'})
    assert response.status_code == 400

@patch('app.routes.tiktok.validate_tiktok_url')
@patch('app.routes.tiktok.tiktok_cache')
def test_tiktok_download_cached(mock_cache, mock_validate, auth_client):
    """Test that cached TikTok content can be retrieved"""
    test_url = 'https://www.tiktok.com/@testuser/video/1234567890'
    test_media = {
        'id': 'test123',
        'title': 'Test TikTok',
        'file_path': 'tiktok/test.mp4',
        'media_type': 'video',
        'metadata': {
            'uploader': 'test_user',
            'like_count': 100,
            'comment_count': 10,
            'timestamp': 1234567890,
            'duration': 30,
            'description': 'Test video',
            'view_count': 1000
        }
    }

    # Mock URL validation
    mock_validate.return_value = (True, "video", None)

    # Mock cache behavior
    mock_cache.is_media_cached.return_value = True
    mock_cache.get_cached_media.return_value = test_media

    # Create test file
    test_file = DOWNLOAD_DIR / 'tiktok' / 'test.mp4'
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.touch()

    # Write some content to the file to prevent empty file error
    with open(test_file, 'wb') as f:
        f.write(b'test content')

    # Test download
    response = auth_client.post('/tiktok-single-download', data={'video_url': test_url})
    assert response.status_code == 200

@patch('app.routes.tiktok.validate_tiktok_url')
@patch('app.routes.tiktok.tiktok_cache')
@patch('app.routes.tiktok.download_tiktok_content')
def test_tiktok_download_new(mock_download, mock_cache, mock_validate, auth_client):
    """Test that new TikTok content can be downloaded"""
    test_url = 'https://www.tiktok.com/@testuser/video/9876543210'
    
    # Mock URL validation
    mock_validate.return_value = (True, "video", None)
    
    # Mock cache miss
    mock_cache.is_media_cached.return_value = False
    
    # Mock download failure
    mock_download.side_effect = Exception('Failed to download TikTok video')

    response = auth_client.post('/tiktok-single-download', data={'video_url': test_url})
    assert response.status_code == 500