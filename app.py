# app.py
import os
import tempfile
import sys
import yt_dlp

# Add the moviepy path to system path
sys.path.append(os.path.join(os.path.dirname(__file__), '.venv/lib/python3.11/site-packages'))

# Import imageio-ffmpeg first
import imageio_ffmpeg
# Set environment variable for ffmpeg
os.environ['IMAGEIO_FFMPEG_EXE'] = imageio_ffmpeg.get_ffmpeg_exe()

from flask import Flask, request, render_template, redirect, url_for, send_file, send_from_directory, flash
from werkzeug.utils import secure_filename
import cv2
import numpy as np
from moviepy.editor import VideoFileClip

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['PROCESSED_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'm4v', '3gp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file uploaded.", 400
        
        file = request.files['file']
        if file.filename == '':
            return "No file selected.", 400
            
        if not allowed_file(file.filename):
            return "Invalid file format. Supported formats: MP4, MOV, M4V, 3GP", 400
            
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return redirect(url_for('remove_watermark', filename=filename))
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/processed/<filename>')
def processed_file(filename):
    file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    print(f"Attempting to serve processed file: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

@app.route('/remove/<filename>', methods=['GET', 'POST'])
def remove_watermark(filename):
    if request.method == 'POST':
        regions_str = request.form.get('regions', '')
        if not regions_str:
            return "No regions selected", 400
        
        try:
            # Parse regions from form data
            regions = []
            for region in regions_str.split(';'):
                if region:
                    try:
                        x, y, w, h = map(float, region.split(','))
                        # Ensure positive width and height
                        w = abs(w)
                        h = abs(h)
                        regions.append([x, y, w, h])
                    except ValueError as e:
                        print(f"Error parsing region {region}: {str(e)}")
                        continue
            
            if not regions:
                return "Invalid region data", 400
            
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            output_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
            
            # Process the video
            if process_video(input_path, regions, output_path):
                return redirect(url_for('preview', filename=filename))
            else:
                return "Error processing video", 500
                
        except Exception as e:
            print(f"Error in remove_watermark: {str(e)}")
            return f"Error processing video: {str(e)}", 500
            
    return render_template('remove.html', filename=filename)

def process_video(input_path, regions, output_path):
    try:
        clip = VideoFileClip(input_path)
        
        def remove_watermark(frame):
            # Convert frame to BGR (OpenCV format)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            for region in regions:
                x, y, w, h = map(int, region)
                
                # Ensure coordinates are within frame bounds
                x = max(0, min(x, frame_bgr.shape[1] - 1))
                y = max(0, min(y, frame_bgr.shape[0] - 1))
                w = max(0, min(w, frame_bgr.shape[1] - x))
                h = max(0, min(h, frame_bgr.shape[0] - y))
                
                if w <= 0 or h <= 0:
                    continue
                
                # Create mask for the selected region
                mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
                mask[y:y+h, x:x+w] = 255
                
                # Expand the region slightly for better blending
                expanded_x = max(0, x - 10)
                expanded_y = max(0, y - 10)
                expanded_w = min(frame_bgr.shape[1] - expanded_x, w + 20)
                expanded_h = min(frame_bgr.shape[0] - expanded_y, h + 20)
                
                # Apply inpainting
                frame_bgr = cv2.inpaint(
                    frame_bgr,
                    mask,
                    inpaintRadius=3,
                    flags=cv2.INPAINT_TELEA
                )
                
                # Additional content-aware fill using surrounding pixels
                roi = frame_bgr[expanded_y:expanded_y+expanded_h, expanded_x:expanded_x+expanded_w]
                if roi.size > 0:
                    # Apply slight blur to blend the edges
                    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
                    mask_roi = mask[expanded_y:expanded_y+expanded_h, expanded_x:expanded_x+expanded_w]
                    roi[mask_roi > 0] = blurred[mask_roi > 0]
            
            # Convert back to RGB
            return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        
        # Process the video
        processed_clip = clip.fl_image(remove_watermark)
        
        # Write the processed video with original audio
        processed_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            audio=clip.audio is not None
        )
        
        # Clean up
        clip.close()
        processed_clip.close()
        
        return True
        
    except Exception as e:
        print(f"Error in process_video: {str(e)}")
        raise e

@app.route('/download/<filename>')
def download(filename):
    return send_file(
        os.path.join(app.config['PROCESSED_FOLDER'], filename),
        as_attachment=True
    )

@app.route('/static/processed/<filename>')
def serve_processed_video(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

@app.route('/preview/<filename>')
def preview(filename):
    file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    print(f"Preview route - Processed file path: {file_path}")
    print(f"Preview route - File exists: {os.path.exists(file_path)}")
    return render_template('preview.html', filename=filename)

@app.route('/download-video', methods=['POST'])
def download_video():
    video_url = request.form.get('url')
    format_type = request.form.get('format', 'video')
    video_quality = request.form.get('video_quality', 'highest')
    audio_quality = request.form.get('audio_quality', 'best')
    output_format = request.form.get('output_format', 'mp4')

    if not video_url:
        flash('Please provide a valid video URL')
        return redirect(url_for('index'))

    try:
        # Create a temporary directory for downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            # Base options
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }

            # Configure format based on user selection
            if format_type == 'audio':
                # Audio-only options
                audio_formats = {
                    'best': 'bestaudio/best',
                    'good': 'bestaudio[abr<=128]/best',
                    'medium': 'bestaudio[abr<=96]/best',
                    'low': 'bestaudio[abr<=64]/best'
                }
                
                # For audio downloads, we need to extract audio
                ydl_opts.update({
                    'format': audio_formats.get(audio_quality, 'bestaudio/best'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': output_format,
                        'preferredquality': '192' if audio_quality == 'best' else '128',
                    }],
                    # Force the extension for audio files
                    'force_overwrites': True,
                    'writethumbnail': False,
                })
            else:
                # Video options
                video_formats = {
                    'highest': 'bestvideo+bestaudio/best',
                    '4k': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
                    '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                    '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                    '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
                    '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]'
                }
                
                # For video downloads
                ydl_opts.update({
                    'format': video_formats.get(video_quality, 'bestvideo+bestaudio/best'),
                    'merge_output_format': output_format,
                    'force_overwrites': True,
                })

            # Download the video/audio
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to get the title
                info = ydl.extract_info(video_url, download=False)
                title = ydl.sanitize_info(info)['title']
                
                # Download the file
                ydl.download([video_url])
                
                # Construct the expected filename
                if format_type == 'audio':
                    downloaded_file = os.path.join(temp_dir, f"{title}.{output_format}")
                else:
                    # For videos, the extension is handled by merge_output_format
                    downloaded_file = os.path.join(temp_dir, f"{title}.{output_format}")
                
                # Check if file exists
                if not os.path.exists(downloaded_file):
                    # Try to find the file with any extension
                    files = os.listdir(temp_dir)
                    if files:
                        downloaded_file = os.path.join(temp_dir, files[0])

            # Send the file to the user with proper filename
            return send_file(
                downloaded_file,
                as_attachment=True,
                download_name=f"{title}.{output_format}"
            )

    except Exception as e:
        print(f"Download error: {str(e)}")  # Add logging for debugging
        flash(f'Error downloading: {str(e)}')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', '5000'), debug=True)