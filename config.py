import os

class Config:
    API_ID = os.environ.get("API_ID", "your_api_id")
    API_HASH = os.environ.get("API_HASH", "your_api_hash")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
    DOWNLOAD_DIR = "./downloads/"
    UPLOAD_DIR = "./uploads/"
    USER_DATA_FILE = "./user_data.json"
