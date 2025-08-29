#!/usr/bin/env python3
"""AWS configuration utilities for consistent region and client handling."""

import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

def get_aws_region() -> str:
    """Get AWS region with consistent fallback logic."""
    return (
        os.environ.get('AWS_DEFAULT_REGION') or 
        os.environ.get('AWS_REGION') or 
        'us-east-1'
    )

def create_s3_client():
    """Create S3 client with proper region and error handling."""
    try:
        return boto3.client('s3', region_name=get_aws_region())
    except NoCredentialsError:
        raise RuntimeError("AWS credentials not configured")

def create_s3vectors_client():
    """Create S3 Vectors client with proper region and error handling."""
    try:
        return boto3.client('s3vectors', region_name=get_aws_region())
    except NoCredentialsError:
        raise RuntimeError("AWS credentials not configured")
    except Exception as e:
        if "Unknown service" in str(e):
            raise RuntimeError("S3 Vectors service not available in this region")
        raise

def create_cloudformation_client():
    """Create CloudFormation client with proper region and error handling."""
    try:
        return boto3.client('cloudformation', region_name=get_aws_region())
    except NoCredentialsError:
        raise RuntimeError("AWS credentials not configured")
