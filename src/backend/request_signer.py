"""
AWS request signing utilities with SigV4 implementation.
"""
import hashlib
import hmac
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import json

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from botocore.exceptions import NoCredentialsError

logger = logging.getLogger(__name__)


class SigningConfig:
    """Configuration for AWS request signing."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize signing configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.enabled = config.get('enabled', True)
        self.signature_version = config.get('signatureVersion', 'v4')
        self.include_headers = config.get('includeHeaders', ['host', 'x-amz-date', 'authorization'])
        self.exclude_services = config.get('excludeServices', [])
        self.cache_ttl = config.get('cacheTTL', 300)
        
        # Additional security options
        self.require_https = config.get('requireHttps', True)
        self.validate_signatures = config.get('validateSignatures', True)
        self.log_signing_events = config.get('logSigningEvents', False)
        
        logger.debug(f"Signing configuration initialized: enabled={self.enabled}")


class RequestSigner:
    """
    AWS request signer with SigV4 support.
    
    Provides secure request signing for AWS API calls with:
    - SigV4 signature generation
    - Credential management
    - Request validation
    - Performance optimization
    """
    
    def __init__(self, config: SigningConfig):
        """
        Initialize request signer.
        
        Args:
            config: Signing configuration
        """
        self.config = config
        self._signature_cache = {}
        self._cache_lock = None
        
        # Initialize thread lock for signature cache
        import threading
        self._cache_lock = threading.RLock()
        
        logger.info("Request signer initialized")
    
    def _get_credentials(self) -> Credentials:
        """
        Get AWS credentials for signing.
        
        Returns:
            AWS credentials
            
        Raises:
            NoCredentialsError: If credentials cannot be found
        """
        try:
            # Try to get credentials from boto3 session
            import boto3
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if not credentials:
                raise NoCredentialsError()
            
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to get AWS credentials: {e}")
            raise NoCredentialsError()
    
    def _canonicalize_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        payload: str = ""
    ) -> Tuple[str, str, str]:
        """
        Create canonical request for signing.
        
        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            payload: Request payload
            
        Returns:
            Tuple of (canonical_request, signed_headers, payload_hash)
        """
        # Parse URL
        parsed_url = urllib.parse.urlparse(url)
        
        # Canonical URI
        canonical_uri = parsed_url.path or '/'
        
        # Canonical query string
        query_params = urllib.parse.parse_qs(parsed_url.query)
        canonical_query = '&'.join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v[0], safe='')}"
            for k, v in sorted(query_params.items())
        )
        
        # Canonical headers
        canonical_headers = []
        signed_headers = []
        
        for header_name in sorted(headers.keys(), key=str.lower):
            header_name_lower = header_name.lower()
            if header_name_lower in self.config.include_headers or header_name_lower.startswith('x-amz-'):
                canonical_headers.append(f"{header_name_lower}:{headers[header_name].strip()}")
                signed_headers.append(header_name_lower)
        
        canonical_headers_str = '\n'.join(canonical_headers) + '\n'
        signed_headers_str = ';'.join(signed_headers)
        
        # Payload hash
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        
        # Canonical request
        canonical_request = '\n'.join([
            method.upper(),
            canonical_uri,
            canonical_query,
            canonical_headers_str,
            signed_headers_str,
            payload_hash
        ])
        
        return canonical_request, signed_headers_str, payload_hash
    
    def _create_string_to_sign(
        self,
        timestamp: datetime,
        region: str,
        service: str,
        canonical_request: str
    ) -> str:
        """
        Create string to sign for SigV4.
        
        Args:
            timestamp: Request timestamp
            region: AWS region
            service: AWS service
            canonical_request: Canonical request string
            
        Returns:
            String to sign
        """
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{timestamp.strftime('%Y%m%d')}/{region}/{service}/aws4_request"
        canonical_request_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        
        string_to_sign = '\n'.join([
            algorithm,
            timestamp.strftime('%Y%m%dT%H%M%SZ'),
            credential_scope,
            canonical_request_hash
        ])
        
        return string_to_sign
    
    def _calculate_signature(
        self,
        secret_key: str,
        timestamp: datetime,
        region: str,
        service: str,
        string_to_sign: str
    ) -> str:
        """
        Calculate SigV4 signature.
        
        Args:
            secret_key: AWS secret access key
            timestamp: Request timestamp
            region: AWS region
            service: AWS service
            string_to_sign: String to sign
            
        Returns:
            Signature string
        """
        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        date_key = sign(f'AWS4{secret_key}'.encode('utf-8'), timestamp.strftime('%Y%m%d'))
        region_key = sign(date_key, region)
        service_key = sign(region_key, service)
        signing_key = sign(service_key, 'aws4_request')
        
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature
    
    def sign_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        payload: str = "",
        service: str = "",
        region: str = ""
    ) -> Dict[str, str]:
        """
        Sign AWS request with SigV4.
        
        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            payload: Request payload
            service: AWS service name
            region: AWS region
            
        Returns:
            Updated headers with signature
            
        Raises:
            NoCredentialsError: If credentials cannot be found
        """
        if not self.config.enabled:
            return headers
        
        try:
            # Get credentials
            credentials = self._get_credentials()
            
            # Get current timestamp
            timestamp = datetime.now(timezone.utc)
            
            # Add required headers
            headers = headers.copy()
            headers['X-Amz-Date'] = timestamp.strftime('%Y%m%dT%H%M%SZ')
            
            # Extract service and region from URL if not provided
            if not service or not region:
                parsed_url = urllib.parse.urlparse(url)
                host_parts = parsed_url.hostname.split('.')
                if len(host_parts) >= 3:
                    service = service or host_parts[0]
                    region = region or host_parts[1]
            
            # Add security token if present
            if credentials.token:
                headers['X-Amz-Security-Token'] = credentials.token
            
            # Create canonical request
            canonical_request, signed_headers, payload_hash = self._canonicalize_request(
                method, url, headers, payload
            )
            
            # Create string to sign
            string_to_sign = self._create_string_to_sign(
                timestamp, region, service, canonical_request
            )
            
            # Calculate signature
            signature = self._calculate_signature(
                credentials.secret_key, timestamp, region, service, string_to_sign
            )
            
            # Create authorization header
            credential = f"{credentials.access_key}/{timestamp.strftime('%Y%m%d')}/{region}/{service}/aws4_request"
            authorization = f"AWS4-HMAC-SHA256 Credential={credential}, SignedHeaders={signed_headers}, Signature={signature}"
            headers['Authorization'] = authorization
            
            if self.config.log_signing_events:
                logger.debug(f"Signed request for {service} in {region}")
            
            return headers
            
        except NoCredentialsError:
            logger.error("No AWS credentials available for request signing")
            raise
        except Exception as e:
            logger.error(f"Failed to sign request: {e}")
            # Return original headers if signing fails (graceful degradation)
            return headers
    
    def attach_to_client(self, client: Any):
        """
        Attach signing to boto3 client.
        
        Args:
            client: Boto3 client instance
        """
        if not self.config.enabled:
            return
        
        try:
            # Get the client's event system
            event_system = client.meta.events
            
            # Register signing event handler
            event_system.register(
                'before-sign',
                self._sign_request_handler,
                unique_id='request-signer'
            )
            
            logger.debug(f"Attached request signer to {client._service_model.service_name} client")
            
        except Exception as e:
            logger.warning(f"Failed to attach signer to client: {e}")
    
    def _sign_request_handler(self, request, **kwargs):
        """
        Event handler for request signing.
        
        Args:
            request: Boto3 request object
            **kwargs: Additional arguments
        """
        if not self.config.enabled:
            return
        
        try:
            # Extract request details
            method = request.method
            url = request.url
            headers = dict(request.headers)
            payload = request.body or ""
            
            # Sign the request
            signed_headers = self.sign_request(
                method=method,
                url=url,
                headers=headers,
                payload=payload if isinstance(payload, str) else payload.decode('utf-8', errors='ignore')
            )
            
            # Update request headers - handle different header types
            if hasattr(request.headers, 'update'):
                request.headers.update(signed_headers)
            else:
                # Handle HTTPHeaders or other header types
                for key, value in signed_headers.items():
                    request.headers[key] = value
            
        except Exception as e:
            logger.warning(f"Request signing failed: {e}")
    
    def validate_signature(self, request_headers: Dict[str, str], expected_signature: str) -> bool:
        """
        Validate request signature.
        
        Args:
            request_headers: Request headers
            expected_signature: Expected signature
            
        Returns:
            True if signature is valid
        """
        if not self.config.validate_signatures:
            return True
        
        try:
            auth_header = request_headers.get('Authorization', '')
            if 'Signature=' in auth_header:
                actual_signature = auth_header.split('Signature=')[1]
                return actual_signature == expected_signature
            return False
        except Exception as e:
            logger.warning(f"Signature validation failed: {e}")
            return False
    
    def clear_cache(self):
        """Clear signature cache."""
        with self._cache_lock:
            self._signature_cache.clear()
        logger.debug("Signature cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            return {
                'cached_signatures': len(self._signature_cache),
                'config_enabled': self.config.enabled,
                'signature_version': self.config.signature_version
            }


# Utility functions
def create_signed_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    payload: str = "",
    config: Optional[SigningConfig] = None
) -> Dict[str, str]:
    """
    Create a signed AWS request.
    
    Args:
        method: HTTP method
        url: Request URL
        headers: Request headers
        payload: Request payload
        config: Signing configuration
        
    Returns:
        Signed headers
    """
    if config is None:
        config = SigningConfig({'enabled': True})
    
    signer = RequestSigner(config)
    return signer.sign_request(method, url, headers or {}, payload)


def validate_aws_request(headers: Dict[str, str]) -> bool:
    """
    Validate AWS request headers.
    
    Args:
        headers: Request headers
        
    Returns:
        True if headers are valid
    """
    required_headers = ['Authorization', 'X-Amz-Date']
    return all(header in headers for header in required_headers)
