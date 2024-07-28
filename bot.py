import os
from flask import Flask, request, redirect, url_for, send_from_directory
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import subprocess
from werkzeug.utils import secure_filename
import aiofiles
from pydub import AudioSegment
import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
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

async def process_video(input_video_path, output_video_path, voice_path):
    command = [
        'ffmpeg',
        '-i', input_video_path,
        '-i', voice_path,
        '-filter_complex', "[0:v][1:a]concat=n=1:v=1:a=1[v][a];[v]drawtext=text='@Anime_warrior_tamil':x=(w-text_w)/2:y=(h-text_h)/2:fontsize=24:fontcolor=white[v]",
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
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename, config.ALLOWED_EXTENSIONS):
            filename = secure_filename(file.filename)
            input_video_path = os.path.join(app_flask.config['UPLOAD_FOLDER'], filename)
            output_video_path = os.path.join(app_flask.config['PROCESSED_FOLDER'], f"processed_{filename}")
            await save_file(file, input_video_path)
            
            # Extract audio and process for voice detection and translation
            voice_path = await extract_audio(input_video_path)
            await process_video(input_video_path, output_video_path, voice_path)
            
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
async def download_file(filename):
    return send_from_directory(app_flask.config['PROCESSED_FOLDER'], filename)

@app_pyrogram.on_message(filters.command(["start"]))
async def start(client: Client, message: Message):
    await message.reply(
        "Welcome to the Anime Voice Dub Bot! Send me a video to start.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Select Language", callback_data="select_language")]
            ]
        )
    )

@app_pyrogram.on_message(filters.video)
async def anime_voice_dub(client: Client, message: Message):
    video = message.video
    input_video_path = f"{config.UPLOAD_FOLDER}/{video.file_id}.mp4"
    output_video_path = f"{config.PROCESSED_FOLDER}/{video.file_id}_dubbed.mp4"
    
    # Download the video
    await message.download(file_name=input_video_path)
    
    # Inform user to select the dubbing language
    await message.reply("Please select the dubbing language.", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Tamil", callback_data=f"dub_language_{video.file_id}_tamil")],
        [InlineKeyboardButton("Other Language", callback_data=f"dub_language_{video.file_id}_other")],
    ]))

@app_pyrogram.on_callback_query()
async def handle_callback_query(client: Client, callback_query):
    data = callback_query.data
    if data.startswith("dub_language_"):
        _, file_id, language = data.split("_")
        input_video_path = f"{config.UPLOAD_FOLDER}/{file_id}.mp4"
        voice_path = await extract_audio(input_video_path)
        
        translated_voice_path = await translate_voice(voice_path, language)
        output_video_path = f"{config.PROCESSED_FOLDER}/{file_id}_dubbed_{language}.mp4"
        
        # Process the video (dub voice and add watermark)
        await process_video(input_video_path, output_video_path, translated_voice_path)
        
        # Send the processed video back to the user
        await callback_query.message.reply_video(video=output_video_path, caption="Here is your dubbed video with watermark!")
        
        # Clean up the files
        os.remove(input_video_path)
        os.remove(output_video_path)
        os.remove(voice_path)
        os.remove(translated_voice_path)

async def save_file(file, path):
    async with aiofiles.open(path, 'wb') as f:
        await f.write(await file.read())

async def extract_audio(video_path):
    audio_path = video_path.rsplit('.', 1)[0] + ".wav"
    command = [
        'ffmpeg',
        '-i', video_path,
        '-q:a', '0',
        '-map', 'a',
        audio_path
    ]
    process = await asyncio.create_subprocess_exec(*command)
    await process.communicate()
    return audio_path

async def translate_voice(voice_path, target_language):
    recognizer = sr.Recognizer()
    translator = Translator()
    
    audio = AudioSegment.from_wav(voice_path)
    audio.export("temp.wav", format="wav")
    
    with sr.AudioFile("temp.wav") as source:
        audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data)
    
    translated_text = translator.translate(text, dest=target_language).text
    
    tts = gTTS(translated_text, lang=target_language)
    translated_voice_path = voice_path.rsplit('.', 1)[0] + f"_{target_language}.mp3"
    tts.save(translated_voice_path)
    
    os.remove("temp.wav")
    return translated_voice_path

if __name__ == "__main__":
    app_pyrogram.run()
