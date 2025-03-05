"""
Splitter Module for Content Repurposing Pipeline.

This module handles video splitting using MoviePy, automatically detecting
logical splits based on duration thresholds or silent sections.
"""

from .splitter import split_video, detect_silence, get_video_info

__all__ = ['split_video', 'detect_silence', 'get_video_info']