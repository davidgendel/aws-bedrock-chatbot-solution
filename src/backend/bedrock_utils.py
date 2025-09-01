"""
Utilities for interacting with Amazon Bedrock.
"""
import json
import logging
import os
import hashlib
import threading
from typing import Any, Dict, List, Optional
from cachetools import TTLCache

import boto3
from botocore.exceptions import ClientError

try:
    from .aws_utils import get_aws_region
    from .model_config import ModelConfig
except ImportError:
    from aws_utils import get_aws_region
    from model_config import ModelConfig

# Initialize logger
logger = logging.getLogger(__name__)

# Guardrail result cache with 2-hour TTL
guardrail_cache = TTLCache(maxsize=1000, ttl=7200)  # 2 hours = 7200 seconds
guardrail_cache_lock = threading.RLock()

# Prompt cache with 1-hour TTL for RAG prompts
prompt_cache = TTLCache(maxsize=500, ttl=3600)  # 1 hour = 3600 seconds
prompt_cache_lock = threading.RLock()

# Context cache with 2-hour TTL for retrieved document context
context_cache = TTLCache(maxsize=300, ttl=7200)  # 2 hours = 7200 seconds
context_cache_lock = threading.RLock()


def get_guardrail_cache_key(text: str) -> str:
    """Generate cache key for guardrail results."""
    return hashlib.md5(text.encode()).hexdigest()


def get_prompt_cache_key(prompt: str, model_id: str) -> str:
    """Generate cache key for prompt responses."""
    combined = f"{prompt}:{model_id}"
    return hashlib.sha256(combined.encode()).hexdigest()


def get_context_cache_key(embedding: List[float], limit: int, threshold: float) -> str:
    """Generate cache key for document context based on query parameters."""
    # Create a stable hash from embedding vector and query parameters
    embedding_str = ",".join([f"{x:.6f}" for x in embedding[:10]])  # Use first 10 dimensions for key
    combined = f"{embedding_str}:{limit}:{threshold}"
    return hashlib.sha256(combined.encode()).hexdigest()


def get_cached_prompt_response(prompt: str, model_id: str) -> Optional[str]:
    """Get cached response for a prompt."""
    cache_key = get_prompt_cache_key(prompt, model_id)
    with prompt_cache_lock:
        cached_result = prompt_cache.get(cache_key)
        if cached_result:
            return cached_result
        return None


def cache_prompt_response(prompt: str, model_id: str, response: str) -> None:
    """Cache response for a prompt."""
    cache_key = get_prompt_cache_key(prompt, model_id)
    with prompt_cache_lock:
        prompt_cache[cache_key] = response


def get_cached_context(embedding: List[float], limit: int, threshold: float) -> Optional[List[Dict[str, Any]]]:
    """Get cached document context for vector query."""
    cache_key = get_context_cache_key(embedding, limit, threshold)
    with context_cache_lock:
        cached_result = context_cache.get(cache_key)
        if cached_result:
            return cached_result
        return None


def cache_context(embedding: List[float], limit: int, threshold: float, context: List[Dict[str, Any]]) -> None:
    """Cache document context for vector query."""
    cache_key = get_context_cache_key(embedding, limit, threshold)
    with context_cache_lock:
        context_cache[cache_key] = context


def should_apply_guardrails(user_input: str) -> bool:
    """
    Determine if guardrails should be applied to user input.
    
    Rules:
    1. Skip for inputs smaller than 18 characters
    2. Skip for document-specific queries
    
    Args:
        user_input: User's input text
        
    Returns:
        Boolean indicating whether to apply guardrails
    """
    # Rule 1: Skip short inputs (< 18 characters)
    if len(user_input.strip()) < 18:
        logger.info(f"Skipping content moderation for short input ({len(user_input)} chars)")
        return False
    
    # Rule 2: Skip document-specific queries
    user_input_lower = user_input.lower()
    document_keywords = [
        "document", "file", "pdf", "upload", "attachment", 
        "content", "text", "page", "section", "chapter",
        "what does the document say", "according to the document",
        "in the file", "from the document", "document contains"
    ]
    
    if any(keyword in user_input_lower for keyword in document_keywords):
        logger.info("Skipping content moderation for document-specific query")
        return False
    
    # Apply guardrails for all other cases
    return True


