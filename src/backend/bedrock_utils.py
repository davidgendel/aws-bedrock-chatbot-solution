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


def get_guardrail_cache_key(text: str) -> str:
    """Generate cache key for guardrail results."""
    return hashlib.md5(text.encode()).hexdigest()


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
        logger.debug(f"Skipping guardrails for short input: {len(user_input)} characters")
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
        logger.debug(f"Skipping guardrails for document-specific query")
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
            logger.debug("Guardrail result found in cache")
            cached_result = guardrail_cache[cache_key].copy()
            cached_result["cached"] = True
            return cached_result
    
    # Apply guardrails if not in cache
    result = apply_guardrails(text, guardrail_id, guardrail_version)
    result["cached"] = False
    
    # Cache the result
    with guardrail_cache_lock:
        guardrail_cache[cache_key] = result.copy()
    
    logger.debug("Guardrail result cached for future use")
    return result


def get_bedrock_client() -> Any:
    """Get Bedrock runtime client."""
    return boto3.client("bedrock-runtime", region_name=get_aws_region())


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
        logger.error(f"Error generating embeddings: {e}")
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
        logger.error(f"Error generating response: {e}")
        raise


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
        logger.error(f"Error generating streaming response: {e}")
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
        if not guardrail_id:
            guardrail_id = os.environ.get("GUARDRAIL_ID")
        if not guardrail_version:
            guardrail_version = os.environ.get("GUARDRAIL_VERSION")
        
        # If no guardrail configured, return unblocked
        if not guardrail_id:
            logger.info("No guardrail configured, allowing content")
            return {
                "blocked": False,
                "reasons": []
            }
        
        bedrock_client = boto3.client("bedrock-runtime", region_name=get_aws_region())
        
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
                    reasons.append(output["text"])
        
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
            logger.error(f"Error applying guardrails: {e}")
            # In case of error, allow content but log the issue
            return {
                "blocked": False,
                "reasons": [f"Guardrail error: {error_code}"]
            }
    except Exception as e:
        logger.error(f"Unexpected error applying guardrails: {e}")
        # In case of error, allow content but log the issue
        return {
            "blocked": False,
            "reasons": [f"Guardrail system error: {str(e)}"]
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
