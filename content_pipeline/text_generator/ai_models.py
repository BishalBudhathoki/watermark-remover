"""
AI Models Integration Module for Content Repurposing Pipeline.

This module provides integration with various AI models for text generation,
including OpenAI, DeepSeek, and Google Gemini.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional, Union
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("OpenAI module not found. OpenAI integration will not be available.")
    OPENAI_AVAILABLE = False

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    logger.warning("Google Generative AI module not found. Gemini integration will not be available.")
    GEMINI_AVAILABLE = False

# We'll use direct API calls for DeepSeek instead of the Python client
DEEPSEEK_AVAILABLE = True

# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class AIModel(Enum):
    """Enum for supported AI models."""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


class AIModelFactory:
    """Factory class for creating AI model clients."""

    @staticmethod
    def create_client(model_type: 'AIModel') -> Any:
        """
        Create a client for the specified AI model type.

        Args:
            model_type: Type of AI model to create a client for

        Returns:
            Client for the specified AI model
        """
        if model_type == AIModel.OPENAI:
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI module not installed. Please install with 'pip install openai'")
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key not found in environment variables")
            openai.api_key = OPENAI_API_KEY
            return openai

        elif model_type == AIModel.DEEPSEEK:
            # Check if API key is available
            if not DEEPSEEK_API_KEY:
                raise ValueError("DeepSeek API key not found in environment variables")

            # For direct API access, we don't need a client - we'll use requests in the generation method
            return "direct_api"

        elif model_type == AIModel.GEMINI:
            if not GOOGLE_API_KEY:
                raise ValueError("Google API key not found in environment variables")

            # For direct API access, we'll use the API key directly
            return "direct_api"

        else:
            raise ValueError(f"Unknown AI model type: {model_type}")


class TextGenerator:
    """Class for generating text using various AI models."""

    def __init__(self, model_type: AIModel = AIModel.OPENAI):
        """
        Initialize the text generator.

        Args:
            model_type: Type of AI model to use
        """
        self.model_type = model_type
        try:
            self.client = AIModelFactory.create_client(model_type)
            logger.info(f"Initialized {model_type.value} client")
        except ValueError as e:
            logger.error(f"Error initializing {model_type.value} client: {str(e)}")
            # Fall back to OpenAI if available
            if model_type != AIModel.OPENAI and OPENAI_AVAILABLE and OPENAI_API_KEY:
                logger.info(f"Falling back to OpenAI")
                self.model_type = AIModel.OPENAI
                self.client = AIModelFactory.create_client(AIModel.OPENAI)
            # Fall back to Gemini if OpenAI is not available
            elif model_type != AIModel.GEMINI and GEMINI_AVAILABLE and GOOGLE_API_KEY:
                logger.info(f"Falling back to Gemini")
                self.model_type = AIModel.GEMINI
                self.client = AIModelFactory.create_client(AIModel.GEMINI)
            # Fall back to DeepSeek if OpenAI and Gemini are not available
            elif model_type != AIModel.DEEPSEEK and DEEPSEEK_AVAILABLE and DEEPSEEK_API_KEY:
                logger.info(f"Falling back to DeepSeek")
                self.model_type = AIModel.DEEPSEEK
                self.client = AIModelFactory.create_client(AIModel.DEEPSEEK)
            else:
                raise ValueError("No AI models available. Please install at least one of: openai, deepseek-chat, or google-generativeai")

    def generate_captions(self, video_description: str, num_variations: int = 3, caption_style: str = "casual", frame_descriptions: List[Dict] = None) -> List[str]:
        """
        Generate caption variations for a video.

        Args:
            video_description: Description of the video content
            num_variations: Number of caption variations to generate
            caption_style: Style of the captions (casual, professional, humorous, etc.)
            frame_descriptions: List of frame descriptions extracted from the video

        Returns:
            List of generated captions
        """
        # Add caption style to the prompt
        style_description = "friendly and conversational"
        if caption_style == "professional":
            style_description = "formal, polished and business-like"
        elif caption_style == "humorous":
            style_description = "funny, entertaining and witty"

        # Create a detailed content description based on video frames if available
        content_description = video_description

        # Detect if this is likely a comedy video based on filename or description
        is_comedy = False
        comedy_keywords = ["funny", "comedy", "laugh", "hilarious", "joke", "humor", "prank", "gag", "blooper"]
        for keyword in comedy_keywords:
            if keyword.lower() in video_description.lower():
                is_comedy = True
                break

        if frame_descriptions and len(frame_descriptions) > 0:
            # Create a detailed description of the video content based on frames
            content_description = f"{video_description}\n\nDetailed video content analysis:"

            # Check for comedy content in frame descriptions
            comedy_frames = 0

            # Add frame descriptions with analysis
            for i, frame in enumerate(frame_descriptions):
                timestamp = frame.get("timestamp", 0)
                position = frame.get("position", f"{timestamp:.2f}s")

                # Include analysis summary if available
                analysis = frame.get("analysis", {})
                analysis_summary = analysis.get("summary", "")

                # Check if this frame might indicate comedy
                if "content_type" in analysis and "comedy" in analysis.get("content_type", "").lower():
                    comedy_frames += 1

                if analysis_summary:
                    content_description += f"\n- Frame {i+1} ({position}): {analysis_summary}"
                else:
                    content_description += f"\n- Frame {i+1} ({position}): A frame from the video showing content at timestamp {position}."

                # Add more detailed analysis if available
                if "has_faces" in analysis and analysis["has_faces"]:
                    content_description += f" Shows {analysis.get('num_faces', 'one or more')} people."

                if "has_text" in analysis and analysis["has_text"]:
                    content_description += " Contains visible text."

            # If multiple frames suggest comedy, note this in the content description
            if comedy_frames >= 2 or is_comedy:
                content_description += "\n\nThis appears to be a comedy or humorous video based on content analysis."
                is_comedy = True

            content_description += "\n\nPlease analyze these frames to generate captions that accurately reflect the actual video content, not just the title."

        # Adjust the prompt based on content type
        genre_guidance = ""
        if is_comedy:
            genre_guidance = """
            This is a COMEDY video. Generate funny, light-hearted captions that match the humorous tone.
            DO NOT generate dark, spooky, or mysterious captions regardless of lighting conditions.
            Focus on the humor and entertainment value of the content.
            """

        prompt = f"""
        Generate {num_variations} engaging and creative caption variations for a social media post about the following video.
        Use a {caption_style} style that is {style_description}.

        Video Content: {content_description}

        {genre_guidance}

        IMPORTANT: DO NOT misinterpret lighting conditions or color tones as mood indicators.
        Low lighting does NOT mean the content is spooky, dark, or mysterious.
        Red tones do NOT indicate horror or suspense.

        Each caption should be concise (max 150 characters), engaging, and designed to maximize engagement on social media.
        Make sure the tone matches the requested {caption_style} style.
        Focus on what's actually happening in the video frames, not just the title.
        Provide only the captions, one per line, without numbering or additional text.
        """

        if self.model_type == AIModel.OPENAI:
            return self._generate_with_openai(prompt, num_variations)
        elif self.model_type == AIModel.DEEPSEEK:
            return self._generate_with_deepseek(prompt, num_variations)
        elif self.model_type == AIModel.GEMINI:
            return self._generate_with_gemini(prompt, num_variations)

    def generate_hashtags(self, video_description: str, num_hashtags: int = 10, caption_style: str = "casual", frame_descriptions: List[Dict] = None) -> List[str]:
        """
        Generate hashtags for a video.

        Args:
            video_description: Description of the video content
            num_hashtags: Number of hashtags to generate
            caption_style: Style of the hashtags (casual, professional, humorous, etc.)
            frame_descriptions: List of frame descriptions extracted from the video

        Returns:
            List of generated hashtags
        """
        # Add caption style to the prompt
        style_description = "friendly and popular"
        if caption_style == "professional":
            style_description = "professional and industry-specific"
        elif caption_style == "humorous":
            style_description = "trending and funny"

        # Detect if this is likely a comedy video based on filename or description
        is_comedy = False
        comedy_keywords = ["funny", "comedy", "laugh", "hilarious", "joke", "humor", "prank", "gag", "blooper"]
        for keyword in comedy_keywords:
            if keyword.lower() in video_description.lower():
                is_comedy = True
                break

        # Create a detailed content description based on video frames if available
        content_description = video_description
        if frame_descriptions and len(frame_descriptions) > 0:
            # Create a detailed description of the video content based on frames
            content_description = f"{video_description}\n\nDetailed video content analysis:"

            # Check for comedy content in frame descriptions
            comedy_frames = 0

            # Add frame descriptions with analysis
            for i, frame in enumerate(frame_descriptions):
                timestamp = frame.get("timestamp", 0)
                position = frame.get("position", f"{timestamp:.2f}s")

                # Include analysis summary if available
                analysis = frame.get("analysis", {})
                analysis_summary = analysis.get("summary", "")

                # Check if this frame might indicate comedy
                if "content_type" in analysis and "comedy" in analysis.get("content_type", "").lower():
                    comedy_frames += 1

                if analysis_summary:
                    content_description += f"\n- Frame {i+1} ({position}): {analysis_summary}"
                else:
                    content_description += f"\n- Frame {i+1} ({position}): A frame from the video showing content at timestamp {position}."

                # Add more detailed analysis if available
                if "has_faces" in analysis and analysis["has_faces"]:
                    content_description += f" Shows {analysis.get('num_faces', 'one or more')} people."

                if "has_text" in analysis and analysis["has_text"]:
                    content_description += " Contains visible text."

            # If multiple frames suggest comedy, note this in the content description
            if comedy_frames >= 2 or is_comedy:
                content_description += "\n\nThis appears to be a comedy or humorous video based on content analysis."
                is_comedy = True

            content_description += "\n\nPlease analyze these frames to generate hashtags that accurately reflect the actual video content, not just the title."

        # Adjust the prompt based on content type
        genre_guidance = ""
        if is_comedy:
            genre_guidance = """
            This is a COMEDY video. Generate funny, trending hashtags that match the humorous tone.
            Include popular comedy and humor hashtags.
            DO NOT generate dark, spooky, or mysterious hashtags regardless of lighting conditions.
            Focus on the humor and entertainment value of the content.
            """

        prompt = f"""
        Generate {num_hashtags} relevant and trending hashtags for a social media post about the following video.
        Use a {caption_style} style that is {style_description}.

        Video Content: {content_description}

        {genre_guidance}

        IMPORTANT: DO NOT misinterpret lighting conditions or color tones as mood indicators.
        Low lighting does NOT mean the content is spooky, dark, or mysterious.
        Red tones do NOT indicate horror or suspense.

        The hashtags should be relevant to the actual content shown in the video frames, include a mix of popular and niche tags, and help maximize reach.
        Make sure the hashtags match the requested {caption_style} style.
        Focus on what's actually happening in the video, not just the title.
        Provide only the hashtags without the # symbol, one per line, without numbering or additional text.
        """

        if self.model_type == AIModel.OPENAI:
            hashtags = self._generate_with_openai(prompt, num_hashtags)
        elif self.model_type == AIModel.DEEPSEEK:
            hashtags = self._generate_with_deepseek(prompt, num_hashtags)
        elif self.model_type == AIModel.GEMINI:
            hashtags = self._generate_with_gemini(prompt, num_hashtags)

        # Clean up hashtags (remove # if present, remove spaces)
        cleaned_hashtags = []
        for tag in hashtags:
            tag = tag.strip()
            if tag.startswith('#'):
                tag = tag[1:]
            tag = tag.replace(' ', '')
            if tag:
                cleaned_hashtags.append(tag)

        return cleaned_hashtags

    def _generate_with_openai(self, prompt: str, num_items: int) -> List[str]:
        """
        Generate text using OpenAI.

        Args:
            prompt: Prompt for text generation
            num_items: Number of items to generate

        Returns:
            List of generated text items
        """
        try:
            import time

            start_time = time.time()
            logger.info(f"Starting OpenAI API call for {num_items} items")

            logger.info(f"Sending request to OpenAI API")
            request_start_time = time.time()

            response = self.client.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates concise, engaging social media content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150 * num_items,
                n=1
            )

            request_duration = time.time() - request_start_time
            logger.info(f"OpenAI API request completed in {request_duration:.2f} seconds")

            text = response.choices[0].message.content.strip()
            logger.info(f"OpenAI API call successful with response length: {len(text)}")

            items = [item.strip() for item in text.split('\n') if item.strip()]
            logger.info(f"OpenAI generated {len(items)} items for prompt")

            # Ensure we have the requested number of items
            if len(items) < num_items:
                logger.warning(f"OpenAI generated fewer items than requested ({len(items)} < {num_items}), padding with fallbacks")
                items.extend([""] * (num_items - len(items)))
            elif len(items) > num_items:
                logger.warning(f"OpenAI generated more items than requested ({len(items)} > {num_items}), truncating")
                items = items[:num_items]

            total_duration = time.time() - start_time
            logger.info(f"OpenAI text generation completed in {total_duration:.2f} seconds")

            return items

        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {str(e)}")
            # Return empty placeholders
            return [""] * num_items

    def _generate_with_deepseek(self, prompt: str, num_items: int) -> List[str]:
        """
        Generate text using DeepSeek.

        Args:
            prompt: Prompt for text generation
            num_items: Number of items to generate

        Returns:
            List of generated text items
        """
        try:
            # Use direct API call instead of client library
            import requests
            import time

            start_time = time.time()
            logger.info(f"Starting DeepSeek API call for {num_items} items")

            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("DeepSeek API key not found in environment variables")

            # DeepSeek API endpoint
            api_url = "https://api.deepseek.com/v1/chat/completions"

            # Set up the headers with API key
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            # Prepare the system prompt and user prompt
            system_prompt = "You are a helpful assistant that generates concise, engaging social media content."

            # Prepare the request payload
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1024
            }

            logger.info(f"Sending request to DeepSeek API")
            request_start_time = time.time()

            # Make the API request
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()

            request_duration = time.time() - request_start_time
            logger.info(f"DeepSeek API request completed in {request_duration:.2f} seconds")

            # Extract the content from the response
            try:
                text = response_data["choices"][0]["message"]["content"].strip()
                logger.info(f"DeepSeek API call successful with response length: {len(text)}")
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing DeepSeek response: {str(e)}")
                raise ValueError(f"Invalid DeepSeek API response format: {str(response_data)}")

            # Split into items
            items = [item.strip() for item in text.split('\n') if item.strip()]

            # Log the number of items generated
            logger.info(f"DeepSeek generated {len(items)} items for prompt")

            # Ensure we have the requested number of items
            if len(items) < num_items:
                logger.warning(f"DeepSeek generated fewer items than requested ({len(items)} < {num_items}), padding with fallbacks")
                # Generate meaningful fallbacks based on context
                for i in range(num_items - len(items)):
                    if items:
                        items.append(f"Alternative {i+1}: {items[0]}")
                    else:
                        items.append(f"Engaging content {i+1}")
            elif len(items) > num_items:
                logger.warning(f"DeepSeek generated more items than requested ({len(items)} > {num_items}), truncating")
                items = items[:num_items]

            total_duration = time.time() - start_time
            logger.info(f"DeepSeek text generation completed in {total_duration:.2f} seconds")

            return items

        except Exception as e:
            logger.error(f"Error generating text with DeepSeek API: {str(e)}")
            # Return fallback placeholders with some content
            return [
                f"Creative caption {i+1}: Check out this amazing content!" for i in range(num_items)
            ]

    def _generate_with_gemini(self, prompt: str, num_items: int) -> List[str]:
        """
        Generate text using Google Gemini.

        Args:
            prompt: Prompt for text generation
            num_items: Number of items to generate

        Returns:
            List of generated text items
        """
        try:
            # Use direct API call rather than the client library
            import requests
            import time

            start_time = time.time()
            logger.info(f"Starting Gemini API call for {num_items} items")

            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("Google API key not found in environment variables")

            # Use model gemini-2.0-flash as specified
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

            # Prepare payload
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.95,
                    "topK": 40,
                    "maxOutputTokens": 1024
                }
            }

            logger.info(f"Sending request to Gemini API")
            request_start_time = time.time()

            # Make API request
            headers = {'Content-Type': 'application/json'}
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()

            request_duration = time.time() - request_start_time
            logger.info(f"Gemini API request completed in {request_duration:.2f} seconds")

            # Extract the generated text
            try:
                generated_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                text = generated_text.strip()
                logger.info(f"Gemini API call successful with response length: {len(text)}")
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing Gemini response: {str(e)}")
                raise ValueError(f"Invalid Gemini API response format: {str(response_data)}")

            # Split into items
            items = [item.strip() for item in text.split('\n') if item.strip()]

            # Log the raw items for debugging
            logger.info(f"Gemini generated {len(items)} items for prompt")

            # Ensure we have the requested number of items
            if len(items) < num_items:
                logger.warning(f"Gemini generated fewer items than requested ({len(items)} < {num_items}), padding with fallbacks")
                # Generate meaningful fallbacks based on the items already generated
                for i in range(num_items - len(items)):
                    if items:
                        items.append(f"Alternative {i+1}: {items[0]}")
                    else:
                        items.append(f"Engaging content {i+1}")
            elif len(items) > num_items:
                logger.warning(f"Gemini generated more items than requested ({len(items)} > {num_items}), truncating")
                items = items[:num_items]

            total_duration = time.time() - start_time
            logger.info(f"Gemini text generation completed in {total_duration:.2f} seconds")

            return items

        except Exception as e:
            logger.error(f"Error generating text with Gemini API: {str(e)}")
            # Return default placeholders with some content instead of empty strings
            return [
                f"Engaging caption {i+1}: This content is amazing!" for i in range(num_items)
            ]


def get_available_models() -> List[str]:
    """
    Get a list of available AI models based on environment variables and installed packages.

    Returns:
        List of available model names
    """
    available_models = []

    if OPENAI_AVAILABLE and OPENAI_API_KEY:
        available_models.append(AIModel.OPENAI.value)

    if DEEPSEEK_AVAILABLE and DEEPSEEK_API_KEY:
        available_models.append(AIModel.DEEPSEEK.value)

    if GEMINI_AVAILABLE and GOOGLE_API_KEY:
        available_models.append(AIModel.GEMINI.value)

    return available_models