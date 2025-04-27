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
import io
from difflib import SequenceMatcher

# Try to import the unified text generator
try:
    from .ai_models import TextGenerator as UnifiedTextGenerator, AIModel
    UNIFIED_AVAILABLE = True
except ImportError:
    UNIFIED_AVAILABLE = False

try:
    import torch
    BLIP_AVAILABLE = True
except ImportError:
    BLIP_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def advanced_frame_caption(image_bytes):
    if not BLIP_AVAILABLE:
        logger.warning("BLIP not available: skipping local frame captioning.")
        return ""
    try:
        from transformers import pipeline
        blip = pipeline('image-to-text', model='Salesforce/blip-image-captioning-base')
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        result = blip(img)
        caption = result[0]['generated_text'] if result and 'generated_text' in result[0] else ''
        logger.info(f"BLIP caption: {caption}")
        return caption
    except Exception as e:
        logger.error(f"BLIP captioning failed: {e}")
        return ''

def process_clip(
    clip_path: str,
    clip_metadata: Optional[Dict[str, Any]] = None,
    platforms: Optional[List[str]] = None,
    num_caption_variations: int = 3,
    num_hashtags: int = 10,
    text_generator: Optional[TextGenerator] = None,
    text_generator_config: Optional[Dict[str, Any]] = None,
    ai_provider: Optional[str] = None,
    tone_style: Optional[str] = None
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
        tone_style: User-selectable tone/style for text generation

    Returns:
        Dictionary containing:
            - captions: List of caption strings
            - hashtags: List of hashtag strings
            - platforms: Dictionary mapping platform names to dictionaries containing:
                - caption: Platform-specific caption
                - hashtags: Platform-specific hashtags
            - tone_style: The selected tone/style for text generation
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

    # --- Dynamic frame sampling based on video length ---
    video_duration = clip_metadata.get("duration", 0)
    if video_duration > 60:
        num_frames = 15
    elif video_duration > 30:
        num_frames = 10
    else:
        num_frames = 5
    frame_descriptions = extract_video_frames(clip_path, num_frames=num_frames)
    if frame_descriptions:
        clip_metadata["frame_descriptions"] = frame_descriptions
        logger.info(f"Extracted {len(frame_descriptions)} frame descriptions from video")

    # Check if this is likely a comedy video based on filename or description
    is_comedy = False
    comedy_keywords = ["funny", "comedy", "laugh", "hilarious", "joke", "humor", "prank", "gag", "blooper"]

    # Only check filename and description for explicit comedy indicators
    filename = os.path.basename(clip_path).lower()
    if any(keyword in filename for keyword in comedy_keywords):
        is_comedy = True
        logger.info(f"Detected comedy content from filename: {filename}")

    # Check metadata description for explicit comedy indicators
    if not is_comedy and "description" in clip_metadata:
        if any(keyword in clip_metadata["description"].lower() for keyword in comedy_keywords):
            is_comedy = True
            logger.info(f"Detected comedy content from description: {clip_metadata['description']}")

    # Remove automatic comedy detection from frame analysis
    if not is_comedy and frame_descriptions:
        for frame in frame_descriptions:
            if "analysis" in frame:
                # Remove content type from frame analysis to prevent false positives
                if "content_type" in frame["analysis"]:
                    del frame["analysis"]["content_type"]

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

    user_description = clip_metadata.get("description", "") if clip_metadata else ""
    fallback = os.path.basename(clip_path)

    # --- Gemini Vision and local analysis integration ---
    gemini_descriptions = []
    frame_captions = []
    try:
        from .ai_models import get_gemini_vision_description
        # Use up to 3 key frames for Gemini Vision and BLIP
        for idx, frame in enumerate((frame_descriptions or [])[:3]):
            img_b64 = frame.get("image_data")
            if img_b64:
                image_bytes = base64.b64decode(img_b64)
                # Try Gemini Vision first
                vision_desc = get_gemini_vision_description(image_bytes)
                if vision_desc:
                    gemini_descriptions.append(vision_desc)
                # Always run BLIP as local fallback
                blip_caption = advanced_frame_caption(image_bytes)
                if blip_caption:
                    frame_captions.append(f"Frame {idx+1}: {blip_caption}")
    except Exception as e:
        logger.error(f"Gemini Vision/BLIP integration failed: {e}")

    # --- Tone/style selection ---
    # Use user-selected tone/style if provided, else fallback to caption_style or 'casual'
    selected_style = tone_style or clip_metadata.get('caption_style', 'casual')
    logger.info(f"Using tone/style: {selected_style}")

    # Build context summary before prompt construction
    context_parts = []
    if user_description:
        context_parts.append(f"User description: {user_description}")
    if gemini_descriptions:
        context_parts.append("Gemini Vision analysis:")
        context_parts.extend(gemini_descriptions)
    if frame_captions:
        context_parts.append("Local frame captions:")
        context_parts.extend(frame_captions)
    if not context_parts:
        context_parts.append(fallback)
    summarized = "\n".join(context_parts)
    logger.info(f"Context summary for AI model:\n{summarized}")

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

            # Get frame descriptions if available
            frame_descriptions = clip_metadata.get('frame_descriptions', None)
            if frame_descriptions:
                logger.info(f"Using {len(frame_descriptions)} frame descriptions for text generation")

            # Build a clear, explicit prompt for the AI model
            def build_generation_prompt(context, task, style, num_items, item_type):
                if item_type == "captions":
                    diversity_instruction = (
                        "Each caption must offer a unique perspective or highlight a different aspect of the video's content. "
                        "Think about different angles a viewer might find interesting or engaging. "
                        "Aim for a mix of concise, descriptive, and potentially engaging tones. "
                        "Avoid repeating the same core message with slightly different wording. "
                        "If possible, relate each caption to a distinct moment, action, or key visual element within the video. "
                        "If the video tells a story or has a progression, each caption should touch upon a different part. "
                        "Vary the tone: some captions can be attention-grabbing, others descriptive, and some humorous or inquisitive."
                    )
                else:
                    diversity_instruction = ""
                # Add explicit style/tone instruction
                style_instruction = f"Use a {style} style that matches the user's preference. "
                return (
                    f"Context:\n{context}\n"
                    f"Task: Generate {num_items} {style} {item_type} for a social media post about this video. "
                    f"Do not mention the context or analysis block. Output only the {item_type}, one per line.\n"
                    f"{style_instruction}"
                    f"{diversity_instruction}"
                )

            # Use the summarized context for both captions and hashtags
            logger.info(f"Context being sent to prompt builder: {summarized}")
            prompt_captions = build_generation_prompt(
                summarized,
                task="Generate captions",
                style=selected_style,
                num_items=num_caption_variations,
                item_type="captions"
            )
            prompt_hashtags = build_generation_prompt(
                summarized,
                task="Generate hashtags",
                style=selected_style,
                num_items=num_hashtags,
                item_type="hashtags"
            )
            # Pass these prompts to the text generator
            # (Override video_description for captions, and pass prompt_hashtags for hashtags)
            # Only for unified text generator
            # Generate captions
            logger.info(f"Prompt for captions:\n{prompt_captions}")
            captions = text_generator.generate_captions(
                video_description=prompt_captions,
                num_variations=num_caption_variations,
                caption_style=selected_style,
                frame_descriptions=frame_descriptions
            )
            # Generate hashtags
            logger.info(f"Prompt for hashtags:\n{prompt_hashtags}")
            hashtags = text_generator.generate_hashtags(
                video_description=prompt_hashtags,
                num_hashtags=num_hashtags,
                caption_style=selected_style,
                frame_descriptions=frame_descriptions
            )

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

        # After hashtags are generated, ensure they all start with #
        if hashtags:
            hashtags = [tag if tag.startswith('#') else f'#{tag.lstrip('#')}' for tag in hashtags]

        # Filter similar captions
        captions = filter_similar_captions(captions)

        # Return the results
        overall_duration = time.time() - overall_start_time
        logger.info(f"Total text generation process completed in {overall_duration:.2f} seconds")

        return {
            "path": clip_path,
            "captions": captions,
            "hashtags": hashtags,
            "platforms": platform_variations,
            "tone_style": selected_style
        }

    except Exception as e:
        logger.error(f"Error processing clip: {str(e)}")
        # Return fallback results (do not reference 'summarized')
        fallback_desc = user_description or os.path.basename(clip_path)
        fallback_captions = [
            f"Check out this {fallback_desc} video!",
            f"Had to share this {fallback_desc} moment!",
            f"This is what happens when {fallback_desc}!"
        ]
        fallback_hashtags = ["#trending", "#viral", "#fyp", "#foryou", "#content", "#video", "#share", "#follow", "#like", "#comment"]
        fallback_platforms = {}
        for platform in platforms:
            fallback_platforms[platform] = {
                "caption": f"Check out this {fallback_desc} video!",
                "hashtags": ["#trending", "#viral", f"#{platform.lower()}", "#content", "#video"]
            }
        overall_duration = time.time() - overall_start_time
        logger.info(f"Total text generation process (fallback) completed in {overall_duration:.2f} seconds")
        return {
            "path": clip_path,
            "captions": fallback_captions[:num_caption_variations],
            "hashtags": fallback_hashtags[:num_hashtags],
            "platforms": fallback_platforms,
            "tone_style": selected_style
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
            raise FileNotFoundError(f"Could not open video file: {video_path}")

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
            try:
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Failed to read frame {idx} from {video_path}")
                    continue
                # Convert frame to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            except cv2.error as e:
                logger.error(f"cv2 error reading frame {idx}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error reading frame {idx}: {e}")
                continue

            # Create a basic description of the frame
            timestamp = idx / fps if fps > 0 else 0
            height, width, _ = frame.shape

            # Perform basic image analysis
            try:
                frame_analysis = analyze_frame_content(frame_rgb)
            except Exception as e:
                logger.error(f"Error analyzing frame {idx}: {e}")
                frame_analysis = {"error": str(e)}

            # Convert frame to base64 for potential use with vision models
            try:
                pil_img = Image.fromarray(frame_rgb)
                buffered = BytesIO()
                pil_img.save(buffered, format="JPEG", quality=70)  # Lower quality to reduce size
                img_str = base64.b64encode(buffered.getvalue()).decode()
            except Exception as e:
                logger.error(f"Error encoding frame {idx} to base64: {e}")
                img_str = ""

            frame_descriptions.append({
                "timestamp": timestamp,
                "position": f"{timestamp:.2f}s / {duration:.2f}s",
                "resolution": f"{width}x{height}",
                "frame_index": idx,
                "image_data": img_str,
                "analysis": frame_analysis
            })

        cap.release()
        logger.info(f"Extracted {len(frame_descriptions)} frames from video {video_path}")
        return frame_descriptions

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return []
    except cv2.error as e:
        logger.error(f"OpenCV error: {e}")
        return []
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

        # Face description
        if has_faces:
            if num_faces == 1:
                description.append("shows 1 person")
                # Check for potential expressive faces (but do not guess comedy)
                for (x, y, w, h) in faces:
                    face_roi = frame[y:y+h, x:x+w]
                    if face_roi.size > 0:
                        face_gray = cv2.cvtColor(face_roi, cv2.COLOR_RGB2GRAY)
                        face_edges = cv2.Canny(face_gray, 100, 200)
                        face_edge_density = np.count_nonzero(face_edges) / (face_edges.shape[0] * face_edges.shape[1])
                        if face_edge_density > 0.15:
                            description.append("possibly expressive face")
            else:
                description.append(f"shows {num_faces} people")
                if num_faces >= 2:
                    description.append("social interaction")

        # Text description
        if has_text:
            description.append("contains text")

        # Create a summary (do not guess content type unless certain)
        summary = "Frame " + ", ".join(description)

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

def filter_similar_captions(captions, threshold=0.8):
    unique = []
    for caption in captions:
        if all(SequenceMatcher(None, caption, u).ratio() < threshold for u in unique):
            unique.append(caption)
    return unique