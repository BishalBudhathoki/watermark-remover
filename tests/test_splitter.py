"""
Tests for the video splitter functionality.
"""

import os
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch
from content_pipeline.splitter import split_video, detect_silence, get_video_info

# Test Constants
TEST_VIDEO_PATH = "test_video.mp4"
TEST_OUTPUT_DIR = "test_output"
TEST_DURATION = 120.0  # 2 minutes
TEST_FPS = 30
TEST_SIZE = (1920, 1080)


@pytest.fixture
def mock_video_clip():
    """Create a mock VideoFileClip for testing."""
    with patch('content_pipeline.splitter.splitter.VideoFileClip') as mock_clip:
        # Configure the mock clip
        instance = mock_clip.return_value.__enter__.return_value
        instance.duration = TEST_DURATION
        instance.fps = TEST_FPS
        instance.size = TEST_SIZE
        
        # Mock audio property
        mock_audio = MagicMock()
        mock_audio.to_soundarray.return_value = np.zeros(int(TEST_DURATION * 22000))
        instance.audio = mock_audio
        
        yield mock_clip


def test_get_video_info(mock_video_clip):
    """Test getting video information."""
    info = get_video_info(TEST_VIDEO_PATH)
    
    assert isinstance(info, dict)
    assert info["duration"] == TEST_DURATION
    assert info["fps"] == TEST_FPS
    assert info["size"] == TEST_SIZE
    assert info["audio"] is True


def test_get_video_info_no_audio(mock_video_clip):
    """Test getting video information for a video without audio."""
    # Configure mock to have no audio
    instance = mock_video_clip.return_value.__enter__.return_value
    instance.audio = None
    
    info = get_video_info(TEST_VIDEO_PATH)
    
    assert isinstance(info, dict)
    assert info["audio"] is False


def test_get_video_info_error():
    """Test error handling when getting video information."""
    with patch('content_pipeline.splitter.splitter.VideoFileClip', side_effect=Exception("Test error")):
        with pytest.raises(Exception) as exc_info:
            get_video_info(TEST_VIDEO_PATH)
        assert "Test error" in str(exc_info.value)


def test_detect_silence(mock_video_clip):
    """Test silence detection in video."""
    # Create mock audio data with known silent sections
    audio_length = int(TEST_DURATION * 22000)
    audio_data = np.ones(audio_length)
    
    # Add two silent sections
    silence_start1 = int(0.5 * 22000)  # 0.5s
    silence_end1 = int(1.5 * 22000)    # 1.5s
    silence_start2 = int(3.0 * 22000)  # 3.0s
    silence_end2 = int(4.0 * 22000)    # 4.0s
    
    audio_data[silence_start1:silence_end1] = 0
    audio_data[silence_start2:silence_end2] = 0
    
    # Configure mock to return our test audio data
    instance = mock_video_clip.return_value.__enter__.return_value
    instance.audio.to_soundarray.return_value = audio_data
    
    silence_segments = detect_silence(
        TEST_VIDEO_PATH,
        threshold=0.1,
        min_silence_duration=0.5
    )
    
    assert len(silence_segments) == 2
    assert pytest.approx(silence_segments[0][0], 0.1) == 0.5
    assert pytest.approx(silence_segments[0][1], 0.1) == 1.5
    assert pytest.approx(silence_segments[1][0], 0.1) == 3.0
    assert pytest.approx(silence_segments[1][1], 0.1) == 4.0


def test_detect_silence_no_audio(mock_video_clip):
    """Test silence detection for video without audio."""
    instance = mock_video_clip.return_value.__enter__.return_value
    instance.audio = None
    
    silence_segments = detect_silence(TEST_VIDEO_PATH)
    assert len(silence_segments) == 0


