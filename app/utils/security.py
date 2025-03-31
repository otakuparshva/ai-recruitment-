import os
import re
import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Union, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from app.utils.config import settings

logger = logging.getLogger(__name__)

# Security configurations
class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: list[str] = []

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt", "argon2"],
    deprecated="auto",
    bcrypt__rounds=12,
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
    argon2__hash_len=32,
    argon2__salt_len=16
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/token",
    scopes={
        "user": "Regular user access",
        "admin": "Admin privileges",
        "read": "Read-only access"
    }
)

class SecurityUtils:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash
        
        Args:
            plain_password: The password to verify
            hashed_password: The stored hash to compare against
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Generate a secure password hash
        
        Args:
            password: The password to hash
            
        Returns:
            str: The hashed password
        """
        return pwd_context.hash(password)

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate a cryptographically secure random token
        
        Args:
            length: Length of the token to generate
            
        Returns:
            str: Generated token
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
        secret_key: str = settings.SECRET_KEY,
        algorithm: str = settings.JWT_ALGORITHM
    ) -> str:
        """
        Create a JWT access token
        
        Args:
            data: Data to encode in the token
            expires_delta: Optional expiration time delta
            secret_key: Secret key for signing
            algorithm: Algorithm to use for signing
            
        Returns:
            str: Encoded JWT token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, secret_key, algorithm=algorithm)

    @staticmethod
    def verify_access_token(
        token: str,
        secret_key: str = settings.SECRET_KEY,
        algorithm: str = settings.JWT_ALGORITHM
    ) -> Dict[str, Any]:
        """
        Verify and decode a JWT token
        
        Args:
            token: The JWT token to verify
            secret_key: Secret key for verification
            algorithm: Algorithm to use for verification
            
        Returns:
            Dict: Decoded token payload
            
        Raises:
            HTTPException: If token is invalid
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {str(e)}")
            raise credentials_exception

    @staticmethod
    def get_current_user(
        token: str = Depends(oauth2_scheme),
        secret_key: str = settings.SECRET_KEY,
        algorithm: str = settings.JWT_ALGORITHM
    ) -> Dict[str, Any]:
        """
        Dependency to get current user from JWT token
        
        Args:
            token: The JWT token
            secret_key: Secret key for verification
            algorithm: Algorithm to use for verification
            
        Returns:
            Dict: Decoded token payload
            
        Raises:
            HTTPException: If token is invalid
        """
        return SecurityUtils.verify_access_token(token, secret_key, algorithm)

    @staticmethod
    def generate_csrf_token() -> str:
        """
        Generate a CSRF token
        
        Returns:
            str: Generated CSRF token
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_csrf_token(token: str, expected_token: str) -> bool:
        """
        Validate a CSRF token
        
        Args:
            token: Token to validate
            expected_token: Expected token value
            
        Returns:
            bool: True if tokens match, False otherwise
        """
        return secrets.compare_digest(token, expected_token)

    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """
        Generate a one-time password (OTP)
        
        Args:
            length: Length of the OTP
            
        Returns:
            str: Generated OTP
        """
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    @staticmethod
    def encrypt_data(data: str, key: Optional[str] = None) -> str:
        """
        Encrypt sensitive data (uses Fernet symmetric encryption)
        
        Args:
            data: Data to encrypt
            key: Optional encryption key (defaults to settings.SECRET_KEY)
            
        Returns:
            str: Encrypted data
        """
        from cryptography.fernet import Fernet, InvalidToken
        try:
            fernet_key = key or settings.SECRET_KEY
            # Ensure the key is 32 url-safe base64-encoded bytes
            if len(fernet_key) != 32:
                fernet_key = fernet_key[:32].ljust(32, '0')
            cipher_suite = Fernet(fernet_key.encode())
            return cipher_suite.encrypt(data.encode()).decode()
        except InvalidToken as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Data encryption failed"
            )

    @staticmethod
    def decrypt_data(encrypted_data: str, key: Optional[str] = None) -> str:
        """
        Decrypt sensitive data
        
        Args:
            encrypted_data: Data to decrypt
            key: Optional decryption key (defaults to settings.SECRET_KEY)
            
        Returns:
            str: Decrypted data
            
        Raises:
            HTTPException: If decryption fails
        """
        from cryptography.fernet import Fernet, InvalidToken
        try:
            fernet_key = key or settings.SECRET_KEY
            if len(fernet_key) != 32:
                fernet_key = fernet_key[:32].ljust(32, '0')
            cipher_suite = Fernet(fernet_key.encode())
            return cipher_suite.decrypt(encrypted_data.encode()).decode()
        except InvalidToken as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or corrupted encrypted data"
            )

    @staticmethod
    def generate_api_key() -> str:
        """
        Generate a secure API key
        
        Returns:
            str: Generated API key
        """
        return secrets.token_urlsafe(64)

    @staticmethod
    def sanitize_input(input_data: Union[str, Dict, List]) -> Union[str, Dict, List]:
        """
        Sanitize user input to prevent XSS and injection attacks
        
        Args:
            input_data: Data to sanitize
            
        Returns:
            Sanitized data
        """
        if isinstance(input_data, str):
            # Remove script tags and dangerous attributes
            input_data = re.sub(r'<script.*?>.*?</script>', '', input_data, flags=re.IGNORECASE)
            input_data = re.sub(r'on\w+=".*?"', '', input_data)
            return input_data.strip()
        elif isinstance(input_data, dict):
            return {k: SecurityUtils.sanitize_input(v) for k, v in input_data.items()}
        elif isinstance(input_data, list):
            return [SecurityUtils.sanitize_input(item) for item in input_data]
        return input_data

    @staticmethod
    def check_password_strength(password: str) -> Dict[str, Any]:
        """
        Check password strength and return analysis
        
        Args:
            password: Password to analyze
            
        Returns:
            Dict: Password strength analysis
        """
        analysis = {
            "length": len(password),
            "has_upper": any(c.isupper() for c in password),
            "has_lower": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_special": any(not c.isalnum() for c in password),
            "is_common": password.lower() in SecurityUtils._load_common_passwords(),
            "entropy": SecurityUtils._calculate_entropy(password)
        }
        
        # Calculate strength score (0-100)
        score = 0
        if analysis["length"] >= 8: score += 20
        if analysis["length"] >= 12: score += 20
        if analysis["has_upper"]: score += 15
        if analysis["has_lower"]: score += 15
        if analysis["has_digit"]: score += 15
        if analysis["has_special"]: score += 15
        if not analysis["is_common"]: score += 20
        if analysis["entropy"] > 3.5: score += 20
        
        analysis["score"] = min(max(score, 0), 100)
        analysis["strength"] = (
            "very weak" if score < 40 else
            "weak" if score < 60 else
            "moderate" if score < 80 else
            "strong" if score < 90 else
            "very strong"
        )
        
        return analysis

    @staticmethod
    def _load_common_passwords() -> List[str]:
        """Load list of common passwords for checking"""
        try:
            with open("data/common_passwords.txt", "r") as f:
                return [line.strip().lower() for line in f if line.strip()]
        except FileNotFoundError:
            return [
                "password", "123456", "qwerty", "letmein", 
                "admin", "welcome", "monkey", "sunshine"
            ]

    @staticmethod
    def _calculate_entropy(password: str) -> float:
        """Calculate password entropy"""
        import math
        from collections import Counter
        
        if not password:
            return 0.0
            
        freq = Counter(password)
        prob = [float(v) / len(password) for v in freq.values()]
        return -sum(p * math.log(p, 2) for p in prob)

    @staticmethod
    def generate_secure_filename(original_filename: str) -> str:
        """
        Generate a secure filename by removing dangerous characters
        
        Args:
            original_filename: Original filename
            
        Returns:
            str: Sanitized filename
        """
        # Keep only alphanumeric, dots, underscores and hyphens
        filename = re.sub(r'[^\w.-]', '', original_filename)
        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')
        # Add random suffix to prevent guessing
        suffix = secrets.token_hex(4)
        return f"{filename}_{suffix}"

    @staticmethod
    def generate_secure_cookie(
        name: str,
        value: str,
        max_age: Optional[int] = None,
        path: str = "/",
        domain: Optional[str] = None,
        secure: bool = True,
        httponly: bool = True,
        samesite: str = "Lax"
    ) -> Dict[str, str]:
        """
        Generate secure cookie headers
        
        Args:
            name: Cookie name
            value: Cookie value
            max_age: Max age in seconds
            path: Cookie path
            domain: Cookie domain
            secure: Secure flag
            httponly: HTTP Only flag
            samesite: SameSite policy
            
        Returns:
            Dict: Cookie headers
        """
        cookie = [
            f"{name}={value}",
            f"Path={path}",
            f"SameSite={samesite}",
        ]
        
        if max_age:
            cookie.append(f"Max-Age={max_age}")
        if domain:
            cookie.append(f"Domain={domain}")
        if secure:
            cookie.append("Secure")
        if httponly:
            cookie.append("HttpOnly")
            
        return {"Set-Cookie": "; ".join(cookie)}
