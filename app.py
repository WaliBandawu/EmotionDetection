from flask import Flask, render_template, request, jsonify, Response
import cv2
import numpy as np
from deepface import DeepFace
import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
import base64
import json

# Configure logging
log_directory = 'logs'
os.makedirs(log_directory, exist_ok=True)
log_filename = os.path.join(log_directory, f'app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load the face cascade classifier
try:
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    logger.info("Face cascade classifier loaded successfully")
except Exception as e:
    logger.error(f"Error loading face cascade classifier: {str(e)}")
    raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_json_serializable(obj):
    """Convert numpy types to Python native types"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

@app.route('/')
def index():
    logger.info("Serving index page")
    return render_template('index.html')

@app.route('/analyze-frame', methods=['POST'])
def analyze_frame():
    """Endpoint to analyze a single frame from webcam"""
    try:
        # Get image data from request
        image_data = request.json['image'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # Convert to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        results = []
        # Process each detected face
        for (x, y, w, h) in faces:
            try:
                # Analyze emotions using DeepFace
                face_roi = frame[y:y+h, x:x+w]
                analysis = DeepFace.analyze(face_roi, 
                                         actions=['emotion'],
                                         enforce_detection=False)
                
                if isinstance(analysis, list):
                    analysis = analysis[0]
                
                emotions = {k: float(v) for k, v in analysis['emotion'].items()}
                dominant_emotion = max(emotions.items(), key=lambda x: x[1])
                
                results.append({
                    'position': {
                        'x': int(x),
                        'y': int(y),
                        'width': int(w),
                        'height': int(h)
                    },
                    'emotions': emotions,
                    'dominant_emotion': (dominant_emotion[0], float(dominant_emotion[1]))
                })
                
            except Exception as e:
                logger.error(f"Error analyzing face: {str(e)}")
                continue
        
        return jsonify({'success': True, 'faces': results})
        
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/process-video', methods=['POST'])
def process_video():
    logger.info("Received video processing request")
    
    if 'video' not in request.files:
        logger.error("No video file in request")
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        logger.error("Empty filename received")
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.info(f"Saving uploaded file: {filename}")
        file.save(filepath)
        
        try:
            logger.info("Starting video processing")
            results = process_video_frames(filepath)
            logger.info("Video processing completed successfully")
            
            # Clean up the uploaded file
            os.remove(filepath)
            logger.info(f"Cleaned up temporary file: {filepath}")
            
            return jsonify(results)
        except Exception as e:
            logger.error(f"Error during video processing: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    logger.error(f"Invalid file type: {file.filename}")
    return jsonify({'error': 'Invalid file type'}), 400

def process_video_frames(video_path):
    logger.info(f"Opening video file: {video_path}")
    cap = cv2.VideoCapture(video_path)
    frames_results = []
    frame_count = 0
    processed_frames = 0
    
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Process every 10th frame to reduce computation
            if frame_count % 10 == 0:
                logger.debug(f"Processing frame {frame_count}")
                # Convert to grayscale for face detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                frame_emotions = []
                # Process each detected face
                for (x, y, w, h) in faces:
                    try:
                        # Analyze emotions using DeepFace
                        face_roi = frame[y:y+h, x:x+w]
                        analysis = DeepFace.analyze(face_roi, 
                                                 actions=['emotion'],
                                                 enforce_detection=False)
                        
                        if isinstance(analysis, list):
                            analysis = analysis[0]
                        
                        emotions = {k: float(v) for k, v in analysis['emotion'].items()}
                        dominant_emotion = max(emotions.items(), key=lambda x: x[1])
                        
                        frame_emotions.append({
                            'position': {
                                'x': int(x),
                                'y': int(y),
                                'width': int(w),
                                'height': int(h)
                            },
                            'emotions': emotions,
                            'dominant_emotion': (dominant_emotion[0], float(dominant_emotion[1]))
                        })
                        
                    except Exception as e:
                        logger.error(f"Error analyzing face in frame {frame_count}: {str(e)}")
                        continue
                
                # Convert frame to base64 for frontend display
                _, buffer = cv2.imencode('.jpg', frame)
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                frames_results.append({
                    'frame': frame_base64,
                    'faces': frame_emotions
                })
                processed_frames += 1
                
            frame_count += 1
            
    finally:
        cap.release()
        
    logger.info(f"Video processing completed. Processed {processed_frames} frames out of {frame_count} total frames")
    return {'frames': frames_results}

@app.route('/save-recording', methods=['POST'])
def save_recording():
    try:
        data = request.json
        video_data = data['videoData'].split(',')[1]  # Remove data URL prefix
        emotions_data = data['emotionsData']
        
        # Generate timestamp for unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save video file
        video_filename = f'recording_{timestamp}.webm'
        video_path = os.path.join(RECORDINGS_FOLDER, video_filename)
        with open(video_path, 'wb') as f:
            f.write(base64.b64decode(video_data))
        
        # Save emotions data
        emotions_filename = f'emotions_{timestamp}.json'
        emotions_path = os.path.join(RECORDINGS_FOLDER, emotions_filename)
        with open(emotions_path, 'w') as f:
            json.dump(emotions_data, f, indent=2)
            
        logger.info(f"Saved recording: {video_filename} with emotions data")
        return jsonify({'success': True, 'filename': video_filename})
        
    except Exception as e:
        logger.error(f"Error saving recording: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    logger.info("Starting Flask application")
    app.run(debug=True) 