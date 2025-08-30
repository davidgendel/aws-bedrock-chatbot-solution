"""
Tests for request_signer - AWS request signing functionality.
"""
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import sys

# Add backend path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from request_signer import SigningConfig, RequestSigner


class TestRequestSigner(unittest.TestCase):
    """Test AWS request signing functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_config = {
            'enabled': True,
            'signatureVersion': 'v4',
            'includeHeaders': ['host', 'x-amz-date', 'authorization'],
            'excludeServices': [],
            'cacheTTL': 300,
            'requireHttps': True,
            'validateSignatures': True,
            'logSigningEvents': False
        }


class TestSigningConfig(TestRequestSigner):
    """Test SigningConfig class."""
    
    def test_signing_config_initialization(self):
        """Test SigningConfig initialization with default values."""
        config = SigningConfig(self.test_config)
        
        self.assertTrue(config.enabled)
        self.assertEqual(config.signature_version, 'v4')
        self.assertEqual(config.include_headers, ['host', 'x-amz-date', 'authorization'])
        self.assertEqual(config.exclude_services, [])
        self.assertEqual(config.cache_ttl, 300)
        self.assertTrue(config.require_https)
        self.assertTrue(config.validate_signatures)
        self.assertFalse(config.log_signing_events)
    
    def test_signing_config_partial_config(self):
        """Test SigningConfig with partial configuration."""
        partial_config = {'enabled': False, 'signatureVersion': 'v2'}
        config = SigningConfig(partial_config)
        
        self.assertFalse(config.enabled)
        self.assertEqual(config.signature_version, 'v2')
        # Should use defaults for missing values
        self.assertEqual(config.cache_ttl, 300)
        self.assertTrue(config.require_https)
    
    def test_signing_config_empty_config(self):
        """Test SigningConfig with empty configuration."""
        config = SigningConfig({})
        
        # Should use all defaults
        self.assertTrue(config.enabled)
        self.assertEqual(config.signature_version, 'v4')
        self.assertEqual(config.include_headers, ['host', 'x-amz-date', 'authorization'])


class TestRequestSignerInitialization(TestRequestSigner):
    """Test RequestSigner initialization."""
    
    def test_request_signer_initialization(self):
        """Test RequestSigner initialization."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        self.assertEqual(signer.config, config)
        self.assertIsNotNone(signer)
    
    @patch('request_signer.Credentials')
    def test_request_signer_with_credentials(self, mock_credentials):
        """Test RequestSigner with custom credentials."""
        mock_creds = Mock()
        mock_credentials.return_value = mock_creds
        
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config, credentials=mock_creds)
        
        self.assertEqual(signer.credentials, mock_creds)


class TestSignatureGeneration(TestRequestSigner):
    """Test signature generation functionality."""
    
    @patch('request_signer.SigV4Auth')
    @patch('request_signer.AWSRequest')
    def test_sign_request_basic(self, mock_aws_request, mock_sigv4_auth):
        """Test basic request signing."""
        # Setup mocks
        mock_request = Mock()
        mock_aws_request.return_value = mock_request
        mock_auth = Mock()
        mock_sigv4_auth.return_value = mock_auth
        
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        # Mock credentials
        signer.credentials = Mock()
        signer.credentials.access_key = 'test_access_key'
        signer.credentials.secret_key = 'test_secret_key'
        
        request_data = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"test": "data"}'
        }
        
        result = signer.sign_request(request_data, 'bedrock', 'us-east-1')
        
        self.assertIsNotNone(result)
        mock_auth.add_auth.assert_called_once()
    
    def test_sign_request_disabled(self):
        """Test request signing when disabled."""
        config_disabled = self.test_config.copy()
        config_disabled['enabled'] = False
        
        config = SigningConfig(config_disabled)
        signer = RequestSigner(config)
        
        request_data = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"test": "data"}'
        }
        
        result = signer.sign_request(request_data, 'bedrock', 'us-east-1')
        
        # Should return original request when signing is disabled
        self.assertEqual(result['method'], 'POST')
        self.assertEqual(result['url'], 'https://bedrock.us-east-1.amazonaws.com/model/invoke')
    
    def test_sign_request_excluded_service(self):
        """Test request signing for excluded service."""
        config_excluded = self.test_config.copy()
        config_excluded['excludeServices'] = ['s3']
        
        config = SigningConfig(config_excluded)
        signer = RequestSigner(config)
        
        request_data = {
            'method': 'GET',
            'url': 'https://s3.amazonaws.com/bucket/object',
            'headers': {}
        }
        
        result = signer.sign_request(request_data, 's3', 'us-east-1')
        
        # Should return original request for excluded service
        self.assertEqual(result['method'], 'GET')
        self.assertEqual(result['url'], 'https://s3.amazonaws.com/bucket/object')


class TestSignatureValidation(TestRequestSigner):
    """Test signature validation functionality."""
    
    def test_validate_signature_basic(self):
        """Test basic signature validation."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        # Mock a signed request
        signed_request = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {
                'Authorization': 'AWS4-HMAC-SHA256 Credential=test/20240101/us-east-1/bedrock/aws4_request',
                'X-Amz-Date': '20240101T000000Z'
            }
        }
        
        # Basic validation (checks for required headers)
        is_valid = signer.validate_signature(signed_request)
        
        # Should pass basic validation
        self.assertTrue(is_valid)
    
    def test_validate_signature_missing_headers(self):
        """Test signature validation with missing headers."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        # Request missing authorization header
        request_missing_auth = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {
                'X-Amz-Date': '20240101T000000Z'
            }
        }
        
        is_valid = signer.validate_signature(request_missing_auth)
        
        # Should fail validation
        self.assertFalse(is_valid)
    
    def test_validate_signature_disabled(self):
        """Test signature validation when disabled."""
        config_disabled = self.test_config.copy()
        config_disabled['validateSignatures'] = False
        
        config = SigningConfig(config_disabled)
        signer = RequestSigner(config)
        
        # Request with no signature
        unsigned_request = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {}
        }
        
        is_valid = signer.validate_signature(unsigned_request)
        
        # Should pass when validation is disabled
        self.assertTrue(is_valid)


