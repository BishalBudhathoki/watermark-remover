from pathlib import Path

# Get application root directory
APP_ROOT = Path(__file__).resolve().parent.parent.parent

# Define common directories (at project root level)
DOWNLOAD_DIR = APP_ROOT / 'downloads'
UPLOAD_DIR = APP_ROOT / 'uploads'
PROCESSED_DIR = APP_ROOT / 'processed'

# Platform-specific directories
TIKTOK_DIR = DOWNLOAD_DIR / 'tiktok'
INSTAGRAM_DIR = DOWNLOAD_DIR / 'instagram'
YOUTUBE_DIR = DOWNLOAD_DIR / 'youtube'

# Create necessary directories
def ensure_directories():
    """Ensure all required directories exist."""
    directories = [
        DOWNLOAD_DIR,
        UPLOAD_DIR,
        PROCESSED_DIR,
        TIKTOK_DIR,
        INSTAGRAM_DIR,
        YOUTUBE_DIR
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_download_path(platform: str, filename: str) -> Path:
    """Get the appropriate download path for a given platform."""
    # If filename already contains platform directory, strip it
    filename_parts = Path(filename).parts
    if any(platform in part for part in filename_parts):
        filename = filename_parts[-1]
    
    # If filename already contains downloads directory, strip it
    if 'downloads' in filename_parts:
        filename = filename_parts[-1]
    
    platform_dirs = {
        'tiktok': TIKTOK_DIR,
        'instagram': INSTAGRAM_DIR,
        'youtube': YOUTUBE_DIR
    }
    return platform_dirs.get(platform, DOWNLOAD_DIR) / filename

def get_relative_path(absolute_path: Path) -> str:
    """Convert absolute path to relative path from APP_ROOT."""
    try:
        # Ensure the path is resolved and relative to APP_ROOT
        abs_path = absolute_path.resolve()
        rel_path = abs_path.relative_to(APP_ROOT)
        
        # If path is in downloads directory but doesn't have platform prefix,
        # add it based on the directory structure
        if 'downloads' in rel_path.parts:
            platform_index = rel_path.parts.index('downloads') + 1
            if platform_index < len(rel_path.parts):
                platform = rel_path.parts[platform_index]
                return str(Path(platform) / rel_path.name)  # Remove downloads from path
        
        return str(rel_path)
    except ValueError:
        # If path is already relative to downloads directory
        if 'downloads' in absolute_path.parts:
            parts = list(absolute_path.parts)
            if 'downloads' in parts:
                # Remove downloads from path
                parts.remove('downloads')
            return str(Path(*parts))
        return str(absolute_path)

def is_safe_path(path: Path) -> bool:
    """Check if a path is safe (within APP_ROOT)."""
    try:
        resolved_path = path.resolve()
        return resolved_path.is_relative_to(APP_ROOT)
    except (ValueError, RuntimeError):
        return False 