def cached_apply_guardrails(text: str, guardrail_id: Optional[str] = None, guardrail_version: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply Bedrock guardrails with caching support.
    
    Args:
        text: Text to check
        guardrail_id: Guardrail ID (optional)
        guardrail_version: Guardrail version (optional)
        
    Returns:
        Dictionary with blocked status and reasons
    """
    # Check if guardrails should be applied
    if not should_apply_guardrails(text):
        return {
            "blocked": False,
            "reasons": ["Skipped - rule applied"],
            "cached": False,
            "rule": "selective_application"
        }
    
    # Generate cache key
    cache_key = get_guardrail_cache_key(text)
    
    # Check cache first
    with guardrail_cache_lock:
        if cache_key in guardrail_cache:
            cached_result = guardrail_cache[cache_key].copy()
            cached_result["cached"] = True
            return cached_result
    
    # Apply guardrails if not in cache
    result = apply_guardrails(text, guardrail_id, guardrail_version)
    result["cached"] = False
    
    # Cache the result
    with guardrail_cache_lock:
        guardrail_cache[cache_key] = result.copy()
    
    return result


def get_bedrock_client() -> Any:
    """Get Bedrock runtime client with SigV4 signing."""
    import boto3
    from botocore.config import Config
    
    config = Config(
        retries={'max_attempts': 3, 'mode': 'adaptive'},
        signature_version='v4'  # Explicit SigV4 signing
    )
    
    return boto3.client(
        'bedrock-runtime', 
        region_name=os.environ.get('REGION', 'us-east-1'),
        config=config
    )


def generate_embeddings(text: str, model_id: Optional[str] = None) -> List[float]:
    """
    Generate embeddings for text using Amazon Titan.
    
    Args:
        text: Text to generate embeddings for
        model_id: Optional model ID (used to determine embedding model)
        
    Returns:
        List of embedding values
    """
    try:
        bedrock_client = get_bedrock_client()
        
        # Get the appropriate embedding model
        embedding_model = ModelConfig.get_embedding_model(model_id)
        
        # Prepare request body
        body = json.dumps({
            "inputText": text
        })
        
        # Invoke model for embeddings
        response = bedrock_client.invoke_model(
            modelId=embedding_model,
            contentType="application/json",
            accept="application/json",
            body=body
        )
        
        # Parse response
        response_body = json.loads(response["body"].read())
        
        return response_body["embedding"]
        
    except Exception as e:
        logger.error("Error generating embeddings")
        raise


def generate_response(prompt: str, model_id: Optional[str] = None) -> str:
    """
    Generate response using Bedrock model.
    
    Args:
        prompt: Input prompt
        model_id: Model ID to use (defaults to configured model)
        
    Returns:
        Generated response text
    """
    try:
        bedrock_client = get_bedrock_client()
        
        if model_id is None:
            model_id = ModelConfig.get_model_id()
        
        # Get properly formatted request body
        body = json.dumps(ModelConfig.get_request_body(prompt, model_id))
        
        # Invoke model for response generation
        response = bedrock_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body
        )
        
        # Parse response
        response_body = json.loads(response["body"].read())
        
        # Extract text based on model type
        return ModelConfig.extract_text_from_response(response_body, model_id)
        
    except Exception as e:
        logger.error("Error generating response")
        raise


def generate_cached_response(prompt: str, model_id: Optional[str] = None, use_bedrock_caching: bool = True) -> Dict[str, Any]:
    """
    Generate response with prompt caching and AWS Bedrock native caching support.
    
    Args:
        prompt: Input prompt
        model_id: Model ID to use (defaults to configured model)
        use_bedrock_caching: Whether to use AWS Bedrock native prompt caching
        
    Returns:
        Dictionary with response text and cache metadata
    """
    try:
        if model_id is None:
            model_id = ModelConfig.get_model_id()
        
        # Check prompt cache first
        cached_response = get_cached_prompt_response(prompt, model_id)
        if cached_response:
            return {
                "response": cached_response,
                "cached": True,
                "cache_type": "lambda_memory",
                "model_id": model_id
            }
        
        bedrock_client = get_bedrock_client()
        
        # Get properly formatted request body with AWS Bedrock caching if supported
        request_body = ModelConfig.get_request_body(prompt, model_id)
        
        # Add AWS Bedrock native prompt caching for supported models
        if use_bedrock_caching and _supports_bedrock_caching(model_id):
            # Enable prompt caching for system prompts and context
            if _is_rag_prompt(prompt):
                request_body = _add_bedrock_caching_config(request_body, prompt)
                logger.info("Enabled prompt caching for RAG query")
        
        body = json.dumps(request_body)
        
        # Invoke model for response generation
        response = bedrock_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body
        )
        
        # Parse response
        response_body = json.loads(response["body"].read())
        
        # Extract text based on model type
        response_text = ModelConfig.extract_text_from_response(response_body, model_id)
        
        # Cache the response in Lambda memory
        cache_prompt_response(prompt, model_id, response_text)
        
        # Check if Bedrock used its native caching
        bedrock_cached = response_body.get("amazon-bedrock-invocationMetrics", {}).get("inputTokenCount", 0) == 0
        
        return {
            "response": response_text,
            "cached": False,
            "cache_type": "bedrock_native" if bedrock_cached else "none",
            "model_id": model_id,
            "bedrock_cached": bedrock_cached
        }
        
    except Exception as e:
        logger.error("Error generating cached response")
        raise


def _supports_bedrock_caching(model_id: str) -> bool:
    """Check if model supports AWS Bedrock native prompt caching."""
    # AWS Bedrock prompt caching is supported by Claude models
    supported_models = [
        "anthropic.claude-sonnet-4-20250514-v1:0",
        "anthropic.claude-3-5-haiku-20241022-v1:0"
    ]
    return model_id in supported_models


def _is_rag_prompt(prompt: str) -> bool:
    """Check if prompt is a RAG prompt with context."""
    # Simple heuristic to identify RAG prompts
    rag_indicators = [
        "Context:",
        "Here is some relevant information",
        "Document",
        "based on the information provided"
    ]
    return any(indicator in prompt for indicator in rag_indicators)


def _add_bedrock_caching_config(request_body: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    """Add AWS Bedrock native caching configuration to request body."""
    try:
        # For Claude models, add caching configuration
        if "messages" in request_body:
            # Claude format - add cache control to system message or context
            messages = request_body["messages"]
            
            # Find system message or first user message with context
            for message in messages:
                if (message.get("role") == "system" or 
                    (message.get("role") == "user" and "Context:" in message.get("content", ""))):
                    
                    # Add cache control for prompt caching
                    if isinstance(message["content"], str):
                        message["content"] = [
                            {
                                "type": "text",
                                "text": message["content"],
                                "cache_control": {"type": "ephemeral"}
                            }
                        ]
                    elif isinstance(message["content"], list):
                        # Add cache control to the last content block
                        if message["content"]:
                            message["content"][-1]["cache_control"] = {"type": "ephemeral"}
                    break
        
        return request_body
        
    except Exception as e:
        logger.warning(f"Failed to add Bedrock caching config: {e}")
        return request_body


def generate_streaming_response(prompt: str, model_id: Optional[str] = None) -> Any:
    """
    Generate streaming response using Bedrock model.
    
    Args:
        prompt: Input prompt
        model_id: Model ID to use (defaults to configured model)
        
    Yields:
        Response chunks
    """
    try:
        bedrock_client = get_bedrock_client()
        
        if model_id is None:
            model_id = ModelConfig.get_model_id()
        
        # Check if model supports streaming
        if not ModelConfig.supports_streaming(model_id):
            raise ValueError(f"Model {model_id} does not support streaming")
        
        # Get properly formatted request body
        body = json.dumps(ModelConfig.get_request_body(prompt, model_id)).encode('utf-8')
        
        # Create streaming request
        response = bedrock_client.invoke_model_with_response_stream(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body
        )
        
        # Process the streaming response
        for event in response["body"]:
            if "chunk" in event and "bytes" in event["chunk"]:
                chunk_data = json.loads(event["chunk"]["bytes"].decode("utf-8"))
                
                # Extract text based on model type
                chunk_text = ModelConfig.extract_streaming_text(chunk_data, model_id)
                
                if chunk_text:
                    yield chunk_text
                    
    except Exception as e:
        logger.error("Error generating streaming response")
        raise


def apply_guardrails(text: str, guardrail_id: Optional[str] = None, guardrail_version: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply Bedrock guardrails to text.
    
    Args:
        text: Text to check
        guardrail_id: Guardrail ID (optional, will use environment variable if not provided)
        guardrail_version: Guardrail version (optional, will use environment variable if not provided)
        
    Returns:
        Dictionary with blocked status and reasons
    """
    try:
        # Get guardrail configuration from environment if not provided
        if guardrail_id is None:
            guardrail_id = os.environ.get("GUARDRAIL_ID")
        if guardrail_version is None:
            guardrail_version = os.environ.get("GUARDRAIL_VERSION")
        
        # If no guardrail configured, return unblocked
        if not guardrail_id:
            logger.info("No guardrail configured, allowing content")
            return {
                "blocked": False,
                "reasons": []
            }
        
        bedrock_client = get_bedrock_client()
        
        # Apply guardrail
        response = bedrock_client.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=guardrail_version or "DRAFT",
            source="INPUT",
            content=[
                {
                    "text": {
                        "text": text
                    }
                }
            ]
        )
        
        # Check if content was blocked
        action = response.get("action", "NONE")
        blocked = action == "GUARDRAIL_INTERVENED"
        
        # Extract reasons if blocked
        reasons = []
        if blocked and "outputs" in response:
            for output in response["outputs"]:
                if "text" in output:
                    # Handle both direct text and nested text structure
                    text_content = output["text"]
                    if isinstance(text_content, dict) and "text" in text_content:
                        reasons.append(text_content["text"])
                    else:
                        reasons.append(text_content)
        
        return {
            "blocked": blocked,
            "reasons": reasons,
            "action": action
        }
        
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Guardrail not found: {guardrail_id}, allowing content")
            return {
                "blocked": False,
                "reasons": ["Guardrail not configured"]
            }
        else:
            logger.error("Error applying guardrails")
            # In case of error, allow content but log the issue
            return {
                "blocked": False,
                "reasons": [f"Guardrail error: {error_code}"]
            }
    except Exception as e:
        logger.error("Unexpected error applying guardrails")
        # In case of error, allow content but log the issue
        return {
            "blocked": False,
            "reasons": [f"Guardrail system error: {e}"]
        }


