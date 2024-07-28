import os
import json
from flask import Flask, request, jsonify, send_file
from gtts import gTTS
import subprocess
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime
import ntplib

# Import configuration
from config import Config

# Initialize Flask app
app = Flask(__name__)

# Directory to store files temporarily
UPLOAD_DIR = Config.UPLOAD_DIR
DOWNLOAD_DIR = Config.DOWNLOAD_DIR
USER_DATA_FILE = Config.USER_DATA_FILE

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Load user data from file
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save user data to file
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

user_data = load_user_data()

# Function to extract audio from video
def extract_audio(video_path, audio_path):
    command = f"ffmpeg -i {video_path} -q:a 0 -map a {audio_path}"
    subprocess.run(command, shell=True, check=True)

# Function to generate TTS audio
def generate_tts_audio(text, audio_path, lang='en'):
    tts = gTTS(text, lang=lang)
    tts.save(audio_path)

# Function to combine audio with video
def combine_audio_video(video_path, audio_path, output_path):
    command = f"ffmpeg -i {video_path} -i {audio_path} -c:v copy -map 0:v:0 -map 1:a:0 {output_path}"
    subprocess.run(command, shell=True, check=True)

# Flask route for web support
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files or 'text' not in request.form:
        return jsonify({"error": "No video file or text provided"}), 400

    video_file = request.files['video']
    text = request.form['text']
    voice = request.form.get('voice', 'en')

    video_filename = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.mp4")
    tts_audio_file = os.path.join(UPLOAD_DIR, f"tts_audio_{uuid.uuid4()}.mp3")
    output_video_file = os.path.join(UPLOAD_DIR, f"dubbed_video_{uuid.uuid4()}.mp4")

    video_file.save(video_filename)

    try:
        # Generate TTS audio and combine it with the video concurrently
        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(executor, generate_tts_audio, text, tts_audio_file, voice),
                loop.run_in_executor(executor, combine_audio_video, video_filename, tts_audio_file, output_video_file)
            ]
            loop.run_until_complete(asyncio.wait(tasks))
        
        # Return the dubbed video
        return send_file(output_video_file, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Clean up files
        if os.path.exists(video_filename):
            os.remove(video_filename)
        if os.path.exists(tts_audio_file):
            os.remove(tts_audio_file)
        if os.path.exists(output_video_file):
            os.remove(output_video_file)

# Function to synchronize time
def synchronize_time():
    try:
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org')
        os.system(f"sudo date {time.strftime('%m%d%H%M%Y.%S', time.localtime(response.tx_time))}")
    except Exception as e:
        print(f"Failed to synchronize time: {e}")

# Main entry point
if __name__ == "__main__":
    app.run()
