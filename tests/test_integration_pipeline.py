import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tempfile
import logging
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from content_pipeline.text_generator import integration

@pytest.fixture
def dummy_video(tmp_path):
    # Create a dummy video file (1 black frame, 640x480)
    import cv2
    video_path = tmp_path / "test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 1.0, (640, 480))
    frame = (0 * np.ones((480, 640, 3), dtype=np.uint8))
    out.write(frame)
    out.release()
    return str(video_path)

@pytest.fixture
def dummy_clip_metadata():
    return {
        "description": "A test video of a cat playing piano.",
        "duration": 5.0,
        "width": 640,
        "height": 480
    }

def test_pipeline_with_gemini(monkeypatch, dummy_video, dummy_clip_metadata, caplog):
    # Patch Gemini Vision to return a fake description
    fake_gemini_desc = "A cat is playing piano in a living room."
    monkeypatch.setattr(
        "content_pipeline.text_generator.ai_models.get_gemini_vision_description",
        lambda image_bytes: fake_gemini_desc
    )
    # Patch BLIP to return a fake caption
    monkeypatch.setattr(
        "content_pipeline.text_generator.integration.advanced_frame_caption",
        lambda image_bytes: "A black frame."
    )
    # Patch TextGeneratorFactory to return a mock generator
    class DummyGen:
        def generate_captions(self, **kwargs): return ["A cat plays piano!"]
        def generate_hashtags(self, **kwargs): return ["#cat", "#piano", "#music"]
        def generate_platform_variations(self, **kwargs): return {"TikTok": {"caption": "A cat plays piano!", "hashtags": ["#cat"]}}
    monkeypatch.setattr(
        "content_pipeline.text_generator.factory.TextGeneratorFactory.create",
        lambda config: DummyGen()
    )
    with caplog.at_level(logging.INFO):
        result = integration.process_clip(
            dummy_video,
            clip_metadata=dummy_clip_metadata,
            ai_provider="gemini"
        )
    # Check context summary in logs
    context_log = [r for r in caplog.messages if "Context summary for AI model" in r]
    assert context_log, "Context summary should be logged"
    assert "User description" in context_log[-1]
    assert "Gemini Vision analysis" in context_log[-1]
    assert "Local frame captions" in context_log[-1]
    # Check output
    assert "captions" in result and result["captions"]
    assert "hashtags" in result and result["hashtags"]

def test_pipeline_without_gemini(monkeypatch, dummy_video, dummy_clip_metadata, caplog):
    # Patch Gemini Vision to raise ImportError (simulate unavailable)
    monkeypatch.setattr(
        "content_pipeline.text_generator.ai_models.get_gemini_vision_description",
        lambda image_bytes: None
    )
    # Patch BLIP to return a fake caption
    monkeypatch.setattr(
        "content_pipeline.text_generator.integration.advanced_frame_caption",
        lambda image_bytes: "A black frame."
    )
    # Patch TextGeneratorFactory to return a mock generator
    class DummyGen:
        def generate_captions(self, **kwargs): return ["A cat plays piano!"]
        def generate_hashtags(self, **kwargs): return ["#cat", "#piano", "#music"]
        def generate_platform_variations(self, **kwargs): return {"TikTok": {"caption": "A cat plays piano!", "hashtags": ["#cat"]}}
    monkeypatch.setattr(
        "content_pipeline.text_generator.factory.TextGeneratorFactory.create",
        lambda config: DummyGen()
    )
    with caplog.at_level(logging.INFO):
        result = integration.process_clip(
            dummy_video,
            clip_metadata=dummy_clip_metadata,
            ai_provider="openai"
        )
    # Check context summary in logs
    context_log = [r for r in caplog.messages if "Context summary for AI model" in r]
    assert context_log, "Context summary should be logged"
    assert "User description" in context_log[-1]
    assert "Local frame captions" in context_log[-1]
    # Gemini Vision analysis should not be present
    assert "Gemini Vision analysis" not in context_log[-1]
    # Check output
    assert "captions" in result and result["captions"]
    assert "hashtags" in result and result["hashtags"]
