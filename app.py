# app.py
import os
import tempfile
# Import imageio-ffmpeg first
import imageio_ffmpeg
# Set environment variable for ffmpeg
os.environ['IMAGEIO_FFMPEG_EXE'] = imageio_ffmpeg.get_ffmpeg_exe()

from flask import Flask, request, render_template, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
import cv2
import numpy as np
# Now import moviepy
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
    return render_template('preview.html', filename=filename)

if __name__ == '__main__':
    app.run(debug=True)