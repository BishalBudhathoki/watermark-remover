You are a highly skilled Python developer and assistant working inside Cursor AI IDE. Your task is to help me build a fully functional **Content Repurposing and Cross-Posting Pipeline** using Python. The project should follow best practices for modularity, scalability, and error handling. The pipeline consists of the following key components:

**2.1 Content Repurposing/Cross-Posting Pipeline**

### Requirements
- Language: Python 3.x
- Tools: MoviePy (for video splitting), OpenAI API (or similar for text generation), HTTP libraries (for cross-posting).
- Structure: Organized into well-separated modules (`upload.py`, `splitter.py`, `text_generator.py`, `poster.py`).
- Logging: Use Python's built-in `logging` library.
- Configurable via `.env` file (API keys, platform endpoints, etc.).

---

### Steps to Implement

#### 1. Video Upload
- Create a function that handles video file uploads (from local directory or user input).
- Accept file path input.
- Perform basic validation (file type, size limit).
- Return a file handle or path for processing.

#### 2. Video Splitting (MoviePy)
- Load the uploaded video using **MoviePy**.
- Automatically detect logical splits based on:
    - Duration thresholds (e.g., split into 60-second segments for TikTok).
    - Optional: silent sections (advanced feature if time allows).
- Save clips to a temporary folder.
- Return metadata: clip count, durations, file paths.

#### 3. Text Variations with AI
- Use OpenAI API (or compatible LLM including Deepseek) to generate:
    - Multiple captions for each clip.
    - Suggested hashtags.
    - Platform-specific text variations (YouTube Shorts, TikTok, Instagram Reels, etc.).
- Implement fallback if API fails.

#### 4. Cross-Posting
- Create functions to upload each clip to:
    - TikTok
    - Instagram Reels
    - YouTube Shorts
- Each platform should have its own posting logic,
- Apply the generated captions and hashtags.

---
Expected AI Behavior in Cursor AI IDE
Generate the full folder structure with initial files.
Add code skeletons for each step with proper docstrings.
Write example functions and handle typical edge cases (network failures, corrupted videos, etc.).
Use async where beneficial (for parallel uploads).
Explain each step inline using comments for clarity.
Suggest improvements where applicable (caching, retries, etc.).
Option to choose target platforms dynamically.
Basic progress bar during processing (using tqdm or similar).
Make sure the code is modular and easy to extend.
Ensure the code is well-documented and easy to understand.

