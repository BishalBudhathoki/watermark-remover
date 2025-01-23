document.addEventListener('DOMContentLoaded', () => {
    const downloadForm = document.getElementById('downloadForm');
    const videoUrlInput = document.getElementById('videoUrl');
    const videoInfo = document.getElementById('videoInfo');
    const optionsPanel = document.getElementById('optionsPanel');
    const downloadTypeSelect = document.getElementById('downloadType');
    const qualitySelect = document.getElementById('quality');
    const formatSelect = document.getElementById('format');
    const downloadStatus = document.getElementById('downloadStatus');
    const progressFill = document.querySelector('.progress-fill');
    const statusText = document.querySelector('.status-text');
    const fetchBtn = document.getElementById('fetchBtn');
    const downloadBtn = document.getElementById('downloadBtn');

    // API endpoints
    const API_ENDPOINTS = {
        FETCH_INFO: '/api/download/fetch-video-info',
        DOWNLOAD_VIDEO: '/api/download/download-video',
        DOWNLOAD_PROGRESS: '/api/download/download-progress'
    };

    function isValidUrl(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    }

    function displayVideoInfo(info) {
        videoInfo.innerHTML = `
            <div class="video-details">
                <h3>${info.title}</h3>
                <p>Duration: ${info.duration}</p>
                ${info.thumbnail ? `<img src="${info.thumbnail}" alt="Video thumbnail">` : ''}
            </div>
        `;
        videoInfo.classList.remove('hidden');
    }

    async function downloadVideo() {
        try {
            const response = await fetch('/api/download/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: document.getElementById('videoUrl').value,
                    type: document.getElementById('downloadType').value,
                    quality: document.getElementById('quality').value,
                    format: document.getElementById('format').value
                })
            });
    
            const data = await response.json();
            
            if (!data.success) {
                // Show detailed error message
                showError(data.error || 'Download failed');
                console.error('Download details:', data);
                return;
            }
    
            // Existing download success logic
        } catch (error) {
            showError(`Network error: ${error.message}`);
            console.error('Download error:', error);
        }
    }

    // Handle form submission for fetching video info
    downloadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = videoUrlInput.value.trim();
        
        if (!url || !isValidUrl(url)) {
            alert('Please enter a valid URL');
            return;
        }

        try {
            fetchBtn.disabled = true;
            fetchBtn.textContent = 'Fetching...';
            
            const formData = new FormData();
            formData.append('url', url);
            
            // Fetch video info
            const response = await fetch(API_ENDPOINTS.FETCH_INFO, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to fetch video info');
            }

            const data = await response.json();

            if (data.success) {
                // Display video info
                displayVideoInfo(data.video_info);
                // Show options panel
                optionsPanel.classList.remove('hidden');
            } else {
                throw new Error(data.error || 'Failed to fetch video info');
            }
        } catch (error) {
            console.error('Error:', error);
            alert(error.message);
        } finally {
            fetchBtn.disabled = false;
            fetchBtn.textContent = 'Fetch Video Info';
        }
    });

    // Handle download type change
    downloadTypeSelect.addEventListener('change', () => {
        const isAudio = downloadTypeSelect.value === 'audio';
        
        // Update format options based on download type
        formatSelect.innerHTML = isAudio ? 
            `<option value="mp3">MP3</option>
             <option value="m4a">M4A</option>` :
            `<option value="mp4">MP4</option>
             <option value="mkv">MKV</option>
             <option value="webm">WebM</option>`;

        // Hide quality selection for audio
        qualitySelect.closest('.option-group').style.display = isAudio ? 'none' : 'block';
    });

    let downloadInProgress = false;
    let progressCheckInterval;

    // Function to check download progress
    async function checkProgress() {
        try {
            const response = await fetch(API_ENDPOINTS.DOWNLOAD_PROGRESS);
            const data = await response.json();
            
            if (data.progress !== undefined) {
                progressFill.style.width = `${data.progress}%`;
                statusText.textContent = `Downloading: ${Math.round(data.progress)}%`;
                
                if (data.progress >= 100 || data.status === 'complete') {
                    clearInterval(progressCheckInterval);
                    downloadInProgress = false;
                    downloadBtn.disabled = false;
                }
            }
        } catch (error) {
            console.error('Error checking progress:', error);
        }
    }

    // Handle download button click
    downloadBtn.addEventListener('click', async () => {
        if (downloadInProgress) {
            alert('A download is already in progress');
            return;
        }

        try {
            const url = videoUrlInput.value.trim();
            if (!url || !isValidUrl(url)) {
                alert('Please enter a valid URL');
                return;
            }

            // Show download status
            downloadStatus.classList.remove('hidden');
            progressFill.style.width = '0%';
            statusText.textContent = 'Starting download...';
            downloadInProgress = true;
            downloadBtn.disabled = true;

            // Prepare request body as JSON
            const requestBody = {
                url: url,
                type: downloadTypeSelect.value,
                quality: qualitySelect.value.endsWith('p') ? 
                    qualitySelect.value : 
                    qualitySelect.value + 'p',
                format: formatSelect.value
            };

            // Start progress checking
            progressCheckInterval = setInterval(checkProgress, 1000);

            // Send download request
            const response = await fetch(API_ENDPOINTS.DOWNLOAD_VIDEO, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                throw new Error('Download failed');
            }

            const data = await response.json();
            
            if (data.success) {
                clearInterval(progressCheckInterval);
                progressFill.style.width = '100%';
                statusText.textContent = 'Download complete!';
                
                // Create download link
                const downloadLink = document.createElement('a');
                downloadLink.href = data.download_url;
                downloadLink.download = data.filename;
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
            } else {
                throw new Error(data.error || 'Download failed');
            }
        } catch (error) {
            console.error('Error:', error);
            alert(error.message);
            downloadStatus.classList.add('hidden');
        } finally {
            downloadInProgress = false;
            downloadBtn.disabled = false;
            clearInterval(progressCheckInterval);
        }
    });
});
