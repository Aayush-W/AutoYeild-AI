from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://diyawani2006_db_user:Xino2SRe9j8PjrMv@cluster0.0dwbwfe.mongodb.net/?appName=Cluster0"

async_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
async_db = async_client["autoyield"]

sync_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
sync_db = sync_client["autoyield"]
