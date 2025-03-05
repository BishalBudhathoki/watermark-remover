"""
Text Generator Module for Content Repurposing Pipeline.

This module handles the generation of captions, hashtags, and platform-specific
text variations for video clips using AI models like OpenAI, DeepSeek, or Google Gemini.
"""

from .text_generator import TextGenerator, OpenAITextGenerator
from .factory import TextGeneratorFactory
from .integration import process_clip

# Try to import AI models
try:
    from .ai_models import TextGenerator as UnifiedTextGenerator, AIModel, get_available_models
    AI_MODELS_AVAILABLE = True
except ImportError:
    AI_MODELS_AVAILABLE = False
    # Define a placeholder function
    def get_available_models():
        return []

__all__ = [
    'TextGenerator',
    'OpenAITextGenerator',
    'TextGeneratorFactory',
    'process_clip',
    'get_available_models'
]

# Add AI model exports if available
if AI_MODELS_AVAILABLE:
    __all__.extend([
        'UnifiedTextGenerator',
        'AIModel'
    ])