def get_guardrail_cache_stats() -> Dict[str, Any]:
    """
    Get guardrail cache statistics for monitoring.
    
    Returns:
        Dictionary with cache statistics
    """
    with guardrail_cache_lock:
        return {
            "cache_size": len(guardrail_cache),
            "max_size": guardrail_cache.maxsize,
            "ttl_seconds": guardrail_cache.ttl,
            "cache_info": {
                "hits": getattr(guardrail_cache, 'hits', 0),
                "misses": getattr(guardrail_cache, 'misses', 0)
            }
        }


def clear_guardrail_cache() -> None:
    """Clear the guardrail cache."""
    with guardrail_cache_lock:
        guardrail_cache.clear()
        logger.info("Guardrail cache cleared")


def get_prompt_cache_stats() -> Dict[str, Any]:
    """
    Get prompt cache statistics for monitoring.
    
    Returns:
        Dictionary with cache statistics
    """
    with prompt_cache_lock:
        return {
            "cache_size": len(prompt_cache),
            "max_size": prompt_cache.maxsize,
            "ttl_seconds": prompt_cache.ttl,
            "cache_info": {
                "hits": getattr(prompt_cache, 'hits', 0),
                "misses": getattr(prompt_cache, 'misses', 0)
            }
        }


def clear_prompt_cache() -> None:
    """Clear the prompt cache."""
    with prompt_cache_lock:
        prompt_cache.clear()
        logger.info("Prompt cache cleared")


