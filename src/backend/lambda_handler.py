"""
Main Lambda handler for the chatbot backend.
"""
import json
import os
import signal
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3

# Handle imports for both Lambda and local environments
try:
    # Try relative imports first (for local development)
    from .aws_utils import get_aws_region
    from .bedrock_utils import (
        apply_guardrails, generate_embeddings, generate_response, cached_apply_guardrails,
        generate_cached_response, get_cached_context, cache_context
    )
    from .cache_manager import cache_manager, CacheType, get_cached_response, cache_response
    from .error_handler import (
        ChatbotError, DatabaseError, BedrockError, ValidationError, WebSocketError,
        handle_error, create_error_response, create_success_response
    )
    from .logging_utils import (
        configure_lambda_logging, log_api_request, log_api_response,
        log_chat_message, log_error_with_context, log_aws_service_call,
        log_execution_time, get_chatbot_logger
    )
    from .model_config import ModelConfig
    from .s3_vector_utils import query_similar_vectors, cleanup_old_vectors
    from .validation import validate_input, validate_websocket_input
except ImportError:
    # Fall back to absolute imports (for Lambda environment)
    from aws_utils import get_aws_region
    from bedrock_utils import (
        apply_guardrails, generate_embeddings, generate_response, cached_apply_guardrails,
        generate_cached_response, get_cached_context, cache_context
    )
    from cache_manager import cache_manager, CacheType, get_cached_response, cache_response
    from error_handler import (
        ChatbotError, DatabaseError, BedrockError, ValidationError, WebSocketError,
        handle_error, create_error_response, create_success_response
    )
    from logging_utils import (
        configure_lambda_logging, log_api_request, log_api_response,
        log_chat_message, log_error_with_context, log_aws_service_call,
        log_execution_time, get_chatbot_logger
    )
    from model_config import ModelConfig
    from s3_vector_utils import query_similar_vectors, cleanup_old_vectors
    from validation import validate_input, validate_websocket_input

# Initialize logger
logger = get_chatbot_logger(__name__)

# Ensure sensitive data is never cached
SENSITIVE_CACHE_KEYS = ['credential', 'password', 'secret', 'token', 'key']

def is_sensitive_data(cache_key: str) -> bool:
    """Check if cache key contains sensitive data indicators."""
    key_lower = cache_key.lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_CACHE_KEYS)


def cache_vector_query_result(query_hash: str, results: List[Dict[str, Any]]) -> None:
    """Cache vector query results."""
    try:
        with vector_cache_lock:
            vector_query_cache[query_hash] = results
    except Exception as e:
        logger.debug(f"Failed to cache vector query result: {e}")


def get_cached_vector_query_result(query_hash: str) -> Optional[List[Dict[str, Any]]]:
    """Get cached vector query results."""
    try:
        with vector_cache_lock:
            return vector_query_cache.get(query_hash)
    except Exception as e:
        logger.debug(f"Failed to get cached vector query result: {e}")
        return None


def get_lambda_cache_stats() -> Dict[str, Any]:
    """Get Lambda cache statistics."""
    try:
        stats = cache_manager.get_stats()
        sizes = cache_manager.get_cache_sizes()
        
        return {
            "cache_stats": stats,
            "cache_sizes": sizes,
            "total_caches": len(stats)
        }
    except Exception as e:
        logger.warning(f"Failed to get Lambda cache stats: {e}")
        return {}


def with_retry(func: callable, max_retries: int = 3) -> Any:
    """
    Retry function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        
    Returns:
        Function result
    """
    import random
    import time
    
    retries = 0
    while True:
        try:
            return func()
        except Exception as error:
            retries += 1
            if retries > max_retries or not is_retryable_error(error):
                raise error
            
            # Calculate exponential backoff with jitter
            delay = min(100 * (2 ** retries) + random.random() * 100, 2000) / 1000.0
            logger.warning(
                f"Retrying after {delay}s (attempt {retries}/{max_retries}): "
                f"{error.__class__.__name__}: {str(error)}"
            )
            time.sleep(delay)


def is_retryable_error(error: Exception) -> bool:
    """
    Check if error is retryable.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is retryable, False otherwise
    """
    error_name = error.__class__.__name__
    error_message = str(error).lower()
    
    # Retry on throttling, timeout, or connection errors
    return (
        error_name in (
            "ThrottlingException",
            "ServiceUnavailableException",
            "InternalServerException",
            "TooManyRequestsException",
            "ClientError"  # boto3 specific error
        )
        or "throttling" in error_message
        or "throttled" in error_message
        or "timeout" in error_message
        or "connection" in error_message
        or "limit exceeded" in error_message
        or "too many requests" in error_message
    )


