"""
Standardized logging configuration for the chatbot RAG solution.
"""
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import structlog


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add AWS Lambda context if available
        if hasattr(record, 'aws_request_id'):
            log_entry["aws_request_id"] = record.aws_request_id
        
        return json.dumps(log_entry, default=str)


class ContextFilter(logging.Filter):
    """Filter to add context information to log records."""
    
    def __init__(self, service_name: str = "chatbot-rag"):
        super().__init__()
        self.service_name = service_name
        self.aws_request_id = None
        self.user_id = None
        self.session_id = None
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context information to log record."""
        record.service_name = self.service_name
        
        if self.aws_request_id:
            record.aws_request_id = self.aws_request_id
        
        if self.user_id:
            record.user_id = self.user_id
        
        if self.session_id:
            record.session_id = self.session_id
        
        return True
    
    def set_aws_context(self, aws_request_id: str):
        """Set AWS Lambda request ID."""
        self.aws_request_id = aws_request_id
    
    def set_user_context(self, user_id: str, session_id: Optional[str] = None):
        """Set user context."""
        self.user_id = user_id
        self.session_id = session_id


class SecurityFilter(logging.Filter):
    """Filter to remove sensitive information from logs."""
    
    SENSITIVE_PATTERNS = [
        'password', 'secret', 'key', 'token', 'credential',
        'auth', 'private', 'confidential', 'ssn', 'credit',
        'card', 'api_key', 'access_token', 'refresh_token'
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Remove sensitive information from log messages."""
        message = record.getMessage().lower()
        
        # Check if message contains sensitive patterns
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in message:
                # Replace the entire message with a warning
                record.msg = f"[REDACTED] Log message contained sensitive information: {pattern}"
                record.args = ()
                break
        
        return True


def setup_logging(
    service_name: str = "chatbot-rag",
    log_level: str = None,
    enable_json: bool = None,
    enable_structlog: bool = True
) -> logging.Logger:
    """
    Set up standardized logging configuration.
    
    Args:
        service_name: Name of the service for logging context
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_json: Enable JSON formatting (auto-detected for Lambda)
        enable_structlog: Enable structured logging with structlog
        
    Returns:
        Configured logger instance
    """
    # Determine environment
    is_lambda = bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    is_development = os.environ.get('ENVIRONMENT', 'production').lower() == 'development'
    
    # Set defaults based on environment
    if log_level is None:
        log_level = 'DEBUG' if is_development else 'INFO'
    
    if enable_json is None:
        enable_json = is_lambda  # Use JSON in Lambda, human-readable locally
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter
    if enable_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    
    # Add filters
    context_filter = ContextFilter(service_name)
    security_filter = SecurityFilter()
    
    handler.addFilter(context_filter)
    handler.addFilter(security_filter)
    
    # Add handler to root logger
    root_logger.addHandler(handler)
    
    # Configure specific loggers
    _configure_aws_loggers()
    _configure_third_party_loggers()
    
    # Set up structlog if enabled
    if enable_structlog:
        _setup_structlog(enable_json)
    
    # Get service logger
    logger = logging.getLogger(service_name)
    
    # Store context filter for later use
    logger.context_filter = context_filter
    
    logger.info(f"Logging configured for {service_name}", extra={
        'extra_fields': {
            'log_level': log_level,
            'json_enabled': enable_json,
            'structlog_enabled': enable_structlog,
            'is_lambda': is_lambda,
            'is_development': is_development
        }
    })
    
    return logger


def _configure_aws_loggers():
    """Configure AWS SDK loggers."""
    # Reduce boto3/botocore verbosity
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Keep important AWS events at INFO level
    logging.getLogger('botocore.credentials').setLevel(logging.INFO)
    logging.getLogger('botocore.auth').setLevel(logging.INFO)


def _configure_third_party_loggers():
    """Configure third-party library loggers."""
    # Reduce verbosity of common libraries
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Keep important events
    logging.getLogger('cachetools').setLevel(logging.INFO)


