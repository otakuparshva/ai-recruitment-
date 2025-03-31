import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from pymongo import MongoClient
from app.utils.config import config
import logging

logger = logging.getLogger(__name__)

# SQLAlchemy Setup
SQLALCHEMY_DATABASE_URL = config.SQLALCHEMY_DATABASE_URI

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MongoDB Setup
class MongoDB:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            try:
                cls._instance.client = MongoClient(
                    config.MONGO_URI,
                    connectTimeoutMS=30000,
                    socketTimeoutMS=None,
                    socketKeepAlive=True
                )
                cls._instance.db = cls._instance.client[config.MONGO_DB_NAME]
                logger.info("Connected to MongoDB successfully")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
        return cls._instance

# Database session dependency
def get_db():
    """
    SQL Database session generator for FastAPI dependency injection
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# Global database session instances
db_session = scoped_session(SessionLocal)
mongo = MongoDB().db

def init_db():
    """
    Initialize database tables and indexes
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create MongoDB indexes
        mongo.users.create_index("email", unique=True)
        mongo.jobs.create_index("creator_email")
        mongo.jobs.create_index("status")
        mongo.applications.create_index("job_id")
        mongo.applications.create_index("candidate_id")
        mongo.interviews.create_index("application_id")
        mongo.activity_logs.create_index("timestamp")
        logger.info("MongoDB indexes created successfully")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

def close_db_connections():
    """
    Properly close all database connections
    """
    try:
        db_session.remove()
        MongoDB().client.close()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")