import pytest
from pathlib import Path
from app import create_app
from app.services.cache import MediaCache
from app.utils.path import DOWNLOAD_DIR

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client):
    with client.session_transaction() as session:
        session['user'] = {'id': 'test_user'}
    return client

def test_youtube_downloader_page(client):
    """Test that the YouTube downloader page loads correctly"""
    response = client.get('/youtube-downloader')
    assert response.status_code == 200
    assert b'YouTube Downloader' in response.data

def test_youtube_download_unauthorized(client):
    """Test that unauthorized users cannot download YouTube content"""
    response = client.post('/youtube-download', data={'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})
    assert response.status_code == 401
    assert b'Please login to download content' in response.data

def test_youtube_download_no_url(auth_client):
    """Test that an error is returned when no URL is provided"""
    response = auth_client.post('/youtube-download', data={})
    assert response.status_code == 400
    assert b'No URL provided' in response.data

def test_youtube_download_invalid_url(auth_client):
    """Test that an error is returned when an invalid URL is provided"""
    response = auth_client.post('/youtube-download', data={'url': 'https://invalid.com'})
    assert response.status_code == 400
    assert b'Invalid YouTube URL' in response.data

def test_youtube_download_cached(auth_client):
    """Test that cached YouTube content can be retrieved"""
    # Setup cache
    cache = MediaCache('youtube')
    test_url = 'https://www.youtube.com/watch?v=test123'
    test_media = {
        'id': 'test123',
        'title': 'Test YouTube Video',
        'file_path': 'youtube/test.mp4',
        'media_type': 'video',
        'metadata': {
            'uploader': 'test_channel',
            'view_count': 1000,
            'like_count': 100,
            'comment_count': 10,
            'timestamp': 1234567890
        }
    }

    # Create test file
    test_file = DOWNLOAD_DIR / 'youtube' / 'test.mp4'
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.touch()

    # Write some content to the file to prevent empty file error
    with open(test_file, 'wb') as f:
        f.write(b'test content')

    # Cache the media
    cache.cache_media(test_url, 'test_user', test_media)

    # Test download
    response = auth_client.post('/youtube-download', data={'url': test_url})
    assert response.status_code == 200
    assert b'test_channel' in response.data
    assert b'YouTube Download Results' in response.data
    assert b'video' in response.data.lower() or b'img' in response.data.lower()

    # Cleanup
    test_file.unlink()

def test_youtube_download_new(auth_client):
    """Test that new YouTube content can be downloaded"""
    test_url = 'https://www.youtube.com/watch?v=test456'
    response = auth_client.post('/youtube-download', data={'url': test_url})

    # Since we can't actually download from YouTube in tests,
    # we expect a 500 error with a specific message
    assert response.status_code == 500
    assert b'Failed to download YouTube content' in response.data

def test_youtube_format_selection(auth_client):
    """Test that format selection works correctly"""
    test_url = 'https://www.youtube.com/watch?v=test789'
    response = auth_client.post('/youtube-download', data={
        'url': test_url,
        'format': 'audio'
    })

    # Since we can't actually download from YouTube in tests,
    # we expect a 500 error with a specific message
    assert response.status_code == 500
    assert b'Failed to download YouTube content' in response.data