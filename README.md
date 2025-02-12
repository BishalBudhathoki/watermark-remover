# WatermarkAway Documentation

## Overview
WatermarkAway is a web application designed to remove watermarks from videos and download content from platforms like TikTok. The application allows users to:
- Upload videos and process them to remove watermarks.
- Download processed videos.
- Download videos from TikTok profiles.

## Table of Contents
1. [Technologies Used](#technologies-used)
2. [Installation](#installation)
3. [Usage](#usage)
4. [File Structure](#file-structure)
5. [Endpoints](#endpoints)
6. [Redis Integration](#redis-integration)
7. [Frontend](#frontend)
8. [Contributing](#contributing)
9. [License](#license)

## Technologies Used

- ![Python](https://img.icons8.com/color/48/000000/python.png) **Python**: Primary programming language for the backend.
- ![Flask](https://img.icons8.com/color/48/000000/flask.png) **Flask**: Lightweight WSGI web application framework for Python.
- ![YouTube](https://img.icons8.com/color/48/000000/youtube-play.png) **yt-dlp**: Command-line program to download videos from YouTube and other sites.
- ![OpenCV](https://img.icons8.com/color/48/000000/opencv.png) **OpenCV**: Library for computer vision tasks, used for video processing.
- ![Movie](https://img.icons8.com/color/48/000000/movie.png) **MoviePy**: Python library for video editing.
- ![Redis](https://img.icons8.com/color/48/000000/redis.png) **Redis**: In-memory data structure store used for caching and tracking downloads.
- ![HTML](https://img.icons8.com/color/48/000000/html-5.png) **HTML/CSS**: For the frontend user interface.

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/watermarkaway.git
   cd watermarkaway
   ```

2. Create a virtual environment:
   ```sh
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```sh
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```sh
     source venv/bin/activate
     ```

4. Install the required packages:
   ```sh
   pip install -r requirements.txt
   ```

5. Set up Redis:
   - Ensure Redis is installed and running on your machine. You can download it from [Redis.io](https://redis.io/).
   - Create a `.env` file in the root directory and add your environment variables:
     ```sh
     RAPID_API_KEY=your_api_key
     RAPID_API_HOST=your_api_host
     ```

## Usage

1. Start the Flask application:
   ```sh
   python app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5001
   ```

3. Use the application to:
   - Upload videos and remove watermarks.
   - Download TikTok videos.

## File Structure
```
watermarkaway/
│
├── app.py                     # Main application file
├── requirements.txt           # Python dependencies
├── .gitignore                  # Files and directories to ignore in Git
├── .env                        # Environment variables
├── static/                     # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   ├── uploads/               # Uploaded videos
│   └── processed/             # Processed videos
├── templates/                  # HTML templates
│   ├── index.html             # Home page
│   ├── tiktok_downloader.html  # TikTok downloader page
│   ├── tiktok_results.html     # Results page for TikTok downloads
│   ├── download_audio_video.html # Audio/video downloader page
│   └── preview.html           # Preview processed video page
└── README.md                  # Project documentation
```

## Endpoints
| Method | Endpoint | Description |
|--------|-------------|-------------|
| GET | `/` | Render the home page. |
| POST | `/tiktok-download` | Download videos from a TikTok profile. |
| GET | `/uploads/<filename>` | Serve uploaded files. |
| GET | `/processed/<filename>` | Serve processed files. |
| GET | `/tiktok-downloader` | Render the TikTok downloader page. |
| GET | `/download-audio-video` | Render the audio/video downloader page. |

## Redis Integration
Redis is used to store metadata about downloaded videos. The application checks Redis to see if a video has already been downloaded before attempting to download it again. This helps manage downloads efficiently and avoids unnecessary duplication.

### Example Redis Commands

Check if a video exists:
```python
if redis_client.exists(video_id):
    # Video already downloaded
```

Store video metadata:
```python
redis_client.hset(video_id, mapping={
    'title': video_info.get('title', ''),
    'description': video_info.get('description', ''),
    'url': url_for('serve_download', filename=clean_filename)
})
```

## Frontend
The frontend is built using **HTML and CSS**, with a responsive design to ensure usability across devices. The application provides a user-friendly interface for uploading videos, viewing download progress, and accessing processed videos.

### Key HTML Templates
- **`index.html`**: Main landing page where users can upload videos.
- **`tiktok_downloader.html`**: Page for downloading TikTok videos.
- **`tiktok_results.html`**: Displays the results of TikTok downloads.
- **`preview.html`**: Shows a preview of the processed video.

## Contributing
Contributions are welcome! Follow these steps:
1. Fork the repository.
2. Create a new branch:
   ```sh
   git checkout -b feature-branch
   ```
3. Make your changes and commit them:
   ```sh
   git commit -m 'Add new feature'
   ```
4. Push to the branch:
   ```sh
   git push origin feature-branch
   ```
5. Create a pull request.

## License
This project is licensed under the **MIT License**. See the `LICENSE` file for details.
