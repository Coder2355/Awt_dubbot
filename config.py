import os

API_ID = os.environ.get("API_ID", "21740783")
API_HASH = os.environ.get("API_HASH", "a5dc7fec8302615f5b441ec5e238cd46")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7116266807:AAFiuS4MxcubBiHRyzKEDnmYPCRiS0f3aGU")
    
CHARACTER_VOICE_PATH = "path/to/character_voice.mp3"  # Path to the character's voice file
WATERMARK_IMAGE_PATH = "path/to/watermark.png"  # Path to your watermark image
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi'}
