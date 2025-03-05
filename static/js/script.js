// static/js/script.js

// Function to create and show a processing indicator
function showProcessingIndicator(message) {
    // Check if an indicator already exists
    let indicator = document.getElementById('processingIndicator');

    if (!indicator) {
        // Create the indicator if it doesn't exist
        indicator = document.createElement('div');
        indicator.id = 'processingIndicator';
        indicator.className = 'fixed top-0 left-0 w-full h-full flex items-center justify-center bg-black bg-opacity-70 z-50';

        const content = document.createElement('div');
        content.className = 'bg-white p-6 rounded-lg shadow-lg text-center max-w-md';

        const spinner = document.createElement('div');
        spinner.className = 'animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4';

        const text = document.createElement('p');
        text.className = 'text-lg font-medium text-gray-700';
        text.textContent = message || 'Processing...';

        const progress = document.createElement('div');
        progress.className = 'w-full bg-gray-200 rounded-full h-2.5 mt-4';
        progress.innerHTML = '<div id="processingProgress" class="bg-indigo-600 h-2.5 rounded-full w-0 transition-all duration-300"></div>';

        content.appendChild(spinner);
        content.appendChild(text);
        content.appendChild(progress);
        indicator.appendChild(content);

        document.body.appendChild(indicator);
    } else {
        // Update the message if it already exists
        const text = indicator.querySelector('p');
        if (text) {
            text.textContent = message || 'Processing...';
        }
        indicator.style.display = 'flex';
    }
}

// Function to hide the processing indicator
function hideProcessingIndicator() {
    const indicator = document.getElementById('processingIndicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
}

// Function to update progress percentage
function updateProgress(percent) {
    const progressBar = document.getElementById('processingProgress');
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
    }
}
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
let isDrawing = false;
let startX, startY;
let regions = [];

document.addEventListener('DOMContentLoaded', () => {
    video = document.getElementById('video');
    canvas = document.getElementById('canvas');

    if (!video || !canvas) {
        console.error('Video or canvas element not found');
        return;
    }

    ctx = canvas.getContext('2d');

    // Wait for video metadata to load before initializing canvas
    video.addEventListener('loadedmetadata', () => {
        // // console.log('Video metadata loaded');
        // // console.log('Video dimensions:', video.videoWidth, 'x', video.videoHeight);
        initializeCanvas();
    });

    // Fallback if metadata doesn't load
    setTimeout(() => {
        if (canvas.width === 0) {
            // // console.log('Fallback initialization');
            initializeCanvas();
        }
    }, 1000);
});

function initializeCanvas() {
    // Set canvas dimensions to match video
    canvas.width = video.videoWidth || video.offsetWidth;
    canvas.height = video.videoHeight || video.offsetHeight;

    // // console.log('Canvas dimensions:', canvas.width, 'x', canvas.height);

    // Position canvas over video
    canvas.style.position = 'absolute';
    canvas.style.left = '0';
    canvas.style.top = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';

    // Clear any existing regions and redraw
    drawRegions();
}

function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY
    };
}

function drawRegions() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#00a3ff';
    ctx.lineWidth = 2;

    regions.forEach(region => {
        ctx.strokeRect(region.x, region.y, region.width, region.height);
        ctx.fillStyle = 'rgba(0, 163, 255, 0.2)';
        ctx.fillRect(region.x, region.y, region.width, region.height);
    });
}

canvas.addEventListener('mousedown', (e) => {
    isDrawing = true;
    const pos = getMousePos(e);
    startX = pos.x;
    startY = pos.y;
});

canvas.addEventListener('mousemove', (e) => {
    if (!isDrawing) return;

    const pos = getMousePos(e);
    const width = pos.x - startX;
    const height = pos.y - startY;

    drawRegions();
    // Draw current selection
    ctx.strokeStyle = '#00a3ff';
    ctx.strokeRect(startX, startY, width, height);
    ctx.fillStyle = 'rgba(0, 163, 255, 0.2)';
    ctx.fillRect(startX, startY, width, height);
});

canvas.addEventListener('mouseup', (e) => {
    if (!isDrawing) return;
    isDrawing = false;

    const pos = getMousePos(e);
    const width = pos.x - startX;
    const height = pos.y - startY;

    regions.push({
        x: startX,
        y: startY,
        width: width,
        height: height
    });

    drawRegions();
    updateRegionsInput();
});

function updateRegionsInput() {
    const regionsInput = document.getElementById('regions');
    regionsInput.value = regions.map(r =>
        `${Math.round(r.x)},${Math.round(r.y)},${Math.round(r.width)},${Math.round(r.height)}`
    ).join(';');
}

document.getElementById('undoButton')?.addEventListener('click', () => {
    regions.pop();
    drawRegions();
    updateRegionsInput();
});

document.getElementById('clearButton')?.addEventListener('click', () => {
    regions = [];
    drawRegions();
    updateRegionsInput();
});

video.addEventListener('loadedmetadata', initializeCanvas);
window.addEventListener('resize', initializeCanvas);

// Form submission
const watermarkForm = document.getElementById('watermarkForm');
if (watermarkForm) {
    watermarkForm.addEventListener('submit', (e) => {
        if (regions.length === 0) {
            e.preventDefault();
            alert('Please select at least one watermark area');
            return;
        }
        document.getElementById('spinner').style.display = 'block';
    });
}

function fetchFormats() {
    const url = document.getElementById('url').value;
    if (!url) {
        alert('Please enter a valid URL');
        return;
    }

    fetch('{{ url_for("get_formats") }}', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ url: url }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            alert('Error fetching formats: ' + data.error);
        } else {
            const formatSelect = document.getElementById('format_id');
            formatSelect.innerHTML = '';
            data.formats.forEach(format => {
                const option = document.createElement('option');
                option.value = format.format_id;
                option.text = `${format.format_id} - ${format.ext} - ${format.resolution} - ${format.filesize || 'unknown size'}`;
                formatSelect.appendChild(option);
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to fetch formats. Please check your network connection and try again.');
    });
}