def handle_chat_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle chat requests.
    
    Args:
        body: Request body
        
    Returns:
        Chat response
    """
    try:
        # Validate input
        try:
            message = validate_input(body.get("message", ""))
        except ValidationError as e:
            logger.warning(f"Input validation failed: {str(e)}")
            return create_error_response(e)
        
        streaming = body.get("streaming", False)
        
        # Check cache for this request (only for non-sensitive data)
        cache_key = f"chat:{message}:{ModelConfig.get_model_id()}"
        
        # Check cache first (unified cache manager handles security checks)
        cached_response = get_cached_response(message)
        if cached_response:
            return create_success_response({
                "response": cached_response,
                "cached": True,
                "model": ModelConfig.get_model_id()
            })
        
        # Apply guardrails to user input
        guardrail_result = cached_apply_guardrails(message)
        
        if guardrail_result["blocked"]:
            error = ValidationError(
                "Content blocked by safety guardrails",
                context={"reasons": guardrail_result["reasons"]}
            )
            return create_error_response(error, status_code=400)
        
        # Generate embeddings for the query
        embedding = generate_embeddings(message)
        
        # Check context cache first
        cached_docs = get_cached_context(embedding, limit=3, threshold=0.45)
        if cached_docs:
            logger.debug("Using cached document context")
            relevant_docs = cached_docs
        else:
            # Retrieve relevant documents using S3 Vectors
            relevant_docs = query_similar_vectors(embedding, limit=3, similarity_threshold=0.45)
            # Cache the retrieved context
            cache_context(embedding, limit=3, threshold=0.45, context=relevant_docs)
            logger.debug("Cached new document context")
        
        # Construct prompt with retrieved documents
        context = ""
        if relevant_docs:
            context = "Here is some relevant information that might help answer the question:\n\n"
            
            for i, doc in enumerate(relevant_docs):
                # Check if we have enhanced metadata
                if doc.get("document_title") and doc.get("heading"):
                    context += f'Document {i + 1}: "{doc["document_title"]}"\n'
                    if doc["heading"]:
                        context += f'Section: {doc["heading"]}\n'
                    context += f'Content: {doc["content"]}\n\n'
                    
                    # Add relevant metadata if available
                    if doc.get("metadata"):
                        try:
                            metadata = (
                                json.loads(doc["metadata"])
                                if isinstance(doc["metadata"], str)
                                else doc["metadata"]
                            )
                            
                            # Add source information if available
                            if metadata.get("source"):
                                context += f'Source: {metadata["source"]}\n'
                            
                            # Add author information if available
                            if metadata.get("author"):
                                context += f'Author: {metadata["author"]}\n'
                            
                            # Add date information if available
                            if metadata.get("date"):
                                context += f'Date: {metadata["date"]}\n'
                            
                            # Add table information if this chunk references a table
                            if "[TABLE" in doc["content"] and metadata.get("tables") and metadata["tables"]:
                                import re
                                table_match = re.search(r"\[TABLE (\d+)\]", doc["content"])
                                if table_match:
                                    table_index = int(table_match.group(1)) - 1
                                    if 0 <= table_index < len(metadata["tables"]):
                                        context += "Table content:\n"
                                        table = metadata["tables"][table_index]
                                        for row in table["rows"]:
                                            context += " | ".join(row) + "\n"
                                        context += "\n"
                        except Exception as e:
                            logger.error(f"Error parsing document metadata: {e}")
                else:
                    # Fallback for old schema
                    context += f'Document {i + 1}:\n{doc["content"]}\n\n'
        
        prompt = f"""{context}
User question: {message}

