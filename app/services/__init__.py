import logging
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from app.utils.config import settings

logger = logging.getLogger(__name__)

class MongoDBConnection:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect_to_mongodb()

    def connect_to_mongodb(self, retries=5, retry_delay=5):
        """Establish connection to MongoDB with retry mechanism."""
        for attempt in range(retries):
            try:
                self.client = MongoClient(
                    settings.MONGO_URI,
                    serverSelectionTimeoutMS=settings.MONGO_TIMEOUT_MS,
                    maxPoolSize=settings.MONGO_MAX_POOL_SIZE
                )
                self.db = self.client[settings.MONGO_DB_NAME]
                # Test connection
                self.client.admin.command('ping')
                logger.info("Successfully connected to MongoDB")
                return
            except ConnectionFailure as e:
                logger.error(f"MongoDB connection failed (Attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.critical("All MongoDB connection attempts failed. Exiting.")
                    raise

    def get_database(self):
        """Return the MongoDB database instance."""
        if not self.db:
            raise RuntimeError("MongoDB connection is not established.")
        return self.db

    def close_connection(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

# Singleton instance of MongoDB connection
mongodb = MongoDBConnection()

__all__ = ["mongodb"]