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

def test_instagram_downloader_page(client):
    response = client.get('/instagram-downloader')
    assert response.status_code == 200
    assert b'Instagram Downloader' in response.data

def test_instagram_download_unauthorized(client):
    response = client.post('/instagram-download', data={'url': 'https://www.instagram.com/p/test123'})
    assert response.status_code == 401
    assert b'Please login to download content' in response.data

def test_instagram_download_no_url(auth_client):
    response = auth_client.post('/instagram-download', data={})
    assert response.status_code == 400
    assert b'No URL provided' in response.data

def test_instagram_download_invalid_url(auth_client):
    response = auth_client.post('/instagram-download', data={'url': 'https://invalid.com'})
    assert response.status_code == 400
    assert b'Invalid Instagram URL domain' in response.data

def test_instagram_download_cached(auth_client):
    # Setup cache
    cache = MediaCache('instagram')
    test_url = 'https://www.instagram.com/p/test123'
    test_media = {
        'id': 'test123',
        'title': 'Test Post',
        'file_path': 'instagram/test.mp4',
        'media_type': 'video',
        'metadata': {
            'uploader': 'test_user',
            'like_count': 100,
            'comment_count': 10,
            'timestamp': 1234567890
        }
    }
    
    # Create test file
    test_file = DOWNLOAD_DIR / 'instagram' / 'test.mp4'
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.touch()
    
    # Write some content to the file to prevent empty file error
    with open(test_file, 'wb') as f:
        f.write(b'test content')
    
    # Cache the media
    cache.cache_media(test_url, 'test_user', test_media)
    
    # Test download
    response = auth_client.post('/instagram-download', data={'url': test_url})
    assert response.status_code == 200
    assert b'test_user' in response.data
    assert b'Test Post' in response.data
    
    # Cleanup
    test_file.unlink()

def test_instagram_download_new(auth_client):
    test_url = 'https://www.instagram.com/p/test456'
    response = auth_client.post('/instagram-download', data={'url': test_url})
    
    # Since we can't actually download from Instagram in tests,
    # we expect a 500 error with a specific message
    assert response.status_code == 500
    assert b'Failed to download Instagram content' in response.data 