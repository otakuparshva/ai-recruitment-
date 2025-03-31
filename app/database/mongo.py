"""
Enhanced MongoDB Service with Connection Recovery and Data Access Layer

Handles all database operations with:
- Automatic connection recovery
- Exponential backoff retry logic
- Type validation against Pydantic models
- Comprehensive error handling
- Index management
"""

from typing import Optional, List, Dict, Any, TypeVar, Type
from pydantic import BaseModel
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import (
    ConnectionFailure,
    OperationFailure,
    DuplicateKeyError,
    PyMongoError,
    ServerSelectionTimeoutError,
    NetworkTimeout,
    AutoReconnect
)
from bson import ObjectId
from bson.errors import InvalidId
import logging
from datetime import datetime
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from app.utils.config import settings
from app.models import (
    UserInDB, JobInDB, ApplicationInDB,
    InterviewInDB, ActivityLog, PyObjectId
)
from dotenv import load_dotenv
import os

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")


logger = logging.getLogger(__name__)
T = TypeVar('T')

class MongoDB:
    _instance = None
    _connection_attempts = 0
    MAX_RECONNECT_ATTEMPTS = 5
    RECONNECT_DELAY = 2  # seconds
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize MongoDB connection with retry logic"""
        self.client: Optional[MongoClient] = None
        self.db = None
        self._connect()
        self._ensure_indexes()

    def _connect(self):
        """Establish MongoDB connection with advanced retry logic"""
        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            try:
                self.client = MongoClient(
                    settings.MONGO_URI,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=30000,
                    serverSelectionTimeoutMS=5000,
                    retryWrites=True,
                    retryReads=True,
                    appname="recruitment-system",
                    heartbeatFrequencyMS=10000,
                    socketKeepAlive=True
                )
                
                # Force connection check
                self.client.admin.command('ping')
                self.db = self.client[settings.MONGO_DB_NAME]
                self._connection_attempts = 0
                logger.info("MongoDB connection established successfully")
                return
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                self._connection_attempts += 1
                logger.warning(f"MongoDB connection attempt {attempt} failed: {str(e)}")
                if attempt == self.MAX_RECONNECT_ATTEMPTS:
                    logger.error("Max connection attempts reached")
                    raise
                time.sleep(self.RECONNECT_DELAY * attempt)
                
            except Exception as e:
                logger.error(f"Unexpected MongoDB connection error: {str(e)}")
                raise

    def _ensure_connection(self):
        """Ensure we have an active connection"""
        try:
            if not self.client or not self.db:
                raise ConnectionFailure("No active connection")
            self.client.admin.command('ping')
        except (ConnectionFailure, OperationFailure):
            logger.warning("MongoDB connection lost, attempting to reconnect...")
            self._connect()

    def _ensure_indexes(self):
        """Ensure required indexes exist with retry logic"""
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(PyMongoError),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        def create_indexes():
            try:
                # Users collection
                self.db.users.create_index([("email", 1)], unique=True, background=True)
                self.db.users.create_index([("role", 1)], background=True)
                
                # Jobs collection
                self.db.jobs.create_index([("status", 1)], background=True)
                self.db.jobs.create_index([("creator_id", 1)], background=True)
                self.db.jobs.create_index([("department", 1)], background=True)
                
                # Applications collection
                self.db.applications.create_index([("job_id", 1)], background=True)
                self.db.applications.create_index([("candidate_id", 1)], background=True)
                self.db.applications.create_index([("status", 1)], background=True)
                
                # Interviews collection
                self.db.interviews.create_index([("application_id", 1)], background=True)
                
                # Activity logs
                self.db.activity_logs.create_index([("timestamp", -1)], background=True)
                
            except OperationFailure as e:
                logger.error(f"Index creation failed: {str(e)}")
                raise

        create_indexes()

    def close(self):
        """Close MongoDB connection"""
        if self.client:
            try:
                self.client.close()
                logger.info("MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {str(e)}")

    def ping(self) -> bool:
        """Check if database is responsive with retry"""
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(PyMongoError),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        def _ping():
            try:
                self._ensure_connection()
                return self.client.admin.command('ping').get('ok', 0) == 1
            except Exception as e:
                logger.warning(f"Ping failed: {str(e)}")
                return False
                
        return _ping()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((AutoReconnect, NetworkTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def insert_document(self, collection: str, document: BaseModel) -> Optional[PyObjectId]:
        """Insert document with connection recovery"""
        try:
            self._ensure_connection()
            result = self.db[collection].insert_one(document.dict(by_alias=True))
            return result.inserted_id
        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error: {str(e)}")
            raise ValueError("Document with this key already exists") from e
        except PyMongoError as e:
            logger.error(f"Insert failed: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((AutoReconnect, NetworkTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def get_document(self, collection: str, model: Type[T], **filters) -> Optional[T]:
        """
        Get a single document with model validation
        """
        try:
            self._ensure_connection()
            doc = self.db[collection].find_one(filters)
            return model(**doc) if doc else None
        except PyMongoError as e:
            logger.error(f"Query failed: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((AutoReconnect, NetworkTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def get_documents(
        self,
        collection: str,
        model: Type[T],
        filter: Optional[Dict] = None,
        skip: int = 0,
        limit: int = 100,
        sort: Optional[List[tuple]] = None
    ) -> List[T]:
        """
        Get multiple documents with pagination and sorting
        """
        try:
            self._ensure_connection()
            filter = filter or {}
            cursor = self.db[collection].find(filter)
            
            if sort:
                cursor = cursor.sort(sort)
                
            if skip:
                cursor = cursor.skip(skip)
                
            if limit:
                cursor = cursor.limit(limit)
                
            return [model(**doc) for doc in cursor]
        except PyMongoError as e:
            logger.error(f"Query failed: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((AutoReconnect, NetworkTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def update_document(
        self,
        collection: str,
        model: Type[T],
        filters: Dict[str, Any],
        update_data: Dict[str, Any],
        return_updated: bool = False
    ) -> Optional[T]:
        """
        Update document(s) and optionally return the updated document
        """
        try:
            self._ensure_connection()
            update_op = {"$set": update_data}
            
            if return_updated:
                result = self.db[collection].find_one_and_update(
                    filters,
                    update_op,
                    return_document=ReturnDocument.AFTER
                )
                return model(**result) if result else None
            else:
                result = self.db[collection].update_many(filters, update_op)
                return result.modified_count
                
        except PyMongoError as e:
            logger.error(f"Update failed: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((AutoReconnect, NetworkTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def delete_document(self, collection: str, **filters) -> int:
        """
        Delete document(s) and return count of deleted items
        """
        try:
            self._ensure_connection()
            result = self.db[collection].delete_many(filters)
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Delete failed: {str(e)}")
            raise

    # ----- User Operations -----
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email with validation"""
        return await self.get_document("users", UserInDB, email=email)

    async def create_user(self, user: UserInDB) -> bool:
        """Create new user with validation"""
        result = await self.insert_document("users", user)
        return result is not None

    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[UserInDB]:
        """Update user and return updated document"""
        try:
            filters = {"_id": PyObjectId.validate(user_id)}
            return await self.update_document(
                "users",
                UserInDB,
                filters,
                update_data,
                return_updated=True
            )
        except InvalidId:
            return None

    # ----- Job Operations -----
    async def create_job(self, job: JobInDB) -> Optional[PyObjectId]:
        """Create new job posting"""
        return await self.insert_document("jobs", job)

    async def get_job_by_id(self, job_id: str) -> Optional[JobInDB]:
        """Get job by ID with validation"""
        try:
            return await self.get_document("jobs", JobInDB, _id=PyObjectId.validate(job_id))
        except InvalidId:
            return None

    async def get_jobs(
        self,
        status: Optional[str] = None,
        department: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[JobInDB]:
        """Get jobs with optional filtering"""
        filters = {}
        if status:
            filters["status"] = status
        if department:
            filters["department"] = department
            
        return await self.get_documents(
            "jobs",
            JobInDB,
            filter=filters,
            skip=skip,
            limit=limit,
            sort=[("created_at", -1)]
        )

    # ----- Application Operations -----
    async def create_application(self, application: ApplicationInDB) -> Optional[PyObjectId]:
        """Create new job application"""
        return await self.insert_document("applications", application)

    async def get_application_by_id(self, application_id: str) -> Optional[ApplicationInDB]:
        """Get application by ID"""
        try:
            return await self.get_document(
                "applications",
                ApplicationInDB,
                _id=PyObjectId.validate(application_id)
            )
        except InvalidId:
            return None

    # ----- Interview Operations -----
    async def create_interview(self, interview: InterviewInDB) -> Optional[PyObjectId]:
        """Create new interview record"""
        return await self.insert_document("interviews", interview)

    # ----- Activity Logging -----
    async def log_activity(self, activity: ActivityLog) -> bool:
        """Log system activity"""
        result = await self.insert_document("activity_logs", activity)
        return result is not None

    async def get_activity_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ActivityLog]:
        """Get activity logs with optional filtering"""
        filters = {}
        if user_id:
            try:
                filters["user_id"] = PyObjectId.validate(user_id)
            except InvalidId:
                return []
        if action:
            filters["action"] = action
            
        return await self.get_documents(
            "activity_logs",
            ActivityLog,
            filter=filters,
            skip=skip,
            limit=limit,
            sort=[("timestamp", -1)]
        )

    # ----- Utility Methods -----
    def get_collection(self, collection_name: str):
        """Get raw MongoDB collection reference"""
        self._ensure_connection()
        return self.db[collection_name]

# Singleton instance
mongodb = MongoDB()

def get_mongodb() -> MongoDB:
    """Dependency function for FastAPI (if used)"""
    return mongodb