def _setup_structlog(json_enabled: bool):
    """Set up structlog for structured logging."""
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if json_enabled:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the standard configuration.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_lambda_context(logger: logging.Logger, context: Any):
    """
    Set AWS Lambda context for logging.
    
    Args:
        logger: Logger instance
        context: AWS Lambda context object
    """
    if hasattr(logger, 'context_filter'):
        logger.context_filter.set_aws_context(context.aws_request_id)


def set_user_context(logger: logging.Logger, user_id: str, session_id: Optional[str] = None):
    """
    Set user context for logging.
    
    Args:
        logger: Logger instance
        user_id: User identifier
        session_id: Session identifier
    """
    if hasattr(logger, 'context_filter'):
        logger.context_filter.set_user_context(user_id, session_id)


def log_performance(logger: logging.Logger, operation: str, duration_ms: float, **kwargs):
    """
    Log performance metrics.
    
    Args:
        logger: Logger instance
        operation: Operation name
        duration_ms: Duration in milliseconds
        **kwargs: Additional context
    """
    logger.info(f"Performance: {operation}", extra={
        'extra_fields': {
            'operation': operation,
            'duration_ms': duration_ms,
            'performance_metric': True,
            **kwargs
        }
    })


def log_security_event(logger: logging.Logger, event_type: str, details: Dict[str, Any]):
    """
    Log security events.
    
    Args:
        logger: Logger instance
        event_type: Type of security event
        details: Event details (sensitive info will be filtered)
    """
    logger.warning(f"Security event: {event_type}", extra={
        'extra_fields': {
            'security_event': True,
            'event_type': event_type,
            **details
        }
    })


def log_business_event(logger: logging.Logger, event_type: str, details: Dict[str, Any]):
    """
    Log business events for analytics.
    
    Args:
        logger: Logger instance
        event_type: Type of business event
        details: Event details
    """
    logger.info(f"Business event: {event_type}", extra={
        'extra_fields': {
            'business_event': True,
            'event_type': event_type,
            **details
        }
    })


# Global logger instance
logger = setup_logging()


# Convenience functions for common logging patterns
def log_api_request(endpoint: str, method: str, user_id: Optional[str] = None):
    """Log API request."""
    logger.info(f"API request: {method} {endpoint}", extra={
        'extra_fields': {
            'api_request': True,
            'endpoint': endpoint,
            'method': method,
            'user_id': user_id
        }
    })


def log_api_response(endpoint: str, status_code: int, duration_ms: float):
    """Log API response."""
    logger.info(f"API response: {endpoint} -> {status_code}", extra={
        'extra_fields': {
            'api_response': True,
            'endpoint': endpoint,
            'status_code': status_code,
            'duration_ms': duration_ms
        }
    })


def log_cache_event(event_type: str, cache_type: str, key: str, hit: bool = None):
    """Log cache events."""
    logger.debug(f"Cache {event_type}: {cache_type}", extra={
        'extra_fields': {
            'cache_event': True,
            'event_type': event_type,
            'cache_type': cache_type,
            'cache_key_hash': hash(key) % 10000,  # Hash for privacy
            'cache_hit': hit
        }
    })


def log_document_processing(document_id: str, operation: str, status: str, **kwargs):
    """Log document processing events."""
    logger.info(f"Document processing: {operation} -> {status}", extra={
        'extra_fields': {
            'document_processing': True,
            'document_id': document_id,
            'operation': operation,
            'status': status,
            **kwargs
        }
    })


def log_vector_operation(operation: str, index_name: str, vector_count: int = None, **kwargs):
    """Log vector operations."""
    logger.info(f"Vector operation: {operation}", extra={
        'extra_fields': {
            'vector_operation': True,
            'operation': operation,
            'index_name': index_name,
            'vector_count': vector_count,
            **kwargs
        }
    })


def log_bedrock_request(model_id: str, operation: str, token_count: int = None, **kwargs):
    """Log Bedrock API requests."""
    logger.info(f"Bedrock request: {operation} with {model_id}", extra={
        'extra_fields': {
            'bedrock_request': True,
            'model_id': model_id,
            'operation': operation,
            'token_count': token_count,
            **kwargs
        }
    })
