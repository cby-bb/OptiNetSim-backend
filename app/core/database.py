from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import settings


class Database:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


db_manager = Database()


async def connect_to_mongo():
    """Connects to MongoDB and initializes the database object."""
    print("Connecting to MongoDB...")
    db_manager.client = AsyncIOMotorClient(settings.MONGO_URI)
    db_manager.db = db_manager.client[settings.MONGO_DB_NAME]
    print("Successfully connected to MongoDB.")


async def close_mongo_connection():
    """Closes the MongoDB connection."""
    if db_manager.client:
        print("Closing MongoDB connection...")
        db_manager.client.close()
        print("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    """Dependency to get the database instance."""
    if db_manager.db is None:
        raise Exception("Database not initialized. Call connect_to_mongo first.")
    return db_manager.db
