"""
Integration module for the text generator.

This module provides functions to integrate the text generator with the rest of the pipeline.
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional

from .factory import TextGeneratorFactory
from .text_generator import TextGenerator
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image

# Try to import the unified text generator
try:
    from .ai_models import TextGenerator as UnifiedTextGenerator, AIModel
    UNIFIED_AVAILABLE = True
except ImportError:
    UNIFIED_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_clip(
    clip_path: str,
    clip_metadata: Optional[Dict[str, Any]] = None,
    platforms: Optional[List[str]] = None,
    num_caption_variations: int = 3,
    num_hashtags: int = 10,
    text_generator: Optional[TextGenerator] = None,
    text_generator_config: Optional[Dict[str, Any]] = None,
    ai_provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a video clip to generate captions, hashtags, and platform-specific text variations.

    Args:
        clip_path: Path to the video clip
        clip_metadata: Dictionary containing metadata about the clip (optional)
        platforms: List of platforms to generate variations for (default: ["TikTok", "Instagram", "YouTube"])
        num_caption_variations: Number of caption variations to generate
        num_hashtags: Number of hashtags to generate
        text_generator: TextGenerator instance (optional, will create one if not provided)
        text_generator_config: Configuration for the text generator (optional)
        ai_provider: AI provider to use ('openai', 'deepseek', or 'gemini') (optional)

    Returns:
        Dictionary containing:
            - captions: List of caption strings
            - hashtags: List of hashtag strings
            - platforms: Dictionary mapping platform names to dictionaries containing:
                - caption: Platform-specific caption
                - hashtags: Platform-specific hashtags
    """
    overall_start_time = time.time()

    # Set default platforms if not provided
    if platforms is None:
        platforms = ["TikTok", "Instagram", "YouTube"]

    # Set default clip_metadata if not provided
    if clip_metadata is None:
        clip_metadata = {
            "description": os.path.basename(clip_path),
            "duration": 0,
            "width": 0,
            "height": 0
        }

    logger.info(f"Starting text generation process for clip: {os.path.basename(clip_path)}")
    logger.info(f"Using AI provider: {ai_provider if ai_provider else 'default'}")

    # Extract frames from the video for better content analysis
    frame_descriptions = extract_video_frames(clip_path)
    if frame_descriptions:
        clip_metadata["frame_descriptions"] = frame_descriptions
        logger.info(f"Extracted {len(frame_descriptions)} frame descriptions from video")

    # Check if this is likely a comedy video based on filename or description
    is_comedy = False
    comedy_keywords = ["funny", "comedy", "laugh", "hilarious", "joke", "humor", "prank", "gag", "blooper"]

    # Check filename for comedy indicators
    filename = os.path.basename(clip_path).lower()
    for keyword in comedy_keywords:
        if keyword.lower() in filename:
            is_comedy = True
            logger.info(f"Detected comedy content from filename: {filename}")
            break

    # Check metadata description for comedy indicators
    if not is_comedy and "description" in clip_metadata:
        for keyword in comedy_keywords:
            if keyword.lower() in clip_metadata["description"].lower():
                is_comedy = True
                logger.info(f"Detected comedy content from description: {clip_metadata['description']}")
                break

    # Check frame descriptions for comedy indicators
    if not is_comedy and frame_descriptions:
        comedy_frames = 0
        for frame in frame_descriptions:
            if "analysis" in frame and "content_type" in frame["analysis"]:
                if "comedy" in frame["analysis"]["content_type"].lower():
                    comedy_frames += 1

        if comedy_frames >= 2:
            is_comedy = True
            logger.info(f"Detected comedy content from {comedy_frames} video frames")

    # If comedy is detected, set the caption style to humorous
    if is_comedy and "caption_style" not in clip_metadata:
        clip_metadata["caption_style"] = "humorous"
        logger.info("Setting caption style to 'humorous' based on content detection")

    # Create text generator if not provided
    if text_generator is None:
        generator_start_time = time.time()
        # Update config with AI provider if specified
        if text_generator_config is None:
            text_generator_config = {}

        if ai_provider:
            text_generator_config['provider'] = ai_provider

        # Set use_unified to True to use the new AI models if available
        if UNIFIED_AVAILABLE:
            text_generator_config['use_unified'] = True

        try:
            logger.info(f"Creating text generator with config: {text_generator_config}")
            text_generator = TextGeneratorFactory.create(text_generator_config)
            generator_creation_time = time.time() - generator_start_time
            logger.info(f"Text generator created in {generator_creation_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error creating text generator: {str(e)}")
            # Fall back to a simple text generator that returns default values
            text_generator = None

    logger.info(f"Generating text for clip: {os.path.basename(clip_path)}")

    try:
        # Check if we're using the unified text generator
        if UNIFIED_AVAILABLE and isinstance(text_generator, UnifiedTextGenerator):
            # Extract video description from metadata
            video_description = clip_metadata.get('description', os.path.basename(clip_path))

            # Add more context to the description for better generation
            if 'duration' in clip_metadata:
                video_description += f" (Duration: {clip_metadata['duration']:.1f} seconds)"

            # Log the provider being used
            logger.info(f"Using AI provider: {text_generator.model_type.value}")

            # Get caption style if provided
            caption_style = clip_metadata.get('caption_style', 'casual')
            logger.info(f"Using caption style: {caption_style}")

            # Get frame descriptions if available
            frame_descriptions = clip_metadata.get('frame_descriptions', None)
            if frame_descriptions:
                logger.info(f"Using {len(frame_descriptions)} frame descriptions for text generation")

            # Generate captions
            logger.info(f"Generating {num_caption_variations} caption variations with {caption_style} style")
            try:
                captions = text_generator.generate_captions(
                    video_description=video_description,
                    num_variations=num_caption_variations,
                    caption_style=caption_style,
                    frame_descriptions=frame_descriptions
                )
                # Ensure there's at least some content
                if not captions or all(not caption for caption in captions):
                    logger.warning("No valid captions returned, using fallback captions")
                    desc = os.path.basename(clip_path).replace('_', ' ').replace('.mp4', '')
                    captions = [
                        f"Check out this {desc} video!",
                        f"Had to share this {desc} moment!",
                        f"This {desc} is too good not to share!"
                    ]
            except Exception as e:
                logger.error(f"Error generating captions: {str(e)}")
                desc = os.path.basename(clip_path).replace('_', ' ').replace('.mp4', '')
                captions = [
                    f"Check out this {desc} video!",
                    f"Had to share this {desc} moment!",
                    f"This {desc} is too good not to share!"
                ]

            # Generate hashtags
            logger.info(f"Generating {num_hashtags} hashtags")
            try:
                hashtags = text_generator.generate_hashtags(
                    video_description=video_description,
                    num_hashtags=num_hashtags,
                    caption_style=caption_style,
                    frame_descriptions=frame_descriptions
                )
                # Ensure there's at least some content
                if not hashtags or all(not tag for tag in hashtags):
                    logger.warning("No valid hashtags returned, using fallback hashtags")
                    hashtags = ["trending", "viral", "video", "content", "social", "follow", "share", "like", "comment", "fyp"]
            except Exception as e:
                logger.error(f"Error generating hashtags: {str(e)}")
                hashtags = ["trending", "viral", "video", "content", "social", "follow", "share", "like", "comment", "fyp"]

            # Log what was generated
            logger.info(f"Generated {len(captions)} captions and {len(hashtags)} hashtags")

            # Generate platform-specific variations (simplified for unified text generator)
            logger.info(f"Generating platform-specific variations for: {', '.join(platforms)}")
            platform_variations = {}
            for platform in platforms:
                platform_variations[platform] = {
                    "caption": captions[0] if captions else "",
                    "hashtags": hashtags
                }
        elif text_generator is not None:
            # Using legacy text generator
            # Generate captions
            logger.info(f"Generating {num_caption_variations} caption variations")
            captions = text_generator.generate_captions(
                video_path=clip_path,
                clip_metadata=clip_metadata,
                num_variations=num_caption_variations
            )

            # Generate hashtags
            logger.info(f"Generating {num_hashtags} hashtags")
            hashtags = text_generator.generate_hashtags(
                video_path=clip_path,
                clip_metadata=clip_metadata,
                num_hashtags=num_hashtags
            )

            # Generate platform-specific variations
            logger.info(f"Generating platform-specific variations for: {', '.join(platforms)}")
            platform_variations = text_generator.generate_platform_variations(
                video_path=clip_path,
                clip_metadata=clip_metadata,
                platforms=platforms
            )
        else:
            # No text generator available, use fallback values
            raise ValueError("No text generator available")

        # Return the results
        overall_duration = time.time() - overall_start_time
        logger.info(f"Total text generation process completed in {overall_duration:.2f} seconds")

        return {
            "path": clip_path,
            "captions": captions,
            "hashtags": hashtags,
            "platforms": platform_variations
        }

    except Exception as e:
        logger.error(f"Error processing clip: {str(e)}")
        # Return fallback results
        fallback_captions = [
            f"Check out this {clip_metadata.get('description', 'amazing')} video!",
            f"Had to share this {clip_metadata.get('description', 'cool')} moment!",
            f"This is what happens when {clip_metadata.get('description', 'creativity strikes')}!"
        ]
        fallback_hashtags = ["trending", "viral", "fyp", "foryou", "content", "video", "share", "follow", "like", "comment"]
        fallback_platforms = {}
        for platform in platforms:
            fallback_platforms[platform] = {
                "caption": f"Check out this {clip_metadata.get('description', 'amazing')} video!",
                "hashtags": ["trending", "viral", platform.lower(), "content", "video"]
            }

        overall_duration = time.time() - overall_start_time
        logger.info(f"Total text generation process (fallback) completed in {overall_duration:.2f} seconds")

        return {
            "path": clip_path,
            "captions": fallback_captions[:num_caption_variations],
            "hashtags": fallback_hashtags[:num_hashtags],
            "platforms": fallback_platforms
        }

