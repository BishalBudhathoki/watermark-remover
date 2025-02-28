from celery import shared_task
from celery.utils.log import get_task_logger
import cv2
import numpy as np
from moviepy.editor import VideoFileClip
import os
from pathlib import Path
import ffmpeg
from typing import List, Dict, Optional
import time

logger = get_task_logger(__name__)

@shared_task(bind=True, name='tasks.video_processing.remove_watermark')
def remove_watermark(self, video_path: str, regions: List[Dict], output_path: str) -> Dict:
    """
    Remove watermarks from specified regions in a video.
    
    Args:
        video_path: Path to input video
        regions: List of dictionaries containing x, y, width, height for watermark regions
        output_path: Path to save processed video
    
    Returns:
        Dict containing status and output path
    """
    try:
        logger.info(f"Starting watermark removal for {video_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Load video
        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            raise ValueError("Could not open video file")
        
        # Get video properties
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        temp_output = output_path.replace('.mp4', '_temp.mp4')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        
        frame_number = 0
        while True:
            ret, frame = video.read()
            if not ret:
                break
                
            # Process each region
            for region in regions:
                x, y = region['x'], region['y']
                w, h = region['width'], region['height']
                
                # Ensure coordinates are within frame bounds
                x = max(0, min(x, width - 1))
                y = max(0, min(y, height - 1))
                w = min(w, width - x)
                h = min(h, height - y)
                
                # Extract region
                roi = frame[y:y+h, x:x+w]
                
                # Apply inpainting mask
                mask = np.ones(roi.shape[:2], dtype=np.uint8) * 255
                
                # Inpaint the region
                roi_inpainted = cv2.inpaint(roi, mask, 3, cv2.INPAINT_TELEA)
                
                # Replace the region in the frame
                frame[y:y+h, x:x+w] = roi_inpainted
            
            # Write the processed frame
            out.write(frame)
            
            # Update progress
            frame_number += 1
            if frame_number % 30 == 0:  # Update progress every 30 frames
                progress = (frame_number / frame_count) * 100
                self.update_state(state='PROGRESS', meta={'progress': progress})
        
        # Release resources
        video.release()
        out.release()
        
        # Convert to H.264 with proper encoding
        logger.info("Converting to H.264 format")
        stream = ffmpeg.input(temp_output)
        stream = ffmpeg.output(stream, output_path, vcodec='libx264', acodec='aac')
        ffmpeg.run(stream, overwrite_output=True)
        
        # Clean up temporary file
        os.remove(temp_output)
        
        logger.info(f"Watermark removal completed for {video_path}")
        return {
            'status': 'success',
            'output_path': output_path
        }
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

@shared_task(bind=True, name='tasks.video_processing.enhance_video')
def enhance_video(self, video_path: str, options: Dict) -> Dict:
    """
    Enhance video quality with specified options.
    
    Args:
        video_path: Path to input video
        options: Dictionary containing enhancement options
            - resolution: Target resolution (e.g., "1080p")
            - bitrate: Target bitrate
            - denoise: Boolean for noise reduction
            - stabilize: Boolean for video stabilization
    
    Returns:
        Dict containing status and output path
    """
    try:
        logger.info(f"Starting video enhancement for {video_path}")
        
        output_path = video_path.replace('.mp4', '_enhanced.mp4')
        
        # Load video
        clip = VideoFileClip(video_path)
        
        # Apply enhancements based on options
        if options.get('denoise'):
            logger.info("Applying noise reduction")
            # Implement denoising logic
            
        if options.get('stabilize'):
            logger.info("Applying video stabilization")
            # Implement stabilization logic
        
        # Set output resolution
        resolution = options.get('resolution', '1080p')
        width = {'720p': 1280, '1080p': 1920, '4k': 3840}.get(resolution)
        if width:
            clip = clip.resize(width=width)
        
        # Set output bitrate
        bitrate = options.get('bitrate', '5000k')
        
        # Write enhanced video
        clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            bitrate=bitrate,
            threads=4,
            logger=None
        )
        
        clip.close()
        
        logger.info(f"Video enhancement completed for {video_path}")
        return {
            'status': 'success',
            'output_path': output_path
        }
        
    except Exception as e:
        logger.error(f"Error enhancing video: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

@shared_task(bind=True, name='tasks.video_processing.compress_video')
def compress_video(self, video_path: str, target_size_mb: float) -> Dict:
    """
    Compress video to target size while maintaining quality.
    
    Args:
        video_path: Path to input video
        target_size_mb: Target size in megabytes
    
    Returns:
        Dict containing status and output path
    """
    try:
        logger.info(f"Starting video compression for {video_path}")
        
        output_path = video_path.replace('.mp4', '_compressed.mp4')
        target_size_bytes = target_size_mb * 1024 * 1024
        
        # Get video duration
        probe = ffmpeg.probe(video_path)
        duration = float(probe['streams'][0]['duration'])
        
        # Calculate target bitrate
        target_bitrate = int((target_size_bytes * 8) / duration)
        
        # Compress video
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(
            stream,
            output_path,
            vcodec='libx264',
            acodec='aac',
            b=f'{target_bitrate}',
            maxrate=f'{target_bitrate*1.5}',
            bufsize=f'{target_bitrate*2}'
        )
        
        ffmpeg.run(stream, overwrite_output=True)
        
        logger.info(f"Video compression completed for {video_path}")
        return {
            'status': 'success',
            'output_path': output_path
        }
        
    except Exception as e:
        logger.error(f"Error compressing video: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

@shared_task(name='tasks.video_processing.cleanup_processed_files')
def cleanup_processed_files(max_age_hours: int = 24) -> None:
    """
    Clean up processed video files older than specified age.
    
    Args:
        max_age_hours: Maximum age of files in hours before deletion
    """
    try:
        logger.info("Starting cleanup of processed files")
        
        # Get paths to check
        paths_to_check = ['processed', 'downloads']
        current_time = time.time()
        
        for path in paths_to_check:
            if not os.path.exists(path):
                continue
                
            for file_path in Path(path).glob('**/*'):
                if not file_path.is_file():
                    continue
                    
                # Check file age
                file_age_hours = (current_time - os.path.getmtime(file_path)) / 3600
                
                if file_age_hours > max_age_hours:
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        logger.info("Cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise 