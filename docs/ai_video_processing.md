# AI Video Processing Documentation

## Overview
The AI Video Processing module provides face detection and highlight generation capabilities using MediaPipe for face detection and FFmpeg for video processing. The system includes Redis caching for improved performance and a thumbnail management system.

## Data Flow

### 1. Video Upload Process
1. **Client-Side Initialization**
   - User selects video file via HTML file input
   - JavaScript captures form submission event
   - FormData object created with video file

2. **Upload Request**
   - Frontend sends POST request to `/ai-video/detect-faces`
   - Content-Type: multipart/form-data
   - Video file transmitted to server

3. **Server-Side Processing**
   ```mermaid
   graph TD
   A[Upload Received] --> B[File Validation]
   B --> C[Save to Processed Directory]
   C --> D[Initialize Face Detection]
   D --> E[Process Video Frames]
   E --> F[Store Results]
   ```

   a. **Initial Validation**
      - File type verification
      - Secure filename generation
      - Save to processed directory

   b. **MediaPipe Initialization**
      - Load Face Detection model
      - Configure detection parameters:
        - Model selection: 1 (full-range)
        - Min detection confidence: 0.6
        - Frame sampling rate: 15

   c. **OpenCV Operations**
      - Open video stream
      - Extract video properties:
        - Frame rate (FPS)
        - Resolution
        - Total frames

4. **Face Detection Pipeline**
   ```mermaid
   graph LR
   A[Read Frame] --> B[Convert to RGB]
   B --> C[MediaPipe Detection]
   C --> D[Process Results]
   D --> E[Generate Thumbnail]
   E --> F[Store Data]
   ```

   a. **Frame Processing**
      - Sample frames (every 15th frame)
      - Convert BGR to RGB for MediaPipe
      - Run face detection
      - Extract bounding boxes

   b. **Thumbnail Generation**
      - Crop detected faces
      - Save as JPG files
      - Generate unique IDs
      - Store paths in metadata

5. **Database Operations**
   ```mermaid
   graph TD
   A[Prepare Metadata] --> B[Insert Video Record]
   B --> C[Get Video ID]
   C --> D[Store Detection Data]
   D --> E[Update Status]
   ```

   a. **Media Items Table**
      - Insert video metadata
      - Store processing status
      - Save file paths

   b. **AI Video Data Table**
      - Store detection results
      - Link to video record
      - Include timestamps

6. **Redis Caching**
   ```mermaid
   graph LR
   A[Process Data] --> B[Set Cache Keys]
   B --> C[Store Detection Data]
   C --> D[Set Status Cache]
   D --> E[Set TTL]
   ```

   a. **Cache Storage**
      - Face detection results (1h TTL)
      - Processing status (5m TTL)
      - Video metadata

   b. **Cache Keys**
      - Format: ai_video:type:video_id
      - Separate keys for different data types
      - Automatic expiration

### 2. Highlight Generation Process

1. **Request Handling**
   ```mermaid
   graph TD
   A[Highlight Request] --> B[Validate Parameters]
   B --> C[Check Cache]
   C --> D[Retrieve Video Data]
   D --> E[Process Highlight]
   ```

   a. **Input Validation**
      - Verify video_id and face_id
      - Check user permissions
      - Validate request format

2. **Video Processing Pipeline**
   ```mermaid
   graph LR
   A[Load Video] --> B[Extract Segments]
   B --> C[Process Audio]
   C --> D[Generate Highlight]
   D --> E[Save Result]
   ```

   a. **Frame Extraction**
      - Calculate frame ranges
      - Buffer segments (3s)
      - Extract relevant frames

   b. **FFmpeg Processing**
      - Video stream copying
      - Audio synchronization
      - Codec configuration:
        - Video: libx264 (medium preset)
        - Audio: AAC (192k)

3. **Output Generation**
   ```mermaid
   graph TD
   A[Combine Segments] --> B[Add Audio]
   B --> C[Encode Final]
   C --> D[Save Output]
   D --> E[Update Database]
   ```

   a. **Final Processing**
      - Combine video segments
      - Synchronize audio
      - Apply encoding settings
      - Generate final output

### 3. Status Checking Process

1. **Client-Side Polling**
   ```mermaid
   graph LR
   A[Status Request] --> B[Check Cache]
   B --> C[Query Database]
   C --> D[Return Status]
   D --> E[Update UI]
   ```

   a. **Status Updates**
      - Poll interval: 2 seconds
      - Cache-first approach
      - Progress calculation
      - UI updates

2. **Response Handling**
   - Status codes:
     - processing: 0-99%
     - complete: 100%
     - error: -1
   - Progress updates
   - Redirect on completion

### 4. Cleanup Processes

1. **Automatic Cleanup**
   ```mermaid
   graph TD
   A[Cleanup Trigger] --> B[Check File Ages]
   B --> C[Remove Old Files]
   C --> D[Update Database]
   D --> E[Clear Cache]
   ```

   a. **Cleanup Criteria**
      - Age > 24 hours
      - Processing complete
      - Error states
      - Manual triggers

2. **Cache Invalidation**
   - Automatic TTL expiration
   - Manual invalidation
   - Bulk cleanup options

## Architecture

### Components
1. **Face Detection**: Uses MediaPipe for accurate face detection
2. **Video Processing**: Utilizes OpenCV and FFmpeg for video manipulation
3. **Caching**: Redis-based caching system for performance optimization
4. **Storage**: SQLite database for metadata and file system for media storage
5. **Thumbnail Management**: Automated system for managing face thumbnails

