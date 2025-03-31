from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from bson import ObjectId
from pymongo import DESCENDING, ASCENDING
from app.database.mongo import mongodb
from app.models import ActivityLog, UserInDB, JobInDB
from app.services.email_service import EmailService
import logging
from app.utils.config import settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class AdminService:
    def __init__(self, admin_email: str):
        """
        Initialize AdminService with admin email and required services
        
        Args:
            admin_email: Email of the admin user
        """
        self.admin_email = admin_email
        self.email_service = EmailService()
        self.db = mongodb
        self.users_col = self.db.users
        self.jobs_col = self.db.jobs
        self.applications_col = self.db.applications
        self.activity_col = self.db.activity_logs
    
    async def get_all_users(
        self, 
        page: int = 1, 
        per_page: int = 10,
        role: Optional[str] = None,
        active: Optional[bool] = None
    ) -> Dict[str, Union[List[Dict], int]]:
        """Get paginated list of users with optional filtering"""
        try:
            skip = (page - 1) * per_page
            query = {}
            
            if role:
                query["role"] = role
            if active is not None:
                query["is_active"] = active
                
            total = await self.users_col.count_documents(query)
            users = await self.users_col.find(query).skip(skip).limit(per_page).to_list(per_page)
            
            return {
                "data": [await self._convert_user(user) for user in users],
                "total": total,
                "page": page,
                "per_page": per_page
            }
        except Exception as e:
            logger.error(f"Error fetching users: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch users")

    async def get_user_details(self, user_id: str) -> Dict:
        """Get detailed information about a specific user"""
        try:
            if not ObjectId.is_valid(user_id):
                raise HTTPException(status_code=400, detail="Invalid user ID")
                
            user = await self.users_col.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
                
            applications_count = await self.applications_col.count_documents({"candidate_id": user_id})
            last_activity = await self._get_last_activity(user["email"])
            
            return {
                **await self._convert_user(user),
                "applications_count": applications_count,
                "last_activity": last_activity,
                "profile_completeness": await self._calculate_profile_completeness(user)
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching user details: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch user details")

    async def toggle_user_status(self, user_id: str) -> Dict:
        """Toggle active/inactive status of a user"""
        try:
            if not ObjectId.is_valid(user_id):
                raise HTTPException(status_code=400, detail="Invalid user ID")
                
            user = await self.users_col.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
                
            new_status = not user.get("is_active", True)
            result = await self.users_col.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": new_status, "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to update user status")
            
            await self._log_activity(f"Set user {user['email']} status to {'active' if new_status else 'inactive'}")
            
            if not new_status:
                await self._notify_user_deactivation(user["email"])
            
            return {"success": True, "new_status": new_status}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error toggling user status: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update user status")

    async def get_pending_jobs(
        self,
        page: int = 1,
        per_page: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Union[List[Dict], int]]:
        """Get paginated list of jobs pending approval with sorting"""
        try:
            skip = (page - 1) * per_page
            sort_direction = DESCENDING if sort_order.lower() == "desc" else ASCENDING
            
            total = await self.jobs_col.count_documents({"status": "pending"})
            jobs = await self.jobs_col.find({"status": "pending"}) \
                .sort(sort_by, sort_direction) \
                .skip(skip) \
                .limit(per_page) \
                .to_list(per_page)
            
            return {
                "data": [await self._convert_job(job) for job in jobs],
                "total": total,
                "page": page,
                "per_page": per_page
            }
        except Exception as e:
            logger.error(f"Error fetching pending jobs: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch pending jobs")

    async def approve_job(self, job_id: str) -> Dict:
        """Approve a job posting"""
        try:
            if not ObjectId.is_valid(job_id):
                raise HTTPException(status_code=400, detail="Invalid job ID")
                
            job = await self.jobs_col.find_one({"_id": ObjectId(job_id)})
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
                
            result = await self.jobs_col.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {
                    "status": "approved",
                    "approved_at": datetime.utcnow(),
                    "approved_by": self.admin_email,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Failed to approve job")
            
            await self._log_activity(f"Approved job: {job['title']} (ID: {job_id})")
            await self._notify_job_approval(job["creator_email"], job["title"])
            
            return {"success": True, "job_id": job_id}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error approving job: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to approve job")

    async def get_system_stats(self, time_range: str = "7d") -> Dict:
        """Get comprehensive system statistics for a time range"""
        try:
            time_delta = self._parse_time_range(time_range)
            cutoff_date = datetime.utcnow() - time_delta
            
            stats = {
                "users": {
                    "total": await self.users_col.count_documents({}),
                    "active": await self.users_col.count_documents({"is_active": True}),
                    "new": await self.users_col.count_documents({"created_at": {"$gte": cutoff_date}}),
                    "by_role": {
                        "candidate": await self.users_col.count_documents({"role": "candidate"}),
                        "recruiter": await self.users_col.count_documents({"role": "recruiter"}),
                        "admin": await self.users_col.count_documents({"role": "admin"}),
                    }
                },
                "jobs": {
                    "total": await self.jobs_col.count_documents({}),
                    "pending": await self.jobs_col.count_documents({"status": "pending"}),
                    "approved": await self.jobs_col.count_documents({"status": "approved"}),
                    "new": await self.jobs_col.count_documents({"created_at": {"$gte": cutoff_date}}),
                },
                "applications": {
                    "total": await self.applications_col.count_documents({}),
                    "new": await self.applications_col.count_documents({"created_at": {"$gte": cutoff_date}}),
                    "by_status": {
                        "applied": await self.applications_col.count_documents({"status": "applied"}),
                        "interviewed": await self.applications_col.count_documents({"status": "interviewed"}),
                        "hired": await self.applications_col.count_documents({"status": "hired"}),
                    }
                },
                "activity": await self._get_activity_stats(cutoff_date),
            }
            return stats
        except Exception as e:
            logger.error(f"Error fetching system stats: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch system statistics")

    async def _calculate_profile_completeness(self, user: Dict) -> float:
        """Calculate how complete a user's profile is"""
        required_fields = ["first_name", "last_name", "skills", "experience"]
        completed = sum(1 for field in required_fields if user.get(field))
        return (completed / len(required_fields)) * 100

    async def _get_activity_stats(self, cutoff_date: datetime) -> Dict:
        """Get activity statistics"""
        return {
            "total": await self.activity_col.count_documents({"timestamp": {"$gte": cutoff_date}}),
            "by_type": {
                "user": await self.activity_col.count_documents({
                    "timestamp": {"$gte": cutoff_date},
                    "action": {"$regex": "^User"}
                }),
                "job": await self.activity_col.count_documents({
                    "timestamp": {"$gte": cutoff_date},
                    "action": {"$regex": "^Job"}
                }),
                "application": await self.activity_col.count_documents({
                    "timestamp": {"$gte": cutoff_date},
                    "action": {"$regex": "^Application"}
                })
            }
        }

    async def _get_last_activity(self, email: str) -> Optional[str]:
        """Get last activity timestamp for a user"""
        try:
            activity = await self.activity_col.find_one(
                {"user_email": email},
                sort=[("timestamp", DESCENDING)]
            )
            return activity["timestamp"].strftime("%Y-%m-%d %H:%M") if activity else None
        except Exception as e:
            logger.error(f"Error fetching user activity: {str(e)}")
            return None

    async def _log_activity(self, action: str):
        """Log admin activity"""
        try:
            await self.activity_col.insert_one({
                "user_email": self.admin_email,
                "action": action,
                "timestamp": datetime.utcnow(),
                "type": "admin"
            })
        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}")

    async def _notify_user_deactivation(self, user_email: str):
        """Send notification about account deactivation"""
        subject = "Your account status has changed"
        body = f"Your account has been deactivated by the administrator."
        await self.email_service.send_email(user_email, subject, body)

    async def _notify_job_approval(self, recruiter_email: str, job_title: str):
        """Notify recruiter about job approval"""
        subject = f"Your job posting has been approved"
        body = f"Your job posting '{job_title}' has been approved and is now visible to candidates."
        await self.email_service.send_email(recruiter_email, subject, body)

    def _parse_time_range(self, time_range: str) -> timedelta:
        """Convert time range string to timedelta"""
        units = {
            "h": "hours",
            "d": "days",
            "w": "weeks",
            "m": "weeks"  # Approximate month as 4 weeks
        }
        
        try:
            value = int(time_range[:-1])
            unit = time_range[-1].lower()
            
            if unit not in units:
                raise ValueError("Invalid time unit")
                
            return timedelta(**{units[unit]: value})
        except (ValueError, IndexError):
            return timedelta(days=7)  # Default to 7 days

    async def _convert_user(self, user: Dict) -> Dict:
        """Convert user document to response format"""
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "role": user["role"],
            "is_active": user.get("is_active", True),
            "created_at": user["created_at"].strftime("%Y-%m-%d"),
            "last_login": user.get("last_login", ""),
        }

    async def _convert_job(self, job: Dict) -> Dict:
        """Convert job document to response format"""
        applications_count = await self.applications_col.count_documents({"job_id": str(job["_id"])})
        
        return {
            "id": str(job["_id"]),
            "title": job["title"],
            "department": job["department"],
            "location": job["location"],
            "status": job["status"],
            "creator_email": job["creator_email"],
            "created_at": job["created_at"].strftime("%Y-%m-%d"),
            "applications_count": applications_count,
        }