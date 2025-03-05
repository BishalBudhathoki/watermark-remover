"""
Text Generator Module for Content Repurposing Pipeline.

This module provides classes for generating captions, hashtags, and platform-specific
text variations for video clips using AI models like OpenAI or Deepseek.
"""

import os
import logging
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Any

import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class TextGenerator(ABC):
    """Abstract base class for text generation services."""

    @abstractmethod
    def generate_captions(self, video_path: str, clip_metadata: Dict[str, Any],
                         num_variations: int = 3) -> List[str]:
        """
        Generate multiple caption variations for a video clip.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            num_variations: Number of caption variations to generate

        Returns:
            List of caption strings
        """
        pass

    @abstractmethod
    def generate_hashtags(self, video_path: str, clip_metadata: Dict[str, Any],
                         num_hashtags: int = 10) -> List[str]:
        """
        Generate relevant hashtags for a video clip.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            num_hashtags: Number of hashtags to generate

        Returns:
            List of hashtag strings (without the # symbol)
        """
        pass

    @abstractmethod
    def generate_platform_variations(self, video_path: str, clip_metadata: Dict[str, Any],
                                    platforms: List[str]) -> Dict[str, Dict[str, Union[str, List[str]]]]:
        """
        Generate platform-specific text variations for a video clip.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            platforms: List of platforms to generate variations for

        Returns:
            Dictionary mapping platform names to dictionaries containing:
                - caption: Platform-specific caption
                - hashtags: Platform-specific hashtags
        """
        pass


