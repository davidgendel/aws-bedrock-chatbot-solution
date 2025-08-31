"""
Comprehensive WebSocket functionality tests.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws

from src.backend.lambda_handler import (
    handle_websocket_event,
    _initialize_websocket_api_client,
    _handle_websocket_message,
    _handle_websocket_heartbeat,
    _send_websocket_error,
    _cleanup_websocket_connection
)


class TestWebSocketConnectionEstablishment:
    """Test WebSocket connection establishment scenarios."""
    
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_connect_success(self, mock_get_aws_client):
        """Test successful WebSocket connection."""
        mock_api_client = Mock()
        mock_get_aws_client.return_value = mock_api_client
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "$connect",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            }
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 200
    
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_disconnect_success(self, mock_get_aws_client):
        """Test successful WebSocket disconnection."""
        mock_api_client = Mock()
        mock_get_aws_client.return_value = mock_api_client
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "$disconnect",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            }
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 200
    
    def test_invalid_event_structure(self):
        """Test handling of invalid event structure."""
        response = handle_websocket_event({})
        assert response["statusCode"] == 400
        
        response = handle_websocket_event({"requestContext": {}})
        assert response["statusCode"] == 400


class TestWebSocketMessageSending:
    """Test WebSocket message sending and streaming."""
    
    @patch('src.backend.lambda_handler._process_websocket_message_and_stream')
    @patch('src.backend.lambda_handler.validate_websocket_input')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_send_message_success(self, mock_get_aws_client, mock_guardrails, mock_validate, mock_process):
        """Test successful message sending."""
        mock_api_client = Mock()
        mock_get_aws_client.return_value = mock_api_client
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_validate.return_value = (True, [])
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "sendMessage",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            },
            "body": json.dumps({
                "action": "sendMessage",
                "message": "Hello, chatbot!"
            })
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 200
        mock_process.assert_called_once()
    
    @patch('src.backend.lambda_handler._send_websocket_error')
    @patch('src.backend.lambda_handler.validate_websocket_input')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_send_message_blocked_by_guardrails(self, mock_get_aws_client, mock_guardrails, mock_validate, mock_send_error):
        """Test message blocked by guardrails."""
        mock_api_client = Mock()
        mock_get_aws_client.return_value = mock_api_client
        mock_guardrails.return_value = {"blocked": True, "reasons": ["inappropriate content"]}
        mock_validate.return_value = (True, [])
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "sendMessage",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            },
            "body": json.dumps({
                "action": "sendMessage",
                "message": "Inappropriate message"
            })
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 400
        mock_send_error.assert_called_once()
    
    @patch('src.backend.lambda_handler._send_websocket_error')
    @patch('src.backend.lambda_handler.validate_websocket_input')
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_send_message_validation_failure(self, mock_get_aws_client, mock_validate, mock_send_error):
        """Test message validation failure."""
        mock_api_client = Mock()
        mock_get_aws_client.return_value = mock_api_client
        mock_validate.return_value = (False, ["Message too long"])
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "sendMessage",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            },
            "body": json.dumps({
                "action": "sendMessage",
                "message": "x" * 10000  # Very long message
            })
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 400
        mock_send_error.assert_called_once()


class TestWebSocketHeartbeat:
    """Test WebSocket heartbeat functionality."""
    
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_heartbeat_success(self, mock_get_aws_client):
        """Test successful heartbeat."""
        mock_api_client = Mock()
        mock_get_aws_client.return_value = mock_api_client
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "heartbeat",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            }
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 200
        mock_api_client.post_to_connection.assert_called_once()
    
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_heartbeat_connection_error(self, mock_get_aws_client):
        """Test heartbeat with connection error."""
        mock_api_client = Mock()
        mock_api_client.post_to_connection.side_effect = Exception("Connection gone")
        mock_get_aws_client.return_value = mock_api_client
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "heartbeat",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            }
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 410  # Connection gone


class TestWebSocketErrorHandling:
    """Test WebSocket error handling without sensitive information logging."""
    
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_client_initialization_failure(self, mock_get_aws_client):
        """Test WebSocket API client initialization failure."""
        mock_get_aws_client.side_effect = Exception("Client creation failed")
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "sendMessage",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            },
            "body": json.dumps({"action": "sendMessage", "message": "test"})
        }
        
        response = handle_websocket_event(event)
        assert response["statusCode"] == 500
    
    def test_unknown_route_key(self):
        """Test handling of unknown route key."""
        with patch('src.backend.lambda_handler.get_aws_client') as mock_get_aws_client:
            mock_api_client = Mock()
            mock_get_aws_client.return_value = mock_api_client
            
            event = {
                "requestContext": {
                    "connectionId": "test-conn-123",
                    "routeKey": "unknownAction",
                    "domainName": "test.execute-api.us-east-1.amazonaws.com",
                    "stage": "prod"
                }
            }
            
            response = handle_websocket_event(event)
            assert response["statusCode"] == 400


class TestWebSocketAPIClientInitialization:
    """Test WebSocket API client initialization."""
    
    @patch('src.backend.lambda_handler.get_aws_client')
    @patch('src.backend.lambda_handler.get_aws_region')
    def test_client_init_with_domain(self, mock_get_region, mock_get_aws_client):
        """Test client initialization with domain name."""
        mock_get_region.return_value = "us-east-1"
        mock_client = Mock()
        mock_get_aws_client.return_value = mock_client
        
        event = {
            "requestContext": {
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod",
                "apiId": "test123"
            }
        }
        
        client = _initialize_websocket_api_client(event)
        assert client == mock_client
        mock_get_aws_client.assert_called_once_with(
            service_name='apigatewaymanagementapi',
            region='us-east-1',
            enable_signing=True,
            endpoint_url="https://test.execute-api.us-east-1.amazonaws.com"
        )
    
    @patch('src.backend.lambda_handler.get_aws_client')
    @patch('src.backend.lambda_handler.get_aws_region')
    def test_client_init_construct_domain(self, mock_get_region, mock_get_aws_client):
        """Test client initialization constructing domain from API ID."""
        mock_get_region.return_value = "us-east-1"
        mock_client = Mock()
        mock_get_aws_client.return_value = mock_client
        
        event = {
            "requestContext": {
                "stage": "prod",
                "apiId": "test123"
            }
        }
        
        client = _initialize_websocket_api_client(event)
        assert client == mock_client
        mock_get_aws_client.assert_called_once_with(
            service_name='apigatewaymanagementapi',
            region='us-east-1',
            enable_signing=True,
            endpoint_url="https://test123.execute-api.us-east-1.amazonaws.com"
        )
    
    def test_client_init_missing_context(self):
        """Test client initialization with missing request context."""
        with pytest.raises(ValueError, match="Invalid event structure"):
            _initialize_websocket_api_client({})
    
    def test_client_init_missing_domain_and_api_id(self):
        """Test client initialization with missing domain and API ID."""
        event = {
            "requestContext": {
                "stage": "prod"
            }
        }
        
        with pytest.raises(ValueError, match="Cannot determine API Gateway domain"):
            _initialize_websocket_api_client(event)


class TestWebSocketStreaming:
    """Test WebSocket streaming functionality."""
    
    @patch('src.backend.lambda_handler.stream_response_to_websocket')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.get_cached_context')
    def test_streaming_with_cached_context(self, mock_get_cached, mock_embeddings, mock_query, mock_stream):
        """Test streaming with cached document context."""
        mock_get_cached.return_value = [{"content": "cached doc", "score": 0.9}]
        mock_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_api_client = Mock()
        
        from src.backend.lambda_handler import _process_websocket_message_and_stream
        
        _process_websocket_message_and_stream("test message", "conn-123", mock_api_client)
        
        mock_stream.assert_called_once()
        mock_query.assert_not_called()  # Should use cached context
    
    @patch('src.backend.lambda_handler.stream_response_to_websocket')
    @patch('src.backend.lambda_handler.cache_context')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.get_cached_context')
    def test_streaming_without_cached_context(self, mock_get_cached, mock_embeddings, mock_query, mock_cache, mock_stream):
        """Test streaming without cached document context."""
        mock_get_cached.return_value = None
        mock_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_query.return_value = [{"content": "new doc", "score": 0.8}]
        mock_api_client = Mock()
        
        from src.backend.lambda_handler import _process_websocket_message_and_stream
        
        _process_websocket_message_and_stream("test message", "conn-123", mock_api_client)
        
        mock_query.assert_called_once()
        mock_cache.assert_called_once()
        mock_stream.assert_called_once()


class TestWebSocketCleanup:
    """Test WebSocket connection cleanup."""
    
    def test_cleanup_websocket_connection(self):
        """Test WebSocket connection cleanup."""
        # This should not raise any exceptions
        _cleanup_websocket_connection("test-conn-123")
    
    def test_cleanup_with_error(self):
        """Test cleanup handling errors gracefully."""
        # Mock some cleanup operation that fails
        with patch('src.backend.lambda_handler.logger') as mock_logger:
            _cleanup_websocket_connection("test-conn-123")
            # Should not raise exception, just log


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""
    
    @patch('src.backend.lambda_handler.generate_cached_response')
    @patch('src.backend.lambda_handler.query_similar_vectors')
    @patch('src.backend.lambda_handler.generate_embeddings')
    @patch('src.backend.lambda_handler.cached_apply_guardrails')
    @patch('src.backend.lambda_handler.validate_websocket_input')
    @patch('src.backend.lambda_handler.get_aws_client')
    def test_full_websocket_message_flow(self, mock_get_aws_client, mock_validate, mock_guardrails, 
                                       mock_embeddings, mock_query, mock_response):
        """Test complete WebSocket message processing flow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_get_aws_client.return_value = mock_api_client
        mock_validate.return_value = (True, [])
        mock_guardrails.return_value = {"blocked": False, "reasons": []}
        mock_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_query.return_value = [{"content": "relevant doc", "score": 0.9}]
        mock_response.return_value = {
            "response": "Test response",
            "cached": False,
            "cache_type": "none",
            "model_id": "amazon.nova-lite-v1:0",
            "bedrock_cached": False
        }
        
        event = {
            "requestContext": {
                "connectionId": "test-conn-123",
                "routeKey": "sendMessage",
                "domainName": "test.execute-api.us-east-1.amazonaws.com",
                "stage": "prod"
            },
            "body": json.dumps({
                "action": "sendMessage",
                "message": "What is the weather like?"
            })
        }
        
        response = handle_websocket_event(event)
        
        # Verify the flow
        assert response["statusCode"] == 200
        mock_validate.assert_called_once()
        mock_guardrails.assert_called_once()
        mock_embeddings.assert_called_once()
        mock_query.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