def extract_video_frames(video_path: str, num_frames: int = 5) -> List[Dict]:
    """
    Extract and describe key frames from a video.

    Args:
        video_path: Path to the video file
        num_frames: Number of frames to extract

    Returns:
        List of frame descriptions
    """
    try:
        # Open the video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video file: {video_path}")
            return []

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0

        # Calculate frame indices to extract (evenly distributed)
        if total_frames <= num_frames:
            frame_indices = list(range(total_frames))
        else:
            frame_indices = [int(i * total_frames / num_frames) for i in range(num_frames)]

        # Extract frames
        frame_descriptions = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                # Convert frame to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Create a basic description of the frame
                timestamp = idx / fps if fps > 0 else 0
                height, width, _ = frame.shape

                # Perform basic image analysis
                frame_analysis = analyze_frame_content(frame_rgb)

                # Convert frame to base64 for potential use with vision models
                pil_img = Image.fromarray(frame_rgb)
                buffered = BytesIO()
                pil_img.save(buffered, format="JPEG", quality=70)  # Lower quality to reduce size
                img_str = base64.b64encode(buffered.getvalue()).decode()

                frame_descriptions.append({
                    "timestamp": timestamp,
                    "position": f"{timestamp:.2f}s / {duration:.2f}s",
                    "resolution": f"{width}x{height}",
                    "frame_index": idx,
                    "image_data": img_str,
                    "analysis": frame_analysis
                })

        cap.release()
        logger.info(f"Extracted {len(frame_descriptions)} frames from video")
        return frame_descriptions

    except Exception as e:
        logger.error(f"Error extracting frames from video: {str(e)}")
        return []

