"""
Database Package Initialization - MongoDB Focused

This module initializes and provides access to MongoDB collections
with proper connection handling and error management.
"""

from datetime import time
from typing import Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from app.utils.config import settings
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MongoDBConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_connection()
        return cls._instance
    
    def _initialize_connection(self):
        """Initialize MongoDB connection with retry logic"""
        self.client: Optional[MongoClient] = None
        self.db = None
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                self.client = MongoClient(
                    settings.MONGO_URI,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=30000,
                    serverSelectionTimeoutMS=5000,
                    retryWrites=True,
                    retryReads=True
                )
                
                # Verify connection
                self.client.admin.command('ping')
                self.db = self.client[settings.MONGO_DB_NAME]
                
                # Initialize collections and indexes
                self._initialize_collections()
                
                logger.info("MongoDB connection established successfully")
                return
                
            except (ConnectionFailure, ConfigurationError) as e:
                logger.warning(f"MongoDB connection attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error("Failed to connect to MongoDB after multiple attempts")
                    raise
                time.sleep(retry_delay)
    
    def _initialize_collections(self):
        """Ensure all collections have proper indexes"""
        collections = {
            'users': [
                [('email', 1), {'unique': True}],
                [('role', 1)],
            ],
            'jobs': [
                [('status', 1)],
                [('creator_id', 1)],
                [('department', 1)],
            ],
            'applications': [
                [('job_id', 1)],
                [('candidate_id', 1)],
                [('status', 1)],
            ],
            'interviews': [
                [('application_id', 1)],
            ],
            'activity_logs': [
                [('timestamp', -1)],
            ]
        }
        
        for collection_name, indexes in collections.items():
            coll = self.db[collection_name]
            for index in indexes:
                keys = index[0] if isinstance(index[0], list) else [index[0]]
                coll.create_index(keys, **index[1] if len(index) > 1 else {})

    def get_collection(self, collection_name: str):
        """Get a MongoDB collection with connection check"""
        if not self.client or not self.db:
            raise RuntimeError("Database connection not established")
        return self.db[collection_name]
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

# Singleton instance
mongodb = MongoDBConnection()

# Collection access shortcuts
def get_users_collection():
    return mongodb.get_collection('users')

def get_jobs_collection():
    return mongodb.get_collection('jobs')

def get_applications_collection():
    return mongodb.get_collection('applications')

def get_interviews_collection():
    return mongodb.get_collection('interviews')

def get_activity_logs_collection():
    return mongodb.get_collection('activity_logs')

__all__ = [
    'mongodb',
    'get_users_collection',
    'get_jobs_collection',
    'get_applications_collection',
    'get_interviews_collection',
    'get_activity_logs_collection'
]

def initialize_database():
    """Initialize database connection when module is imported"""
    try:
        # This will trigger connection on first import
        if not mongodb.client:
            raise RuntimeError("Failed to initialize MongoDB connection")
        
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# Initialize on import
initialize_database()