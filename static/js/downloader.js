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

            // Fetch video info
            const response = await fetch('/fetch-video-info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url }),
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

    // Function to display video information
    function displayVideoInfo(info) {
        const durationInMinutes = Math.floor(info.duration / 60);
        const durationSeconds = info.duration % 60;

        videoInfo.innerHTML = `
            <div class="video-info-content">
                <img src="${info.thumbnail}" alt="${info.title}" class="video-thumbnail">
                <div class="video-details">
                    <h3>${info.title}</h3>
                    <p><strong>Uploader:</strong> ${info.uploader}</p>
                    <p><strong>Duration:</strong> ${durationInMinutes}:${durationSeconds.toString().padStart(2, '0')}</p>
                    <p><strong>Views:</strong> ${info.view_count.toLocaleString()}</p>
                </div>
            </div>
        `;
        videoInfo.classList.remove('hidden');

        // Update quality options based on available qualities
        if (info.available_qualities && info.available_qualities.length > 0) {
            const qualitySelect = document.getElementById('quality');
            const currentValue = qualitySelect.value;

            // Keep the "Best" option and add available qualities
            let options = '<option value="best">Best</option>';

            info.available_qualities.forEach(height => {
                const label = height >= 2160 ? `4K (${height}p)` :
                             height >= 1440 ? `2K (${height}p)` :
                             `${height}p`;
                options += `<option value="${height}"${currentValue == height ? ' selected' : ''}>${label}</option>`;
            });

            qualitySelect.innerHTML = options;
        }

        // Show options panel
        optionsPanel.classList.remove('hidden');
    }

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
            const response = await fetch('/download-progress');
            const data = await response.json();

            if (data.progress !== undefined) {
                progressFill.style.width = `${data.progress}%`;
                statusText.textContent = data.status || `Downloading: ${Math.round(data.progress)}%`;

                if (data.progress >= 100 || data.status === 'Processing...' || data.status.startsWith('Error')) {
                    if (data.status === 'Processing...') {
                        statusText.textContent = 'Processing video, please wait...';
                    } else if (data.status.startsWith('Error')) {
                        clearInterval(progressCheckInterval);
                        downloadInProgress = false;
                        alert('Download failed: ' + data.status);
                    } else if (data.progress >= 100) {
                        clearInterval(progressCheckInterval);
                        downloadInProgress = false;
                        statusText.textContent = 'Download complete!';
                    }
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

            const downloadType = downloadTypeSelect.value;
            const quality = qualitySelect.value;
            const format = formatSelect.value;

            // Show download status
            downloadStatus.classList.remove('hidden');
            progressFill.style.width = '0%';
            statusText.textContent = 'Starting download...';
            downloadInProgress = true;
            downloadBtn.disabled = true;

            // Start progress checking
            progressCheckInterval = setInterval(checkProgress, 1000);

            // Send download request
            const response = await fetch('/download-video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url,
                    downloadType,
                    quality,
                    format,
                }),
            });

            if (!response.ok) {
                throw new Error('Download failed');
            }

            const data = await response.json();

            if (data.success) {
                clearInterval(progressCheckInterval);
                // Update progress to complete
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
            console.error('Download error:', error);
            statusText.textContent = `Error: ${error.message}`;
        } finally {
            downloadInProgress = false;
            downloadBtn.disabled = false;
            clearInterval(progressCheckInterval);
        }
    });

    // Function to validate URL
    function isValidUrl(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    }
});
