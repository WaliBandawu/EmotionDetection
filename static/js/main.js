document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.querySelector('.file-upload');
    const videoInput = document.getElementById('videoInput');
    
    // Drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('highlight');
    }

    function unhighlight(e) {
        dropZone.classList.remove('highlight');
    }

    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        videoInput.files = files;
    }
});

document.getElementById('videoForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const videoInput = document.getElementById('videoInput');
    const loading = document.getElementById('loading');
    const frameImage = document.getElementById('frameImage');
    const emotionsDiv = document.getElementById('emotionsContent');
    
    if (!videoInput.files[0]) {
        alert('Please select a video file');
        return;
    }
    
    const formData = new FormData();
    formData.append('video', videoInput.files[0]);
    
    loading.classList.remove('hidden');
    
    try {
        const response = await fetch('/process-video', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
            return;
        }
        
        let currentFrameIndex = 0;
        
        function displayFrame() {
            if (currentFrameIndex >= data.frames.length) {
                currentFrameIndex = 0;
            }
            
            const frame = data.frames[currentFrameIndex];
            frameImage.src = `data:image/jpeg;base64,${frame.frame}`;
            
            emotionsDiv.innerHTML = frame.emotions
                .map(emotion => `
                    <div class="emotion-bar">
                        <span class="label">
                            <i class="fas fa-${getEmotionIcon(emotion.label)}"></i>
                            ${capitalizeFirstLetter(emotion.label)}
                        </span>
                        <span class="score">${(emotion.score * 100).toFixed(1)}%</span>
                    </div>
                `)
                .join('');
            
            currentFrameIndex++;
        }
        
        displayFrame();
        setInterval(displayFrame, 1000);
        
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while processing the video');
    } finally {
        loading.classList.add('hidden');
    }
});

function getEmotionIcon(emotion) {
    const icons = {
        'happy': 'smile-beam',
        'sad': 'sad-tear',
        'angry': 'angry',
        'fear': 'fear',
        'surprise': 'surprise',
        'neutral': 'meh',
        'disgust': 'grimace'
    };
    return icons[emotion.toLowerCase()] || 'emoji-neutral';
}

function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1).toLowerCase();
} 