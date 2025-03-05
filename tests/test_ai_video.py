import pytest
import os
import json
from pathlib import Path
from app import create_app
from unittest.mock import patch, MagicMock
from flask.sessions import SecureCookieSessionInterface
import numpy as np

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SESSION_TYPE'] = None  # Use Flask's default session
    app.session_interface = SecureCookieSessionInterface()  # Use Flask's default session interface
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client):
    with client.session_transaction() as session:
        session['user'] = {'id': 'test_user'}
    return client

def test_ai_video_index_unauthorized(client):
    """Test that unauthorized users cannot access the AI video page"""
    response = client.get('/ai-video/')
    assert response.status_code == 302  # Redirect to login

def test_ai_video_index_authorized(auth_client):
    """Test that authorized users can access the AI video page"""
    response = auth_client.get('/ai-video/')
    assert response.status_code == 200
    assert b'AI Video' in response.data

def test_detect_faces_no_file(auth_client):
    """Test that an error is returned when no file is provided"""
    response = auth_client.post('/ai-video/detect-faces')
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert 'error' in response_data
    assert response_data['error'] == 'No video file provided'

@patch('app.routes.ai_video.mp.solutions.face_detection.FaceDetection')
@patch('app.routes.ai_video.cv2.VideoCapture')
def test_detect_faces_success(mock_video_capture, mock_face_detection, auth_client, tmp_path):
    """Test that face detection works correctly"""
    # Create a mock frame as a numpy array
    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Mock video capture
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.side_effect = [(True, mock_frame), (False, None)]
    mock_cap.get.return_value = 30  # FPS
    mock_video_capture.return_value = mock_cap

    # Mock face detection
    mock_detection = MagicMock()
    mock_detection.process.return_value = MagicMock(detections=[MagicMock(
        score=[0.9],
        location_data=MagicMock(
            relative_bounding_box=MagicMock(
                xmin=0.1, ymin=0.1, width=0.2, height=0.2
            )
        )
    )])
    mock_face_detection.return_value = mock_detection

    # Create a temporary test video file
    test_video = tmp_path / "test_video.mp4"
    with open(test_video, 'wb') as f:
        f.write(b'test video content')

    # Mock database connection
    with patch('app.routes.ai_video.get_db_connection') as mock_db:
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # Mock cv2.imwrite to avoid writing actual files
        with patch('app.routes.ai_video.cv2.imwrite'):
            # Mock os.path.join to return a predictable path
            with patch('app.routes.ai_video.os.path.join', return_value=str(tmp_path / "face.jpg")):
                # Test the face detection endpoint
                with open(test_video, 'rb') as f:
                    response = auth_client.post(
                        '/ai-video/detect-faces',
                        data={'video': (f, 'test_video.mp4')}
                    )

                # Check the response
                assert response.status_code == 200
                data = response.get_json()
                assert 'video_id' in data
                assert 'unique_faces' in data
                assert 'video_path' in data

def test_generate_highlight_missing_params(auth_client):
    """Test that an error is returned when parameters are missing"""
    response = auth_client.post('/ai-video/generate-highlight', json={})
    assert response.status_code == 400
    assert b'Missing required parameters' in response.data

@patch('app.routes.ai_video.get_db_connection')
def test_generate_highlight_video_not_found(mock_db, auth_client):
    """Test that an error is returned when the video is not found"""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_db.return_value = mock_conn

    response = auth_client.post('/ai-video/generate-highlight', json={
        'video_id': 999,
        'face_id': 'test_face'
    })

    assert response.status_code == 404
    assert b'Video not found' in response.data

def test_check_status_unauthorized(client):
    """Test that unauthorized users cannot check video status"""
    response = client.get('/ai-video/check-status/1')
    assert response.status_code == 302  # Redirect to login

@patch('app.routes.ai_video.ai_video_cache.get_status')
@patch('app.routes.ai_video.get_db_connection')
def test_check_status_not_found(mock_db, mock_cache, auth_client):
    """Test that an error is returned when the video is not found"""
    mock_cache.return_value = None
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_db.return_value = mock_conn

    response = auth_client.get('/ai-video/check-status/999')

    assert response.status_code == 404
    assert b'Video not found' in response.data

@patch('app.routes.ai_video.ai_video_cache.get_status')
@patch('app.routes.ai_video.get_db_connection')
def test_check_status_success(mock_db, mock_cache, auth_client):
    """Test that video status can be checked successfully"""
    # Mock cache miss
    mock_cache.return_value = None

    # Mock database response
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        'status': 'completed',
        'metadata': json.dumps({
            'faces_detected': 2,
            'frame_count': 100,
            'duration': 10.0
        })
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_db.return_value = mock_conn

    response = auth_client.get('/ai-video/check-status/1')

    assert response.status_code == 200
    response_data = json.loads(response.data)
    assert response_data['status'] == 'completed'
    assert response_data['progress'] == 100
    assert 'metadata' in response_data

def test_serve_ai_video_not_found(auth_client):
    """Test that an error is returned when the file is not found"""
    with patch('app.routes.ai_video.os.path.exists', return_value=False):
        response = auth_client.get('/ai-video/media/test.mp4')
        assert response.status_code == 404
        assert b'File not found' in response.data