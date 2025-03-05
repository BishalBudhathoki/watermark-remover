// static/js/instagram_downloader.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('instagram-form');
    const statusMessage = document.getElementById('status-message');
    const urlInput = document.getElementById('instagram-url');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        // Clean the URL by removing query parameters and trailing slashes
        let cleanedUrl = urlInput.value.split('?')[0].replace(/\/$/, '');

        // Show loading state
        statusMessage.innerHTML = 'Processing your request...';
        statusMessage.classList.remove('hidden');

        try {
            const response = await fetch('/instagram-download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: cleanedUrl }),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Download failed');
            }

            if (result.content) {
                displayContent(result.content);
            }
        } catch (error) {
            statusMessage.innerHTML = `Error: ${error.message}`;
        }
    });

    function displayContent(content) {
        // Clear the form and status
        form.style.display = 'none';
        statusMessage.innerHTML = '';

        // Create the results container
        const resultsContainer = document.createElement('div');
        resultsContainer.className = 'results-container';

        // Add header with profile info
        const header = document.createElement('div');
        header.className = 'results-header';
        header.innerHTML = `
            <h2>Profile: @${content.username}</h2>
            <p>Found ${content.videos.length} posts</p>
        `;
        resultsContainer.appendChild(header);

        // Create table
        const table = document.createElement('table');
        table.className = 'styled-table';

        // Add table header
        table.innerHTML = `
            <thead>
                <tr>
                    <th>#</th>
                    <th>Type</th>
                    <th>Title</th>
                    <th>Description</th>
                    <th>Duration</th>
                    <th>Views</th>
                    <th>Likes</th>
                    <th>Comments</th>
                    <th>Date</th>
                    <th>Actions</th>
                </tr>
            </thead>
        `;

        // Add table body
        const tbody = document.createElement('tbody');
        content.videos.forEach((item, index) => {
            const tr = document.createElement('tr');

            // Get appropriate icon and class based on content type
            const getTypeIcon = (type) => {
                switch(type) {
                    case 'reel':
                        return '📱';
                    case 'video':
                        return '🎥';
                    case 'photo':
                        return '📷';
                    default:
                        return '📄';
                }
            };

            tr.innerHTML = `
                <td>${index + 1}</td>
                <td>${getTypeIcon(item.type)} ${item.type.charAt(0).toUpperCase() + item.type.slice(1)}</td>
                <td>${item.title}</td>
                <td>${item.description.substring(0, 100)}${item.description.length > 100 ? '...' : ''}</td>
                <td>${item.duration_string}</td>
                <td>${item.view_count.toLocaleString()}</td>
                <td>${item.like_count.toLocaleString()}</td>
                <td>${item.comment_count.toLocaleString()}</td>
                <td>${item.date}</td>
                <td>
                    <div class="action-buttons">
                        ${item.is_video ?
                            `<button class="view-btn" data-url="${item.url}">View</button>` :
                            `<button class="view-btn" data-url="${item.url}" data-type="image">View</button>`
                        }
                        <a href="${item.url}" download class="download-btn">Download</a>
                        ${item.additional_media.length > 0 ?
                            `<button class="more-btn" data-media='${JSON.stringify(item.additional_media)}'>+${item.additional_media.length}</button>` :
                            ''
                        }
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);

        // Add table to results container
        resultsContainer.appendChild(table);

        // Add back button
        const backButton = document.createElement('button');
        backButton.className = 'back-btn';
        backButton.textContent = 'Download Another';
        backButton.onclick = () => {
            resultsContainer.remove();
            form.style.display = 'block';
            urlInput.value = '';
        };
        resultsContainer.appendChild(backButton);

        // Add results container to the page
        document.querySelector('.downloader-card').appendChild(resultsContainer);

        // Add event listeners for buttons
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const url = btn.dataset.url;
                const type = btn.dataset.type;
                showPreviewModal(url, type);
            });
        });

        document.querySelectorAll('.more-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const additionalMedia = JSON.parse(btn.dataset.media);
                showGalleryModal(additionalMedia);
            });
        });
    }

    function showPreviewModal(url, type = 'video') {
        const modal = document.createElement('div');
        modal.className = 'modal';

        const content = type === 'image'
            ? `<img src="${url}" alt="Preview" style="max-width: 100%; max-height: 80vh;">`
            : `<video controls style="max-width: 100%; max-height: 80vh;">
                <source src="${url}" type="video/mp4">
                Your browser does not support the video tag.
               </video>`;

        modal.innerHTML = `
            <div class="modal-content">
                <span class="close">&times;</span>
                ${content}
                <a href="${url}" download class="download-btn modal-download">Download</a>
            </div>
        `;

        document.body.appendChild(modal);

        const close = modal.querySelector('.close');
        close.onclick = () => {
            if (type === 'video') {
                const video = modal.querySelector('video');
                video.pause();
            }
            modal.remove();
        };

        modal.onclick = (e) => {
            if (e.target === modal) {
                if (type === 'video') {
                    const video = modal.querySelector('video');
                    video.pause();
                }
                modal.remove();
            }
        };
    }

    function showGalleryModal(mediaUrls) {
        const modal = document.createElement('div');
        modal.className = 'modal gallery-modal';

        let galleryContent = '<div class="gallery-content">';
        mediaUrls.forEach((url, index) => {
            const isVideo = url.toLowerCase().endsWith('.mp4');
            if (isVideo) {
                galleryContent += `
                    <div class="gallery-item">
                        <video controls>
                            <source src="${url}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        <a href="${url}" download class="download-btn">Download</a>
                    </div>
                `;
            } else {
                galleryContent += `
                    <div class="gallery-item">
                        <img src="${url}" alt="Media ${index + 1}">
                        <a href="${url}" download class="download-btn">Download</a>
                    </div>
                `;
            }
        });
        galleryContent += '</div>';

        modal.innerHTML = `
            <div class="modal-content gallery">
                <span class="close">&times;</span>
                ${galleryContent}
            </div>
        `;

        document.body.appendChild(modal);

        const close = modal.querySelector('.close');
        close.onclick = () => {
            const videos = modal.querySelectorAll('video');
            videos.forEach(video => video.pause());
            modal.remove();
        };

        modal.onclick = (e) => {
            if (e.target === modal) {
                const videos = modal.querySelectorAll('video');
                videos.forEach(video => video.pause());
                modal.remove();
            }
        };
    }

    // Add these styles dynamically if not already in your CSS
    const styles = `
        .gallery-modal .modal-content {
            width: 90%;
            max-width: 1200px;
            padding: 20px;
        }
        .gallery-content {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            max-height: 70vh;
            overflow-y: auto;
        }
        .gallery-item {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
        }
        .gallery-item img,
        .gallery-item video {
            width: 100%;
            height: 200px;
            object-fit: cover;
            border-radius: 8px;
        }
        .modal-download {
            margin-top: 15px;
        }
        .action-buttons {
            display: flex;
            gap: 8px;
            justify-content: flex-end;
        }
        .more-btn {
            background-color: #6c757d;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 5px 10px;
            cursor: pointer;
        }
        .more-btn:hover {
            background-color: #5a6268;
        }
    `;

    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);
});