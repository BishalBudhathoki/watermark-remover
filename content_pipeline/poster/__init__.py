"""
Poster Module for Content Repurposing Pipeline.

This module handles cross-posting of video clips to various social media platforms,
applying the generated captions and hashtags.
"""

from .poster import post_to_platform, post_to_all_platforms, get_available_platforms
from .tiktok import post_to_tiktok
from .instagram import post_to_instagram
from .youtube import post_to_youtube

__all__ = [
    'post_to_platform',
    'post_to_all_platforms',
    'get_available_platforms',
    'post_to_tiktok',
    'post_to_instagram',
    'post_to_youtube'
]