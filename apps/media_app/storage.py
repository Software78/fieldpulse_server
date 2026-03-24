"""
MinIO S3 storage backend for media uploads.
"""
import os
import uuid
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class MinIOStorage:
    """
    MinIO S3 storage backend for handling file uploads.
    """
    
    def __init__(self):
        self.access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.endpoint_url = os.getenv('AWS_S3_ENDPOINT_URL')
        self.bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
        
        if not all([self.access_key, self.secret_key, self.endpoint_url, self.bucket_name]):
            raise ValueError("Missing required MinIO configuration. Check environment variables.")
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='us-east-1'  # MinIO doesn't care about region
        )
        
        # Ensure bucket exists on startup
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self) -> None:
        """
        Ensure the S3 bucket exists, create it if it doesn't.
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created bucket '{self.bucket_name}'")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    raise
            else:
                logger.error(f"Error checking bucket: {e}")
                raise
    
    def upload_file(self, file_obj, key: str, content_type: Optional[str] = None) -> str:
        """
        Upload a file to MinIO and return the public URL.
        
        Args:
            file_obj: File-like object to upload
            key: S3 key (path) for the file
            content_type: MIME type of the file
            
        Returns:
            Public URL of the uploaded file
            
        Raises:
            ClientError: If upload fails
            NoCredentialsError: If credentials are missing
        """
        try:
            # Reset file pointer to beginning
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            # Upload file with public read ACL
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs={
                    **extra_args,
                    'ACL': 'public-read'
                }
            )
            
            # Construct public URL
            public_url = f"{self.endpoint_url}/{self.bucket_name}/{key}"
            logger.info(f"Successfully uploaded file to {key}")
            return public_url
            
        except ClientError as e:
            logger.error(f"Failed to upload file {key}: {e}")
            raise
        except NoCredentialsError as e:
            logger.error(f"Missing AWS credentials: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading file {key}: {e}")
            raise
    
    def delete_file(self, key: str) -> bool:
        """
        Delete a file from MinIO.
        
        Args:
            key: S3 key (path) of the file to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully deleted file {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file {key}: {e}")
            return False
    
    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in MinIO.
        
        Args:
            key: S3 key (path) of the file to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking if file exists {key}: {e}")
            return False
    
    def get_file(self, key: str):
        """
        Retrieve a file from MinIO.
        
        Args:
            key: S3 key (path) of the file to retrieve
            
        Returns:
            File-like object containing the file data
            
        Raises:
            ClientError: If file retrieval fails
            NoCredentialsError: If credentials are missing
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body']
        except ClientError as e:
            logger.error(f"Failed to retrieve file {key}: {e}")
            raise
        except NoCredentialsError as e:
            logger.error(f"Missing AWS credentials: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving file {key}: {e}")
            raise


# Global storage instance
storage = MinIOStorage()