Please provide a brief, conversational response (2-3 sentences max) based on the information provided. Be direct and helpful. If the information doesn't contain the answer, just say you don't have enough information to answer accurately."""
        
        # Generate response
        model_id = ModelConfig.get_model_id()
        
        # If streaming is requested and this is not a WebSocket connection, use non-streaming response
        if not streaming:
            # Use cached response generation with Bedrock native caching
            response_result = generate_cached_response(prompt, model_id, use_bedrock_caching=True)
            response = response_result["response"]
            
            # Cache the response using unified cache manager (if not already cached)
            if not response_result["cached"]:
                cache_response(message, response)
            
            # Return response with cache metadata
            return create_success_response({
                "response": response,
                "cached": response_result["cached"],
                "cache_type": response_result.get("cache_type", "none"),
                "bedrock_cached": response_result.get("bedrock_cached", False),
                "model": model_id
            })
        else:
            # For streaming, we'll use WebSocket API
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "message": "Streaming is not supported in this endpoint. Please use the WebSocket API for streaming.",
                    "streamingUrl": os.environ.get("WEBSOCKET_API_URL")
                })
            }
    except Exception as e:
        error = handle_error(e, context={"function": "handle_chat_request"})
        return create_error_response(error)


def handle_cleanup_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle cleanup requests.
    
    Args:
        event: Lambda event
        
    Returns:
        Cleanup response
    """
    try:
        # Verify this is an internal request (e.g., from EventBridge)
        if (
            event.get("source") == "aws.events"
            or event.get("headers", {}).get("x-cleanup-token") == os.environ.get("CLEANUP_TOKEN")
        ):
            logger.info("Starting scheduled vector cleanup...")
            cleanup_result = cleanup_old_vectors(days_old=90)
            
            return create_success_response({
                "message": "Database cleanup completed",
                "results": cleanup_result
            })
        else:
            error = ValidationError("Unauthorized cleanup request")
            return create_error_response(error, status_code=403)
    except Exception as e:
        error = handle_error(e, context={"function": "handle_cleanup_request"})
        return create_error_response(error)


def send_to_connection(api_client, connection_id: str, data: Dict[str, Any], raise_error: bool = False) -> bool:
    """
    Send message to WebSocket connection.
    
    Args:
        api_client: API Gateway Management API client
        connection_id: WebSocket connection ID
        data: Message data
        raise_error: Whether to raise exceptions (default: False)
        
    Returns:
        True if message was sent successfully, False otherwise
    """
    import time
    
    try:
        api_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode("utf-8")
        )
        return True
    except api_client.exceptions.GoneException:
        logger.info(f"Connection {connection_id} is stale")
        return False
    except api_client.exceptions.LimitExceededException:
        # Handle rate limiting by adding a small delay and retrying
        logger.info(f"Rate limit exceeded for connection {connection_id}, retrying after delay")
        time.sleep(0.2)
        return send_to_connection(api_client, connection_id, data, raise_error)
    except Exception as e:
        logger.error(f"Error sending message to connection {connection_id}: {e}")
        if raise_error:
            raise
        return False


def stream_response_to_connection(
    api_client: Any, connection_id: str, prompt: str, model_id: str
) -> None:
    """
    Stream response to WebSocket connection.
    
    Args:
        api_client: API Gateway Management API client
        connection_id: WebSocket connection ID
        prompt: Input prompt
        model_id: Bedrock model ID
    """
    bedrock_client = get_bedrock_client()
    
    try:
        # Send initial message with connection ID
        if not send_to_connection(
            api_client,
            connection_id,
            {
                "type": "start",
                "connectionId": connection_id,
                "message": "Response streaming started"
            }
        ):
            logger.warning(f"Failed to send initial message to connection {connection_id}")
            return
        
        # Format request based on model
        model_config = ModelConfig.get_model_config(model_id)
        body = json.dumps(ModelConfig.get_request_body(prompt, model_id)).encode('utf-8')
        
        # Create streaming request
        try:
            response = bedrock_client.invoke_model_with_response_stream(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=body
            )
        except Exception as bedrock_error:
            logger.error(f"Error invoking Bedrock model: {bedrock_error}")
            send_to_connection(
                api_client,
                connection_id,
                {
                    "type": "error",
                    "error": "Failed to generate response",
                    "details": str(bedrock_error)
                }
            )
            return
        
        # Process the streaming response
        accumulated_text = ""
        last_sent_time = time.time()
        chunk_interval = 0.3  # 300ms between chunks to avoid overwhelming the connection
        
        try:
            for event in response["body"]:
                try:
                    if "chunk" in event and "bytes" in event["chunk"]:
                        chunk_data = json.loads(event["chunk"]["bytes"].decode("utf-8"))
                        
                        # Extract text based on model
                        chunk_text = ModelConfig.extract_streaming_text(chunk_data, model_id)
                        
                        if chunk_text:
                            accumulated_text += chunk_text
                            
                            # Rate limit sending chunks to avoid overwhelming the connection
                            current_time = time.time()
                            if current_time - last_sent_time >= chunk_interval:
                                # Send chunk to client with error handling
                                send_to_connection(
                                    api_client,
                                    connection_id,
                                    {
                                        "type": "chunk",
                                        "text": chunk_text,
                                        "complete": False
                                    }
                                )
                                last_sent_time = current_time
                except Exception as chunk_error:
                    logger.error(f"Error processing chunk: {chunk_error}")
                    # Continue processing other chunks
        except Exception as stream_error:
            logger.error(f"Error processing stream: {stream_error}")
            send_to_connection(
                api_client,
                connection_id,
                {
                    "type": "error",
                    "error": "Error processing response stream",
                    "details": str(stream_error)
                }
            )
            return
        
        # Send final message with complete response
        send_to_connection(
            api_client,
            connection_id,
            {
                "type": "end",
                "connectionId": connection_id,
                "text": accumulated_text,
                "complete": True
            }
        )
    
    except Exception as e:
        logger.error(f"Error streaming response: {e}", exc_info=True)
        
        # Send error message to client
        send_to_connection(
            api_client,
            connection_id,
            {
                "type": "error",
                "connectionId": connection_id,
                "error": "An error occurred while streaming the response",
                "details": str(e)
            }
        )


