document.addEventListener('DOMContentLoaded', () => {
    const downloadForm = document.querySelector('.download-form');
    const profileUrlInput = document.getElementById('profile_url');
    const downloadStatus = document.getElementById('downloadStatus');
    const progressFill = document.querySelector('.progress-fill');
    const statusText = document.querySelector('.status-text');

    // Handle form submission
    downloadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = profileUrlInput.value.trim();
        
        if (!url || !isValidTikTokUrl(url)) {
            alert('Please enter a valid TikTok profile URL');
            return;
        }

        try {
            // Show download status
            downloadStatus.classList.remove('hidden');
            progressFill.style.width = '0%';
            statusText.textContent = 'Starting download...';

            // Submit the form
            downloadForm.submit();

        } catch (error) {
            console.error('Download error:', error);
            statusText.textContent = `Error: ${error.message}`;
            downloadStatus.classList.remove('hidden');
        }
    });

    // Function to validate TikTok URL
    function isValidTikTokUrl(url) {
        try {
            const parsedUrl = new URL(url);
            return (
                parsedUrl.hostname.includes('tiktok.com') && 
                parsedUrl.pathname.includes('@')
            );
        } catch {
            return false;
        }
    }
}); 