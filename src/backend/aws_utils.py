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


def get_aws_client(service_name: str, region: str = None, **kwargs):
    """Get AWS client with standard boto3."""
    return boto3.client(
        service_name,
        region_name=region or get_aws_region(),
        config=get_boto3_config(),
        **kwargs
    )


def get_bedrock_client():
    """Get Bedrock runtime client with SigV4 signing."""
    return boto3.client(
        'bedrock-runtime', 
        region_name=get_aws_region(),
        config=get_boto3_config()
    )


def get_s3_client():
    """Get S3 client with SigV4 signing.""" 
    return boto3.client(
        's3', 
        region_name=get_aws_region(),
        config=get_boto3_config()
    )


def get_dynamodb_client():
    """Get DynamoDB client with SigV4 signing."""
    return boto3.client(
        'dynamodb', 
        region_name=get_aws_region(),
        config=get_boto3_config()
    )


def get_secretsmanager_client():
    """Get Secrets Manager client with SigV4 signing."""
    return boto3.client(
        'secretsmanager', 
        region_name=get_aws_region(),
        config=get_boto3_config()
    )


def get_textract_client():
    """Get Textract client with SigV4 signing."""
    return boto3.client(
        'textract', 
        region_name=get_aws_region(),
        config=get_boto3_config()
    )


def get_logs_client():
    """Get CloudWatch Logs client with SigV4 signing."""
    return boto3.client(
        'logs', 
        region_name=get_aws_region(),
        config=get_boto3_config()
    )


def get_cloudwatch_client():
    """Get CloudWatch client with SigV4 signing."""
    return boto3.client(
        'cloudwatch', 
        region_name=get_aws_region(),
        config=get_boto3_config()
    )
