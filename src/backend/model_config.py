"""
Centralized model configuration for Bedrock models.
"""
import os
from typing import Dict, Any, Optional
from enum import Enum


class ModelType(Enum):
    """Supported model types."""
    NOVA_LITE = "amazon.nova-lite-v1:0"
    NOVA_PRO = "amazon.nova-pro-v1:0"
    AI21_JAMBA_MINI = "ai21.jamba-1-5-mini-v1:0"
    META_LLAMA4_SCOUT = "meta.llama4-scout-17b-instruct-v1:0"
    CLAUDE_SONNET_4 = "anthropic.claude-sonnet-4-20250514-v1:0"
    CLAUDE_3_5_HAIKU = "anthropic.claude-3-5-haiku-20241022-v1:0"


class ModelConfig:
    """Model configuration manager."""
    
    # Model-specific configurations
    MODEL_CONFIGS = {
        ModelType.NOVA_LITE.value: {
            "type": "nova",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stop_sequences": [],
            "request_format": "nova",
            "streaming_supported": True,
            "embedding_model": "amazon.titan-embed-text-v2:0"
        },
        ModelType.NOVA_PRO.value: {
            "type": "nova",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stop_sequences": [],
            "request_format": "nova",
            "streaming_supported": True,
            "embedding_model": "amazon.titan-embed-text-v2:0"
        },
        ModelType.AI21_JAMBA_MINI.value: {
            "type": "ai21",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stop_sequences": [],
            "request_format": "ai21",
            "streaming_supported": True,
            "embedding_model": "amazon.titan-embed-text-v2:0"
        },
        ModelType.META_LLAMA4_SCOUT.value: {
            "type": "meta",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stop_sequences": [],
            "request_format": "meta",
            "streaming_supported": True,
            "embedding_model": "amazon.titan-embed-text-v2:0"
        },
        ModelType.CLAUDE_SONNET_4.value: {
            "type": "anthropic",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stop_sequences": [],
            "request_format": "anthropic",
            "streaming_supported": True,
            "embedding_model": "amazon.titan-embed-text-v2:0"
        },
        ModelType.CLAUDE_3_5_HAIKU.value: {
            "type": "anthropic",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stop_sequences": [],
            "request_format": "anthropic",
            "streaming_supported": True,
            "embedding_model": "amazon.titan-embed-text-v2:0"
        }
    }
    
    @classmethod
    def get_model_id(cls) -> str:
        """Get the configured model ID."""
        return os.environ.get("BEDROCK_MODEL_ID", ModelType.NOVA_LITE.value)
    
    @classmethod
    def get_model_config(cls, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration for a specific model."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        return cls.MODEL_CONFIGS.get(model_id, cls.MODEL_CONFIGS[ModelType.NOVA_LITE.value])
    
    @classmethod
    def is_nova_model(cls, model_id: Optional[str] = None) -> bool:
        """Check if the model is a Nova model."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        config = cls.get_model_config(model_id)
        return config["type"] == "nova"
    
    @classmethod
    def is_anthropic_model(cls, model_id: Optional[str] = None) -> bool:
        """Check if the model is an Anthropic model."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        config = cls.get_model_config(model_id)
        return config["type"] == "anthropic"
    
    @classmethod
    def get_request_body(cls, prompt: str, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get properly formatted request body for the model."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        config = cls.get_model_config(model_id)
        
        if config["type"] == "nova":
            return {
                "messages": [
                    {
                        "role": "user", 
                        "content": [
                            {"text": prompt}
                        ]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": config["max_tokens"],
                    "temperature": config["temperature"],
                    "topP": config["top_p"],
                    "stopSequences": config["stop_sequences"]
                }
            }
        elif config["type"] == "anthropic":
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": config["max_tokens"],
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        elif config["type"] == "ai21":
            return {
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": config["max_tokens"],
                "temperature": config["temperature"],
                "top_p": config["top_p"]
            }
        elif config["type"] == "meta":
            return {
                "prompt": prompt,
                "max_gen_len": config["max_tokens"],
                "temperature": config["temperature"],
                "top_p": config["top_p"]
            }
        else:
            raise ValueError(f"Unsupported model type: {config['type']}")
    
    @classmethod
    def extract_text_from_response(cls, response_data: Dict[str, Any], model_id: Optional[str] = None) -> str:
        """Extract text from model response based on model type."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        config = cls.get_model_config(model_id)
        
        if config["type"] == "nova":
            # Nova models return response in output.message.content format
            output = response_data.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            if content and len(content) > 0:
                return content[0].get("text", "")
            return ""
        elif config["type"] == "anthropic":
            return response_data.get("completion", "")
        elif config["type"] == "ai21":
            choices = response_data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""
        elif config["type"] == "meta":
            return response_data.get("generation", "")
        else:
            raise ValueError(f"Unsupported model type: {config['type']}")
    
    @classmethod
    def extract_streaming_text(cls, chunk_data: Dict[str, Any], model_id: Optional[str] = None) -> str:
        """Extract text from streaming response chunk based on model type."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        config = cls.get_model_config(model_id)
        
        if config["type"] == "nova":
            # Nova streaming chunks have contentBlockDelta.delta.text format
            content_block_delta = chunk_data.get("contentBlockDelta", {})
            delta = content_block_delta.get("delta", {})
            return delta.get("text", "")
        elif config["type"] == "anthropic":
            return chunk_data.get("completion", "")
        elif config["type"] == "ai21":
            return chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
        elif config["type"] == "meta":
            return chunk_data.get("generation", "")
        else:
            raise ValueError(f"Unsupported model type: {config['type']}")
    
    @classmethod
    def get_embedding_model(cls, model_id: Optional[str] = None) -> str:
        """Get the embedding model for the specified text model."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        config = cls.get_model_config(model_id)
        return config["embedding_model"]
    
    @classmethod
    def supports_streaming(cls, model_id: Optional[str] = None) -> bool:
        """Check if the model supports streaming."""
        if model_id is None:
            model_id = cls.get_model_id()
        
        config = cls.get_model_config(model_id)
        return config["streaming_supported"]
    
    @classmethod
    def validate_model_id(cls, model_id: str) -> bool:
        """Validate if the model ID is supported."""
        return model_id in cls.MODEL_CONFIGS
    
    @classmethod
    def get_supported_models(cls) -> list:
        """Get list of supported model IDs."""
        return list(cls.MODEL_CONFIGS.keys())
