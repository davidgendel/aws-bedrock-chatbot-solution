"""
Logging utilities for the chatbot RAG solution.
This module provides backward compatibility while using the new standardized logging.
"""
import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

try:
    from .logging_config import (
        setup_logging,
        get_logger,
        set_lambda_context,
        set_user_context,
        log_performance,
        log_security_event,
        log_business_event,
        log_api_request,
        log_api_response,
        log_cache_event,
        log_document_processing,
        log_vector_operation,
        log_bedrock_request
    )
except ImportError:
    from logging_config import (
        setup_logging,
        get_logger,
        set_lambda_context,
        set_user_context,
        log_performance,
        log_security_event,
        log_business_event,
        log_api_request,
        log_api_response,
        log_cache_event,
        log_document_processing,
        log_vector_operation,
        log_bedrock_request
    )

# Initialize standardized logging
logger = setup_logging("chatbot-rag")


def get_chatbot_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance with chatbot-specific configuration.
    
    Args:
        name: Logger name (defaults to calling module)
        
    Returns:
        Configured logger instance
    """
    if name is None:
        # Get the calling module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'chatbot-rag')
    
    return get_logger(name)


def configure_lambda_logging(context: Any) -> logging.Logger:
    """
    Configure logging for AWS Lambda environment.
    
    Args:
        context: AWS Lambda context object
        
    Returns:
        Configured logger instance
    """
    lambda_logger = get_chatbot_logger("lambda")
    set_lambda_context(lambda_logger, context)
    
    lambda_logger.info("Lambda function started", extra={
        'extra_fields': {
            'function_name': context.function_name,
            'function_version': context.function_version,
            'memory_limit': context.memory_limit_in_mb,
            'remaining_time': context.get_remaining_time_in_millis()
        }
    })
    
    return lambda_logger


@contextmanager
def log_execution_time(operation_name: str, logger_instance: logging.Logger = None):
    """
    Context manager to log execution time of operations.
    
    Args:
        operation_name: Name of the operation being timed
        logger_instance: Logger to use (defaults to module logger)
    """
    if logger_instance is None:
        logger_instance = logger
    
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        log_performance(logger_instance, operation_name, duration_ms)


def log_function_call(func: Callable) -> Callable:
    """
    Decorator to log function calls with execution time.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_logger = get_chatbot_logger(func.__module__)
        
        # Log function entry
        func_logger.debug(f"Entering function: {func.__name__}", extra={
            'extra_fields': {
                'function_call': True,
                'function_name': func.__name__,
                'module': func.__module__,
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            }
        })
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            
            # Log successful completion
            duration_ms = (time.time() - start_time) * 1000
            func_logger.debug(f"Function completed: {func.__name__}", extra={
                'extra_fields': {
                    'function_completion': True,
                    'function_name': func.__name__,
                    'duration_ms': duration_ms,
                    'success': True
                }
            })
            
            return result
            
        except Exception as e:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            func_logger.error(f"Function failed: {func.__name__}: {str(e)}", extra={
                'extra_fields': {
                    'function_error': True,
                    'function_name': func.__name__,
                    'duration_ms': duration_ms,
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            })
            raise
    
    return wrapper


def log_user_interaction(user_id: str, action: str, details: Dict[str, Any] = None):
    """
    Log user interactions for analytics.
    
    Args:
        user_id: User identifier
        action: Action performed
        details: Additional details
    """
    interaction_details = {
        'user_id': user_id,
        'action': action,
        **(details or {})
    }
    
    log_business_event(logger, 'user_interaction', interaction_details)


def log_chat_message(user_id: str, message_length: int, response_length: int, 
                    cached: bool, model_used: str, processing_time_ms: float):
    """
    Log chat message interactions.
    
    Args:
        user_id: User identifier
        message_length: Length of user message
        response_length: Length of bot response
        cached: Whether response was cached
        model_used: AI model used
        processing_time_ms: Processing time in milliseconds
    """
    log_business_event(logger, 'chat_message', {
        'user_id': user_id,
        'message_length': message_length,
        'response_length': response_length,
        'cached': cached,
        'model_used': model_used,
        'processing_time_ms': processing_time_ms
    })


def log_document_upload(user_id: str, document_name: str, document_size: int, 
                       document_type: str, processing_status: str):
    """
    Log document upload events.
    
    Args:
        user_id: User identifier
        document_name: Name of uploaded document
        document_size: Size in bytes
        document_type: Document type/format
        processing_status: Processing status
    """
    log_document_processing(document_name, 'upload', processing_status,
                           user_id=user_id,
                           document_size=document_size,
                           document_type=document_type)


def log_rate_limit_event(user_id: str, endpoint: str, limit_type: str):
    """
    Log rate limiting events.
    
    Args:
        user_id: User identifier
        endpoint: API endpoint
        limit_type: Type of limit hit
    """
    log_security_event(logger, 'rate_limit_exceeded', {
        'user_id': user_id,
        'endpoint': endpoint,
        'limit_type': limit_type
    })


def log_guardrail_event(user_id: str, message_hash: str, blocked: bool, reasons: list):
    """
    Log content moderation events.
    
    Args:
        user_id: User identifier
        message_hash: Hash of the message (for privacy)
        blocked: Whether content was blocked
        reasons: Reasons for blocking
    """
    log_security_event(logger, 'content_moderation', {
        'user_id': user_id,
        'message_hash': message_hash,
        'blocked': blocked,
        'reasons': reasons
    })


def log_error_with_context(error: Exception, context: Dict[str, Any] = None, 
                          logger_instance: logging.Logger = None):
    """
    Log errors with additional context.
    
    Args:
        error: Exception that occurred
        context: Additional context information
        logger_instance: Logger to use (defaults to module logger)
    """
    if logger_instance is None:
        logger_instance = logger
    
    error_context = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        **(context or {})
    }
    
    logger_instance.error(f"Error occurred: {type(error).__name__}", 
                         extra={'extra_fields': error_context},
                         exc_info=True)


