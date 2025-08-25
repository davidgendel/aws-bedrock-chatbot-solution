"""
Centralized AWS client factory with request signing support.
"""
import logging
import threading
from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

# Thread-local storage for clients and signing context
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
            # Look for config.json in the project root
            config_paths = [
                Path(__file__).parent.parent / "config.json",
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


class AWSClientFactory:
    """
    Centralized factory for creating AWS clients with optional request signing.
    
    Features:
    - Request signing with SigV4
    - Client caching and reuse
    - Configuration-driven signing
    - Comprehensive error handling
    - Performance monitoring
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for factory instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the factory."""
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._config = self._load_configuration()
        
        # Import signing components here to avoid circular imports
        try:
            from .request_signer import RequestSigner, SigningConfig
            self._signing_config = SigningConfig(self._config.get('aws', {}).get('requestSigning', {}))
            self._request_signer = RequestSigner(self._signing_config) if self._signing_config.enabled else None
        except ImportError:
            try:
                from request_signer import RequestSigner, SigningConfig
                self._signing_config = SigningConfig(self._config.get('aws', {}).get('requestSigning', {}))
                self._request_signer = RequestSigner(self._signing_config) if self._signing_config.enabled else None
            except ImportError:
                logger.warning("Request signing modules not available, signing disabled")
                self._signing_config = None
                self._request_signer = None
        
        # Import error handling
        try:
            from .error_handler import ChatbotError, ErrorType
            self._ChatbotError = ChatbotError
            self._ErrorType = ErrorType
        except ImportError:
            try:
                from error_handler import ChatbotError, ErrorType
                self._ChatbotError = ChatbotError
                self._ErrorType = ErrorType
            except ImportError:
                logger.warning("Error handling modules not available")
                self._ChatbotError = Exception
                self._ErrorType = None
        
        self._client_cache = {}
        self._cache_lock = threading.RLock()
        self._initialized = True
        
        signing_status = 'enabled' if (self._signing_config and self._signing_config.enabled) else 'disabled'
        logger.info(f"AWS Client Factory initialized with signing {signing_status}")
    
    def _load_configuration(self) -> Dict[str, Any]:
        """Load configuration from config.json."""
        config_paths = [
            Path(__file__).parent.parent / "config.json",
            Path.cwd() / "config.json",
            Path("/tmp/config.json")  # For Lambda environments
        ]
        
        for config_path in config_paths:
            try:
                if config_path.exists():
                    with open(config_path, "r") as f:
                        config = json.load(f)
                        logger.debug(f"Loaded configuration from {config_path}")
                        return config
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        # Return default configuration
        logger.info("Using default configuration")
        return {
            "aws": {
                "requestSigning": {
                    "enabled": True,
                    "signatureVersion": "v4",
                    "includeHeaders": ["host", "x-amz-date", "authorization"],
                    "excludeServices": [],
                    "cacheTTL": 300
                }
            }
        }
    
    def _get_cache_key(self, service_name: str, region: str, enable_signing: bool, **kwargs) -> str:
        """Generate cache key for client."""
        key_parts = [service_name, region, str(enable_signing)]
        
        # Add relevant kwargs to cache key
        for key, value in sorted(kwargs.items()):
            if key in ['config', 'use_ssl', 'verify']:
                key_parts.append(f"{key}:{value}")
        
        return "|".join(key_parts)
    
    def _create_boto3_config(self, enable_signing: bool, **kwargs) -> Config:
        """Create boto3 Config object with signing configuration."""
        config_params = {
            'region_name': kwargs.get('region_name', get_aws_region()),
            'retries': {
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            'max_pool_connections': 50,
            'user_agent_extra': 'chatbot-rag/1.0'
        }
        
        # Add signing configuration if enabled
        if enable_signing and self._signing_config and self._signing_config.enabled:
            config_params['signature_version'] = self._signing_config.signature_version
        
        # Merge with any provided config
        if 'config' in kwargs and isinstance(kwargs['config'], dict):
            config_params.update(kwargs['config'])
        
        return Config(**config_params)
    
    @classmethod
    def create_client(
        cls,
        service_name: str,
        region_name: Optional[str] = None,
        enable_signing: bool = True,
        use_cache: bool = True,
        **kwargs
    ) -> Any:
        """
        Create AWS client with optional request signing.
        
        Args:
            service_name: AWS service name (e.g., 's3', 'bedrock-runtime')
            region_name: AWS region (defaults to configured region)
            enable_signing: Whether to enable request signing
            use_cache: Whether to use cached clients
            **kwargs: Additional arguments passed to boto3.client()
            
        Returns:
            AWS client instance
            
        Raises:
            Exception: If client creation fails
        """
        factory = cls()
        
        try:
            region = region_name or get_aws_region()
            
            # Check if signing should be disabled for this service
            if factory._signing_config and service_name in factory._signing_config.exclude_services:
                enable_signing = False
            
            # Generate cache key
            cache_key = factory._get_cache_key(service_name, region, enable_signing, **kwargs)
            
            # Return cached client if available and caching is enabled
            if use_cache:
                with factory._cache_lock:
                    if cache_key in factory._client_cache:
                        cached_client = factory._client_cache[cache_key]
                        logger.debug(f"Returning cached client for {service_name}")
                        return cached_client
            
            # Create new client
            logger.debug(f"Creating new {'signed' if enable_signing else 'unsigned'} client for {service_name} in {region}")
            
            # Prepare client arguments
            client_kwargs = {
                'service_name': service_name,
                'region_name': region,
                'config': factory._create_boto3_config(enable_signing, **kwargs)
            }
            
            # Add any additional kwargs (excluding our custom ones)
            excluded_keys = {'enable_signing', 'use_cache', 'config'}
            for key, value in kwargs.items():
                if key not in excluded_keys:
                    client_kwargs[key] = value
            
            # Create the client
            client = boto3.client(**client_kwargs)
            
            # Add signing event handler if enabled
            if enable_signing and factory._request_signer:
                factory._request_signer.attach_to_client(client)
            
            # Cache the client
            if use_cache:
                with factory._cache_lock:
                    factory._client_cache[cache_key] = client
            
            logger.info(f"Created {'signed' if enable_signing else 'unsigned'} client for {service_name}")
            return client
            
        except NoCredentialsError as e:
            error_msg = f"AWS credentials not found for {service_name} client"
            logger.error(error_msg)
            if factory._ChatbotError and factory._ErrorType:
                raise factory._ChatbotError(error_msg, factory._ErrorType.AUTHENTICATION_ERROR, e)
            else:
                raise Exception(error_msg) from e
        
        except ClientError as e:
            error_msg = f"Failed to create {service_name} client: {e}"
            logger.error(error_msg)
            if factory._ChatbotError and factory._ErrorType:
                raise factory._ChatbotError(error_msg, factory._ErrorType.EXTERNAL_SERVICE_ERROR, e)
            else:
                raise Exception(error_msg) from e
        
        except Exception as e:
            error_msg = f"Unexpected error creating {service_name} client: {e}"
            logger.error(error_msg)
            if factory._ChatbotError and factory._ErrorType:
                raise factory._ChatbotError(error_msg, factory._ErrorType.INTERNAL_SERVER_ERROR, e)
            else:
                raise Exception(error_msg) from e
    
    @classmethod
    def create_resource(
        cls,
        service_name: str,
        region_name: Optional[str] = None,
        enable_signing: bool = True,
        **kwargs
    ) -> Any:
        """
        Create AWS resource with optional request signing.
        
        Args:
            service_name: AWS service name
            region_name: AWS region
            enable_signing: Whether to enable request signing
            **kwargs: Additional arguments
            
        Returns:
            AWS resource instance
        """
        factory = cls()
        
        try:
            region = region_name or get_aws_region()
            
            # Create underlying client with signing
            client = cls.create_client(
                service_name=service_name,
                region_name=region,
                enable_signing=enable_signing,
                **kwargs
            )
            
            # Create resource using the signed client
            resource = boto3.resource(service_name, region_name=region)
            
            # Replace the resource's client with our signed client
            resource.meta.client = client
            
            logger.info(f"Created {'signed' if enable_signing else 'unsigned'} resource for {service_name}")
            return resource
            
        except Exception as e:
            error_msg = f"Failed to create {service_name} resource: {e}"
            logger.error(error_msg)
            if factory._ChatbotError and factory._ErrorType:
                raise factory._ChatbotError(error_msg, factory._ErrorType.EXTERNAL_SERVICE_ERROR, e)
            else:
                raise Exception(error_msg) from e
    
    @classmethod
    def clear_cache(cls):
        """Clear the client cache."""
        factory = cls()
        with factory._cache_lock:
            factory._client_cache.clear()
        logger.info("Client cache cleared")
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Get cache statistics."""
        factory = cls()
        with factory._cache_lock:
            return {
                'cached_clients': len(factory._client_cache),
                'cache_keys': list(factory._client_cache.keys()),
                'signing_enabled': factory._signing_config.enabled if factory._signing_config else False
            }
    
    @classmethod
    def configure_signing(cls, enabled: bool, **config_updates):
        """
        Update signing configuration at runtime.
        
        Args:
            enabled: Whether to enable signing
            **config_updates: Configuration updates
        """
        factory = cls()
        
        # Update signing configuration
        if hasattr(factory, '_signing_config') and factory._signing_config:
            factory._signing_config.enabled = enabled
            for key, value in config_updates.items():
                if hasattr(factory._signing_config, key):
                    setattr(factory._signing_config, key, value)
        
        # Recreate request signer if needed
        if enabled and not factory._request_signer and factory._signing_config:
            try:
                from .request_signer import RequestSigner
                factory._request_signer = RequestSigner(factory._signing_config)
            except ImportError:
                from request_signer import RequestSigner
                factory._request_signer = RequestSigner(factory._signing_config)
        elif not enabled:
            factory._request_signer = None
        
        # Clear cache to force recreation of clients
        cls.clear_cache()
        
        logger.info(f"Request signing {'enabled' if enabled else 'disabled'}")


# Convenience functions for backward compatibility
def get_signed_client(service_name: str, region_name: Optional[str] = None, **kwargs) -> Any:
    """Get a signed AWS client."""
    return AWSClientFactory.create_client(
        service_name=service_name,
        region_name=region_name,
        enable_signing=True,
        **kwargs
    )


def get_unsigned_client(service_name: str, region_name: Optional[str] = None, **kwargs) -> Any:
    """Get an unsigned AWS client."""
    return AWSClientFactory.create_client(
        service_name=service_name,
        region_name=region_name,
        enable_signing=False,
        **kwargs
    )
