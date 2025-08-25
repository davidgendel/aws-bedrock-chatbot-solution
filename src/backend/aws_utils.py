"""
AWS utilities for the chatbot backend with request signing support.
"""
import logging
import os
import threading
from typing import Any, Optional

try:
    from .aws_client_factory import AWSClientFactory
except ImportError:
    from aws_client_factory import AWSClientFactory

# Initialize logger
logger = logging.getLogger(__name__)

# Thread-local storage for AWS clients
_thread_local = threading.local()


def get_aws_region() -> str:
    """
    Get AWS region from environment or config.
    
    Returns:
        AWS region string
    """
    # Try environment variables first
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("CDK_DEPLOY_REGION")
    )
    
    # If no environment variable, try to load from config
    if not region:
        try:
            import json
            from pathlib import Path
            
            # Look for config.json in the project root
            config_paths = [
                Path(__file__).parent.parent.parent / "config.json",
                Path.cwd() / "config.json",
                Path("/tmp/config.json")  # For Lambda environments
            ]
            
            for config_path in config_paths:
                if config_path.exists():
                    with open(config_path, "r") as f:
                        config = json.load(f)
                        region = config.get("region")
                        if region:
                            break
        except Exception as e:
            logger.debug(f"Could not load region from config: {e}")
    
    # Final fallback - but log a warning
    if not region:
        region = "us-east-1"
        logger.warning("No region specified in environment or config, defaulting to us-east-1. "
                      "Set AWS_REGION environment variable or region in config.json for other regions.")
    
    return region


def get_aws_client(service_name: str, region: Optional[str] = None, enable_signing: bool = True) -> Any:
    """
    Get an AWS client with optional request signing.
    
    Args:
        service_name: AWS service name
        region: AWS region (optional)
        enable_signing: Whether to enable request signing
        
    Returns:
        AWS client
    """
    try:
        return AWSClientFactory.create_client(
            service_name=service_name,
            region_name=region or get_aws_region(),
            enable_signing=enable_signing
        )
    except Exception as e:
        logger.error(f"Failed to create AWS client for {service_name}: {e}")
        raise


def get_aws_resource(service_name: str, region: Optional[str] = None, enable_signing: bool = True) -> Any:
    """
    Get an AWS resource with optional request signing.
    
    Args:
        service_name: AWS service name
        region: AWS region (optional)
        enable_signing: Whether to enable request signing
        
    Returns:
        AWS resource
    """
    try:
        return AWSClientFactory.create_resource(
            service_name=service_name,
            region_name=region or get_aws_region(),
            enable_signing=enable_signing
        )
    except Exception as e:
        logger.error(f"Failed to create AWS resource for {service_name}: {e}")
        raise


# Specific client getters for commonly used services with signing support
def get_bedrock_client(enable_signing: bool = True) -> Any:
    """
    Get a Bedrock client with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        Bedrock client
    """
    return get_aws_client("bedrock-runtime", enable_signing=enable_signing)


def get_s3_client(enable_signing: bool = True) -> Any:
    """
    Get an S3 client with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        S3 client
    """
    return get_aws_client("s3", enable_signing=enable_signing)


def get_s3_resource(enable_signing: bool = True) -> Any:
    """
    Get an S3 resource with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        S3 resource
    """
    return get_aws_resource("s3", enable_signing=enable_signing)


def get_dynamodb_client(enable_signing: bool = True) -> Any:
    """
    Get a DynamoDB client with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        DynamoDB client
    """
    return get_aws_client("dynamodb", enable_signing=enable_signing)


def get_dynamodb_resource(enable_signing: bool = True) -> Any:
    """
    Get a DynamoDB resource with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        DynamoDB resource
    """
    return get_aws_resource("dynamodb", enable_signing=enable_signing)


def get_secrets_manager_client(enable_signing: bool = True) -> Any:
    """
    Get a Secrets Manager client with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        Secrets Manager client
    """
    return get_aws_client("secretsmanager", enable_signing=enable_signing)


def get_textract_client(enable_signing: bool = True) -> Any:
    """
    Get a Textract client with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        Textract client
    """
    return get_aws_client("textract", enable_signing=enable_signing)


def get_cloudwatch_client(enable_signing: bool = True) -> Any:
    """
    Get a CloudWatch client with optional signing.
    
    Args:
        enable_signing: Whether to enable request signing
        
    Returns:
        CloudWatch client
    """
    return get_aws_client("logs", enable_signing=enable_signing)


# Configuration and management functions
def configure_request_signing(enabled: bool, **config_updates):
    """
    Configure request signing at runtime.
    
    Args:
        enabled: Whether to enable request signing
        **config_updates: Additional configuration updates
    """
    AWSClientFactory.configure_signing(enabled, **config_updates)
    logger.info(f"Request signing {'enabled' if enabled else 'disabled'}")


def clear_client_cache():
    """Clear the AWS client cache."""
    AWSClientFactory.clear_cache()
    logger.info("AWS client cache cleared")


def get_client_cache_stats():
    """Get AWS client cache statistics."""
    return AWSClientFactory.get_cache_stats()