def test_split_video_duration_based(mock_video_clip):
    """Test splitting video based on duration."""
    # Mock the subclip and write_videofile methods
    instance = mock_video_clip.return_value.__enter__.return_value
    instance.subclip.return_value.write_videofile = MagicMock()
    
    result = split_video(
        video_path=TEST_VIDEO_PATH,
        output_dir=TEST_OUTPUT_DIR,
        max_clip_duration=30,  # 30 second clips
        split_on_silence=False
    )
    
    assert result["success"] is True
    assert len(result["clips"]) == 4  # 120 seconds / 30 seconds = 4 clips
    
    # Verify clip properties
    for i, clip in enumerate(result["clips"]):
        assert clip["duration"] == 30.0
        assert clip["start_time"] == i * 30.0
        assert clip["end_time"] == (i + 1) * 30.0
        assert clip["index"] == i + 1
        assert clip["path"].endswith(f"clip_{i+1:03d}.mp4")


def test_split_video_silence_based(mock_video_clip):
    """Test splitting video based on silence detection."""
    # Mock silence detection to return specific split points
    with patch('content_pipeline.splitter.splitter.detect_silence') as mock_detect:
        mock_detect.return_value = [
            (30.0, 31.0),  # Split around 30.5s
            (60.0, 61.0),  # Split around 60.5s
            (90.0, 91.0)   # Split around 90.5s
        ]
        
        # Mock the subclip and write_videofile methods
        instance = mock_video_clip.return_value.__enter__.return_value
        instance.subclip.return_value.write_videofile = MagicMock()
        
        result = split_video(
            video_path=TEST_VIDEO_PATH,
            output_dir=TEST_OUTPUT_DIR,
            split_on_silence=True
        )
        
        assert result["success"] is True
        assert len(result["clips"]) == 4  # Should create 4 clips based on 3 split points
        
        # Verify clip properties
        expected_splits = [0, 30.5, 60.5, 90.5, 120.0]
        for i, clip in enumerate(result["clips"]):
            assert pytest.approx(clip["start_time"], 0.1) == expected_splits[i]
            assert pytest.approx(clip["end_time"], 0.1) == expected_splits[i + 1]
            assert clip["index"] == i + 1


def test_split_video_min_duration_filter(mock_video_clip):
    """Test that clips shorter than min_clip_duration are filtered out."""
    # Mock silence detection to return split points that would create some short clips
    with patch('content_pipeline.splitter.splitter.detect_silence') as mock_detect:
        mock_detect.return_value = [
            (10.0, 10.5),   # Would create a 10-second clip (keep)
            (12.0, 12.5),   # Would create a 2-second clip (filter out)
            (30.0, 30.5),   # Would create an 18-second clip (keep)
            (60.0, 60.5)    # Would create a 30-second clip (keep)
        ]
        
        # Mock the subclip and write_videofile methods
        instance = mock_video_clip.return_value.__enter__.return_value
        instance.subclip.return_value.write_videofile = MagicMock()
        
        result = split_video(
            video_path=TEST_VIDEO_PATH,
            output_dir=TEST_OUTPUT_DIR,
            split_on_silence=True,
            min_clip_duration=5.0  # Minimum 5 seconds
        )
        
        assert result["success"] is True
        assert len(result["clips"]) == 4  # Should create 4 clips, filtering out the 2-second clip
        
        # Verify no clips are shorter than min_clip_duration
        for clip in result["clips"]:
            assert clip["duration"] >= 5.0


def test_split_video_error_handling(mock_video_clip):
    """Test error handling during video splitting."""
    # Mock VideoFileClip to raise an exception
    mock_video_clip.side_effect = Exception("Test error")
    
    result = split_video(TEST_VIDEO_PATH)
    
    assert result["success"] is False
    assert "error" in result
    assert "Test error" in result["error"]


def test_split_video_output_directory_creation():
    """Test that the output directory is created if it doesn't exist."""
    with patch('os.makedirs') as mock_makedirs:
        with patch('content_pipeline.splitter.splitter.VideoFileClip') as mock_clip:
            # Configure the mock clip
            instance = mock_clip.return_value.__enter__.return_value
            instance.duration = TEST_DURATION
            instance.fps = TEST_FPS
            instance.size = TEST_SIZE
            instance.audio = None
            instance.subclip.return_value.write_videofile = MagicMock()
            
            split_video(
                video_path=TEST_VIDEO_PATH,
                output_dir=TEST_OUTPUT_DIR
            )
            
            # Verify that makedirs was called with the output directory
            mock_makedirs.assert_called_with(TEST_OUTPUT_DIR, exist_ok=True) 