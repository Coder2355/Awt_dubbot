import os
from flask import Flask, request, redirect, url_for, send_from_directory
from pyrogram import Client, filters
from pyrogram.types import Message
import asyncio
import subprocess
from werkzeug.utils import secure_filename
import aiofiles
import aiohttp
import config
import threading

# Create a Pyrogram Client
app_pyrogram = Client("anime_voice_dub_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

# Create Flask App
app_flask = Flask(__name__)
app_flask.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app_flask.config['PROCESSED_FOLDER'] = config.PROCESSED_FOLDER

if not os.path.exists(config.UPLOAD_FOLDER):
    os.makedirs(config.UPLOAD_FOLDER)
if not os.path.exists(config.PROCESSED_FOLDER):
    os.makedirs(config.PROCESSED_FOLDER)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

async def process_video(input_video_path, output_video_path, voice_path, watermark_path):
    command = [
        'ffmpeg',
        '-i', input_video_path,
        '-i', voice_path,
        '-filter_complex', f"[0:v][1:a]concat=n=1:v=1:a=1[v][a];[v]drawbox=x=0:y=0:w=iw:h=ih:color=black@0.5:t=fill,drawtext=text='Sample Watermark':x=(w-text_w)/2:y=(h-text_h)/2:fontsize=24:fontcolor=white[v]",
        '-map', '[v]',
        '-map', '[a]',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-strict', 'experimental',
        output_video_path
    ]
    process = await asyncio.create_subprocess_exec(*command)
    await process.communicate()

@app_flask.route('/', methods=['GET', 'POST'])
async def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files or 'voice' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        voice = request.files['voice']
        if file.filename == '' or voice.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename, config.ALLOWED_EXTENSIONS) and voice and allowed_file(voice.filename, config.ALLOWED_AUDIO_EXTENSIONS):
            filename = secure_filename(file.filename)
            voice_filename = secure_filename(voice.filename)
            input_video_path = os.path.join(app_flask.config['UPLOAD_FOLDER'], filename)
            voice_path = os.path.join(app_flask.config['UPLOAD_FOLDER'], voice_filename)
            output_video_path = os.path.join(app_flask.config['PROCESSED_FOLDER'], f"processed_{filename}")
            await save_file(file, input_video_path)
            await save_file(voice, voice_path)
            
            # Process the video
            await process_video(input_video_path, output_video_path, voice_path, config.WATERMARK_IMAGE_PATH)
            
            return redirect(url_for('download_file', filename=f"processed_{filename}"))
    return '''
    <!doctype html>
    <title>Upload Video</title>
    <h1>Upload a video and character voice for dubbing and watermarking</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=file name=voice>
      <input type=submit value=Upload>
    </form>
    '''

@app_flask.route('/uploads/<filename>')
async def download_file(filename):
    return send_from_directory(app_flask.config['PROCESSED_FOLDER'], filename)

@app_pyrogram.on_message(filters.video)
async def anime_voice_dub(client: Client, message: Message):
    video = message.video
    input_video_path = f"{config.UPLOAD_FOLDER}/{video.file_id}.mp4"
    output_video_path = f"{config.PROCESSED_FOLDER}/{video.file_id}_dubbed.mp4"
    
    # Download the video
    await message.download(file_name=input_video_path)
    
    # Inform user to upload the voice file
    await message.reply("Please send the character voice file (audio) as the next message.")

    @app_pyrogram.on_message(filters.audio & filters.reply)
    async def receive_voice_file(client: Client, voice_message: Message):
        if voice_message.reply_to_message.message_id == message.message_id:
            voice = voice_message.audio
            voice_path = f"{config.UPLOAD_FOLDER}/{voice.file_id}.mp3"
            
            # Download the voice file
            await voice_message.download(file_name=voice_path)
            
            # Process the video (dub voice and add watermark)
            await process_video(input_video_path, output_video_path, voice_path, config.WATERMARK_IMAGE_PATH)
            
            # Send the processed video back to the user
            await voice_message.reply_video(video=output_video_path, caption="Here is your dubbed video with watermark!")
            
            # Clean up the files
            os.remove(input_video_path)
            os.remove(output_video_path)
            os.remove(voice_path)

@app_pyrogram.on_message(filters.command(["start"]))
async def start(client: Client, message: Message):
    await message.reply("Welcome to the Anime Voice Dub Bot! Send me a video and then send a voice file for dubbing, and I will dub it with the character's voice and add a watermark.")

async def save_file(file, path):
    async with aiofiles.open(path, 'wb') as f:
        await f.write(file.read())

if __name__ == "__main__":
    app_pyrogram.run()
