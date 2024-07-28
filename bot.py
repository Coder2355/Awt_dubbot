import os
from flask import Flask, request, redirect, url_for, send_from_directory, render_template
from pyrogram import Client, filters
from pyrogram.types import Message
import subprocess
import threading
from werkzeug.utils import secure_filename
import config  # Import configuration

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def process_video(input_video_path, output_video_path, voice_path, watermark_path):
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
    subprocess.run(command, check=True)

@app_flask.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            input_video_path = os.path.join(app_flask.config['UPLOAD_FOLDER'], filename)
            output_video_path = os.path.join(app_flask.config['PROCESSED_FOLDER'], f"processed_{filename}")
            file.save(input_video_path)
            
            # Process the video
            process_video(input_video_path, output_video_path, config.CHARACTER_VOICE_PATH, config.WATERMARK_IMAGE_PATH)
            
            return redirect(url_for('download_file', filename=f"processed_{filename}"))
    return '''
    <!doctype html>
    <title>Upload Video</title>
    <h1>Upload a video for dubbing and watermarking</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

@app_flask.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app_flask.config['PROCESSED_FOLDER'], filename)

@app_pyrogram.on_message(filters.video)
async def anime_voice_dub(client: Client, message: Message):
    video = message.video
    input_video_path = f"{config.UPLOAD_FOLDER}/{video.file_id}.mp4"
    output_video_path = f"{config.PROCESSED_FOLDER}/{video.file_id}_dubbed.mp4"

    # Download the video
    await message.download(file_name=input_video_path)

    # Process the video (dub voice and add watermark)
    process_video(input_video_path, output_video_path, config.CHARACTER_VOICE_PATH, config.WATERMARK_IMAGE_PATH)

    # Send the processed video back to the user
    await message.reply_video(video=output_video_path, caption="Here is your dubbed video with watermark!")

    # Clean up the files
    os.remove(input_video_path)
    os.remove(output_video_path)

@app_pyrogram.on_message(filters.command(["start"]))
async def start(client: Client, message: Message):
    await message.reply("Welcome to the Anime Voice Dub Bot! Send me a video and I will dub it with a character voice and add a watermark.")

if __name__ == "__main__":
    app.run()
