import os
import subprocess
import json
from datetime import datetime
from pyrogram import Client, filters
import requests
from gtts import gTTS
import config

app = Client("anime_dub_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

# Create directories if they don't exist
if not os.path.exists(config.VOICE_DIR):
    os.makedirs(config.VOICE_DIR)
if not os.path.exists(config.DOWNLOAD_DIR):
    os.makedirs(config.DOWNLOAD_DIR)

# Load existing voice map or create a new one
if os.path.exists(config.VOICE_MAP_FILE):
    with open(config.VOICE_MAP_FILE, "r") as f:
        voice_map = json.load(f)
else:
    voice_map = {}

# Function to merge video and audio using FFmpeg
def merge_video_audio(video_path, audio_path, output_path):
    command = [
        'ffmpeg', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', output_path
    ]
    subprocess.run(command)

# Function to download video from a URL
def download_video_from_url(url):
    response = requests.get(url)
    video_path = os.path.join(config.DOWNLOAD_DIR, os.path.basename(url))
    with open(video_path, 'wb') as f:
        f.write(response.content)
    return video_path

@app.on_message(filters.command(["start"]))
def start(client, message):
    message.reply_text("Welcome to the Anime Dub Bot! Send me a video or a video URL to dub in Tamil or another language with character voices. To add voice for a character, use /addvoice character_name. To dub using text, use /dubtext character_name text_to_dub language_code.")

@app.on_message(filters.command(["addvoice"]))
def add_voice(client, message):
    parts = message.text.split(" ", 1)
    if len(parts) != 2:
        message.reply_text("Usage: /addvoice character_name")
        return
    
    character_name = parts[1].strip()
    message.reply_text(f"Send me the voice audio for {character_name}.")
    
    # Store the character name in the user session for the next message
    app.set_parse_mode("adding_voice", message.chat.id, character_name)

@app.on_message(filters.audio & filters.parse_mode("adding_voice"))
def receive_voice(client, message):
    character_name = app.get_parse_mode(message.chat.id)
    audio_path = os.path.join(config.VOICE_DIR, f"{character_name}.mp3")
    message.download(audio_path)
    
    voice_map[character_name] = audio_path
    
    with open(config.VOICE_MAP_FILE, "w") as f:
        json.dump(voice_map, f)
    
    message.reply_text(f"Voice for {character_name} has been added.")
    app.clear_parse_mode(message.chat.id)

@app.on_message(filters.video | filters.text)
def handle_video(client, message):
    if message.video:
        video_path = message.download()
    elif message.text and message.text.startswith("http"):
        video_url = message.text.strip()
        video_path = download_video_from_url(video_url)
    else:
        message.reply_text("Send me a video file or a URL to a video.")
        return
    
    # Determine the character's audio (this is a placeholder, logic to determine the character should be added)
    character = "character1"  # Example character
    audio_path = voice_map.get(character, None)
    
    if not audio_path:
        message.reply_text(f"No voice found for {character}. Please add a voice using /addvoice character_name.")
        return
    
    output_path = "dubbed_video.mp4"
    merge_video_audio(video_path, audio_path, output_path)
    
    client.send_video(message.chat.id, video=output_path, caption="Here is your dubbed video!")

@app.on_message(filters.command(["dubtext"]))
def dub_text(client, message):
    parts = message.text.split(" ", 3)
    if len(parts) != 4:
        message.reply_text("Usage: /dubtext character_name text_to_dub language_code")
        return

    character_name = parts[1].strip()
    text_to_dub = parts[2].strip()
    language_code = parts[3].strip()

    tts = gTTS(text=text_to_dub, lang=language_code)
    audio_path = os.path.join(config.VOICE_DIR, f"{character_name}_tts.mp3")
    tts.save(audio_path)
    
    voice_map[character_name] = audio_path
    
    with open(config.VOICE_MAP_FILE, "w") as f:
        json.dump(voice_map, f)
    
    message.reply_text(f"Text for {character_name} has been converted to audio and added.")
    
    app.clear_parse_mode(message.chat.id)

app.run()
