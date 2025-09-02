"""
Tests for config_validator.py - Configuration validation functionality.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

# Add backend path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from config_validator import ConfigValidator, ConfigValidationError, validate_config


class TestConfigValidator(unittest.TestCase):
    """Test configuration validator functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.valid_config = {
            "region": "us-east-1",
            "lambda": {
                "chatbot": {
                    "provisionedConcurrency": {
                        "enabled": True,
                        "concurrentExecutions": 2
                    }
                }
            },
            "api": {
                "throttling": {
                    "ratePerMinute": 50,
                    "ratePerHour": 500
                }
            },
            "s3Vectors": {
                "indexName": "test-index",
                "dimensions": 1536,
                "similarityMetric": "COSINE"
            },
            "widget": {
                "defaultTheme": {
                    "primaryColor": "#4287f5",
                    "secondaryColor": "#ffffff",
                    "fontFamily": "Arial, sans-serif",
                    "fontSize": "16px"
                }
            },
            "bedrock": {
                "modelId": "amazon.nova-lite-v1:0",
                "guardrails": {
                    "createDefault": True,
                    "defaultGuardrailConfig": {
                        "name": "test-guardrail",
                        "contentPolicyConfig": {
                            "filters": [
                                {"type": "SEXUAL", "strength": "HIGH"},
                                {"type": "VIOLENCE", "strength": "MEDIUM"}
                            ]
                        },
                        "wordPolicyConfig": {
                            "managedWordLists": [
                                {"type": "PROFANITY"}
                            ]
                        }
                    }
                }
            }
        }
    
    def test_load_config_success(self):
        """Test successful config loading."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.valid_config, f)
            config_path = f.name
        
        try:
            validator = ConfigValidator(config_path)
            result = validator.load_config()
            self.assertTrue(result)
            self.assertEqual(validator.config, self.valid_config)
        finally:
            os.unlink(config_path)
    
    def test_load_config_file_not_found(self):
        """Test config loading with missing file."""
        validator = ConfigValidator("nonexistent.json")
        result = validator.load_config()
        self.assertFalse(result)
        self.assertIn("not found", validator.errors[0])
    
    def test_load_config_invalid_json(self):
        """Test config loading with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')
            config_path = f.name
        
        try:
            validator = ConfigValidator(config_path)
            result = validator.load_config()
            self.assertFalse(result)
            self.assertIn("Invalid JSON", validator.errors[0])
        finally:
            os.unlink(config_path)
    
    def test_validate_region_valid(self):
        """Test valid region validation."""
        validator = ConfigValidator()
        validator.config = {"region": "us-east-1"}
        validator._validate_region()
        self.assertEqual(len(validator.errors), 0)
    
    def test_validate_region_missing(self):
        """Test missing region validation."""
        validator = ConfigValidator()
        validator.config = {}
        validator._validate_region()
        self.assertIn("region is required", validator.errors)
    
    def test_validate_region_invalid_format(self):
        """Test invalid region format."""
        validator = ConfigValidator()
        validator.config = {"region": "invalid-region"}
        validator._validate_region()
        self.assertIn("Invalid region format", validator.errors[0])
    
    def test_validate_region_uncommon(self):
        """Test uncommon region warning."""
        validator = ConfigValidator()
        validator.config = {"region": "ap-south-1"}
        validator._validate_region()
        self.assertIn("may not support all required services", validator.warnings[0])
    
    def test_validate_lambda_config_valid(self):
        """Test valid lambda configuration."""
        validator = ConfigValidator()
        validator.config = {
            "lambda": {
                "chatbot": {
                    "provisionedConcurrency": {
                        "enabled": True,
                        "concurrentExecutions": 5
                    }
                }
            }
        }
        validator._validate_lambda_config()
        self.assertEqual(len(validator.errors), 0)
    
    def test_validate_lambda_config_invalid_concurrency(self):
        """Test invalid provisioned concurrency."""
        validator = ConfigValidator()
        validator.config = {
            "lambda": {
                "chatbot": {
                    "provisionedConcurrency": {
                        "enabled": True,
                        "concurrentExecutions": 0
                    }
                }
            }
        }
        validator._validate_lambda_config()
        self.assertIn("must be a positive integer", validator.errors[0])
    
    def test_validate_lambda_config_high_concurrency_warning(self):
        """Test high concurrency warning."""
        validator = ConfigValidator()
        validator.config = {
            "lambda": {
                "chatbot": {
                    "provisionedConcurrency": {
                        "enabled": True,
                        "concurrentExecutions": 15
                    }
                }
            }
        }
        validator._validate_lambda_config()
        self.assertIn("may increase costs significantly", validator.warnings[0])
    
    def test_validate_api_config_valid(self):
        """Test valid API configuration."""
        validator = ConfigValidator()
        validator.config = {
            "api": {
                "throttling": {
                    "ratePerMinute": 100,
                    "ratePerHour": 1000
                }
            }
        }
        validator._validate_api_config()
        self.assertEqual(len(validator.errors), 0)
    
    def test_validate_api_config_invalid_rates(self):
        """Test invalid API rates."""
        validator = ConfigValidator()
        validator.config = {
            "api": {
                "throttling": {
                    "ratePerMinute": -1,
                    "ratePerHour": 50
                }
            }
        }
        validator._validate_api_config()
        # Should have at least one error for invalid rate
        self.assertGreater(len(validator.errors), 0)
        self.assertIn("must be a positive integer", validator.errors[0])
    
    def test_validate_s3_vectors_config_valid(self):
        """Test valid S3 Vectors configuration."""
        validator = ConfigValidator()
        validator.config = {
            "s3Vectors": {
                "indexName": "valid-index-name",
                "dimensions": 1536,
                "similarityMetric": "COSINE"
            }
        }
        validator._validate_s3_vectors_config()
        self.assertEqual(len(validator.errors), 0)
    
    def test_validate_s3_vectors_config_invalid_index_name(self):
        """Test invalid S3 Vectors index name."""
        validator = ConfigValidator()
        validator.config = {
            "s3Vectors": {
                "indexName": "invalid@index#name"
            }
        }
        validator._validate_s3_vectors_config()
        self.assertIn("must contain only alphanumeric characters", validator.errors[0])
    
    def test_validate_s3_vectors_config_invalid_dimensions(self):
        """Test invalid dimensions."""
        validator = ConfigValidator()
        validator.config = {
            "s3Vectors": {
                "dimensions": -1
            }
        }
        validator._validate_s3_vectors_config()
        self.assertIn("must be a positive integer", validator.errors[0])
    
    def test_validate_s3_vectors_config_non_standard_dimensions(self):
        """Test non-standard dimensions warning."""
        validator = ConfigValidator()
        validator.config = {
            "s3Vectors": {
                "dimensions": 512
            }
        }
        validator._validate_s3_vectors_config()
        self.assertIn("should be 1536 for Amazon Titan", validator.warnings[0])
    
    def test_validate_widget_config_valid(self):
        """Test valid widget configuration."""
        validator = ConfigValidator()
        validator.config = {
            "widget": {
                "defaultTheme": {
                    "primaryColor": "#4287f5",
                    "secondaryColor": "#ffffff",
                    "fontFamily": "Arial",
                    "fontSize": "16px"
                }
            }
        }
        validator._validate_widget_config()
        self.assertEqual(len(validator.errors), 0)
    
    def test_validate_widget_config_invalid_colors(self):
        """Test invalid widget colors."""
        validator = ConfigValidator()
        validator.config = {
            "widget": {
                "defaultTheme": {
                    "primaryColor": "invalid-color",
                    "secondaryColor": "#gggggg"
                }
            }
        }
        validator._validate_widget_config()
        self.assertEqual(len(validator.errors), 2)
        self.assertIn("must be a valid hex color", validator.errors[0])
        self.assertIn("must be a valid hex color", validator.errors[1])
    
    def test_validate_bedrock_config_valid(self):
        """Test valid Bedrock configuration."""
        validator = ConfigValidator()
        validator.config = {
            "bedrock": {
                "modelId": "amazon.nova-lite-v1:0",
                "guardrails": {
                    "createDefault": True,
                    "defaultGuardrailConfig": {
                        "name": "test-guardrail",
                        "contentPolicyConfig": {
                            "filters": [
                                {"type": "SEXUAL", "strength": "HIGH"}
                            ]
                        },
                        "wordPolicyConfig": {
                            "managedWordLists": [
                                {"type": "PROFANITY"}
                            ]
                        }
                    }
                }
            }
        }
        validator._validate_bedrock_config()
        self.assertEqual(len(validator.errors), 0)
    
    def test_validate_bedrock_config_missing_model(self):
        """Test missing Bedrock model ID."""
        validator = ConfigValidator()
        validator.config = {"bedrock": {}}
        validator._validate_bedrock_config()
        self.assertIn("bedrock.modelId is required", validator.errors)
    
    def test_validate_guardrail_config_invalid(self):
        """Test invalid guardrail configuration."""
        validator = ConfigValidator()
        guardrail_config = {
            "name": "",
            "contentPolicyConfig": {
                "filters": [
                    {"type": "INVALID_TYPE", "strength": "INVALID_STRENGTH"}
                ]
            },
            "wordPolicyConfig": {
                "managedWordLists": [
                    {"type": "INVALID_LIST_TYPE"}
                ]
            }
        }
        validator._validate_guardrail_config(guardrail_config)
        self.assertIn("name is required", validator.errors[0])
        self.assertIn("Invalid content filter type", validator.errors[1])
        self.assertIn("Invalid filter strength", validator.errors[2])
        self.assertIn("Invalid managed word list type", validator.errors[3])
    
    def test_validate_all_success(self):
        """Test complete validation success."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.valid_config, f)
            config_path = f.name
        
        try:
            validator = ConfigValidator(config_path)
            is_valid, errors, warnings = validator.validate_all()
            self.assertTrue(is_valid)
            self.assertEqual(len(errors), 0)
        finally:
            os.unlink(config_path)
    
    def test_get_validation_summary(self):
        """Test validation summary generation."""
        validator = ConfigValidator()
        validator.errors = ["Error 1", "Error 2"]
        validator.warnings = ["Warning 1"]
        
        summary = validator.get_validation_summary()
        self.assertIn("❌ ERRORS:", summary)
        self.assertIn("Error 1", summary)
        self.assertIn("⚠️  WARNINGS:", summary)
        self.assertIn("Warning 1", summary)
    
    def test_get_validation_summary_success(self):
        """Test validation summary for successful validation."""
        validator = ConfigValidator()
        summary = validator.get_validation_summary()
        self.assertIn("✅ Configuration is valid!", summary)
    
    def test_validate_config_function(self):
        """Test standalone validate_config function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.valid_config, f)
            config_path = f.name
        
        try:
            is_valid, summary = validate_config(config_path)
            self.assertTrue(is_valid)
            self.assertIn("✅", summary)
        finally:
            os.unlink(config_path)


if __name__ == '__main__':
    unittest.main()
