document.addEventListener('DOMContentLoaded', () => {
    const downloadForm = document.querySelector('.download-form');
    const profileUrlInput = document.getElementById('profile_url');
    const downloadStatus = document.getElementById('downloadStatus');
    const progressFill = document.querySelector('.progress-fill');
    const statusText = document.querySelector('.status-text');
    const uploadBtn = document.querySelector('.upload-btn');
    const checkboxes = document.querySelectorAll('.checkbox-input');

    // Handle checkbox state
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            const isAnyChecked = Array.from(checkboxes).some(checkbox => checkbox.checked);
            uploadBtn.disabled = !isAnyChecked;
        });
    });

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

    // Load the Google API client library
    function loadGoogleAPI() {
        gapi.load('auth2', () => {
            gapi.auth2.init({
                client_id: document.querySelector('meta[name="google-signin-client_id"]').content,
                scope: 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl'
            }).then(() => {
                console.log('Google API initialized successfully');
            }).catch(error => {
                console.error('Google API initialization failed:', error);
            });
        });
    }

    // Handle video upload to YouTube
    async function uploadToYouTube(authToken) {
        const selectedVideos = Array.from(checkboxes)
            .filter(checkbox => checkbox.checked)
            .map(checkbox => {
                const row = checkbox.closest('tr');
                return {
                    title: row.cells[1].textContent,
                    description: row.cells[2].textContent,
                    downloadUrl: row.querySelector('.download-btn').href
                };
            });

        if (selectedVideos.length === 0) {
            alert('Please select at least one video to upload');
            return;
        }

        for (const video of selectedVideos) {
            try {
                // Show upload status
                const originalBtnText = uploadBtn.textContent;
                uploadBtn.textContent = `Uploading ${video.title}...`;
                uploadBtn.disabled = true;

                // Prepare video metadata for Shorts
                const shortsMetadata = {
                    title: `${video.title} #Shorts`,
                    description: `${video.description}\n\n#Shorts #TikTok #Viral`,
                    video_url: video.downloadUrl,
                    credentials: {
                        access_token: authToken
                    }
                };

                // Send upload request to Flask backend
                const response = await fetch('/upload-video', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(shortsMetadata)
                });

                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.error || 'Upload failed');
                }

                alert(`Successfully uploaded ${video.title} to YouTube Shorts!`);

            } catch (error) {
                console.error('Upload error:', error);
                alert(`Failed to upload ${video.title}: ${error.message}`);
            }
        }

        // Reset button state
        uploadBtn.textContent = 'Upload to YouTube Shorts';
        uploadBtn.disabled = false;
    }

    // Handle upload button click
    uploadBtn.addEventListener('click', () => {
        const auth2 = gapi.auth2.getAuthInstance();
        
        if (!auth2.isSignedIn.get()) {
            // If not signed in, trigger sign in flow
            auth2.signIn().then(googleUser => {
                const authToken = googleUser.getAuthResponse().access_token;
                uploadToYouTube(authToken);
            }).catch(error => {
                console.error('Sign in error:', error);
                alert('Failed to sign in to Google');
            });
        } else {
            // If already signed in, proceed with upload
            const authToken = auth2.currentUser.get().getAuthResponse().access_token;
            uploadToYouTube(authToken);
        }
    });

    // Load Google API on page load
    loadGoogleAPI();
}); 