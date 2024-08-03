import os
import re
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from tqdm.asyncio import tqdm
import config

# Initialize Pyrogram Client
app = Client("gdrive_url_uploader_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

# Helper function to get Google Drive file ID from URL
def get_file_id(url):
    pattern = r'(?:https://drive.google.com/file/d/|https://drive.google.com/open\?id=)([^/]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

# Function to download file using aiohttp
async def download_file(file_id, file_name, message, client):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            chunk_size = 1024 * 1024  # 1 MB
            progress = tqdm(total=total_size, unit='B', unit_scale=True, desc=file_name)
            
            with open(file_name, 'wb') as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    f.write(chunk)
                    progress.update(len(chunk))
                    await client.send_chat_action(message.chat.id, "upload_document")

            progress.close()

# Command handler to upload Google Drive files
@app.on_message(filters.command("upload") & filters.private)
async def upload_gdrive_file(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Please provide a Google Drive URL.")
        return

    url = message.command[1]
    file_id = get_file_id(url)
    
    if not file_id:
        await message.reply_text("Invalid Google Drive URL.")
        return

    try:
        file_name = f"{file_id}.file"  # Default file name
        await message.reply_text(f"Downloading file with ID: {file_id}")

        # Download file with progress bar
        await download_file(file_id, file_name, message, client)
        
        await message.reply_text(f"File downloaded: {file_name}")

        # Upload to Telegram
        await client.send_document(chat_id=message.chat.id, document=file_name)
        os.remove(file_name)
    except Exception as e:
        await message.reply_text(f"Failed to upload file: {e}")

# Start the bot with long polling
if __name__ == "__main__":
    app.run()