class OpenAITextGenerator(TextGenerator):
    """Text generator using OpenAI's API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the OpenAI text generator.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY environment variable)
            model: OpenAI model to use (defaults to gpt-4o)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")

        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _call_openai_api(self, messages: List[Dict[str, str]],
                        temperature: float = 0.7,
                        max_tokens: int = 500) -> Dict[str, Any]:
        """
        Call the OpenAI API with the given messages.

        Args:
            messages: List of message dictionaries
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate

        Returns:
            API response as a dictionary
        """
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Implement retry logic with exponential backoff
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"API call failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API call failed after {max_retries} attempts")
                    raise

    def _extract_json_from_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract JSON data from an OpenAI API response.

        Args:
            response: OpenAI API response

        Returns:
            Extracted JSON data
        """
        try:
            content = response["choices"][0]["message"]["content"]
            # Try to extract JSON from the content
            try:
                # First, try to parse the entire content as JSON
                return json.loads(content)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))

                # If that fails too, try to find any JSON-like structure
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))

                # If all else fails, raise an exception
                raise ValueError("Could not extract JSON from response")
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting content from API response: {str(e)}")
            raise ValueError(f"Invalid API response format: {str(e)}")

    def generate_captions(self, video_path: str, clip_metadata: Dict[str, Any],
                         num_variations: int = 3) -> List[str]:
        """
        Generate multiple caption variations for a video clip using OpenAI.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            num_variations: Number of caption variations to generate

        Returns:
            List of caption strings
        """
        # Prepare the prompt
        messages = [
            {"role": "system", "content": "You are a social media content expert specializing in creating engaging captions for short-form videos."},
            {"role": "user", "content": f"""
            Generate {num_variations} different engaging captions for a short video clip with the following details:

            Video details:
            - Duration: {clip_metadata.get('duration', 'unknown')} seconds
            - Content description: {clip_metadata.get('description', 'A short video clip')}
            - Target audience: {clip_metadata.get('target_audience', 'General audience')}
            - Tone: {clip_metadata.get('tone', 'Casual and engaging')}

            Please format your response as a JSON array of strings, with each string being a caption.
            Make each caption unique, engaging, and appropriate for social media.
            Keep captions concise (under 150 characters if possible).
            Do not include hashtags in the captions.
            """}
        ]

        try:
            response = self._call_openai_api(messages)
            captions_data = self._extract_json_from_response(response)

            # Handle both array and object formats
            if isinstance(captions_data, list):
                return captions_data
            elif isinstance(captions_data, dict) and "captions" in captions_data:
                return captions_data["captions"]
            else:
                logger.warning(f"Unexpected response format: {captions_data}")
                # Try to extract captions from any field that might contain them
                for key, value in captions_data.items():
                    if isinstance(value, list) and all(isinstance(item, str) for item in value):
                        return value

                # If all else fails, return an empty list
                return []
        except Exception as e:
            logger.error(f"Error generating captions: {str(e)}")
            # Implement fallback
            return [
                f"Check out this {clip_metadata.get('description', 'amazing')} video!",
                f"Had to share this {clip_metadata.get('description', 'cool')} moment!",
                f"This is what happens when {clip_metadata.get('description', 'creativity strikes')}!"
            ]

    def generate_hashtags(self, video_path: str, clip_metadata: Dict[str, Any],
                         num_hashtags: int = 10) -> List[str]:
        """
        Generate relevant hashtags for a video clip using OpenAI.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            num_hashtags: Number of hashtags to generate

        Returns:
            List of hashtag strings (without the # symbol)
        """
        # Prepare the prompt
        messages = [
            {"role": "system", "content": "You are a social media hashtag expert who knows how to create trending, relevant hashtags for maximum engagement."},
            {"role": "user", "content": f"""
            Generate {num_hashtags} relevant hashtags for a short video clip with the following details:

            Video details:
            - Duration: {clip_metadata.get('duration', 'unknown')} seconds
            - Content description: {clip_metadata.get('description', 'A short video clip')}
            - Target audience: {clip_metadata.get('target_audience', 'General audience')}
            - Tone: {clip_metadata.get('tone', 'Casual and engaging')}

            Please format your response as a JSON array of strings, with each string being a hashtag WITHOUT the # symbol.
            Include a mix of popular/trending hashtags and specific ones related to the content.
            Do not include spaces in hashtags.
            """}
        ]

        try:
            response = self._call_openai_api(messages)
            hashtags_data = self._extract_json_from_response(response)

            # Handle both array and object formats
            if isinstance(hashtags_data, list):
                # Remove # symbols if present
                return [tag.lstrip('#') for tag in hashtags_data]
            elif isinstance(hashtags_data, dict) and "hashtags" in hashtags_data:
                return [tag.lstrip('#') for tag in hashtags_data["hashtags"]]
            else:
                logger.warning(f"Unexpected response format: {hashtags_data}")
                # Try to extract hashtags from any field that might contain them
                for key, value in hashtags_data.items():
                    if isinstance(value, list) and all(isinstance(item, str) for item in value):
                        return [tag.lstrip('#') for tag in value]

                # If all else fails, return an empty list
                return []
        except Exception as e:
            logger.error(f"Error generating hashtags: {str(e)}")
            # Implement fallback
            return ["trending", "viral", "fyp", "foryou", "content", "video", "share", "follow", "like", "comment"]

    def generate_platform_variations(self, video_path: str, clip_metadata: Dict[str, Any],
                                    platforms: List[str]) -> Dict[str, Dict[str, Union[str, List[str]]]]:
        """
        Generate platform-specific text variations for a video clip using OpenAI.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            platforms: List of platforms to generate variations for

        Returns:
            Dictionary mapping platform names to dictionaries containing:
                - caption: Platform-specific caption
                - hashtags: Platform-specific hashtags
        """
        # Prepare the prompt
        platforms_str = ", ".join(platforms)
        messages = [
            {"role": "system", "content": "You are a cross-platform social media expert who understands the nuances and best practices for different social media platforms."},
            {"role": "user", "content": f"""
            Generate platform-specific captions and hashtags for a short video clip for the following platforms: {platforms_str}.

            Video details:
            - Duration: {clip_metadata.get('duration', 'unknown')} seconds
            - Content description: {clip_metadata.get('description', 'A short video clip')}
            - Target audience: {clip_metadata.get('target_audience', 'General audience')}
            - Tone: {clip_metadata.get('tone', 'Casual and engaging')}

            For each platform, provide:
            1. A caption optimized for that platform's audience and algorithm
            2. A list of 5-10 hashtags that work well on that specific platform (without the # symbol)

            Please format your response as a JSON object where keys are platform names and values are objects with "caption" and "hashtags" fields.
            Example format:
            {
                "TikTok": {
                    "caption": "Caption text here",
                    "hashtags": ["hashtag1", "hashtag2"]
                },
                "Instagram": {
                    "caption": "Caption text here",
                    "hashtags": ["hashtag1", "hashtag2"]
                }
            }
            """}
        ]

        try:
            response = self._call_openai_api(messages, max_tokens=1000)
            variations_data = self._extract_json_from_response(response)

            # Process the response to ensure consistent format
            result = {}
            for platform in platforms:
                if platform in variations_data:
                    platform_data = variations_data[platform]
                    result[platform] = {
                        "caption": platform_data.get("caption", ""),
                        "hashtags": [tag.lstrip('#') for tag in platform_data.get("hashtags", [])]
                    }
                else:
                    # Fallback if platform not in response
                    result[platform] = {
                        "caption": f"Check out this {clip_metadata.get('description', 'amazing')} video!",
                        "hashtags": ["trending", "viral", platform.lower(), "content", "video"]
                    }

            return result
        except Exception as e:
            logger.error(f"Error generating platform variations: {str(e)}")
            # Implement fallback
            result = {}
            for platform in platforms:
                result[platform] = {
                    "caption": f"Check out this {clip_metadata.get('description', 'amazing')} video!",
                    "hashtags": ["trending", "viral", platform.lower(), "content", "video"]
                }
            return result


