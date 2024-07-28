import os
import json
from flask import Flask, request, jsonify, send_file
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
import subprocess
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Thread

# Import configuration
from config import Config

# Initialize Flask app
flask_app = Flask(__name__)

# Initialize the bot with your API ID and hash
app = Client("anime_dub_bot", api_id=Config.API_ID, api_hash=Config.API_HASH, bot_token=Config.BOT_TOKEN)

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

# Function to handle errors
async def handle_error(client, message: Message, error: str):
    await message.reply_text(f"An error occurred: {error}")

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text("Hello! Send me a video and text to dub it with an anime voice. Use /tamil for Tamil dubbing. Use /voices to see available voices.")

@app.on_message(filters.command("voices"))
async def show_voices(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("English", callback_data="voice_en")],
        [InlineKeyboardButton("Tamil", callback_data="voice_ta")]
    ])
    await message.reply_text("Choose a voice:", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^voice_"))
async def handle_voice_selection(client, callback_query):
    voice = callback_query.data.split("_")[1]
    user_id = str(callback_query.from_user.id)
    user_data[user_id] = user_data.get(user_id, {})
    user_data[user_id]["voice"] = voice
    save_user_data(user_data)
    await callback_query.message.edit_text(f"Voice set to {voice}. Now send me the video.")

@app.on_message(filters.video)
async def handle_video(client, message: Message):
    try:
        # Download the video
        video_file = await message.download(DOWNLOAD_DIR)
        
        # Save video file path to user's session
        user_id = str(message.from_user.id)
        user_data[user_id] = user_data.get(user_id, {})
        user_data[user_id]["video_file"] = video_file
        save_user_data(user_data)
        
        await message.reply_text("Video received! Now send me the text to dub.")
    except Exception as e:
        await handle_error(client, message, str(e))

@app.on_message(filters.text & filters.private & ~filters.command(["tamil", "voices"]))
async def handle_text(client, message: Message):
    user_id = str(message.from_user.id)
    user_session = user_data.get(user_id, {})
    video_file = user_session.get("video_file")
    voice = user_session.get("voice", "en")
    
    if not video_file:
        await message.reply_text("Please send a video first.")
        return

    try:
        tts_audio_file = os.path.join(DOWNLOAD_DIR, f"tts_audio_{voice}.mp3")
        output_video_file = os.path.join(DOWNLOAD_DIR, f"dubbed_video_{voice}.mp4")
        
        # Generate TTS audio and combine it with the video concurrently
        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(executor, generate_tts_audio, message.text, tts_audio_file, voice),
                loop.run_in_executor(executor, combine_audio_video, video_file, tts_audio_file, output_video_file)
            ]
            await asyncio.wait(tasks)
        
        # Send the dubbed video back to the user
        await message.reply_video(output_video_file)

        # Clean up files
        os.remove(video_file)
        os.remove(tts_audio_file)
        os.remove(output_video_file)
    except Exception as e:
        await handle_error(client, message, str(e))

@app.on_message(filters.command("tamil"))
async def handle_tamil_command(client, message: Message):
    user_id = str(message.from_user.id)
    user_session = user_data.get(user_id, {})
    video_file = user_session.get("video_file")
    
    if not video_file:
        await message.reply_text("Please send a video first.")
        return

    try:
        tts_audio_file = os.path.join(DOWNLOAD_DIR, "tts_audio_tamil.mp3")
        output_video_file = os.path.join(DOWNLOAD_DIR, "dubbed_video_tamil.mp4")
        
        # Generate TTS audio and combine it with the video concurrently
        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(executor, generate_tts_audio, message.text, tts_audio_file, 'ta'),
                loop.run_in_executor(executor, combine_audio_video, video_file, tts_audio_file, output_video_file)
            ]
            await asyncio.wait(tasks)
        
        # Send the dubbed video back to the user
        await message.reply_video(output_video_file)

        # Clean up files
        os.remove(video_file)
        os.remove(tts_audio_file)
        os.remove(output_video_file)
    except Exception as e:
        await handle_error(client, message, str(e))

# Flask route for web support
@flask_app.route('/upload', methods=['POST'])
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

# Run both Flask and Pyrogram
if __name__ == "__main__":
    app.run()
