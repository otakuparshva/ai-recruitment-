import re
from app.database.mongo import mongo
from app.database.models import User
from datetime import datetime
import bcrypt
import logging
from typing import Tuple, Optional
from fastapi import HTTPException
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.password_min_length = 8
        self.max_login_attempts = 5
        self.login_attempts = {}

    async def register(
        self, 
        email: str, 
        password: str, 
        role: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Register a new user with email, password and role.
        
        Args:
            email: User's email address
            password: User's plain text password
            role: User's role (e.g., 'admin', 'user', 'recruiter', 'candidate')
            first_name: Optional first name
            last_name: Optional last name
            
        Returns:
            Tuple of (success: bool, message: str)
            
        Raises:
            HTTPException: If registration fails due to validation or database error
        """
        # Validate inputs
        if not self._validate_email(email):
            raise HTTPException(
                status_code=400,
                detail="Invalid email format"
            )
            
        if not self._validate_password(password):
            raise HTTPException(
                status_code=400,
                detail=f"Password must be at least {self.password_min_length} characters"
            )
            
        if role not in ['admin', 'recruiter', 'candidate']:
            raise HTTPException(
                status_code=400,
                detail="Invalid user role"
            )

        # Check if user exists
        existing_user = await mongo.db.users.find_one({"email": email})
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        try:
            # Hash password
            hashed_pw = self._hash_password(password)
            
            # Create user
            user = User(
                email=email,
                password_hash=hashed_pw,
                role=role,
                first_name=first_name,
                last_name=last_name,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True,
                login_attempts=0
            )
            
            # Insert into database
            result = await mongo.db.users.insert_one(user.dict(by_alias=True))
            
            if not result.inserted_id:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create user"
                )
                
            return True, "Registration successful"
            
        except PyMongoError as e:
            logger.error(f"Database error during registration: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Database operation failed"
            )
        except Exception as e:
            logger.error(f"Unexpected error during registration: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Registration failed"
            )

    async def login(self, email: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email address
            password: User's plain text password
            
        Returns:
            Tuple of (success: bool, role: Optional[str])
            Returns (False, None) if authentication fails
            
        Raises:
            HTTPException: If account is locked or other errors occur
        """
        try:
            # Check login attempts
            if self._is_account_locked(email):
                raise HTTPException(
                    status_code=403,
                    detail="Account temporarily locked due to too many failed attempts"
                )
                
            # Find user
            user_data = await mongo.db.users.find_one({"email": email})
            if not user_data:
                self._record_failed_attempt(email)
                return False, None
                
            user = User(**user_data)
            
            # Check if account is active
            if not user.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="Account is inactive"
                )
                
            # Verify password
            if not self._verify_password(password, user.password_hash):
                await self._increment_login_attempts(email)
                return False, None
                
            # Reset login attempts on successful login
            await self._reset_login_attempts(email)
            return True, user.role
            
        except PyMongoError as e:
            logger.error(f"Database error during login: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Authentication service unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Login failed"
            )

    async def change_password(
        self,
        email: str,
        old_password: str,
        new_password: str
    ) -> Tuple[bool, str]:
        """
        Change user's password after verifying old password.
        
        Args:
            email: User's email address
            old_password: Current password for verification
            new_password: New password to set
            
        Returns:
            Tuple of (success: bool, message: str)
            
        Raises:
            HTTPException: If password change fails validation or database error
        """
        try:
            # Validate new password
            if not self._validate_password(new_password):
                raise HTTPException(
                    status_code=400,
                    detail=f"New password must be at least {self.password_min_length} characters"
                )
                
            # Verify old credentials
            auth_success, _ = await self.login(email, old_password)
            if not auth_success:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid credentials"
                )
                
            # Hash new password
            new_hashed_pw = self._hash_password(new_password)
            
            # Update password in database
            result = await mongo.db.users.update_one(
                {"email": email},
                {"$set": {
                    "password_hash": new_hashed_pw,
                    "updated_at": datetime.utcnow(),
                    "login_attempts": 0  # Reset login attempts on password change
                }}
            )
            
            if result.modified_count != 1:
                raise HTTPException(
                    status_code=500,
                    detail="Password update failed"
                )
                
            return True, "Password changed successfully"
            
        except PyMongoError as e:
            logger.error(f"Database error during password change: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Password change failed"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during password change: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Password change failed"
            )

    async def reset_password(self, email: str, new_password: str) -> Tuple[bool, str]:
        """
        Admin password reset without requiring old password.
        
        Args:
            email: User's email address
            new_password: New password to set
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if not self._validate_password(new_password):
                raise HTTPException(
                    status_code=400,
                    detail=f"New password must be at least {self.password_min_length} characters"
                )
                
            # Hash new password
            new_hashed_pw = self._hash_password(new_password)
            
            # Update password in database
            result = await mongo.db.users.update_one(
                {"email": email},
                {"$set": {
                    "password_hash": new_hashed_pw,
                    "updated_at": datetime.utcnow(),
                    "login_attempts": 0
                }}
            )
            
            if result.modified_count != 1:
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )
                
            return True, "Password reset successfully"
            
        except PyMongoError as e:
            logger.error(f"Database error during password reset: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Password reset failed"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during password reset: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Password reset failed"
            )

    async def deactivate_user(self, email: str) -> bool:
        """
        Deactivate a user account.
        
        Args:
            email: User's email address
            
        Returns:
            bool: True if deactivation was successful
        """
        try:
            result = await mongo.db.users.update_one(
                {"email": email},
                {"$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }}
            )
            return result.modified_count == 1
        except PyMongoError as e:
            logger.error(f"Database error during deactivation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Account deactivation failed"
            )

    def _hash_password(self, password: str) -> str:
        """Hash a password for storage."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify_password(self, password: str, hashed_pw: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode(), hashed_pw.encode())

    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

    def _validate_password(self, password: str) -> bool:
        """Validate password meets requirements."""
        return len(password) >= self.password_min_length

    async def _increment_login_attempts(self, email: str):
        """Record a failed login attempt."""
        try:
            await mongo.db.users.update_one(
                {"email": email},
                {"$inc": {"login_attempts": 1}},
                upsert=False
            )
            
            # Update in-memory cache
            if email not in self.login_attempts:
                self.login_attempts[email] = 0
            self.login_attempts[email] += 1
            
        except PyMongoError as e:
            logger.error(f"Failed to record login attempt: {str(e)}")

    async def _reset_login_attempts(self, email: str):
        """Reset login attempts after successful login."""
        try:
            await mongo.db.users.update_one(
                {"email": email},
                {"$set": {"login_attempts": 0}}
            )
            
            # Clear from in-memory cache
            if email in self.login_attempts:
                del self.login_attempts[email]
                
        except PyMongoError as e:
            logger.error(f"Failed to reset login attempts: {str(e)}")

    def _is_account_locked(self, email: str) -> bool:
        """Check if account is locked due to too many failed attempts."""
        # First check in-memory cache
        if email in self.login_attempts and self.login_attempts[email] >= self.max_login_attempts:
            return True
            
        # Fallback to database check
        user_data = mongo.db.users.find_one({"email": email})
        if user_data and user_data.get("login_attempts", 0) >= self.max_login_attempts:
            return True
            
        return False

    def _record_failed_attempt(self, email: str):
        """Record failed attempt in memory cache."""
        if email not in self.login_attempts:
            self.login_attempts[email] = 0
        self.login_attempts[email] += 1