class DeepseekTextGenerator(TextGenerator):
    """Text generator using Deepseek's API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        """
        Initialize the Deepseek text generator.

        Args:
            api_key: Deepseek API key (defaults to DEEPSEEK_API_KEY environment variable)
            model: Deepseek model to use (defaults to deepseek-chat)
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            logger.warning("Deepseek API key not found. Please set DEEPSEEK_API_KEY environment variable.")

        self.model = model
        self.api_url = "https://api.deepseek.com/v1/chat/completions"  # This is a placeholder URL
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _call_deepseek_api(self, messages: List[Dict[str, str]],
                          temperature: float = 0.7,
                          max_tokens: int = 500) -> Dict[str, Any]:
        """
        Call the Deepseek API with the given messages.

        Args:
            messages: List of message dictionaries
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate

        Returns:
            API response as a dictionary
        """
        if not self.api_key:
            raise ValueError("Deepseek API key not found. Please set DEEPSEEK_API_KEY environment variable.")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Implement retry logic with exponential backoff
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"API call failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API call failed after {max_retries} attempts")
                    raise

    def _extract_json_from_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract JSON data from a Deepseek API response.

        Args:
            response: Deepseek API response

        Returns:
            Extracted JSON data
        """
        try:
            content = response["choices"][0]["message"]["content"]
            # Try to extract JSON from the content
            try:
                # First, try to parse the entire content as JSON
                return json.loads(content)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))

                # If that fails too, try to find any JSON-like structure
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))

                # If all else fails, raise an exception
                raise ValueError("Could not extract JSON from response")
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting content from API response: {str(e)}")
            raise ValueError(f"Invalid API response format: {str(e)}")

    def generate_captions(self, video_path: str, clip_metadata: Dict[str, Any],
                         num_variations: int = 3) -> List[str]:
        """
        Generate multiple caption variations for a video clip using Deepseek.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            num_variations: Number of caption variations to generate

        Returns:
            List of caption strings
        """
        # Implementation similar to OpenAITextGenerator.generate_captions
        # For now, we'll use a fallback implementation
        return [
            f"Check out this {clip_metadata.get('description', 'amazing')} video!",
            f"Had to share this {clip_metadata.get('description', 'cool')} moment!",
            f"This is what happens when {clip_metadata.get('description', 'creativity strikes')}!"
        ]

    def generate_hashtags(self, video_path: str, clip_metadata: Dict[str, Any],
                         num_hashtags: int = 10) -> List[str]:
        """
        Generate relevant hashtags for a video clip using Deepseek.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            num_hashtags: Number of hashtags to generate

        Returns:
            List of hashtag strings (without the # symbol)
        """
        # Implementation similar to OpenAITextGenerator.generate_hashtags
        # For now, we'll use a fallback implementation
        return ["trending", "viral", "fyp", "foryou", "content", "video", "share", "follow", "like", "comment"]

    def generate_platform_variations(self, video_path: str, clip_metadata: Dict[str, Any],
                                    platforms: List[str]) -> Dict[str, Dict[str, Union[str, List[str]]]]:
        """
        Generate platform-specific text variations for a video clip using Deepseek.

        Args:
            video_path: Path to the video clip
            clip_metadata: Dictionary containing metadata about the clip
            platforms: List of platforms to generate variations for

        Returns:
            Dictionary mapping platform names to dictionaries containing:
                - caption: Platform-specific caption
                - hashtags: Platform-specific hashtags
        """
        # Implementation similar to OpenAITextGenerator.generate_platform_variations
        # For now, we'll use a fallback implementation
        result = {}
        for platform in platforms:
            result[platform] = {
                "caption": f"Check out this {clip_metadata.get('description', 'amazing')} video!",
                "hashtags": ["trending", "viral", platform.lower(), "content", "video"]
            }
        return result