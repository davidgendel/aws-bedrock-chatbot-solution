"""
Configuration validation utilities for the chatbot RAG solution.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""
    pass


class ConfigValidator:
    """Configuration validator for the chatbot RAG solution."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = {}
        self.errors = []
        self.warnings = []
    
    def load_config(self) -> bool:
        """Load configuration from file."""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                self.errors.append(f"Configuration file {self.config_path} not found")
                return False
            
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            
            return True
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {self.config_path}: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading configuration: {e}")
            return False
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all configuration sections.
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        if not self.load_config():
            return False, self.errors, self.warnings
        
        # Validate each section
        self._validate_basic_config()
        self._validate_region()
        self._validate_lambda_config()
        self._validate_api_config()
        self._validate_s3_vectors_config()
        self._validate_widget_config()
        self._validate_bedrock_config()
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_basic_config(self):
        """Validate basic configuration fields."""
        # No longer validating businessName, businessType, useCase as they're not used
        pass
    
    def _validate_region(self):
        """Validate AWS region configuration."""
        region = self.config.get("region")
        if not region:
            self.errors.append("region is required")
            return
        
        # Valid AWS regions (subset of most common ones)
        valid_regions = [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
            "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
            "ca-central-1", "sa-east-1"
        ]
        
        if region not in valid_regions:
            self.warnings.append(f"Region '{region}' may not support all required services")
        
        # Check region format
        if not re.match(r'^[a-z]{2}-[a-z]+-\d+$', region):
            self.errors.append(f"Invalid region format: {region}")
    
    def _validate_lambda_config(self):
        """Validate Lambda configuration."""
        lambda_config = self.config.get("lambda", {})
        chatbot_config = lambda_config.get("chatbot", {})
        
        # Provisioned concurrency validation
        pc_config = chatbot_config.get("provisionedConcurrency", {})
        if pc_config.get("enabled", False):
            concurrent_executions = pc_config.get("concurrentExecutions", 1)
            if not isinstance(concurrent_executions, int) or concurrent_executions < 1:
                self.errors.append("lambda.chatbot.provisionedConcurrency.concurrentExecutions must be a positive integer")
            elif concurrent_executions > 10:
                self.warnings.append("High provisioned concurrency may increase costs significantly")
    
    def _validate_api_config(self):
        """Validate API configuration."""
        api_config = self.config.get("api", {})
        throttling = api_config.get("throttling", {})
        
        # Rate limiting validation
        rate_per_minute = throttling.get("ratePerMinute", 10)
        if not isinstance(rate_per_minute, int) or rate_per_minute < 1:
            self.errors.append("api.throttling.ratePerMinute must be a positive integer")
        elif rate_per_minute > 1000:
            self.warnings.append("Very high rate limit may impact costs and security")
        
        rate_per_hour = throttling.get("ratePerHour", 100)
        if not isinstance(rate_per_hour, int) or rate_per_hour < 1:
            self.errors.append("api.throttling.ratePerHour must be a positive integer")
        elif rate_per_hour < rate_per_minute:
            self.errors.append("api.throttling.ratePerHour should be >= ratePerMinute")
    
    def _validate_s3_vectors_config(self):
        """Validate S3 Vectors configuration."""
        s3_vectors_config = self.config.get("s3Vectors", {})
        
        # Index name validation
        index_name = s3_vectors_config.get("indexName", "")
        if index_name and not re.match(r'^[a-zA-Z0-9\-_]+$', index_name):
            self.errors.append("s3Vectors.indexName must contain only alphanumeric characters, hyphens, and underscores")
        
        # Dimensions validation
        dimensions = s3_vectors_config.get("dimensions")
        if dimensions is not None:
            if not isinstance(dimensions, int) or dimensions <= 0:
                self.errors.append("s3Vectors.dimensions must be a positive integer")
            elif dimensions != 1536:
                self.warnings.append("s3Vectors.dimensions should be 1536 for Amazon Titan embeddings")
        
        # Similarity metric validation
        similarity_metric = s3_vectors_config.get("similarityMetric", "")
        valid_metrics = ["COSINE", "EUCLIDEAN", "DOT_PRODUCT"]
        if similarity_metric and similarity_metric not in valid_metrics:
            self.errors.append(f"s3Vectors.similarityMetric must be one of: {', '.join(valid_metrics)}")
    
    
    def _validate_widget_config(self):
        """Validate widget configuration."""
        widget_config = self.config.get("widget", {})
        default_theme = widget_config.get("defaultTheme", {})
        
        # Color validation
        primary_color = default_theme.get("primaryColor", "")
        if primary_color and not re.match(r'^#[0-9a-fA-F]{6}$', primary_color):
            self.errors.append("widget.defaultTheme.primaryColor must be a valid hex color (e.g., #4287f5)")
        
        secondary_color = default_theme.get("secondaryColor", "")
        if secondary_color and not re.match(r'^#[0-9a-fA-F]{6}$', secondary_color):
            self.errors.append("widget.defaultTheme.secondaryColor must be a valid hex color")
        
        # Font validation
        font_family = default_theme.get("fontFamily", "")
        if font_family and len(font_family) > 200:
            self.errors.append("widget.defaultTheme.fontFamily is too long")
        
        # Font size validation
        font_size = default_theme.get("fontSize", "")
        if font_size and not re.match(r'^\d+px$', font_size):
            self.warnings.append("widget.defaultTheme.fontSize should be in px format (e.g., '16px')")
    
    def _validate_bedrock_config(self):
        """Validate Bedrock configuration."""
        bedrock_config = self.config.get("bedrock", {})
        
        # Model ID validation
        model_id = bedrock_config.get("modelId", "")
        if not model_id:
            self.errors.append("bedrock.modelId is required")
        elif not model_id.startswith("amazon."):
            self.warnings.append("bedrock.modelId should typically start with 'amazon.' for Amazon models")
        
        # Guardrails validation
        guardrails = bedrock_config.get("guardrails", {})
        if guardrails.get("createDefault", False):
            self._validate_guardrail_config(guardrails.get("defaultGuardrailConfig", {}))
    
    def _validate_guardrail_config(self, guardrail_config: Dict[str, Any]):
        """Validate guardrail configuration."""
        # Name validation
        name = guardrail_config.get("name", "")
        if not name:
            self.errors.append("bedrock.guardrails.defaultGuardrailConfig.name is required")
        elif len(name) > 50:
            self.errors.append("Guardrail name is too long (max 50 characters)")
        
        # Content policy validation
        content_policy = guardrail_config.get("contentPolicyConfig", {})
        filters = content_policy.get("filters", [])
        
        valid_filter_types = ["SEXUAL", "VIOLENCE", "HATE", "INSULTS", "MISCONDUCT"]
        valid_strengths = ["NONE", "LOW", "MEDIUM", "HIGH"]
        
        for filter_config in filters:
            filter_type = filter_config.get("type", "")
            if filter_type not in valid_filter_types:
                self.errors.append(f"Invalid content filter type: {filter_type}")
            
            strength = filter_config.get("strength", "")
            if strength not in valid_strengths:
                self.errors.append(f"Invalid filter strength: {strength}")
        
        # Word policy validation
        word_policy = guardrail_config.get("wordPolicyConfig", {})
        managed_word_lists = word_policy.get("managedWordLists", [])
        
        valid_word_list_types = ["PROFANITY"]
        for word_list in managed_word_lists:
            list_type = word_list.get("type", "")
            if list_type not in valid_word_list_types:
                self.errors.append(f"Invalid managed word list type: {list_type}")
        
        # Note: PII and topic restrictions removed for cost optimization
    
    def get_validation_summary(self) -> str:
        """Get a formatted validation summary."""
        summary = []
        
        if self.errors:
            summary.append("❌ ERRORS:")
            for error in self.errors:
                summary.append(f"  • {error}")
        
        if self.warnings:
            summary.append("⚠️  WARNINGS:")
            for warning in self.warnings:
                summary.append(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            summary.append("✅ Configuration is valid!")
        
        return "\n".join(summary)


def validate_config(config_path: str = "config.json") -> Tuple[bool, str]:
    """
    Validate configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Tuple of (is_valid, summary_message)
    """
    validator = ConfigValidator(config_path)
    is_valid, errors, warnings = validator.validate_all()
    summary = validator.get_validation_summary()
    
    return is_valid, summary


if __name__ == "__main__":
    # Command line usage
    import sys
    
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    is_valid, summary = validate_config(config_file)
    
    print(summary)
    sys.exit(0 if is_valid else 1)
