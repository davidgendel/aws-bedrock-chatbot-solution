"""
Integration tests for Lambda handler with AWS service mocking.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from moto import mock_apigatewaymanagementapi

from src.backend.lambda_handler import (
    lambda_handler,
    websocket_handler,
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
    def test_lambda_handler_success(self, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test successful Lambda handler execution."""
        # Setup mocks
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_query_vectors.return_value = [
            {"content": "Relevant document content", "score": 0.9}
        ]
        mock_generate_response.return_value = "This is a helpful response"
        
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
        response = lambda_handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["response"] == "This is a helpful response"
        assert body["cached"] is False
        
        # Verify mocks were called
        mock_guardrails.assert_called_once_with("What is the weather like?")
        mock_query_vectors.assert_called_once()
        mock_generate_response.assert_called_once()
    
    @patch('src.backend.lambda_handler.apply_guardrails')
    def test_lambda_handler_guardrail_blocked(self, mock_guardrails):
        """Test Lambda handler when content is blocked by guardrails."""
        # Setup mock to block content
        mock_guardrails.return_value = {
            "blocked": True,
            "reasons": ["Content contains inappropriate language"]
        }
        
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
        response = lambda_handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "blocked by safety guardrails" in body["error"]
    
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
        response = lambda_handler(event, context)
        
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
        response = lambda_handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
    
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_response')
    def test_lambda_handler_caching(self, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test Lambda handler caching functionality."""
        # Setup mocks
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_query_vectors.return_value = [
            {"content": "Relevant document content", "score": 0.9}
        ]
        mock_generate_response.return_value = "Cached response"
        
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
        response1 = lambda_handler(event, context)
        assert response1["statusCode"] == 200
        body1 = json.loads(response1["body"])
        assert body1["cached"] is False
        
        # Second request - should use cache
        response2 = lambda_handler(event, context)
        assert response2["statusCode"] == 200
        body2 = json.loads(response2["body"])
        assert body2["cached"] is True
        assert body2["response"] == "Cached response"
        
        # Verify generate_response was only called once
        assert mock_generate_response.call_count == 1
    
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
        response = lambda_handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 200
        assert "Access-Control-Allow-Origin" in response["headers"]
        assert "Access-Control-Allow-Methods" in response["headers"]
        assert "Access-Control-Allow-Headers" in response["headers"]
    
    def test_lambda_handler_get_stats(self):
        """Test Lambda handler stats endpoint."""
        event = {
            "httpMethod": "GET",
            "path": "/stats"
        }
        
        context = Mock()
        
        # Execute
        response = lambda_handler(event, context)
        
        # Assertions
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "cache_stats" in body or "cache_sizes" in body
    
    @mock_apigatewaymanagementapi
    @patch('src.backend.lambda_handler.apply_guardrails')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_response')
    def test_websocket_handler_success(self, mock_generate_response, mock_query_vectors, mock_guardrails):
        """Test successful WebSocket handler execution."""
        # Setup mocks
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_query_vectors.return_value = [
            {"content": "Relevant document content", "score": 0.9}
        ]
        mock_generate_response.return_value = "WebSocket response"
        
        # Create test event
        event = {
            "requestContext": {
                "connectionId": "test-connection-id",
                "routeKey": "sendMessage"
            },
            "body": json.dumps({
                "action": "sendMessage",
                "message": "Test WebSocket message"
            })
        }
        
        context = Mock()
        
        # Mock API Gateway Management API
        with patch('boto3.client') as mock_boto3:
            mock_api_client = Mock()
            mock_boto3.return_value = mock_api_client
            
            # Execute
            response = websocket_handler(event, context)
            
            # Assertions
            assert response["statusCode"] == 200
            
            # Verify API Gateway Management API was called to send response
            mock_api_client.post_to_connection.assert_called()
    
    def test_websocket_handler_invalid_action(self):
        """Test WebSocket handler with invalid action."""
        event = {
            "requestContext": {
                "connectionId": "test-connection-id",
                "routeKey": "invalidAction"
            },
            "body": json.dumps({
                "action": "invalidAction",
                "message": "Test message"
            })
        }
        
        context = Mock()
        
        # Execute
        response = websocket_handler(event, context)
        
        # Should handle gracefully
        assert response["statusCode"] in [200, 400]
    
    def test_websocket_handler_heartbeat(self):
        """Test WebSocket handler heartbeat."""
        event = {
            "requestContext": {
                "connectionId": "test-connection-id",
                "routeKey": "heartbeat"
            },
            "body": json.dumps({
                "action": "heartbeat"
            })
        }
        
        context = Mock()
        
        # Execute
        response = websocket_handler(event, context)
        
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
    @patch('src.backend.lambda_handler.query_similar_vectors')
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
        response = lambda_handler(event, context)
        
        # Should handle error gracefully
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
    
    def test_lambda_handler_streaming_fallback(self):
        """Test Lambda handler streaming fallback."""
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
        response = lambda_handler(event, context)
        
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
        response = lambda_handler(event, context)
        
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
        response = lambda_handler(event, context)
        
        # Should handle gracefully
        assert response["statusCode"] == 400
    
    def test_lambda_handler_unsupported_method(self):
        """Test Lambda handler with unsupported HTTP method."""
        event = {
            "httpMethod": "DELETE",
            "body": json.dumps({"message": "test"}),
            "headers": {
                "Content-Type": "application/json"
            }
        }
        
        context = Mock()
        
        # Execute
        response = lambda_handler(event, context)
        
        # Should return method not allowed
        assert response["statusCode"] == 405


if __name__ == "__main__":
    pytest.main([__file__])
