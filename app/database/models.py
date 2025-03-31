"""
MongoDB Models (Schemas) with Pydantic Validation

Defines the document structures and validation for all MongoDB collections.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, validator
from bson import ObjectId
from pymongo import MongoClient
from bson.objectid import ObjectId

class MongoDB:
    def __init__(self, uri="mongodb://localhost:27017", db_name="recruitment_db"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def insert_user(self, user_data):
        return self.db.users.insert_one(user_data).inserted_id

    def find_user(self, query):
        return self.db.users.find_one(query)

    def update_user(self, user_id, update_data):
        return self.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})

    def delete_user(self, user_id):
        return self.db.users.delete_one({"_id": ObjectId(user_id)})

# Import settings (adjust path if needed)
try:
    from app.utils.config import settings
except ImportError:
    from ..utils.config import settings

class PyObjectId(str):
    """Custom type for MongoDB ObjectId with Pydantic compatibility"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)  # Return as string to avoid BSON serialization issues

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class ModelBase(BaseModel):
    """Base model with common configuration"""
    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True
        orm_mode = True

# ----- User Models -----
class UserBase(ModelBase):
    email: EmailStr
    role: str = Field(..., regex="^(candidate|recruiter|admin)$")
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v  # You can add further password validation

class UserInDB(UserBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    login_attempts: int = 0

# ----- Job Models -----
class JobSkill(ModelBase):
    name: str = Field(..., max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    proficiency: Optional[str] = Field(None, regex="^(basic|intermediate|advanced|expert)$")

class JobBase(ModelBase):
    title: str = Field(..., max_length=100)
    department: str = Field(..., max_length=100)
    location: str = Field(..., max_length=100)
    description: str
    skills: List[JobSkill] = []
    salary_min: int = Field(..., gt=0)
    salary_max: int = Field(..., gt=0)

class JobCreate(JobBase):
    creator_id: PyObjectId

class JobInDB(JobBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    creator_id: PyObjectId
    status: str = Field("pending", regex="^(pending|approved|rejected|closed)$")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[PyObjectId] = None

# ----- Application Models -----
class ApplicationBase(ModelBase):
    job_id: PyObjectId
    candidate_id: PyObjectId
    resume_s3_key: str
    resume_text: str

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationInDB(ApplicationBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    match_score: float = Field(0.0, ge=0, le=100)
    status: str = Field("applied", regex="^(applied|reviewed|interviewed|rejected|hired)$")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ----- Interview Models -----
class InterviewQuestion(ModelBase):
    question: str
    options: List[str] = Field(..., min_items=2, max_items=5)
    correct_index: int = Field(..., ge=0)
    difficulty: float = Field(1.0, gt=0, le=3.0)
    skill_tested: Optional[str]

class InterviewAnswer(ModelBase):
    question_id: PyObjectId
    answer: str
    is_correct: bool
    time_taken: float  # seconds

class InterviewBase(ModelBase):
    application_id: PyObjectId
    questions: List[InterviewQuestion]

class InterviewCreate(InterviewBase):
    pass

class InterviewInDB(InterviewBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    answers: List[InterviewAnswer] = []
    score: int = Field(0, ge=0)
    total_questions: int = Field(0, ge=0)
    status: str = Field("pending", regex="^(pending|completed|reviewed)$")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

# ----- Activity Log Model -----
class ActivityLog(ModelBase):
    user_id: PyObjectId
    action: str
    entity_type: Optional[str]  # e.g., "job", "application"
    entity_id: Optional[PyObjectId]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ----- Resume Parser Model -----
class ParsedResume(ModelBase):
    candidate_id: PyObjectId
    raw_text: str
    skills: List[str] = []
    experience_years: float = 0.0
    education: List[str] = []
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

# Export all models
__all__ = [
    # Users
    "UserBase", "UserCreate", "UserInDB",
    
    # Jobs
    "JobSkill", "JobBase", "JobCreate", "JobInDB",
    
    # Applications
    "ApplicationBase", "ApplicationCreate", "ApplicationInDB",
    
    # Interviews
    "InterviewQuestion", "InterviewAnswer", 
    "InterviewBase", "InterviewCreate", "InterviewInDB",
    
    # Other
    "ActivityLog", "ParsedResume",
    "PyObjectId"  # Custom ObjectId type
]

if __name__ == "__main__":
    db = MongoDB()
    new_user = {"name": "John Doe", "email": "john@example.com"}
    user_id = db.insert_user(new_user)
    print(f"Inserted User ID: {user_id}")
