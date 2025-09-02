"""
Simple AWS utilities using direct boto3 clients.
"""
import os
import boto3
from botocore.config import Config


def get_aws_region() -> str:
    """Get AWS region from environment."""
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("REGION") 
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def get_boto3_config() -> Config:
    """Get standard boto3 configuration with SigV4 signing."""
    return Config(
        retries={'max_attempts': 3, 'mode': 'adaptive'},
        max_pool_connections=50,
        signature_version='v4'  # Explicit SigV4 for all supported services
    )



