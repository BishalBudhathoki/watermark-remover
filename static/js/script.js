// static/js/script.js
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
        console.log('Video metadata loaded');
        console.log('Video dimensions:', video.videoWidth, 'x', video.videoHeight);
        initializeCanvas();
    });
    
    // Fallback if metadata doesn't load
    setTimeout(() => {
        if (canvas.width === 0) {
            console.log('Fallback initialization');
            initializeCanvas();
        }
    }, 1000);
});

function initializeCanvas() {
    // Set canvas dimensions to match video
    canvas.width = video.videoWidth || video.offsetWidth;
    canvas.height = video.videoHeight || video.offsetHeight;
    
    console.log('Canvas dimensions:', canvas.width, 'x', canvas.height);
    
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