import os
import asyncio
import subprocess
from flask import Flask, request, send_from_directory
from pyrogram import Client, filters
from threading import Thread
from pyrogram.types import Message
from config import API_ID, API_HASH, BOT_TOKEN, FFMPEG_PATH, UPLOAD_FOLDER, DUBBED_FOLDER, PORT

# Initialize the bot with your credentials
app = Client("dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Initialize Flask app
web_app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DUBBED_FOLDER, exist_ok=True)

# Asynchronous function to process audio
async def dub_voice(input_path, output_path):
    command = [
        FFMPEG_PATH, "-i", input_path,
        "-vf", "subtitles=subtitles.srt",  # Assuming subtitles.srt contains Tamil translations
        output_path
    ]
    process = await asyncio.create_subprocess_exec(*command)
    await process.communicate()

@app.on_message(filters.command("dub") & filters.audio)
async def dub_anime(client: Client, message: Message):
    audio = message.audio
    file_path = await client.download_media(audio, file_name=os.path.join(UPLOAD_FOLDER, audio.file_name))
    
    input_path = file_path
    output_path = os.path.join(DUBBED_FOLDER, "dubbed_" + os.path.basename(file_path))
    
    await message.reply_text("Dubbing in progress, please wait...")
    
    try:
        await dub_voice(input_path, output_path)
        await message.reply_audio(audio=output_path, caption="Here's your dubbed audio!")
    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")
    finally:
        os.remove(file_path)
        os.remove(output_path)

@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply_text("Send me an audio file with the /dub command to get it dubbed into Tamil!")

# Flask route to upload audio files
@web_app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    output_path = os.path.join(DUBBED_FOLDER, "dubbed_" + file.filename)
    try:
        asyncio.run(dub_voice(file_path, output_path))
        return send_from_directory(directory=DUBBED_FOLDER, path="dubbed_" + file.filename, as_attachment=True)
    except Exception as e:
        return str(e), 500
    finally:
        os.remove(file_path)
        os.remove(output_path)

# Flask route to serve the upload form
@web_app.route('/')
def index():
    return '''
    <!doctype html>
    <title>Upload Audio File</title>
    <h1>Upload Audio File to Dub into Tamil</h1>
    <form method=post enctype=multipart/form-data action="/upload">
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

if __name__ == '__main__':
    app.run()
