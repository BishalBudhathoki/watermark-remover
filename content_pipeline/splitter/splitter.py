"""
Splitter Module for Content Repurposing Pipeline.

This module provides functions to split videos using MoviePy, automatically
detecting logical splits based on duration thresholds or silent sections.
"""

import os
import logging
import tempfile
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path

import moviepy.editor as mp
from moviepy.video.io.VideoFileClip import VideoFileClip
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define constants
DEFAULT_MAX_CLIP_DURATION = 60  # 60 seconds (for TikTok, Instagram Reels, etc.)
DEFAULT_MIN_CLIP_DURATION = 5   # 5 seconds
DEFAULT_SILENCE_THRESHOLD = 0.03  # Threshold for silence detection
DEFAULT_SILENCE_DURATION = 0.5   # Minimum duration of silence to consider for splitting


def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    Get information about a video file.

    Args:
        video_path: Path to the video file

    Returns:
        Dictionary containing video information:
            - duration: Duration of the video in seconds
            - fps: Frames per second
            - size: Tuple of (width, height)
            - audio: Boolean indicating if the video has audio
    """
    logger.info(f"Getting video info for: {video_path}")

    try:
        with VideoFileClip(video_path) as clip:
            has_audio = clip.audio is not None

            return {
                "duration": clip.duration,
                "fps": clip.fps,
                "size": clip.size,
                "audio": has_audio
            }
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        raise


def detect_silence(video_path: str,
                  threshold: float = DEFAULT_SILENCE_THRESHOLD,
                  min_silence_duration: float = DEFAULT_SILENCE_DURATION) -> List[Tuple[float, float]]:
    """
    Detect silent sections in a video.

    Args:
        video_path: Path to the video file
        threshold: Threshold for silence detection (0.0 to 1.0)
        min_silence_duration: Minimum duration of silence to consider (in seconds)

    Returns:
        List of tuples containing (start_time, end_time) of silent sections
    """
    logger.info(f"Detecting silence in video: {video_path}")

    try:
        with VideoFileClip(video_path) as clip:
            # Check if the video has audio
            if clip.audio is None:
                logger.warning(f"Video has no audio: {video_path}")
                return []

            # Extract the audio as a numpy array
            audio = clip.audio.to_soundarray(fps=22000, nbytes=2)

            # If audio has multiple channels, take the mean
            if audio.ndim > 1:
                audio = audio.mean(axis=1)

            # Calculate the absolute amplitude
            abs_audio = np.abs(audio)

            # Normalize to 0-1 range
            if abs_audio.max() > 0:
                abs_audio = abs_audio / abs_audio.max()

            # Find segments below the threshold
            is_silence = abs_audio < threshold

            # Convert to time segments
            silence_segments = []
            in_silence = False
            silence_start = 0

            for i, silent in enumerate(is_silence):
                time = i / 22000  # Convert sample index to time

                if silent and not in_silence:
                    # Start of a silent segment
                    in_silence = True
                    silence_start = time
                elif not silent and in_silence:
                    # End of a silent segment
                    in_silence = False
                    silence_duration = time - silence_start

                    # Only consider segments longer than min_silence_duration
                    if silence_duration >= min_silence_duration:
                        silence_segments.append((silence_start, time))

            # Handle the case where the video ends during a silent segment
            if in_silence:
                silence_duration = clip.duration - silence_start
                if silence_duration >= min_silence_duration:
                    silence_segments.append((silence_start, clip.duration))

            logger.info(f"Found {len(silence_segments)} silent segments")
            return silence_segments

    except Exception as e:
        logger.error(f"Error detecting silence: {str(e)}")
        return []


def split_video(video_path: str,
               output_dir: Optional[str] = None,
               max_clip_duration: float = DEFAULT_MAX_CLIP_DURATION,
               min_clip_duration: float = DEFAULT_MIN_CLIP_DURATION,
               split_on_silence: bool = False,
               silence_threshold: float = DEFAULT_SILENCE_THRESHOLD,
               silence_duration: float = DEFAULT_SILENCE_DURATION) -> Dict[str, Any]:
    """
    Split a video into multiple clips based on duration thresholds and optionally silent sections.

    Args:
        video_path: Path to the video file
        output_dir: Directory to save the clips (optional, will create a temp dir if not provided)
        max_clip_duration: Maximum duration of each clip in seconds
        min_clip_duration: Minimum duration of each clip in seconds
        split_on_silence: Whether to split on silent sections
        silence_threshold: Threshold for silence detection (0.0 to 1.0)
        silence_duration: Minimum duration of silence to consider (in seconds)

    Returns:
        Dictionary containing:
            - success: Boolean indicating if the splitting was successful
            - clips: List of dictionaries containing clip information:
                - path: Path to the clip
                - duration: Duration of the clip in seconds
                - start_time: Start time of the clip in the original video
                - end_time: End time of the clip in the original video
            - error: Error message (if any)
    """
    logger.info(f"Splitting video: {video_path}")

    try:
        # Create output directory if not provided
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="video_clips_")
            logger.info(f"Created temporary directory for clips: {output_dir}")
        else:
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Using output directory: {output_dir}")

        # Get video info
        video_info = get_video_info(video_path)
        video_duration = video_info["duration"]
        logger.info(f"Video duration: {video_duration:.2f} seconds")

        # Determine split points
        split_points = []

        if split_on_silence and video_info["audio"]:
            # Split on silent sections
            logger.info("Detecting silent sections for splitting...")
            silence_segments = detect_silence(
                video_path,
                threshold=silence_threshold,
                min_silence_duration=silence_duration
            )

            # Use the middle of each silent segment as a split point
            for start, end in silence_segments:
                split_point = (start + end) / 2
                split_points.append(split_point)

            # Add start and end points
            split_points = [0] + sorted(split_points) + [video_duration]
        else:
            # Split based on max_clip_duration
            logger.info(f"Splitting based on max clip duration: {max_clip_duration} seconds")
            num_clips = int(np.ceil(video_duration / max_clip_duration))
            split_points = np.linspace(0, video_duration, num_clips + 1)

        # Filter out split points that would create clips shorter than min_clip_duration
        filtered_split_points = [split_points[0]]
        for i in range(1, len(split_points)):
            if split_points[i] - filtered_split_points[-1] >= min_clip_duration:
                filtered_split_points.append(split_points[i])

        split_points = filtered_split_points
        logger.info(f"Split points: {split_points}")

        # Create clips
        clips = []
        with VideoFileClip(video_path) as video:
            # Get the base filename without extension
            base_filename = os.path.splitext(os.path.basename(video_path))[0]

            # Create a progress bar
            progress_bar = tqdm(total=len(split_points) - 1, desc="Creating clips")

            for i in range(len(split_points) - 1):
                start_time = split_points[i]
                end_time = split_points[i + 1]

                # Create the subclip
                subclip = video.subclip(start_time, end_time)

                # Generate the output filename
                output_filename = f"{base_filename}_clip_{i+1:03d}.mp4"
                output_path = os.path.join(output_dir, output_filename)

                # Write the clip to file
                subclip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=os.path.join(output_dir, f"temp_audio_{i+1}.m4a"),
                    remove_temp=True,
                    logger=None  # Disable moviepy's logger to avoid cluttering the output
                )

                # Add clip info to the list
                clips.append({
                    "path": output_path,
                    "duration": end_time - start_time,
                    "start_time": start_time,
                    "end_time": end_time,
                    "index": i + 1
                })

                # Update the progress bar
                progress_bar.update(1)

            # Close the progress bar
            progress_bar.close()

        logger.info(f"Created {len(clips)} clips")

        return {
            "success": True,
            "clips": clips,
            "error": None,
            "metadata": {
                "original_video": video_path,
                "output_dir": output_dir,
                "total_duration": video_duration,
                "num_clips": len(clips)
            }
        }

    except Exception as e:
        logger.error(f"Error splitting video: {str(e)}")
        return {
            "success": False,
            "clips": [],
            "error": str(e),
            "metadata": {}
        }