def handle_websocket_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle WebSocket events with comprehensive error handling and cleanup.
    
    Args:
        event: WebSocket event
        
    Returns:
        WebSocket response
    """
    connection_id = None
    api_client = None
    
    try:
        # Validate event structure
        if not event or "requestContext" not in event:
            logger.error("Invalid WebSocket event: missing requestContext")
            return {"statusCode": 400}
        
        request_context = event["requestContext"]
        
        # Extract connection ID and route key safely
        connection_id = request_context.get("connectionId")
        route_key = request_context.get("routeKey")
        
        if not connection_id:
            logger.error("Invalid WebSocket event: missing connectionId")
            return {"statusCode": 400}
        
        if not route_key:
            logger.error(f"Invalid WebSocket event: missing routeKey for connection {connection_id}")
            return {"statusCode": 400}
        
        # Initialize API Gateway Management API client
        try:
            api_client = _initialize_websocket_api_client(event)
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket API client for connection {connection_id}: {e}")
            return {"statusCode": 500}
        
        # Handle different WebSocket route keys
        if route_key == "$connect":
            logger.info(f"WebSocket connection established: {connection_id}")
            return {"statusCode": 200}
        elif route_key == "$disconnect":
            logger.info(f"WebSocket connection closed: {connection_id}")
            # Perform any necessary cleanup for this connection
            _cleanup_websocket_connection(connection_id)
            return {"statusCode": 200}
        elif route_key == "sendMessage":
            return _handle_websocket_message(event, connection_id, api_client)
        elif route_key == "heartbeat":
            return _handle_websocket_heartbeat(connection_id, api_client)
        else:
            logger.warning(f"Unknown route key '{route_key}' for connection {connection_id}")
            if api_client:
                _send_websocket_error(api_client, connection_id, f"Unknown action: {route_key}")
            return {"statusCode": 400}
            
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket handler: {e}", exc_info=True)
        
        # Try to send error message to client if possible
        if api_client and connection_id:
            try:
                _send_websocket_error(api_client, connection_id, "Internal server error")
            except Exception as send_error:
                logger.error(f"Failed to send error message to WebSocket connection {connection_id}: {send_error}")
        
        return {"statusCode": 500}


def _cleanup_websocket_connection(connection_id: str) -> None:
    """Clean up resources associated with a WebSocket connection."""
    try:
        # Add any connection-specific cleanup logic here
        # For example, removing connection from active connections tracking
        logger.info(f"Cleaned up resources for WebSocket connection: {connection_id}")
    except Exception as e:
        logger.error(f"Error during WebSocket connection cleanup for {connection_id}: {e}")


def _initialize_websocket_api_client(event: Dict[str, Any]) -> Any:
    """Initialize API Gateway Management API client with error handling."""
    try:
        # Validate event structure
        if not event or "requestContext" not in event:
            raise ValueError("Invalid event structure: missing requestContext")
        
        request_context = event["requestContext"]
        
        # Validate required fields
        if "domainName" not in request_context:
            raise ValueError("Invalid event structure: missing domainName")
        if "stage" not in request_context:
            raise ValueError("Invalid event structure: missing stage")
        
        domain = request_context["domainName"]
        stage = request_context["stage"]
        region = get_aws_region()
        
        # Validate domain and stage values
        if not domain or not isinstance(domain, str):
            raise ValueError("Invalid domain name")
        if not stage or not isinstance(stage, str):
            raise ValueError("Invalid stage name")
        
        return get_aws_client(
            "apigatewaymanagementapi",
            region_name=region,
            enable_signing=True,
            endpoint_url=f"https://{domain}/{stage}"
        )
    except Exception as e:
        logger.error(f"Error initializing WebSocket API client: {e}")
        raise


def _handle_websocket_message(event: Dict[str, Any], connection_id: str, api_client) -> Dict[str, Any]:
    """Handle WebSocket message processing."""
    try:
        # Parse and validate input
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", "").strip()
        
        if not message:
            _send_websocket_error(api_client, connection_id, "Message cannot be empty")
            return {"statusCode": 400}
        
        # Validate WebSocket input
        is_valid, validation_errors = validate_websocket_input(body, "sendMessage")
        if not is_valid:
            error_message = "; ".join(validation_errors) if isinstance(validation_errors, list) else str(validation_errors)
            _send_websocket_error(api_client, connection_id, error_message)
            return {"statusCode": 400}
        
        # Apply guardrails
        guardrail_result = cached_apply_guardrails(message)
        if guardrail_result["blocked"]:
            _send_websocket_error(api_client, connection_id, "Your message was blocked by content filters.")
            return {"statusCode": 400}
        
        # Process the message and stream response
        _process_websocket_message_and_stream(message, connection_id, api_client)
        
        return {"statusCode": 200}
        
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        _send_websocket_error(api_client, connection_id, "An error occurred processing your message")
        return {"statusCode": 500}


def _handle_websocket_heartbeat(connection_id: str, api_client) -> Dict[str, Any]:
    """Handle WebSocket heartbeat."""
    try:
        api_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            })
        )
        return {"statusCode": 200}
    except Exception as e:
        logger.error(f"Error sending heartbeat: {e}")
        return {"statusCode": 500}


def _send_websocket_error(api_client, connection_id: str, error_message: str) -> None:
    """Send error message via WebSocket."""
    try:
        api_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({
                "type": "error",
                "message": error_message
            })
        )
    except Exception as e:
        logger.error(f"Error sending WebSocket error: {e}")


def _process_websocket_message_and_stream(message: str, connection_id: str, api_client) -> None:
    """Process WebSocket message and stream the response."""
    try:
        # Generate embeddings and query S3 Vector index with caching
        embeddings = generate_embeddings(message)
        
        # Check context cache first
        cached_docs = get_cached_context(embeddings, limit=5, threshold=0.45)
        if cached_docs:
            logger.debug("Using cached document context for WebSocket")
            relevant_docs = cached_docs
        else:
            relevant_docs = query_similar_vectors(embeddings, limit=5, similarity_threshold=0.45)
            # Cache the retrieved context
            cache_context(embeddings, limit=5, threshold=0.45, context=relevant_docs)
            logger.debug("Cached new document context for WebSocket")
        
        # Construct prompt
        if relevant_docs:
            context = "\n\n".join([doc["content"] for doc in relevant_docs])
            prompt = f"""Context: {context}

