# Model Configuration Guide

This document describes the supported foundation models and how to configure them.

## Supported Models

The chatbot supports the following foundation models:

### Amazon Nova Models
- **Nova Lite**: `amazon.nova-lite-v1:0` (default)
- **Nova Pro**: `amazon.nova-pro-v1:0`

### AI21 Labs Models
- **Jamba 1.5 Mini**: `ai21.jamba-1-5-mini-v1:0`

### Meta Models
- **Llama 4 Scout 17B**: `meta.llama4-scout-17b-instruct-v1:0`

### Anthropic Models
- **Claude Sonnet 4**: `anthropic.claude-sonnet-4-20250514-v1:0`
- **Claude 3.5 Haiku**: `anthropic.claude-3-5-haiku-20241022-v1:0`

## Configuration

To change the model, update the `bedrock.modelId` field in `config.json`:

```json
{
  "bedrock": {
    "modelId": "ai21.jamba-1-5-mini-v1:0"
  }
}
```

## Model Features

| Model | Streaming | Bedrock Caching | Multimodal |
|-------|-----------|-----------------|------------|
| Nova Lite | ✅ | ✅ | ✅ (Text, Image, Video) |
| Nova Pro | ✅ | ✅ | ✅ (Text, Image, Video) |
| Jamba 1.5 Mini | ✅ | ❌ | ❌ (Text only) |
| Llama 4 Scout 17B | ✅ | ❌ | ✅ (Text, Image) |
| Claude Sonnet 4 | ✅ | ✅ | ✅ (Text, Image) |
| Claude 3.5 Haiku | ✅ | ✅ | ❌ (Text only) |

## Cost Considerations

- **Nova Lite**: Most cost-effective option
- **Nova Pro**: Higher capability, moderate cost
- **Jamba 1.5 Mini**: Competitive pricing for text tasks
- **Llama 4 Scout 17B**: Good balance of cost and performance
- **Claude models**: Premium pricing with advanced capabilities

## Deployment

After changing the model configuration:

1. Redeploy the stack: `./chatbot deploy`
2. The new model will be used for all subsequent requests
3. Existing cached responses remain valid

## Notes

- All models use Amazon Titan Embeddings v2 for document vectorization
- Bedrock native caching is available for Nova and Claude models
- Nova models require 1K token minimum for prompt caching
- Claude models require 1K-2K token minimum for prompt caching
- Model availability may vary by AWS region
