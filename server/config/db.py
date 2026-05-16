import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

APP_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(APP_ROOT / ".env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "autoyield")
MONGO_TIMEOUT_MS = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000"))

if "<" in MONGO_URI or ">" in MONGO_URI:
    raise RuntimeError(
        "Invalid MONGO_URI: it still contains placeholder tokens. "
        "Replace <username> and <password> in your .env file."
    )

async_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS)
async_db = async_client[MONGO_DB_NAME]

sync_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS)
sync_db = sync_client[MONGO_DB_NAME]
