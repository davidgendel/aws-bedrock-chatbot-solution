"""
Simple AWS client factory using direct boto3 clients.
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
        region_name=get_aws_region(),
        signature_version='v4'  # Explicit SigV4 for all supported services
    )


def get_aws_client(service_name: str, region: str = None):
    """Get AWS client with standard boto3."""
    return boto3.client(
        service_name,
        region_name=region or get_aws_region(),
        config=get_boto3_config()
    )
