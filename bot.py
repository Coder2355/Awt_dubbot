import os
import asyncio
import subprocess
from flask import Flask, request, send_from_directory
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, FFMPEG_PATH, UPLOAD_FOLDER, DUBBED_FOLDER, PORT, GOOGLE_CLOUD_SPEECH_CREDENTIALS
from googletrans import Translator
from threading import Thread
from google.cloud import speech_v1p1beta1 as speech
from gtts import gTTS

# Initialize the bot with your credentials
app = Client("dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
translator = Translator()

# Initialize Flask app
web_app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DUBBED_FOLDER, exist_ok=True)

def transcribe_audio(audio_file_path):
    client = speech.SpeechClient.from_service_account_json(GOOGLE_CLOUD_SPEECH_CREDENTIALS)
    with open(audio_file_path, 'rb') as audio_file:
        content = audio_file.read()
    
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )
    
    response = client.recognize(config=config, audio=audio)
    return ' '.join([result.alternatives[0].transcript for result in response.results])

async def dub_voice(input_path, output_path):
    # Step 1: Transcribe English audio to text
    english_text = transcribe_audio(input_path)

    # Step 2: Translate English text to Tamil text
    translated_text = translator.translate(english_text, src='en', dest='ta').text

    # Step 3: Convert Tamil text to speech
    tts = gTTS(translated_text, lang='ta')
    tts.save(output_path)

@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Upload Audio for Dubbing", callback_data="upload_audio")]
    ])
    await message.reply_text("Welcome! Use the button below to upload an audio file for dubbing into Tamil.", reply_markup=keyboard)

@app.on_callback_query(filters.regex("upload_audio"))
async def upload_audio(client: Client, callback_query):
    await callback_query.message.reply_text("Please send me an audio file with the /dub command to get it dubbed into Tamil.")

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
        if os.path.exists(output_path):
            os.remove(output_path)

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
        if os.path.exists(output_path):
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