### File Structure
```
app/
├── routes/
│   └── ai_video.py       # Main processing logic
├── static/
│   └── processed/        # Stores processed videos and thumbnails
├── models/              # Face detection models
└── templates/
    └── ai_video/        # Frontend templates
```

## Redis Caching System

### Cache Types
1. **Face Detection Cache**
   - Key Format: `ai_video:face_detection:{video_id}`
   - TTL: 1 hour
   - Stores: Detection results and metadata

2. **Status Cache**
   - Key Format: `ai_video:status:{video_id}`
   - TTL: 5 minutes
   - Stores: Processing status and progress

3. **Highlight Cache**
   - Key Format: `ai_video:highlight:{video_id}:{face_id}`
   - TTL: 1 hour
   - Stores: Generated highlight video information

### Cache Methods
- `cache_face_detection(video_id, detection_data)`
- `get_face_detection(video_id)`
- `cache_status(video_id, status_data)`
- `get_status(video_id)`
- `cache_highlight(video_id, face_id, highlight_data)`
- `get_highlight(video_id, face_id)`
- `invalidate_video_cache(video_id)`

## Thumbnail Management

### Retention Policy
- Default retention period: 24 hours
- Thumbnails are kept until:
  1. They exceed the retention period
  2. A new video processing starts
  3. Manual cleanup is triggered

### Cleanup Functions
1. **cleanup_face_thumbnails(face_thumbnails, force=False)**
   - Cleans up specific thumbnails
   - Respects retention period unless forced
   - Parameters:
     - `face_thumbnails`: List of thumbnail URLs
     - `force`: Boolean to override retention period

2. **cleanup_old_files(max_age_hours=24)**
   - Removes old thumbnails and temporary files
   - Parameters:
     - `max_age_hours`: Maximum age before cleanup

3. **manage_thumbnails(video_id, new_thumbnails=None)**
   - Manages thumbnails across all videos
   - Updates database records
   - Parameters:
     - `video_id`: Current video ID
     - `new_thumbnails`: New thumbnails to track

## API Endpoints

### 1. Face Detection
```http
POST /ai-video/detect-faces
Content-Type: multipart/form-data

file: video_file
```
- Detects faces in uploaded video
- Generates thumbnails
- Returns video ID and face data

### 2. Generate Highlight
```http
POST /ai-video/generate-highlight
Content-Type: application/json

{
    "video_id": "integer",
    "face_id": "string"
}
```
- Creates highlight video for selected face
- Uses cached data if available
- Returns highlight video path

### 3. Check Status
```http
GET /ai-video/check-status/<video_id>
```
- Returns processing status
- Includes progress information
- Uses cache for faster responses

## Database Schema

### media_items Table
```sql
CREATE TABLE media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    platform TEXT NOT NULL,
    media_type TEXT NOT NULL,
    local_path TEXT NOT NULL,
    original_url TEXT,
    metadata TEXT,
    status TEXT NOT NULL
);
```

### ai_video_data Table
```sql
CREATE TABLE ai_video_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    detection_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES media_items (id)
);
```

## Troubleshooting

### Common Issues

1. **Redis Connection Issues**
   - Check Redis server status: `redis-cli ping`
   - Verify connection settings in code
   - Check Redis logs

2. **Missing Thumbnails**
   - Verify retention period hasn't expired
   - Check file permissions in processed directory
   - Review cleanup logs

3. **Processing Errors**
   - Check FFmpeg installation and codecs
   - Verify MediaPipe face detection model
   - Review error logs

4. **Cache Issues**
   - Clear Redis cache: `redis-cli FLUSHDB`
   - Check Redis memory usage
   - Verify TTL settings

### Logging
- Location: Application logs
- Level: INFO for normal operations, WARNING/ERROR for issues
- Key log messages:
  - Face detection completion
  - Thumbnail management
  - Cache operations
  - Processing status updates

## Performance Optimization

1. **Video Processing**
   - Frame sampling rate: 15 frames
   - Face detection confidence threshold: 0.6
   - Segment length for highlights: 3 seconds

2. **Caching Strategy**
   - Short TTL for status (5 minutes)
   - Longer TTL for detection/highlight data (1 hour)
   - Automatic invalidation on updates

3. **Storage Management**
   - Automatic cleanup of old files
   - Thumbnail retention management
   - Temporary file cleanup

## Security Considerations

1. **File Access**
   - Secure file paths
   - User authentication required
   - File type validation

2. **API Security**
   - Login required for all routes
   - User-specific data access
   - Input validation

3. **Data Protection**
   - Secure storage of metadata
   - Protected file access
   - Cleanup of sensitive data

## Maintenance Tasks

1. **Regular Cleanup**
   - Run `cleanup_old_files()` daily
   - Monitor storage usage
   - Review cached data

2. **Performance Monitoring**
   - Check Redis memory usage
   - Monitor processing times
   - Review error logs

3. **Database Maintenance**
   - Regular backups
   - Index optimization
   - Clean old records

## Future Improvements

1. **Face Recognition**
   - Implement face recognition for better tracking
   - Improve face matching across frames
   - Add face clustering

2. **Performance**
   - Implement parallel processing
   - Optimize video encoding
   - Enhance caching strategy

3. **User Experience**
   - Add progress bar
   - Improve error messages
   - Add preview functionality