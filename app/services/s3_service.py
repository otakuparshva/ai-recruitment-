"""
Enhanced S3 Service with Bucket Validation and Improved Error Handling
"""

import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    EndpointConnectionError
)
from app.utils.config import settings
import logging
import uuid
import os
from typing import Tuple, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        """
        Initialize S3 client with connection validation
        """
        self._initialize_client()
        self._validate_bucket()

    def _initialize_client(self):
        """Initialize S3 client with retry logic"""
        try:
            self.s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
                config=boto3.session.Config(
                    connect_timeout=5,
                    read_timeout=30,
                    retries={'max_attempts': 3}
                )
            )
            # Verify credentials work
            self.s3.list_buckets()
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"S3 client initialization failed: {str(e)}")
            raise

    def _validate_bucket(self):
        """Validate bucket exists and is accessible"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.s3.head_bucket(Bucket=settings.S3_BUCKET_NAME)
                self.bucket = settings.S3_BUCKET_NAME
                logger.info(f"Successfully connected to S3 bucket: {self.bucket}")
                return
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == '404':
                    logger.error(f"S3 bucket not found: {settings.S3_BUCKET_NAME}")
                    raise ValueError(f"S3 bucket {settings.S3_BUCKET_NAME} does not exist")
                elif error_code == '403':
                    logger.error(f"Access denied to S3 bucket: {settings.S3_BUCKET_NAME}")
                    raise PermissionError(f"No access to S3 bucket {settings.S3_BUCKET_NAME}")
                else:
                    logger.warning(f"S3 bucket validation attempt {attempt + 1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        raise
            except Exception as e:
                logger.warning(f"S3 bucket validation attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Failed to validate S3 bucket after {max_retries} attempts")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ClientError, EndpointConnectionError)),
        reraise=True
    )
    def upload_resume(self, file_path: str, user_email: str) -> Tuple[bool, Optional[str]]:
        """
        Upload resume to S3 with validation
        
        Args:
            file_path: Path to the file to upload
            user_email: User email for folder structure
            
        Returns:
            Tuple of (success: bool, s3_key: Optional[str])
        """
        try:
            # Validate file exists and is readable
            if not os.path.isfile(file_path):
                logger.error(f"File not found: {file_path}")
                return False, None
                
            if not os.access(file_path, os.R_OK):
                logger.error(f"File not readable: {file_path}")
                return False, None

            # Generate unique filename
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in settings.ALLOWED_FILE_TYPES:
                logger.error(f"Invalid file extension: {ext}")
                return False, None
                
            filename = f"resumes/{user_email}/{uuid.uuid4()}{ext}"
            
            # Upload file with metadata
            self.s3.upload_file(
                file_path,
                self.bucket,
                filename,
                ExtraArgs={
                    'ContentType': self._get_content_type(ext),
                    'Metadata': {
                        'uploaded-by': user_email,
                        'original-filename': os.path.basename(file_path)
                    }
                }
            )
            
            # Verify upload succeeded
            self.s3.head_object(Bucket=self.bucket, Key=filename)
            
            return True, filename
            
        except ClientError as e:
            logger.error(f"S3 upload error: {str(e)}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected upload error: {str(e)}")
            return False, str(e)

    def _get_content_type(self, ext: str) -> str:
        """Map file extension to content type"""
        return {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg'
        }.get(ext, 'application/octet-stream')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ClientError, EndpointConnectionError)),
        reraise=True
    )
    def get_resume_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for resume download
        
        Args:
            s3_key: S3 object key
            expires_in: URL expiration in seconds
            
        Returns:
            Presigned URL or None if failed
        """
        try:
            # Validate object exists first
            self.s3.head_object(Bucket=self.bucket, Key=s3_key)
            
            return self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': s3_key,
                    'ResponseContentType': 'application/octet-stream'
                },
                ExpiresIn=expires_in
            )
        except ClientError as e:
            logger.error(f"S3 URL generation error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected URL generation error: {str(e)}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ClientError, EndpointConnectionError)),
        reraise=True
    )
    def delete_resume(self, s3_key: str) -> bool:
        """
        Delete resume from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected delete error: {str(e)}")
            return False