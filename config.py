import os

class Config:
    API_ID = os.environ.get("API_ID", "21740783")
    API_HASH = os.environ.get("API_HASH", "a5dc7fec8302615f5b441ec5e238cd46")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "7116266807:AAFiuS4MxcubBiHRyzKEDnmYPCRiS0f3aGU")
    
    VOICE_DIR = os.getenv('VOICE_DIR', 'voices')
    DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', 'downloads')

# File paths
    VOICE_MAP_FILE = os.getenv('VOICE_MAP_FILE', 'voice_map.json')
