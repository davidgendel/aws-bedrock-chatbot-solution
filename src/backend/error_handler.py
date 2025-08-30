"""
Centralized error handling utilities for consistent error management.
"""
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Standard error types for consistent categorization."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    BEDROCK_ERROR = "BEDROCK_ERROR"
    WEBSOCKET_ERROR = "WEBSOCKET_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    SIGNING_ERROR = "SIGNING_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


class ChatbotError(Exception):
    """Base exception class for all chatbot-related errors."""
    
    def __init__(
        self, 
        message: str, 
        error_type: ErrorType = ErrorType.INTERNAL_SERVER_ERROR,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_type = error_type
        self.original_error = original_error
        self.context = context or {}
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)


class SigningError(ChatbotError):
    """Exception raised for request signing errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorType.SIGNING_ERROR, original_error, context)


class DatabaseError(ChatbotError):
    """Exception raised for database-related errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorType.DATABASE_ERROR, original_error, context)


class BedrockError(ChatbotError):
    """Exception raised for Bedrock-related errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorType.BEDROCK_ERROR, original_error, context)


class ValidationError(ChatbotError):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorType.VALIDATION_ERROR, original_error, context)


class WebSocketError(ChatbotError):
    """Exception raised for WebSocket-related errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorType.WEBSOCKET_ERROR, original_error, context)


def handle_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    log_level: int = logging.ERROR
) -> ChatbotError:
    """
    Centralized error handling function.
    
    Args:
        error: The original exception
        context: Additional context information
        log_level: Logging level for the error
        
    Returns:
        Standardized ChatbotError
    """
    # If it's already a ChatbotError, just log and return
    if isinstance(error, ChatbotError):
        logger.log(log_level, f"[{error.error_type.value}] {error.message}", extra={
            "error_type": error.error_type.value,
            "context": error.context,
            "original_error": str(error.original_error) if error.original_error else None
        })
        return error
    
    # Determine error type based on exception type and message
    error_type = _classify_error(error)
    
    # Create context for server-side logging only (never sent to client)
    error_context = context or {}
    error_context.update({
        "exception_type": type(error).__name__,
        "traceback": traceback.format_exc()
    })
    
    # Create user-friendly message (never expose technical details)
    user_message = _get_user_friendly_message(error_type)
    
    # Create standardized error
    chatbot_error = ChatbotError(
        message=user_message,  # Use friendly message, not raw error
        error_type=error_type,
        original_error=error,
        context=error_context
    )
    
    # Log the error with full technical details (server-side only)
    logger.log(log_level, f"[{error_type.value}] {str(error)}", extra={
        "error_type": error_type.value,
        "context": error_context,
        "original_error": str(error),
        "traceback": traceback.format_exc()
    })
    
    return chatbot_error


def _classify_error(error: Exception) -> ErrorType:
    """Classify error based on exception type and message."""
    error_name = type(error).__name__
    error_message = str(error).lower()
    
    # Database-related errors
    if any(db_error in error_name for db_error in ['psycopg2', 'DatabaseError', 'OperationalError', 'IntegrityError']):
        return ErrorType.DATABASE_ERROR
    
    # Bedrock/AWS-related errors
    if any(aws_error in error_name for aws_error in ['ClientError', 'BotoCoreError', 'NoCredentialsError']):
        return ErrorType.BEDROCK_ERROR
    
    # Validation errors
    if 'validation' in error_message or 'invalid' in error_message:
        return ErrorType.VALIDATION_ERROR
    
    # Rate limiting
    if any(rate_term in error_message for rate_term in ['throttl', 'rate limit', 'too many requests']):
        return ErrorType.RATE_LIMIT_ERROR
    
    # Authentication/Authorization/Signing
    if any(auth_term in error_message for auth_term in ['unauthorized', 'forbidden', 'access denied', 'signature', 'credential']):
        if any(signing_term in error_message.lower() for signing_term in ['signature', 'signing', 'sigv4']):
            return ErrorType.SIGNING_ERROR
        return ErrorType.AUTHORIZATION_ERROR
    
    # Default to internal server error
    return ErrorType.INTERNAL_SERVER_ERROR


def create_error_response(
    error: Union[Exception, ChatbotError],
    status_code: Optional[int] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create standardized error response for API endpoints.
    
    Args:
        error: The error to convert to response
        status_code: HTTP status code (auto-determined if not provided)
        request_id: Request ID for tracking
        
    Returns:
        Standardized error response dictionary
    """
    # Handle the error through centralized handler
    if not isinstance(error, ChatbotError):
        error = handle_error(error)
    
    # Determine status code if not provided
    if status_code is None:
        status_code = _get_status_code_for_error_type(error.error_type)
    
    # Create user-friendly error message (never expose technical details)
    user_message = _get_user_friendly_message(error.error_type)
    
    error_response = {
        "success": False,
        "error": {
            "type": error.error_type.value,
            "message": user_message,
            "code": status_code,
            "timestamp": error.timestamp
        }
    }
    
    # Add request ID if provided
    if request_id:
        error_response["error"]["requestId"] = request_id
    
    # Never expose context, traceback, or technical details to clients
    
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(error_response)
    }


def _get_user_friendly_message(error_type: ErrorType) -> str:
    """Get user-friendly error message that doesn't expose technical details."""
    friendly_messages = {
        ErrorType.VALIDATION_ERROR: "Please check your input and try again.",
        ErrorType.AUTHENTICATION_ERROR: "Authentication failed. Please check your credentials.",
        ErrorType.AUTHORIZATION_ERROR: "You don't have permission to perform this action.",
        ErrorType.RATE_LIMIT_ERROR: "Too many requests. Please wait a moment and try again.",
        ErrorType.DATABASE_ERROR: "We're experiencing technical difficulties. Please try again later.",
        ErrorType.BEDROCK_ERROR: "AI service is temporarily unavailable. Please try again later.",
        ErrorType.WEBSOCKET_ERROR: "Connection error occurred. Please refresh and try again.",
        ErrorType.EXTERNAL_SERVICE_ERROR: "External service is temporarily unavailable. Please try again later.",
        ErrorType.CONFIGURATION_ERROR: "Service configuration error. Please contact support.",
        ErrorType.SIGNING_ERROR: "Request authentication failed. Please try again.",
        ErrorType.INTERNAL_SERVER_ERROR: "An unexpected error occurred. Please try again later."
    }
    return friendly_messages.get(error_type, "An unexpected error occurred. Please try again later.")


def _get_status_code_for_error_type(error_type: ErrorType) -> int:
    """Get appropriate HTTP status code for error type."""
    status_map = {
        ErrorType.VALIDATION_ERROR: 400,
        ErrorType.AUTHENTICATION_ERROR: 401,
        ErrorType.AUTHORIZATION_ERROR: 403,
        ErrorType.RATE_LIMIT_ERROR: 429,
        ErrorType.DATABASE_ERROR: 500,
        ErrorType.BEDROCK_ERROR: 502,
        ErrorType.WEBSOCKET_ERROR: 500,
        ErrorType.EXTERNAL_SERVICE_ERROR: 502,
        ErrorType.CONFIGURATION_ERROR: 500,
        ErrorType.INTERNAL_SERVER_ERROR: 500,
    }
    return status_map.get(error_type, 500)


def create_success_response(data: Any, status_code: int = 200) -> Dict[str, Any]:
    """
    Create standardized success response.
    
    Args:
        data: Response data
        status_code: HTTP status code
        
    Returns:
        Success response dictionary
    """
    success_response = {
        "success": True,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(success_response)
    }