def get_context_cache_stats() -> Dict[str, Any]:
    """
    Get context cache statistics for monitoring.
    
    Returns:
        Dictionary with cache statistics
    """
    with context_cache_lock:
        return {
            "cache_size": len(context_cache),
            "max_size": context_cache.maxsize,
            "ttl_seconds": context_cache.ttl,
            "cache_info": {
                "hits": getattr(context_cache, 'hits', 0),
                "misses": getattr(context_cache, 'misses', 0)
            }
        }


def clear_context_cache() -> None:
    """Clear the context cache."""
    with context_cache_lock:
        context_cache.clear()
        logger.info("Context cache cleared")


def get_all_bedrock_cache_stats() -> Dict[str, Any]:
    """
    Get comprehensive cache statistics for all Bedrock caches.
    
    Returns:
        Dictionary with all cache statistics
    """
    return {
        "guardrail_cache": get_guardrail_cache_stats(),
        "prompt_cache": get_prompt_cache_stats(),
        "context_cache": get_context_cache_stats(),
        "total_cached_items": (
            len(guardrail_cache) + 
            len(prompt_cache) + 
            len(context_cache)
        )
    }


def clear_all_bedrock_caches() -> None:
    """Clear all Bedrock-related caches."""
    clear_guardrail_cache()
    clear_prompt_cache()
    clear_context_cache()
    logger.info("All Bedrock caches cleared")
