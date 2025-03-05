"""
Factory module for creating text generators.

This module provides a factory class for creating text generators based on configuration.
"""

import os
import logging
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
from .text_generator import TextGenerator, OpenAITextGenerator
# We'll skip importing DeepseekTextGenerator since it's not working
from .ai_models import (
    TextGenerator as UnifiedTextGenerator,
    AIModel,
    get_available_models,
    OPENAI_AVAILABLE,
    DEEPSEEK_AVAILABLE,
    GEMINI_AVAILABLE,
    OPENAI_API_KEY,
    DEEPSEEK_API_KEY,
    GOOGLE_API_KEY
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class TextGeneratorFactory:
    """Factory class for creating text generators."""

    @staticmethod
    def create(config: Optional[Dict[str, Any]] = None) -> TextGenerator:
        """
        Create a text generator based on configuration.

        Args:
            config: Configuration dictionary (optional)
                - provider: The AI provider to use ('openai', 'deepseek', or 'gemini')
                - api_key: The API key to use (optional, will use environment variable if not provided)
                - model: The model to use (optional, will use default if not provided)

        Returns:
            A TextGenerator instance
        """
        if config is None:
            config = {}

        # Get provider from config or environment variable or default to 'openai'
        provider = config.get('provider') or os.getenv('AI_PROVIDER', 'openai').lower()

        # Check if we should use the unified text generator
        use_unified = config.get('use_unified', False) or os.getenv('USE_UNIFIED_TEXT_GENERATOR', 'false').lower() == 'true'

        if use_unified:
            # Use the unified text generator with the specified model
            try:
                if provider == 'openai' and OPENAI_AVAILABLE and OPENAI_API_KEY:
                    return UnifiedTextGenerator(model_type=AIModel.OPENAI)
                elif provider == 'deepseek' and DEEPSEEK_API_KEY:
                    return UnifiedTextGenerator(model_type=AIModel.DEEPSEEK)
                elif provider == 'gemini' and GOOGLE_API_KEY:
                    return UnifiedTextGenerator(model_type=AIModel.GEMINI)
                else:
                    # Default to OpenAI if available, otherwise try other available models
                    available_models = get_available_models()
                    if 'openai' in available_models and OPENAI_API_KEY:
                        return UnifiedTextGenerator(model_type=AIModel.OPENAI)
                    elif 'deepseek' in available_models and DEEPSEEK_API_KEY:
                        return UnifiedTextGenerator(model_type=AIModel.DEEPSEEK)
                    elif 'gemini' in available_models and GOOGLE_API_KEY:
                        return UnifiedTextGenerator(model_type=AIModel.GEMINI)
                    else:
                        logger.warning("No AI models available for unified text generator. Falling back to legacy text generator.")
                        use_unified = False
            except Exception as e:
                logger.error(f"Error creating unified text generator: {str(e)}")
                logger.warning("Falling back to legacy text generator.")
                use_unified = False

        if not use_unified:
            # Use the legacy text generators
            try:
                if provider == 'openai':
                    api_key = config.get('api_key') or os.getenv('OPENAI_API_KEY')
                    model = config.get('model') or os.getenv('OPENAI_MODEL', 'gpt-4o')
                    return OpenAITextGenerator(api_key=api_key, model=model)
                elif provider == 'deepseek':
                    # Use the UnifiedTextGenerator instead
                    return UnifiedTextGenerator(model_type=AIModel.DEEPSEEK)
                elif provider == 'gemini':
                    # Use the UnifiedTextGenerator for Gemini
                    return UnifiedTextGenerator(model_type=AIModel.GEMINI)
                else:
                    logger.warning(f"Unsupported AI provider: {provider}. Using fallback providers.")
                    # Try each provider in order of preference
                    if DEEPSEEK_API_KEY:
                        return UnifiedTextGenerator(model_type=AIModel.DEEPSEEK)
                    elif GOOGLE_API_KEY:
                        return UnifiedTextGenerator(model_type=AIModel.GEMINI)
                    elif OPENAI_API_KEY:
                        return OpenAITextGenerator(api_key=OPENAI_API_KEY)
                    else:
                        raise ValueError("No API keys available for any AI provider")
            except Exception as e:
                logger.error(f"Error creating legacy text generator: {str(e)}")
                raise ValueError(f"Failed to create text generator: {str(e)}")

    @staticmethod
    def get_available_providers() -> List[str]:
        """
        Get a list of available AI providers based on environment variables.

        Returns:
            List of available provider names
        """
        return get_available_models()