def log_aws_service_call(service: str, operation: str, success: bool, 
                        duration_ms: float, error: str = None):
    """
    Log AWS service calls.
    
    Args:
        service: AWS service name
        operation: Operation performed
        success: Whether call was successful
        duration_ms: Duration in milliseconds
        error: Error message if failed
    """
    logger.info(f"AWS {service} call: {operation}", extra={
        'extra_fields': {
            'aws_service_call': True,
            'service': service,
            'operation': operation,
            'success': success,
            'duration_ms': duration_ms,
            'error': error
        }
    })


def log_cost_metric(service: str, operation: str, estimated_cost: float, 
                   units: str, quantity: int):
    """
    Log cost-related metrics.
    
    Args:
        service: AWS service name
        operation: Operation performed
        estimated_cost: Estimated cost in USD
        units: Cost units (requests, tokens, etc.)
        quantity: Quantity of units
    """
    logger.info(f"Cost metric: {service} {operation}", extra={
        'extra_fields': {
            'cost_metric': True,
            'service': service,
            'operation': operation,
            'estimated_cost_usd': estimated_cost,
            'units': units,
            'quantity': quantity
        }
    })


# Backward compatibility functions
def setup_lambda_logging(context: Any) -> logging.Logger:
    """Backward compatibility function."""
    return configure_lambda_logging(context)


def get_structured_logger(name: str) -> logging.Logger:
    """Backward compatibility function."""
    return get_chatbot_logger(name)


# Export commonly used functions
__all__ = [
    'get_chatbot_logger',
    'configure_lambda_logging',
    'log_execution_time',
    'log_function_call',
    'log_user_interaction',
    'log_chat_message',
    'log_document_upload',
    'log_rate_limit_event',
    'log_guardrail_event',
    'log_error_with_context',
    'log_aws_service_call',
    'log_cost_metric',
    'log_api_request',
    'log_api_response',
    'log_cache_event',
    'log_document_processing',
    'log_vector_operation',
    'log_bedrock_request',
    'logger'
]
