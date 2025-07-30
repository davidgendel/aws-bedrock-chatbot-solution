"""
Tests for Bedrock utilities with AWS service mocking.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.backend.bedrock_utils import (
    get_bedrock_client,
    generate_embeddings,
    generate_response,
    apply_guardrails
)


class TestBedrockUtils:
    """Test cases for Bedrock utilities."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_bedrock_client = Mock()
    
    @patch('src.backend.bedrock_utils.boto3.client')
    def test_get_bedrock_client(self, mock_boto3_client):
        """Test Bedrock client creation."""
        mock_boto3_client.return_value = self.mock_bedrock_client
        
        client = get_bedrock_client()
        
        mock_boto3_client.assert_called_once_with("bedrock-runtime", region_name="us-east-1")
        assert client == self.mock_bedrock_client
    
    @patch('src.backend.bedrock_utils.get_bedrock_client')
    @patch('src.backend.bedrock_utils.ModelConfig')
    def test_generate_embeddings_success(self, mock_model_config, mock_get_client):
        """Test successful embedding generation."""
        # Setup mocks
        mock_get_client.return_value = self.mock_bedrock_client
        mock_model_config.get_embedding_model.return_value = "amazon.titan-embed-text-v1"
        
        # Mock response
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
        }).encode()
        
        self.mock_bedrock_client.invoke_model.return_value = mock_response
        
        # Test
        result = generate_embeddings("test text")
        
        # Assertions
        assert result == [0.1, 0.2, 0.3, 0.4, 0.5]
        self.mock_bedrock_client.invoke_model.assert_called_once()
        
        # Check call arguments
        call_args = self.mock_bedrock_client.invoke_model.call_args
        assert call_args[1]["modelId"] == "amazon.titan-embed-text-v1"
        assert call_args[1]["contentType"] == "application/json"
        assert call_args[1]["accept"] == "application/json"
        assert "cacheConfig" in call_args[1]
        assert call_args[1]["cacheConfig"]["ttlSeconds"] == 259200  # 3 days
    
    @patch('src.backend.bedrock_utils.get_bedrock_client')
    def test_generate_embeddings_error(self, mock_get_client):
        """Test embedding generation error handling."""
        mock_get_client.return_value = self.mock_bedrock_client
        self.mock_bedrock_client.invoke_model.side_effect = Exception("API Error")
        
        with pytest.raises(Exception):
            generate_embeddings("test text")
    
    @patch('src.backend.bedrock_utils.get_bedrock_client')
    @patch('src.backend.bedrock_utils.ModelConfig')
    def test_generate_response_success(self, mock_model_config, mock_get_client):
        """Test successful response generation."""
        # Setup mocks
        mock_get_client.return_value = self.mock_bedrock_client
        mock_model_config.get_model_id.return_value = "amazon.nova-lite-v1"
        mock_model_config.get_request_body.return_value = {
            "messages": [{"role": "user", "content": "test prompt"}],
            "max_tokens": 1000
        }
        mock_model_config.extract_text_from_response.return_value = "Generated response"
        
        # Mock response
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "output": {"message": {"content": [{"text": "Generated response"}]}}
        }).encode()
        
        self.mock_bedrock_client.invoke_model.return_value = mock_response
        
        # Test
        result = generate_response("test prompt")
        
        # Assertions
        assert result == "Generated response"
        self.mock_bedrock_client.invoke_model.assert_called_once()
        
        # Check call arguments
        call_args = self.mock_bedrock_client.invoke_model.call_args
        assert call_args[1]["modelId"] == "amazon.nova-lite-v1"
        assert "cacheConfig" in call_args[1]
    
    @patch('src.backend.bedrock_utils.get_bedrock_client')
    def test_generate_response_error(self, mock_get_client):
        """Test response generation error handling."""
        mock_get_client.return_value = self.mock_bedrock_client
        self.mock_bedrock_client.invoke_model.side_effect = Exception("API Error")
        
        with pytest.raises(Exception):
            generate_response("test prompt")
    
    @patch('src.backend.bedrock_utils.boto3.client')
    @patch.dict('os.environ', {'GUARDRAIL_ID': 'test-guardrail-id', 'GUARDRAIL_VERSION': 'DRAFT'})
    def test_apply_guardrails_success_not_blocked(self, mock_boto3_client):
        """Test successful guardrail application - content not blocked."""
        mock_bedrock_client = Mock()
        mock_boto3_client.return_value = mock_bedrock_client
        
        # Mock response - content not blocked
        mock_response = {
            "action": "NONE",
            "outputs": []
        }
        mock_bedrock_client.apply_guardrail.return_value = mock_response
        
        # Test
        result = apply_guardrails("This is safe content")
        
        # Assertions
        assert result["blocked"] is False
        assert result["reasons"] == []
        assert result["action"] == "NONE"
        
        mock_bedrock_client.apply_guardrail.assert_called_once_with(
            guardrailIdentifier="test-guardrail-id",
            guardrailVersion="DRAFT",
            source="INPUT",
            content=[{"text": {"text": "This is safe content"}}]
        )
    
    @patch('src.backend.bedrock_utils.boto3.client')
    @patch.dict('os.environ', {'GUARDRAIL_ID': 'test-guardrail-id'})
    def test_apply_guardrails_success_blocked(self, mock_boto3_client):
        """Test successful guardrail application - content blocked."""
        mock_bedrock_client = Mock()
        mock_boto3_client.return_value = mock_bedrock_client
        
        # Mock response - content blocked
        mock_response = {
            "action": "GUARDRAIL_INTERVENED",
            "outputs": [
                {"text": "Content contains inappropriate language"}
            ]
        }
        mock_bedrock_client.apply_guardrail.return_value = mock_response
        
        # Test
        result = apply_guardrails("This is inappropriate content")
        
        # Assertions
        assert result["blocked"] is True
        assert "Content contains inappropriate language" in result["reasons"]
        assert result["action"] == "GUARDRAIL_INTERVENED"
    
    @patch('src.backend.bedrock_utils.boto3.client')
    def test_apply_guardrails_no_guardrail_configured(self, mock_boto3_client):
        """Test guardrail application when no guardrail is configured."""
        # Test without environment variables
        result = apply_guardrails("Any content")
        
        # Should allow content when no guardrail is configured
        assert result["blocked"] is False
        assert result["reasons"] == []
        
        # Should not call AWS API
        mock_boto3_client.assert_not_called()
    
    @patch('src.backend.bedrock_utils.boto3.client')
    @patch.dict('os.environ', {'GUARDRAIL_ID': 'nonexistent-guardrail'})
    def test_apply_guardrails_resource_not_found(self, mock_boto3_client):
        """Test guardrail application when guardrail doesn't exist."""
        mock_bedrock_client = Mock()
        mock_boto3_client.return_value = mock_bedrock_client
        
        # Mock ResourceNotFoundException
        error_response = {
            'Error': {
                'Code': 'ResourceNotFoundException',
                'Message': 'Guardrail not found'
            }
        }
        mock_bedrock_client.apply_guardrail.side_effect = ClientError(
            error_response, 'ApplyGuardrail'
        )
        
        # Test
        result = apply_guardrails("Any content")
        
        # Should allow content when guardrail is not found
        assert result["blocked"] is False
        assert "Guardrail not configured" in result["reasons"]
    
    @patch('src.backend.bedrock_utils.boto3.client')
    @patch.dict('os.environ', {'GUARDRAIL_ID': 'test-guardrail-id'})
    def test_apply_guardrails_client_error(self, mock_boto3_client):
        """Test guardrail application with other client errors."""
        mock_bedrock_client = Mock()
        mock_boto3_client.return_value = mock_bedrock_client
        
        # Mock other ClientError
        error_response = {
            'Error': {
                'Code': 'AccessDeniedException',
                'Message': 'Access denied'
            }
        }
        mock_bedrock_client.apply_guardrail.side_effect = ClientError(
            error_response, 'ApplyGuardrail'
        )
        
        # Test
        result = apply_guardrails("Any content")
        
        # Should allow content but log error
        assert result["blocked"] is False
        assert "Guardrail error: AccessDeniedException" in result["reasons"]
    
    @patch('src.backend.bedrock_utils.boto3.client')
    @patch.dict('os.environ', {'GUARDRAIL_ID': 'test-guardrail-id'})
    def test_apply_guardrails_unexpected_error(self, mock_boto3_client):
        """Test guardrail application with unexpected errors."""
        mock_bedrock_client = Mock()
        mock_boto3_client.return_value = mock_bedrock_client
        
        # Mock unexpected error
        mock_bedrock_client.apply_guardrail.side_effect = Exception("Unexpected error")
        
        # Test
        result = apply_guardrails("Any content")
        
        # Should allow content but log error
        assert result["blocked"] is False
        assert "Guardrail system error: Unexpected error" in result["reasons"]
    
    def test_apply_guardrails_with_custom_parameters(self):
        """Test guardrail application with custom parameters."""
        with patch('src.backend.bedrock_utils.boto3.client') as mock_boto3_client:
            mock_bedrock_client = Mock()
            mock_boto3_client.return_value = mock_bedrock_client
            
            mock_response = {
                "action": "NONE",
                "outputs": []
            }
            mock_bedrock_client.apply_guardrail.return_value = mock_response
            
            # Test with custom parameters
            result = apply_guardrails(
                "Test content",
                guardrail_id="custom-guardrail",
                guardrail_version="1.0"
            )
            
            # Should use custom parameters
            mock_bedrock_client.apply_guardrail.assert_called_once_with(
                guardrailIdentifier="custom-guardrail",
                guardrailVersion="1.0",
                source="INPUT",
                content=[{"text": {"text": "Test content"}}]
            )
            
            assert result["blocked"] is False


if __name__ == "__main__":
    pytest.main([__file__])
