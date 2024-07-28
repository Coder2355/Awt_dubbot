import os

class Config:
    API_ID = os.environ.get("API_ID", "21740783")
    API_HASH = os.environ.get("API_HASH", "a5dc7fec8302615f5b441ec5e238cd46")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "7116266807:AAFiuS4MxcubBiHRyzKEDnmYPCRiS0f3aGU")
    DOWNLOAD_DIR = "./downloads/"
    UPLOAD_DIR = "./uploads/"
    USER_DATA_FILE = "./user_data.json"
