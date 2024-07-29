import os
import asyncio
import subprocess
from flask import Flask, request, send_from_directory
from pyrogram import Client, filters
from threading import Thread
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, FFMPEG_PATH, UPLOAD_FOLDER, DUBBED_FOLDER, PORT, GOOGLE_CLOUD_SPEECH_CREDENTIALS
from googletrans import Translator
from google.cloud import speech_v1p1beta1 as speech
from gtts import gTTS

# Initialize the bot with your credentials
app = Client("dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
translator = Translator()

# Initialize Flask app
web_app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DUBBED_FOLDER, exist_ok=True)

user_language = {}

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

async def dub_voice(input_path, output_path, lang_code):
    # Convert input audio to WAV format for processing
    wav_path = input_path.replace('.mp3', '.wav')
    command = [FFMPEG_PATH, '-i', input_path, wav_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await process.communicate()

    # Step 1: Transcribe English audio to text
    english_text = transcribe_audio(wav_path)

    # Step 2: Translate English text to the selected language text
    translated_text = translator.translate(english_text, src='en', dest=lang_code).text

    # Step 3: Convert the translated text to speech
    tts_path = output_path.replace('.mp3', '_tts.mp3')
    tts = gTTS(translated_text, lang=lang_code)
    tts.save(tts_path)

    # Step 4: Combine original audio with TTS audio
    command = [
        FFMPEG_PATH, '-i', input_path, '-i', tts_path, '-filter_complex',
        '[0:a][1:a]amerge=inputs=2[a]', '-map', '[a]', '-ac', '2', output_path
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await process.communicate()

    # Clean up temporary files
    os.remove(wav_path)
    os.remove(tts_path)

@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Upload Audio for Dubbing", callback_data="upload_audio")],
        [InlineKeyboardButton("Select Language", callback_data="select_language")]
    ])
    await message.reply_text("Welcome! Use the buttons below to upload an audio file for dubbing or to select a language.", reply_markup=keyboard)

@app.on_callback_query(filters.regex("upload_audio"))
async def upload_audio(client: Client, callback_query):
    await callback_query.message.reply_text("Please send me an audio file with the /dub command to get it dubbed.")

@app.on_callback_query(filters.regex("select_language"))
async def select_language(client: Client, callback_query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Tamil", callback_data="lang_ta")],
        [InlineKeyboardButton("Hindi", callback_data="lang_hi")],
        [InlineKeyboardButton("Spanish", callback_data="lang_es")],
        [InlineKeyboardButton("French", callback_data="lang_fr")],
    ])
    await callback_query.message.reply_text("Please select the language for dubbing:", reply_markup=keyboard)

@app.on_callback_query(filters.regex("lang_"))
async def set_language(client: Client, callback_query):
    lang_code = callback_query.data.split("_")[1]
    user_language[callback_query.from_user.id] = lang_code
    await callback_query.message.reply_text(f"Language set to {lang_code}. Now you can send an audio file with the /dub command.")

@app.on_message(filters.command("dub") & filters.audio)
async def dub_anime(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_language:
        await message.reply_text("Please select a language first using the /start command.")
        return
    
    lang_code = user_language[user_id]
    audio = message.audio
    file_path = await client.download_media(audio, file_name=os.path.join(UPLOAD_FOLDER, audio.file_name))
    
    input_path = file_path
    output_path = os.path.join(DUBBED_FOLDER, "dubbed_" + os.path.basename(file_path))
    
    await message.reply_text("Dubbing in progress, please wait...")
    
    try:
        await dub_voice(input_path, output_path, lang_code)
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
        asyncio.run(dub_voice(file_path, output_path, 'ta'))  # Default to Tamil for web uploads
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
    <h1>Upload Audio File to Dub</h1>
    <form method=post enctype=multipart/form-data action="/upload">
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

if __name__ == '__main__':
    app.run()
