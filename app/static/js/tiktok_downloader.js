document.addEventListener('DOMContentLoaded', () => {
    const downloadForm = document.querySelector('.download-form');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const lottiePlayer = document.getElementById('lottieContainer');

    downloadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Show loading overlay and start animation
        loadingOverlay.style.display = 'flex';
        if (lottiePlayer) {
            lottiePlayer.play();
        }

        try {
            const formData = new FormData(downloadForm);
            const response = await fetch(downloadForm.action, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Download failed');
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                throw new Error(data.error || 'Download failed');
            } else {
                document.documentElement.innerHTML = await response.text();
            }
        } catch (error) {
            console.error('Error:', error);
            // Stop animation and show error
            if (lottiePlayer) {
                lottiePlayer.stop();
            }
            alert(error.message);
        } finally {
            loadingOverlay.style.display = 'none';
        }
    });
    // Check cache status on page load
    checkCacheStatus();
});

async function checkCacheStatus() {
    try {
        const response = await fetch('/api/download/cache-status');
        if (!response.ok) {
            throw new Error('Failed to fetch cache status');
        }
        const data = await response.json();
        
        const cacheInfo = document.getElementById('cacheInfo');
        const cacheCount = document.querySelector('.cache-count');
        
        if (data.cached_videos > 0) {
            cacheCount.textContent = data.cached_videos;
            cacheInfo.style.display = 'flex';
        }
    } catch (error) {
        console.error('Error checking cache:', error);
    }
}