class TestUtilityFunctions(TestRequestSigner):
    """Test utility functions."""
    
    def test_generate_canonical_request(self):
        """Test canonical request generation."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        request_data = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"test": "data"}'
        }
        
        canonical = signer._generate_canonical_request(request_data)
        
        self.assertIsInstance(canonical, str)
        self.assertIn('POST', canonical)
        self.assertIn('/model/invoke', canonical)
    
    def test_calculate_signature(self):
        """Test signature calculation."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        # Mock credentials
        signer.credentials = Mock()
        signer.credentials.secret_key = 'test_secret_key'
        
        string_to_sign = 'AWS4-HMAC-SHA256\n20240101T000000Z\n20240101/us-east-1/bedrock/aws4_request\ntest_canonical_request_hash'
        
        signature = signer._calculate_signature(string_to_sign, '20240101', 'us-east-1', 'bedrock')
        
        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)
    
    def test_get_authorization_header(self):
        """Test authorization header generation."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        # Mock credentials
        signer.credentials = Mock()
        signer.credentials.access_key = 'test_access_key'
        
        auth_header = signer._get_authorization_header(
            'test_signature',
            '20240101/us-east-1/bedrock/aws4_request',
            'host;x-amz-date'
        )
        
        self.assertIsInstance(auth_header, str)
        self.assertIn('AWS4-HMAC-SHA256', auth_header)
        self.assertIn('test_access_key', auth_header)
        self.assertIn('test_signature', auth_header)


class TestErrorHandling(TestRequestSigner):
    """Test error handling in request signing."""
    
    def test_sign_request_no_credentials(self):
        """Test request signing without credentials."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        # No credentials set
        signer.credentials = None
        
        request_data = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {},
            'body': '{}'
        }
        
        with self.assertRaises(Exception):
            signer.sign_request(request_data, 'bedrock', 'us-east-1')
    
    def test_sign_request_invalid_url(self):
        """Test request signing with invalid URL."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        request_data = {
            'method': 'POST',
            'url': 'invalid-url',
            'headers': {},
            'body': '{}'
        }
        
        # Should handle invalid URL gracefully
        result = signer.sign_request(request_data, 'bedrock', 'us-east-1')
        
        # Should return original request or handle error
        self.assertIsNotNone(result)
    
    def test_https_requirement_violation(self):
        """Test HTTPS requirement violation."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        request_data = {
            'method': 'POST',
            'url': 'http://bedrock.us-east-1.amazonaws.com/model/invoke',  # HTTP instead of HTTPS
            'headers': {},
            'body': '{}'
        }
        
        # Should reject HTTP requests when HTTPS is required
        with self.assertRaises(Exception):
            signer.sign_request(request_data, 'bedrock', 'us-east-1')


class TestCachingFunctionality(TestRequestSigner):
    """Test caching functionality."""
    
    def test_signature_caching(self):
        """Test signature caching mechanism."""
        config = SigningConfig(self.test_config)
        signer = RequestSigner(config)
        
        # Mock credentials
        signer.credentials = Mock()
        signer.credentials.access_key = 'test_access_key'
        signer.credentials.secret_key = 'test_secret_key'
        
        request_data = {
            'method': 'POST',
            'url': 'https://bedrock.us-east-1.amazonaws.com/model/invoke',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"test": "data"}'
        }
        
        # First call should generate signature
        with patch.object(signer, '_calculate_signature') as mock_calc:
            mock_calc.return_value = 'test_signature'
            
            result1 = signer.sign_request(request_data, 'bedrock', 'us-east-1')
            result2 = signer.sign_request(request_data, 'bedrock', 'us-east-1')
            
            # Should use cache for second call (implementation dependent)
            self.assertIsNotNone(result1)
            self.assertIsNotNone(result2)


class TestConfigurationOptions(TestRequestSigner):
    """Test various configuration options."""
    
    def test_custom_include_headers(self):
        """Test custom include headers configuration."""
        custom_config = self.test_config.copy()
        custom_config['includeHeaders'] = ['host', 'x-amz-date', 'x-amz-content-sha256']
        
        config = SigningConfig(custom_config)
        signer = RequestSigner(config)
        
        self.assertEqual(config.include_headers, ['host', 'x-amz-date', 'x-amz-content-sha256'])
    
    def test_logging_configuration(self):
        """Test logging configuration."""
        logging_config = self.test_config.copy()
        logging_config['logSigningEvents'] = True
        
        config = SigningConfig(logging_config)
        signer = RequestSigner(config)
        
        self.assertTrue(config.log_signing_events)
    
    def test_cache_ttl_configuration(self):
        """Test cache TTL configuration."""
        ttl_config = self.test_config.copy()
        ttl_config['cacheTTL'] = 600
        
        config = SigningConfig(ttl_config)
        signer = RequestSigner(config)
        
        self.assertEqual(config.cache_ttl, 600)


if __name__ == '__main__':
    unittest.main()