def analyze_frame_content(frame):
    """
    Perform basic analysis of frame content.

    Args:
        frame: RGB frame as numpy array

    Returns:
        Dictionary with analysis results
    """
    try:
        # Convert to grayscale for some analyses
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # Calculate brightness
        brightness = np.mean(gray) / 255.0

        # Calculate color distribution
        color_means = np.mean(frame, axis=(0, 1)) / 255.0

        # Detect edges (for complexity estimation)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.count_nonzero(edges) / (edges.shape[0] * edges.shape[1])

        # Attempt to detect faces
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        has_faces = len(faces) > 0
        num_faces = len(faces)

        # Attempt to detect text using contour analysis
        # This is a simple approximation, not as good as OCR
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
        dilated = cv2.dilate(thresh, kernel, iterations=3)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter contours that might be text
        potential_text_regions = 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if 10 < w < 300 and 10 < h < 100 and w > h:
                potential_text_regions += 1

        has_text = potential_text_regions > 3

        # Create a textual description
        description = []

        # Brightness description - use more neutral language
        if brightness < 0.2:
            description.append("low lighting")
        elif brightness < 0.4:
            description.append("dim lighting")
        elif brightness > 0.8:
            description.append("bright lighting")
        elif brightness > 0.6:
            description.append("well-lit")
        else:
            description.append("moderate lighting")

        # Color description - use more neutral language
        r, g, b = color_means

        # Determine dominant color
        max_color = max(r, g, b)
        if max_color > 0.3:  # Only describe color if it's significant
            if r > g * 1.2 and r > b * 1.2:
                description.append("warm color tones")
            elif g > r * 1.2 and g > b * 1.2:
                description.append("green color tones")
            elif b > r * 1.2 and b > g * 1.2:
                description.append("cool color tones")
            elif r > 0.6 and g > 0.6 and b < 0.5:
                description.append("warm yellow tones")
            elif r > 0.6 and b > 0.6 and g < 0.5:
                description.append("purple tones")
            elif g > 0.6 and b > 0.6 and r < 0.5:
                description.append("teal tones")

        # Complexity description
        if edge_density < 0.05:
            description.append("simple composition")
        elif edge_density > 0.2:
            description.append("detailed composition")

        # Face description - add potential for comedy detection
        if has_faces:
            if num_faces == 1:
                description.append("shows 1 person")

                # Check for potential comedy indicators in facial features
                # This is a simple heuristic and not very accurate
                for (x, y, w, h) in faces:
                    face_roi = frame[y:y+h, x:x+w]
                    # A simple check for exaggerated expressions
                    if face_roi.size > 0:  # Make sure the ROI is valid
                        face_gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
                        face_edges = cv2.Canny(face_gray, 100, 200)
                        face_edge_density = np.count_nonzero(face_edges) / (face_edges.shape[0] * face_edges.shape[1])

                        # Higher edge density in face might indicate exaggerated expressions
                        if face_edge_density > 0.15:
                            description.append("possibly expressive face")
            else:
                description.append(f"shows {num_faces} people")
                # Multiple people often indicates social/comedy content
                if num_faces >= 2:
                    description.append("social interaction")

        # Text description
        if has_text:
            description.append("contains text")

        # Create a summary
        summary = "Frame " + ", ".join(description)

        # Add content type estimation
        content_type = estimate_content_type(frame, brightness, edge_density, has_faces, num_faces)
        if content_type:
            summary += f". Possible content type: {content_type}."

        return {
            "brightness": brightness,
            "color_distribution": {
                "red": float(r),
                "green": float(g),
                "blue": float(b)
            },
            "complexity": edge_density,
            "has_faces": has_faces,
            "num_faces": num_faces,
            "has_text": has_text,
            "content_type": content_type,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Error analyzing frame: {str(e)}")
        return {"summary": "Frame analysis failed", "error": str(e)}

def estimate_content_type(frame, brightness, edge_density, has_faces, num_faces):
    """
    Estimate the content type of a frame based on visual characteristics.
    This is a simple heuristic and not very accurate.

    Args:
        frame: RGB frame as numpy array
        brightness: Frame brightness value
        edge_density: Edge density value
        has_faces: Whether faces are detected
        num_faces: Number of faces detected

    Returns:
        String describing the estimated content type
    """
    # Multiple faces often indicate social/comedy content
    if num_faces >= 2:
        return "social or comedy"

    # High edge density can indicate action or comedy
    if edge_density > 0.2:
        return "action or comedy"

    # Check for color variance (comedy often has higher color variance)
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)
    color_variance = np.var(h)

    if color_variance > 1500:
        return "vibrant or comedy"

    # Default to neutral description
    return "general content"