User question: {message}

Please provide a brief, conversational response (2-3 sentences max) based on the information provided. Be direct and helpful. If the information doesn't contain the answer, just say you don't have enough information to answer accurately."""
        else:
            prompt = f"""User question: {message}

Please provide a brief, conversational response (2-3 sentences max). Be direct and helpful."""
        
        # Stream response using Bedrock streaming API
        model_id = ModelConfig.get_model_id()
        stream_response_to_connection(api_client, connection_id, prompt, model_id)
        
    except Exception as e:
        logger.error(f"Error processing WebSocket message: {e}")
        _send_websocket_error(api_client, connection_id, "An error occurred processing your message")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Lambda response
    """
    # Check if this is a WebSocket connection
    if event.get("requestContext", {}).get("connectionId"):
        return handle_websocket_event(event)
    
    # Check if this is a cleanup request
    if event.get("httpMethod") == "POST" and event.get("path") == "/cleanup":
        return handle_cleanup_request(event)
    
    # Parse request body for chat requests
    try:
        body = json.loads(event["body"])
    except (json.JSONDecodeError, KeyError) as e:
        error = ValidationError("Invalid request body", original_error=e)
        return create_error_response(error)
    
    return handle_chat_request(body)


def cleanup_sensitive_data() -> None:
    """Clean up sensitive data from memory."""
    try:
        # Clear all caches using unified cache manager
        cache_manager.clear()
        
        # Force garbage collection to clear any lingering references
        import gc
        gc.collect()
        
        logger.info("Sensitive data cleanup completed")
    except Exception as e:
        logger.error(f"Error during sensitive data cleanup: {e}")


# Register signal handlers for graceful shutdown
def handle_sigterm(*args: Any) -> None:
    """Handle SIGTERM signal."""
    logger.info("SIGTERM received, performing graceful shutdown...")
    cleanup_sensitive_data()
    sys.exit(0)


def handle_sigint(*args: Any) -> None:
    """Handle SIGINT signal."""
    logger.info("SIGINT received, performing graceful shutdown...")
    cleanup_sensitive_data()
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigint)
