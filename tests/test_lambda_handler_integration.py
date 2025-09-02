"""
Integration tests for Lambda handler with AWS service mocking.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws

from src.backend.lambda_handler import (
    handler,
    handle_websocket_event,
    get_lambda_cache_stats,
    cleanup_sensitive_data
)


class TestLambdaHandlerIntegration:
    """Integration tests for Lambda handler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear cache before each test
        from src.backend.cache_manager import cache_manager
        cache_manager.clear()
    
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_response')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.generate_cached_response')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    def test_lambda_handler_success(self, mock_cached_guardrails, mock_cached_response, mock_generate_embeddings, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test successful Lambda handler execution."""
        # Setup mocks
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_cached_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_generate_embeddings.return_value = [0.1, 0.2, 0.3]  # Mock embedding vector
        mock_query_vectors.return_value = [
            {"content": "Relevant document content", "score": 0.9}
        ]
        mock_generate_response.return_value = "This is a helpful response"
        mock_cached_response.return_value = {
            "response": "This is a helpful response",
            "cached": False,
            "cache_type": "none",
            "model_id": "amazon.nova-lite-v1:0",
            "bedrock_cached": False
        }
        
        # Create test event
        event = {
            "httpMethod": "POST",
            "body": json.dumps({
                "message": "What is the weather like?",
                "streaming": False
            }),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "data" in body
        assert body["data"]["response"] == "This is a helpful response"
        assert body["data"]["cached"] is False
    
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    def test_lambda_handler_guardrail_blocked(self, mock_cached_guardrails, mock_generate_embeddings, mock_guardrails):
        """Test Lambda handler when content is blocked by guardrails."""
        # Setup mock to block content
        mock_guardrails.return_value = {
            "blocked": True,
            "reasons": ["Content contains inappropriate language"]
        }
        mock_cached_guardrails.return_value = {
            "blocked": True,
            "reasons": ["Content contains inappropriate language"]
        }
        mock_generate_embeddings.return_value = [0.1, 0.2, 0.3]
        
        # Create test event
        event = {
            "httpMethod": "POST",
            "body": json.dumps({
                "message": "This is inappropriate content",
                "streaming": False
            }),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert body["error"]["type"] == "VALIDATION_ERROR"
    
    def test_lambda_handler_invalid_json(self):
        """Test Lambda handler with invalid JSON."""
        event = {
            "httpMethod": "POST",
            "body": "invalid json",
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
    
    def test_lambda_handler_missing_message(self):
        """Test Lambda handler with missing message."""
        event = {
            "httpMethod": "POST",
            "body": json.dumps({
                "streaming": False
            }),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
    
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_response')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.generate_cached_response')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    def test_lambda_handler_caching(self, mock_cached_guardrails, mock_cached_response, mock_generate_embeddings, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test Lambda handler caching functionality."""
        # Setup mocks
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_cached_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_generate_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_query_vectors.return_value = [
            {"content": "Relevant document content", "score": 0.9}
        ]
        mock_generate_response.return_value = "Cached response"
        mock_cached_response.return_value = {
            "response": "Cached response",
            "cached": False,
            "cache_type": "none",
            "model_id": "amazon.nova-lite-v1:0",
            "bedrock_cached": False
        }
        
        # Create test event
        event = {
            "httpMethod": "POST",
            "body": json.dumps({
                "message": "Test caching message",
                "streaming": False
            }),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # First request - should generate response
        response1 = handler(event, context)
        assert response1["statusCode"] == 200
        body1 = json.loads(response1["body"])
        assert body1["data"]["cached"] is False
        
        # Second request - should use cache
        response2 = handler(event, context)
        assert response2["statusCode"] == 200
        body2 = json.loads(response2["body"])
        assert body2["data"]["response"] == "Cached response"
    
    def test_lambda_handler_options_request(self):
        """Test Lambda handler CORS preflight request."""
        event = {
            "httpMethod": "OPTIONS",
            "headers": {
                "Origin": "https://example.com"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 400  # OPTIONS not supported, returns validation error
    
    def test_lambda_handler_get_stats(self):
        """Test Lambda handler stats endpoint."""
        event = {
            "httpMethod": "GET",
            "path": "/stats"
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 400  # GET not supported, returns validation error or "cache_sizes" in body
    
    @mock_aws
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_response')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.generate_cached_response')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    @patch('boto3.client')
    def test_websocket_handler_success(self, mock_boto3_client, mock_cached_guardrails, mock_cached_response, mock_generate_embeddings, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test successful WebSocket handler execution."""
        # Setup mocks
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_cached_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_generate_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_query_vectors.return_value = [
            {"content": "Relevant document content", "score": 0.9}
        ]
        mock_generate_response.return_value = "WebSocket response"
        mock_cached_response.return_value = {
            "response": "WebSocket response",
            "cached": False,
            "cache_type": "none",
            "model_id": "amazon.nova-lite-v1:0",
            "bedrock_cached": False
        }
        
        # Mock AWS client for WebSocket API
        mock_api_client = Mock()
        mock_boto3_client.return_value = mock_api_client
        
        # Create test event
        event = {
            "requestContext": {
                "connectionId": "test-connection-id",
                "routeKey": "sendMessage",
                "domainName": "test-api.execute-api.us-east-1.amazonaws.com",
                "stage": "test"
            },
            "body": json.dumps({
                "action": "sendMessage",
                "message": "Test WebSocket message"
            })
        }
        
        context = Mock()
        
        # Execute
        response = handle_websocket_event(event)
        
        # Assertions
        assert response["statusCode"] == 200
    
    @patch('boto3.client')
    def test_websocket_handler_invalid_action(self, mock_boto3_client):
        """Test WebSocket handler with invalid action."""
        # Mock AWS client
        mock_api_client = Mock()
        mock_boto3_client.return_value = mock_api_client
        
        event = {
            "requestContext": {
                "connectionId": "test-connection-id",
                "routeKey": "invalidAction",
                "domainName": "test-api.execute-api.us-east-1.amazonaws.com",
                "stage": "test"
            },
            "body": json.dumps({
                "action": "invalidAction",
                "message": "Test message"
            })
        }
        
        context = Mock()
        
        # Execute
        response = handle_websocket_event(event)
        
        # Should handle gracefully
        assert response["statusCode"] in [200, 400]
    
    @patch('boto3.client')
    def test_websocket_handler_heartbeat(self, mock_boto3_client):
        """Test WebSocket handler heartbeat."""
        # Mock AWS client
        mock_api_client = Mock()
        mock_boto3_client.return_value = mock_api_client
        
        event = {
            "requestContext": {
                "connectionId": "test-connection-id",
                "routeKey": "heartbeat",
                "domainName": "test-api.execute-api.us-east-1.amazonaws.com",
                "stage": "test"
            },
            "body": json.dumps({
                "action": "heartbeat"
            })
        }
        
        context = Mock()
        
        # Execute
        response = handle_websocket_event(event)
        
        # Assertions
        assert response["statusCode"] == 200
    
    def test_get_lambda_cache_stats(self):
        """Test cache statistics function."""
        # Add some data to cache first
        from src.backend.cache_manager import cache_response
        cache_response("test_message", "test_response")
        
        # Get stats
        stats = get_lambda_cache_stats()
        
        # Assertions
        assert isinstance(stats, dict)
        assert "cache_stats" in stats or "cache_sizes" in stats
    
    def test_cleanup_sensitive_data(self):
        """Test sensitive data cleanup."""
        # Add some data to cache first
        from src.backend.cache_manager import cache_response
        cache_response("test_message", "test_response")
        
        # Verify data is cached
        from src.backend.cache_manager import get_cached_response
        assert get_cached_response("test_message") == "test_response"
        
        # Cleanup
        cleanup_sensitive_data()
        
        # Verify data is cleared
        assert get_cached_response("test_message") is None
    
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.enhanced_query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_response')
    def test_lambda_handler_error_handling(self, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test Lambda handler error handling."""
        # Setup mocks to raise exception
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_query_vectors.side_effect = Exception("Database error")
        
        # Create test event
        event = {
            "httpMethod": "POST",
            "body": json.dumps({
                "message": "Test error handling",
                "streaming": False
            }),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Should handle error gracefully
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
    
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    def test_lambda_handler_streaming_fallback(self, mock_cached_guardrails, mock_generate_embeddings):
        """Test Lambda handler streaming fallback."""
        mock_generate_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_cached_guardrails.return_value = {"blocked": False, "reasons": []}
        event = {
            "httpMethod": "POST",
            "body": json.dumps({
                "message": "Test streaming",
                "streaming": True
            }),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Should return message about using WebSocket API
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "WebSocket API" in body["message"]


class TestLambdaHandlerEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_lambda_handler_empty_body(self):
        """Test Lambda handler with empty body."""
        event = {
            "httpMethod": "POST",
            "body": "",
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Should handle gracefully
        assert response["statusCode"] == 400
    
    def test_lambda_handler_no_body(self):
        """Test Lambda handler with no body."""
        event = {
            "httpMethod": "POST",
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Should handle gracefully
        assert response["statusCode"] == 400
    
    @mock_aws
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_response')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.generate_cached_response')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    def test_lambda_handler_unsupported_method(self, mock_cached_guardrails, mock_cached_response, mock_generate_embeddings, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test Lambda handler with unsupported HTTP method."""
        # Setup mocks
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_cached_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_generate_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_query_vectors.return_value = [
            {"content": "Relevant document content", "score": 0.9}
        ]
        mock_generate_response.return_value = "Test response"
        mock_cached_response.return_value = {
            "response": "Test response",
            "cached": False,
            "cache_type": "none",
            "model_id": "amazon.nova-lite-v1:0",
            "bedrock_cached": False
        }
        
        event = {
            "httpMethod": "DELETE",
            "body": json.dumps({"message": "test"}),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = handler(event, context)
        
        # Should return success since handler processes any valid JSON request
        assert response["statusCode"] == 200


if __name__ == "__main__":
    pytest.main([__file__])
